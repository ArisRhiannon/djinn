"""
Cog: Listeners — motor de reglas heurísticas automáticas.

Integra ListenerEvaluator + ActionDispatcher con el bot.
Las reglas se cargan de DB al inicio y se hot-reloadean vía ToolExecutor.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import discord
from discord.ext import commands, tasks
from loguru import logger


# ══════════════════════════════════════════════════════════════════════════════
# Semantic: singleton del modelo + caché de embeddings por rule_id
# ══════════════════════════════════════════════════════════════════════════════

_semantic_cache: dict = {}
_semantic_cache_lock = threading.Lock()
_semantic_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="semantic"
)


def _get_embedder(bot):
    """Obtiene el EmbedEngine del bot (modelo compartido, sin duplicar)."""
    embedder = getattr(bot, "embedder", None)
    if embedder and embedder.available:
        return embedder
    return None


def _semantic_check_sync(
    rule_id: str,
    reference_phrases: list,
    text: str,
    threshold: float,
    embedder=None,
) -> "ListenerMatch":
    """
    Corre en el ThreadPoolExecutor — no bloquea el event loop.
    Calcula similitud coseno entre `text` y las frases de referencia.
    Los embeddings de referencia se cachean por rule_id.
    Usa el EmbedEngine compartido del bot.
    """
    if embedder is None or not reference_phrases:
        return ListenerMatch(matched=False)

    with _semantic_cache_lock:
        if rule_id not in _semantic_cache:
            _semantic_cache[rule_id] = embedder.encode(
                reference_phrases, normalize_embeddings=True
            )
        ref_embs = _semantic_cache[rule_id]
    msg_emb = embedder.encode([text], normalize_embeddings=True)[0]
    sims = ref_embs @ msg_emb  # dot product = cosine sim (embeddings normalizados)
    max_sim = float(sims.max())
    best_idx = int(sims.argmax())
    matched = max_sim >= threshold

    return ListenerMatch(
        matched=matched,
        score=round(max_sim, 4),
        matched_patterns=[reference_phrases[best_idx]] if matched else [],
    )


# ══════════════════════════════════════════════════════════════════════════════
# Match result
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ListenerMatch:
    matched:          bool
    score:            float     = 0.0
    matched_patterns: List[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# Evaluador (Python puro — sin I/O en el hot path)
# ══════════════════════════════════════════════════════════════════════════════

class ListenerEvaluator:

    _BUCKET_TTL = 3600  # 1h — entries más viejas se purgan

    def __init__(self, db, bot=None) -> None:
        self.db             = db
        self.bot            = bot
        self._rules:        Dict[str, List[dict]] = {}
        self._cache:        Dict[str, re.Pattern] = {}
        self._rate_buckets: Dict[str, List[float]] = {}
        self._cooldowns:    Dict[str, float]       = {}
        self._lock:         asyncio.Lock           = asyncio.Lock()
        self._last_cleanup: float                  = time.time()

    def _cleanup_expired(self) -> None:
        """Purga entries expiradas de _rate_buckets y _cooldowns (cada 10 min)."""
        now = time.time()
        if now - self._last_cleanup < 600:
            return
        self._last_cleanup = now
        cutoff = now - self._BUCKET_TTL
        self._rate_buckets = {
            k: [t for t in v if t > cutoff]
            for k, v in self._rate_buckets.items()
            if any(t > cutoff for t in v)
        }
        self._cooldowns = {k: v for k, v in self._cooldowns.items() if v > cutoff}

    # ── Regex con caché ───────────────────────────────────────────────────

    def _re(self, pattern: str, flags: int = re.IGNORECASE) -> re.Pattern:
        key = f"{pattern}:{flags}"
        if key not in self._cache:
            try:
                self._cache[key] = re.compile(pattern, flags)
            except re.error:
                self._cache[key] = re.compile(re.escape(pattern), flags)
        return self._cache[key]

    # ── Fuzzy matching para frases ────────────────────────────────────────

    @staticmethod
    def _normalize_for_fuzzy(text: str) -> str:
        """Normaliza: quita acentos, lowercase, solo alfanuméricos y espacios."""
        import unicodedata
        nfkd = unicodedata.normalize("NFKD", text.lower())
        clean = "".join(c for c in nfkd if not unicodedata.combining(c))
        # Solo letras, números y espacios
        return "".join(c if c.isalnum() or c == " " else " " for c in clean).strip()

    @staticmethod
    def _fuzzy_word_match(word: str, needle: str, threshold: float = 0.80) -> bool:
        """Fuzzy match for single words: 'atellier' matches 'atelier', etc."""
        from difflib import SequenceMatcher
        if not word or not needle:
            return False
        # Substring check only if lengths are similar (avoid "ate" matching "atelier")
        shorter, longer = (word, needle) if len(word) <= len(needle) else (needle, word)
        if len(shorter) >= 4 and shorter in longer and len(shorter) / len(longer) >= 0.6:
            return True
        ratio = SequenceMatcher(None, word, needle).ratio()
        return ratio >= threshold

    @staticmethod
    def _fuzzy_phrase_match(haystack: str, needle: str, threshold: float = 0.88) -> bool:
        """
        Fuzzy matching basado en tokens (palabras). Busca una subsecuencia
        de palabras en el haystack que sea similar a la needle.
        
        Más preciso que char-level: evita falsos positivos con texto corto.
        "que rica piñix" matchea "que rica piña" pero "que pasa piña" no.
        """
        from difflib import SequenceMatcher
        if not needle or not haystack:
            return False
        
        needle_words = needle.split()
        hay_words = haystack.split()
        n_words = len(needle_words)
        
        if not needle_words or not hay_words:
            return False
        
        # Sliding window de palabras (mismo tamaño que needle ±1 palabra)
        for window_size in (n_words, n_words + 1, n_words - 1):
            if window_size < 1 or window_size > len(hay_words):
                continue
            for i in range(len(hay_words) - window_size + 1):
                chunk_words = hay_words[i:i + window_size]
                chunk = " ".join(chunk_words)
                needle_str = " ".join(needle_words)
                ratio = SequenceMatcher(None, chunk, needle_str).ratio()
                if ratio >= threshold:
                    return True
        return False

    # ── Evaluación de condición (síncrona — no incluye semantic) ─────────

    def _eval_condition(self, condition: dict, text: str) -> ListenerMatch:
        t        = condition.get("type", "none")
        # Always case-insensitive — ignore whatever the LLM set
        cmp_text = text.lower()

        if t == "none":
            return ListenerMatch(matched=True)

        if t in ("exact", "contains", "starts_with", "ends_with"):
            for v in condition.get("values", []):
                needle = v.lower()
                hit = (
                    (t == "exact"       and cmp_text == needle)             or
                    (t == "contains"    and needle in cmp_text)             or
                    (t == "starts_with" and cmp_text.startswith(needle))    or
                    (t == "ends_with"   and cmp_text.endswith(needle))
                )
                if hit:
                    return ListenerMatch(matched=True, score=1.0, matched_patterns=[v])

            # ── Fuzzy fallback (todas las palabras/frases) ────────────
            values = condition.get("values", [])
            if values:
                norm_text = self._normalize_for_fuzzy(cmp_text)
                for v in values:
                    norm_needle = self._normalize_for_fuzzy(v.lower())
                    if not norm_needle:
                        continue
                    # Single word: check if any word in text is similar
                    if len(norm_needle.split()) == 1:
                        for word in norm_text.split():
                            if self._fuzzy_word_match(word, norm_needle, 0.80):
                                return ListenerMatch(matched=True, score=0.85, matched_patterns=[v])
                    else:
                        # Multi-word phrase
                        if self._fuzzy_phrase_match(norm_text, norm_needle, 0.85):
                            return ListenerMatch(matched=True, score=0.88, matched_patterns=[v])

            return ListenerMatch(matched=False)

        if t == "regex":
            flags = re.IGNORECASE
            for p in condition.get("patterns", []):
                try:
                    if self._re(p, flags).search(text):
                        return ListenerMatch(matched=True, matched_patterns=[p])
                except Exception as exc:
                    logger.debug("listeners: regex error: {}", exc)
            return ListenerMatch(matched=False)

        if t == "scored":
            if condition.get("require_subject"):
                if not any(
                    self._re(p).search(text)
                    for p in condition.get("subject_patterns", [])
                ):
                    return ListenerMatch(matched=False)
            score, matched = 0.0, []
            for rule in condition.get("scoring_rules", []):
                try:
                    if self._re(rule["pattern"]).search(text):
                        score += rule.get("weight", 1.0)
                        matched.append(rule["pattern"])
                    elif rule.get("required"):
                        return ListenerMatch(matched=False)
                except Exception as exc:
                    logger.debug("listeners: regex error: {}", exc)
            threshold = condition.get("score_threshold", 3.0)
            return ListenerMatch(matched=score >= threshold, score=score, matched_patterns=matched)

        return ListenerMatch(matched=False)

    # ── Rate / cooldown ───────────────────────────────────────────────────

    def _check_rate(self, rule_id: str, user_id: str, condition: dict) -> bool:
        key    = f"rate:{rule_id}:{user_id}"
        window = condition.get("window_seconds", 60)
        maxc   = condition.get("max_count", 10)
        now    = time.time()
        bucket = self._rate_buckets.setdefault(key, [])
        while bucket and now - bucket[0] > window:
            bucket.pop(0)
        bucket.append(now)
        return len(bucket) >= maxc

    def _check_cooldown(self, rule: dict, user_id: str) -> bool:
        """Check rápido en memoria (se sincroniza con DB en evaluate_message)."""
        cd = rule.get("limits", {}).get("cooldown_seconds", 0)
        if not cd:
            return True
        key = f"cd:{rule['id']}:{user_id}"
        return time.time() - self._cooldowns.get(key, 0) >= cd

    async def _check_cooldown_db(self, rule: dict, user_id: str) -> bool:
        """Check persistente contra la DB (sobrevive reinicios)."""
        cd = rule.get("limits", {}).get("cooldown_seconds", 0)
        if not cd:
            return True
        last = await self.db.get_last_trigger_time(rule["id"], int(user_id))
        if last and (time.time() - last) < cd:
            return False
        # También checkear max_triggers_per_user_per_hour
        max_per_hour = rule.get("limits", {}).get("max_triggers_per_user_per_hour", 0)
        if max_per_hour:
            count = await self.db.count_triggers_in_window(rule["id"], int(user_id), 3600)
            if count >= max_per_hour:
                return False
        return True

    def _mark_cooldown(self, rule: dict, user_id: str) -> None:
        self._cooldowns[f"cd:{rule['id']}:{user_id}"] = time.time()

    # ── Filtros ───────────────────────────────────────────────────────────

    def _apply_filters(
        self, rule: dict, message: discord.Message, member: discord.Member
    ) -> bool:
        trigger = rule.get("trigger")
        f = trigger.get("filters", {}) if isinstance(trigger, dict) else {}

        _FAIRY_BOT_ID = 1488300519234470108
        if f.get("ignore_bots") and member.bot and member.id != _FAIRY_BOT_ID:
            return False

        ch  = str(message.channel.id)
        uid = str(member.id)
        mr  = {str(r.id) for r in member.roles}

        ch_ids     = [str(x) for x in f.get("channel_ids", [])]
        ig_ch_ids  = [str(x) for x in f.get("ignore_channel_ids", [])]
        only_uids  = [str(x) for x in f.get("only_user_ids", [])]
        only_rids  = {str(x) for x in f.get("only_role_ids", [])}
        ig_rids    = {str(x) for x in f.get("ignore_role_ids", [])}

        if ch_ids    and ch  not in ch_ids:    return False
        if ig_ch_ids and ch      in ig_ch_ids: return False
        if only_uids and uid not in only_uids: return False
        if only_rids and not mr & only_rids:   return False
        if ig_rids   and     mr & ig_rids:     return False

        return True

    # ── Safe helpers (legacy DB rules can have string conditions/triggers) ──

    @staticmethod
    def _safe_trigger_type(rule: dict) -> str:
        trigger = rule.get("trigger", {})
        if isinstance(trigger, dict):
            return trigger.get("type", "")
        return ""

    @staticmethod
    def _safe_condition(rule: dict) -> dict:
        cond = rule.get("condition", {"type": "none"})
        if isinstance(cond, dict):
            return cond
        return {"type": "none"}

    # ── Evaluación de mensaje ─────────────────────────────────────────────

    async def evaluate_message(
        self, guild_id: str, message: discord.Message, member: discord.Member
    ) -> List[Tuple[dict, ListenerMatch]]:
        self._cleanup_expired()
        results = []
        async with self._lock:
            rules = list(self._rules.get(str(guild_id), []))
        for rule in rules:
            if not rule.get("enabled"):
                continue
            if not self._safe_trigger_type(rule) == "on_message":
                continue
            if not self._apply_filters(rule, message, member):
                continue
            if not self._check_cooldown(rule, str(member.id)):
                continue
            if not await self._check_cooldown_db(rule, str(member.id)):
                continue

            cond = self._safe_condition(rule)

            if not isinstance(cond, dict):
                continue

            if cond.get("type") == "semantic":
                loop = asyncio.get_running_loop()
                embedder = _get_embedder(self.bot)
                match = await loop.run_in_executor(
                    _semantic_executor,
                    _semantic_check_sync,
                    rule["id"],
                    cond.get("reference_phrases", []),
                    message.content or "",
                    float(cond.get("threshold", 0.72)),
                    embedder,
                )
            elif cond.get("type") == "rate":
                match = ListenerMatch(
                    matched=self._check_rate(rule["id"], str(member.id), cond)
                )
            else:
                match = self._eval_condition(cond, message.content or "")

            if not match.matched:
                continue

            self._mark_cooldown(rule, str(member.id))
            results.append((rule, match))
        return results

    # ── Hot-reload ────────────────────────────────────────────────────────

    async def load_rule(self, rule: dict) -> None:
        gid   = str(rule["guild_id"])
        async with self._lock:
            rules = self._rules.setdefault(gid, [])
            for i, r in enumerate(rules):
                if r["id"] == rule["id"]:
                    rules[i] = rule
                    _semantic_cache.pop(rule["id"], None)
                    return
            rules.append(rule)
            _semantic_cache.pop(rule["id"], None)

    async def unload_rule(self, guild_id: str, rule_id: str) -> None:
        g = str(guild_id)
        async with self._lock:
            self._rules[g] = [r for r in self._rules.get(g, []) if r["id"] != rule_id]
        _semantic_cache.pop(rule_id, None)

    async def toggle_rule(self, guild_id: str, rule_id: str, enabled: bool) -> None:
        async with self._lock:
            for r in self._rules.get(str(guild_id), []):
                if r["id"] == rule_id:
                    r["enabled"] = enabled
                    return

    async def load_all_from_db(self, guild_id: str) -> int:
        rules = await self.db.get_listeners(int(guild_id))
        for rule in rules:
            await self.load_rule(rule)
        return len(rules)


# ══════════════════════════════════════════════════════════════════════════════
# Dispatcher de acciones
# ══════════════════════════════════════════════════════════════════════════════

class ActionDispatcher:

    ALLOWED_ACTION_TYPES = {
        "reply_text", "reply_embed", "reply_link",
        "send_text", "send_embed",
        "add_reaction", "pin_message", "delete_message",
        "mute_user", "warn_user", "kick_user", "ban_user", "seal_user",
        "assign_role", "remove_role", "purge_n",
        "lock_channel", "set_slowmode", "create_thread",
        "llm_respond",
        # v2 actions
        "dm_user", "copy_to_channel", "rename_user",
        "escalate", "notify_mods", "conditional_action", "multi_reaction",
        # v3: webhook impersonation + transforms
        "impersonate",
    }

    def __init__(self, guild: discord.Guild, db, fairy_llm_fn=None, bot=None) -> None:
        self.guild   = guild
        self.db      = db
        self._llm_fn = fairy_llm_fn
        self._bot    = bot

    async def dispatch(
        self,
        actions: list,
        message: discord.Message,
        member: discord.Member,
        match: ListenerMatch,
    ) -> None:
        from utils.discord_tools import ToolExecutor

        executor = ToolExecutor(self.guild, message.channel, self.db)
        uid = str(member.id)
        cid = str(message.channel.id)
        mid = str(message.id)

        for action in actions:
            atype = action.get("type", "")
            if atype not in self.ALLOWED_ACTION_TYPES:
                logger.warning("ActionDispatcher: tipo desconocido '{}', ignorado.", atype)
                continue
            try:
                await self._run_action(
                    action, atype, message, member, executor, uid, cid, mid, match
                )
            except Exception as exc:
                logger.error("ActionDispatcher: error en acción '{}': {}", atype, exc)

    async def _run_action(
        self,
        action: dict,
        atype: str,
        message: discord.Message,
        member: discord.Member,
        executor,
        uid: str,
        cid: str,
        mid: str,
        match: ListenerMatch,
    ) -> None:

        if atype == "reply_text":
            text = action.get("text") or action.get("content") or action.get("message") or ""
            if text:
                await message.reply(text[:2000])

        elif atype == "reply_link":
            await message.reply(f"{action.get('text', '')}\n{action['url']}".strip())

        elif atype == "reply_embed":
            color_raw = action.get("color", "A855F7").lstrip("#")
            try:
                color_int = int(color_raw, 16)
            except ValueError:
                color_int = 0xA855F7
            embed = discord.Embed(
                title       = action.get("title"),
                description = action.get("description", ""),
                color       = discord.Color(color_int),
            )
            await message.reply(embed=embed)

        elif atype == "send_text":
            await executor.execute_by_name("send_message", {
                "channel_id": action.get("channel_id", cid),
                "content":    action["text"],
            })

        elif atype == "send_embed":
            await executor.execute_by_name("send_embed", {
                "channel_id":  action.get("channel_id", cid),
                "title":       action.get("title", ""),
                "description": action.get("description", ""),
                "color":       action.get("color", ""),
            })

        elif atype == "add_reaction":
            await executor.execute_by_name("add_reaction", {
                "message_id": mid,
                "emoji":      action["emoji"],
                "channel_id": cid,
            })

        elif atype == "pin_message":
            await executor.execute_by_name("pin_message", {
                "message_id": mid,
                "channel_id": cid,
            })

        elif atype == "delete_message":
            await executor.execute_by_name("purge_messages", {
                "count":      1,
                "channel_id": cid,
                "user_id":    uid,
            })

        elif atype == "mute_user":
            await executor.execute_by_name("mute_user", {
                "user_id":  uid,
                "duration": action.get("duration", "10m"),
                "reason":   action.get("reason", "Regla automática"),
            })

        elif atype == "warn_user":
            await executor.execute_by_name("warn_user", {
                "user_id": uid,
                "reason":  action.get("reason", "Regla automática"),
            })

        elif atype == "kick_user":
            await executor.execute_by_name("kick_user", {
                "user_id": uid,
                "reason":  action.get("reason", "Regla automática"),
            })

        elif atype == "ban_user":
            await executor.execute_by_name("ban_user", {
                "user_id":     uid,
                "reason":      action.get("reason", "Regla automática"),
                "delete_days": action.get("delete_days", 0),
            })

        elif atype == "seal_user":
            await executor.execute_by_name("seal_user", {
                "user_id":  uid,
                "duration": action.get("duration", "1h"),
                "reason":   action.get("reason", "Regla automática"),
            })

        elif atype == "assign_role":
            await executor.execute_by_name("assign_role", {
                "user_id": uid,
                "role_id": action["role_id"],
            })

        elif atype == "remove_role":
            await executor.execute_by_name("remove_role", {
                "user_id": uid,
                "role_id": action["role_id"],
            })

        elif atype == "purge_n":
            await executor.execute_by_name("purge_messages", {
                "count":      action.get("count", 1),
                "channel_id": cid,
            })

        elif atype == "lock_channel":
            await executor.execute_by_name("lock_channel", {"channel_id": cid})

        elif atype == "set_slowmode":
            await executor.execute_by_name("set_slowmode", {
                "seconds":    action.get("seconds", 5),
                "channel_id": cid,
            })

        elif atype == "create_thread":
            await executor.execute_by_name("create_thread", {
                "message_id":  mid,
                "thread_name": action["thread_name"],
            })

        elif atype == "llm_respond":
            if self._llm_fn is None:
                return
            sys_p    = action.get("system_prompt", "Eres Fairy. Responde brevemente.")
            response = await self._llm_fn(sys_p, message.content)
            mode     = action.get("channel_mode", "reply")
            if mode == "reply":
                await message.reply(response)
            elif mode == "channel":
                dest_id = action.get("channel_id", cid)
                dest    = self.guild.get_channel(int(dest_id))
                if dest:
                    await dest.send(response)
            elif mode == "dm":
                try:
                    await member.send(response)
                except discord.Forbidden:
                    pass

        # ── v2 actions ────────────────────────────────────────────────

        elif atype == "dm_user":
            # Resolve target: specific user_id or the message author
            target_id = action.get("user_id")
            if target_id:
                target = self.guild.get_member(int(target_id))
            else:
                target = member
            if not target:
                return

            # Resolve text tokens
            dm_text = action.get("text") or action.get("content") or action.get("message") or ""
            if dm_text:
                dm_text = dm_text.replace("{original}", message.content or "")
                dm_text = dm_text.replace("{author}", str(member.display_name))
                dm_text = dm_text.replace("{author_id}", str(member.id))
                dm_text = dm_text.replace("{channel}", message.channel.name)
                dm_text = dm_text.replace("{message_url}", message.jump_url)
                dm_text = dm_text.replace("{timestamp}", message.created_at.strftime("%H:%M"))

            # Send as embed if specified
            dm_embed_data = action.get("embed")
            try:
                if dm_embed_data:
                    def _resolve(s):
                        if not isinstance(s, str): return s
                        return (s.replace("{original}", message.content or "")
                                 .replace("{author}", str(member.display_name))
                                 .replace("{author_id}", str(member.id))
                                 .replace("{channel}", message.channel.name)
                                 .replace("{message_url}", message.jump_url)
                                 .replace("{timestamp}", message.created_at.strftime("%H:%M"))
                                 .replace("{author_avatar}", str(member.display_avatar.url) if member.display_avatar else ""))
                    embed = discord.Embed(
                        title=_resolve(dm_embed_data.get("title", "")),
                        description=_resolve(dm_embed_data.get("description", "")),
                        color=dm_embed_data.get("color", 0x5865F2),
                        url=_resolve(dm_embed_data.get("url")) or None,
                    )
                    for field in dm_embed_data.get("fields", []):
                        embed.add_field(name=field.get("name",""), value=_resolve(field.get("value","")), inline=field.get("inline", False))
                    if dm_embed_data.get("footer"):
                        embed.set_footer(text=dm_embed_data["footer"].get("text",""))
                    thumb = _resolve(dm_embed_data.get("thumbnail", ""))
                    if thumb and thumb.startswith("http"):
                        embed.set_thumbnail(url=thumb)
                    await target.send(content=dm_text or None, embed=embed)
                elif dm_text:
                    await target.send(dm_text)
            except discord.Forbidden:
                pass

        elif atype == "copy_to_channel":
            dest = self.guild.get_channel(int(action.get("channel_id", 0)))
            if dest:
                embed = discord.Embed(
                    description=message.content[:2000],
                    color=discord.Color.orange(),
                    timestamp=message.created_at,
                )
                embed.set_author(name=str(member), icon_url=member.display_avatar.url if member.display_avatar else None)
                embed.add_field(name="Canal", value=f"<#{message.channel.id}>", inline=True)
                embed.add_field(name="Link", value=f"[Ir al mensaje]({message.jump_url})", inline=True)
                await dest.send(embed=embed)

        elif atype == "rename_user":
            nick = action.get("nickname", "")
            try:
                await member.edit(nick=nick[:32] or None)
            except discord.Forbidden:
                pass

        elif atype == "escalate":
            # Escalado progresivo: warn → mute → ban según historial
            warnings = await self.db.count_warnings(self.guild.id, member.id)
            reason = action.get("reason", "Escalado automático")
            thresholds = action.get("thresholds", {"mute": 2, "ban": 5})
            mute_at = thresholds.get("mute", 2)
            ban_at = thresholds.get("ban", 5)

            if warnings >= ban_at:
                await executor.execute_by_name("ban_user", {
                    "user_id": uid, "reason": f"{reason} ({warnings} warns previos)"
                })
            elif warnings >= mute_at:
                duration = action.get("mute_duration", "1h")
                await executor.execute_by_name("mute_user", {
                    "user_id": uid, "duration": duration, "reason": f"{reason} ({warnings} warns)"
                })
            # Siempre añadir warn
            await executor.execute_by_name("warn_user", {
                "user_id": uid, "reason": reason
            })

        elif atype == "notify_mods":
            mod_ch = self.guild.get_channel(int(action.get("channel_id", 0)))
            if mod_ch:
                color_raw = action.get("color", "FFA500").lstrip("#")
                try:
                    color_int = int(color_raw, 16)
                except ValueError:
                    color_int = 0xFFA500
                embed = discord.Embed(
                    title=action.get("title", "⚠️ Alerta automática"),
                    description=action.get("template", "Regla disparada por {user} en {channel}").format(
                        user=str(member),
                        user_id=member.id,
                        channel=f"<#{message.channel.id}>",
                        content=message.content[:200],
                        score=getattr(match, 'score', 0),
                    ),
                    color=discord.Color(color_int),
                    timestamp=message.created_at,
                )
                embed.set_footer(text=f"User ID: {member.id}")
                await mod_ch.send(embed=embed)

        elif atype == "conditional_action":
            # Ejecutar sub-acciones solo si se cumple una condición extra
            cond_type = action.get("if", "")
            should_run = False
            if cond_type == "warns_gte":
                count = await self.db.count_warnings(self.guild.id, member.id)
                should_run = count >= action.get("value", 1)
            elif cond_type == "account_age_lt_days":
                if member.created_at:
                    import datetime
                    age = (discord.utils.utcnow() - member.created_at).days
                    should_run = age < action.get("value", 7)
            elif cond_type == "has_role":
                should_run = any(str(r.id) == str(action.get("value")) for r in member.roles)
            elif cond_type == "no_role":
                should_run = not any(str(r.id) == str(action.get("value")) for r in member.roles)

            if should_run:
                sub_actions = action.get("then", [])
                for sub in sub_actions:
                    sub_type = sub.get("type", "")
                    if sub_type in self.ALLOWED_ACTION_TYPES and sub_type != "conditional_action":
                        await self._run_action(sub, sub_type, message, member, executor, uid, cid, mid)

        elif atype == "multi_reaction":
            for emoji in action.get("emojis", []):
                try:
                    await message.add_reaction(emoji)
                except (discord.HTTPException, discord.NotFound):
                    pass

        elif atype == "impersonate":
            # Reemplaza el mensaje del autor por otro contenido, usando un webhook
            # con el nombre y avatar del autor original (o del bot si as_bot=True).
            # Derivado del modelo de la Maldición pero con transforms heurísticas.
            from utils.curse_webhook import CurseWebhookManager
            from utils import message_transforms as mt

            # Solo funciona en canales de texto normales (webhooks no disponibles en DMs/threads)
            channel = message.channel
            if not isinstance(channel, discord.TextChannel):
                logger.debug("impersonate: canal no soporta webhooks (tipo={})", type(channel).__name__)
                return

            # 1) Derivar el contenido final desde el mensaje original
            try:
                content = mt.compose(
                    original=message.content or "",
                    template=action.get("content") or action.get("template"),
                    transforms=action.get("transforms") or [],
                    author_name=member.display_name,
                    author_id=str(member.id),
                    channel_name=getattr(channel, "name", ""),
                    channel_id=str(channel.id),
                )
            except Exception as exc:
                logger.error("impersonate: error construyendo contenido: {}", exc)
                return

            # Fallback si quedó vacío
            if not content or not content.strip():
                content = action.get("fallback") or "▓▓▓▓▓"

            # Discord limita mensajes a 2000 chars
            if len(content) > 2000:
                content = content[:1997] + "…"

            # 2) Borrar el mensaje original (si así lo pide la regla; default True)
            if action.get("delete_original", True):
                try:
                    await message.delete()
                except discord.NotFound:
                    pass  # Ya borrado
                except discord.Forbidden:
                    logger.warning("impersonate: sin MANAGE_MESSAGES en #{}", channel.name)
                    # Seguimos igual y enviamos el webhook, aunque quede el original
                except discord.HTTPException as exc:
                    logger.debug("impersonate: error borrando original: {}", exc)

            # 3) Decidir identidad a mostrar
            as_bot = bool(action.get("as_bot", False))
            if as_bot or not member.display_avatar:
                username = self.guild.me.display_name if self.guild.me else "Youkai"
                avatar_url = str(self.guild.me.display_avatar.url) if self.guild.me and self.guild.me.display_avatar else ""
            else:
                username = member.display_name
                avatar_url = str(member.display_avatar.url)

            # 4) Enviar el webhook impersonando
            try:
                bot_user = self._bot.user if self._bot else None
                if bot_user is None:
                    logger.warning("impersonate: bot no disponible, no puedo enviar webhook")
                    return
                await CurseWebhookManager.send_cursed(
                    channel=channel,
                    content=content,
                    username=username,
                    avatar_url=avatar_url,
                    bot_user=bot_user,
                )
            except Exception as exc:
                logger.error("impersonate: fallo en webhook: {}", exc)


# ══════════════════════════════════════════════════════════════════════════════
# Cog
# ══════════════════════════════════════════════════════════════════════════════

class ListenersCog(commands.Cog, name="Listeners"):
    """Motor de reglas automáticas heurísticas."""

    _instance: Optional["ListenersCog"] = None

    def __init__(self, bot) -> None:
        self.bot         = bot
        self.evaluators:  Dict[int, ListenerEvaluator] = {}
        self.dispatchers: Dict[int, ActionDispatcher]  = {}
        self._schedule_last_run: Dict[str, float] = {}  # rule_id → last epoch
        ListenersCog._instance = self
        self._schedule_loop.start()

    # ── LLM fn para llm_respond ───────────────────────────────────────────

    def cog_unload(self) -> None:
        self._schedule_loop.cancel()

    # ── Scheduler: ejecuta reglas on_schedule ─────────────────────────────

    @tasks.loop(minutes=1)
    async def _schedule_loop(self) -> None:
        """Cada minuto revisa reglas on_schedule y ejecuta las que toca."""
        now = time.time()
        for gid, evaluator in list(self.evaluators.items()):
            guild = self.bot.get_guild(gid)
            if not guild:
                continue
            async with evaluator._lock:
                rules = list(evaluator._rules.get(str(gid), []))
            for rule in rules:
                if not rule.get("enabled"):
                    continue
                trigger = rule.get("trigger", {})
                if not isinstance(trigger, dict) or trigger.get("type") != "on_schedule":
                    continue
                schedule = trigger.get("schedule", {})
                interval_secs = self._parse_interval(schedule)
                if interval_secs <= 0:
                    continue
                last = self._schedule_last_run.get(rule["id"], 0)
                if last == 0:
                    # Primera vez que vemos esta regla desde el arranque:
                    # asumir que "acaba de correr" para no disparar inmediatamente.
                    self._schedule_last_run[rule["id"]] = now
                    continue
                if now - last < interval_secs:
                    continue
                # Time to fire
                self._schedule_last_run[rule["id"]] = now
                try:
                    await self._dispatch_scheduled(rule, guild)
                    logger.info("Scheduler: regla '{}' disparada en guild {}", rule["id"], gid)
                except Exception as exc:
                    logger.error("Scheduler: error en regla '{}': {}", rule["id"], exc)

    @_schedule_loop.before_loop
    async def _before_schedule_loop(self) -> None:
        await self.bot.wait_until_ready()
        # Ensure all guilds are loaded
        for guild in self.bot.guilds:
            await self._ensure_guild(guild)

    @staticmethod
    def _parse_interval(schedule: dict) -> int:
        """Convierte schedule config a segundos."""
        stype = schedule.get("type", "interval")
        if stype == "interval":
            secs = schedule.get("seconds", 0)
            secs += schedule.get("minutes", 0) * 60
            secs += schedule.get("hours", 0) * 3600
            secs += schedule.get("days", 0) * 86400
            return int(secs)
        return 0

    async def _dispatch_scheduled(self, rule: dict, guild: discord.Guild) -> None:
        """Ejecuta las acciones de una regla on_schedule (sin contexto de mensaje)."""
        from utils.discord_tools import ToolExecutor

        for action in rule.get("actions", []):
            atype = action.get("type", "")
            try:
                if atype == "send_text":
                    ch_id = action.get("channel_id")
                    text = action.get("text", "")
                    if ch_id and text:
                        channel = guild.get_channel(int(ch_id))
                        if channel:
                            await channel.send(text[:2000])
                elif atype == "send_embed":
                    ch_id = action.get("channel_id")
                    if ch_id:
                        channel = guild.get_channel(int(ch_id))
                        if channel:
                            color_raw = action.get("color", "A855F7").lstrip("#")
                            try:
                                color_int = int(color_raw, 16)
                            except ValueError:
                                color_int = 0xA855F7
                            embed = discord.Embed(
                                title=action.get("title", ""),
                                description=action.get("description", ""),
                                color=discord.Color(color_int),
                            )
                            await channel.send(embed=embed)
                else:
                    logger.debug("Scheduler: acción '{}' no soportada en on_schedule", atype)
            except Exception as exc:
                logger.error("Scheduler: error ejecutando acción '{}': {}", atype, exc)

    # ── LLM fn para llm_respond ───────────────────────────────────────────

    def _get_llm_fn(self):
        """
        Devuelve una función async(system_prompt, user_text) → str
        usando el cliente de Google AI del orchestrator si está disponible.
        """
        orchestrator = getattr(self.bot, "orchestrator", None)
        if orchestrator is None:
            return None

        client = (
            getattr(orchestrator, "client", None)
            or getattr(orchestrator, "llm", None)
            or getattr(orchestrator, "_client", None)
        )
        if client is None:
            return None

        async def _call(system_prompt: str, user_text: str) -> str:
            try:
                from google.genai import types as gtypes
                return await client._generate_plain(
                    system_prompt,
                    [gtypes.Content(
                        role="user",
                        parts=[gtypes.Part.from_text(text=user_text)],
                    )],
                )
            except Exception as exc:
                logger.error("llm_respond: error en _generate_plain: {}", exc)
                return ""

        return _call

    # ── Asegurar evaluador/dispatcher por guild ───────────────────────────

    async def _ensure_guild(
        self, guild: discord.Guild
    ) -> Tuple[ListenerEvaluator, ActionDispatcher]:
        gid = guild.id
        if gid not in self.evaluators:
            ev     = ListenerEvaluator(self.bot.db, bot=self.bot)
            loaded = await ev.load_all_from_db(str(gid))
            self.evaluators[gid] = ev
            logger.info("Listeners: {} reglas cargadas para guild {}", loaded, gid)
        if gid not in self.dispatchers:
            self.dispatchers[gid] = ActionDispatcher(
                guild, self.bot.db, self._get_llm_fn(), bot=self.bot,
            )
        return self.evaluators[gid], self.dispatchers[gid]

    # ── API pública para ToolExecutor (hot-reload) ────────────────────────

    async def load_rule(self, guild_id: int, rule: dict) -> None:
        if guild_id in self.evaluators:
            await self.evaluators[guild_id].load_rule(rule)

    async def unload_rule(self, guild_id: int, rule_id: str) -> None:
        if guild_id in self.evaluators:
            await self.evaluators[guild_id].unload_rule(str(guild_id), rule_id)

    async def toggle_rule(self, guild_id: int, rule_id: str, enabled: bool) -> None:
        if guild_id in self.evaluators:
            await self.evaluators[guild_id].toggle_rule(str(guild_id), rule_id, enabled)

    # ── Events ────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or not message.author:
            return
        member = message.guild.get_member(message.author.id)
        if not member:
            try:
                member = await message.guild.fetch_member(message.author.id)
            except Exception:
                return

        evaluator, dispatcher = await self._ensure_guild(message.guild)

        try:
            matched = await evaluator.evaluate_message(
                str(message.guild.id), message, member
            )
        except Exception as exc:
            logger.error("Listeners: error evaluando mensaje: {}", exc)
            return

        for rule, match in matched:
            try:
                await dispatcher.dispatch(rule["actions"], message, member, match)
            except Exception as exc:
                logger.error("Listeners: error en dispatch de regla '{}': {}", rule.get("id"), exc)
                continue
            try:
                await self.bot.db.log_listener_trigger(
                    guild_id   = message.guild.id,
                    rule_id    = rule["id"],
                    user_id    = member.id,
                    channel_id = message.channel.id,
                    message_id = message.id,
                    score      = match.score,
                    actions    = str([a["type"] for a in rule["actions"]]),
                )
            except Exception as exc:
                logger.error(
                    "Listeners: error en dispatch de regla '{}': {}",
                    rule.get("id"), exc,
                )
                # Si FK falla, la regla fue borrada de la DB — descargarla de memoria
                if "FOREIGN KEY" in str(exc):
                    await evaluator.unload_rule(str(message.guild.id), rule["id"])

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Pre-carga las reglas cuando el bot entra a un servidor nuevo."""
        await self._ensure_guild(guild)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Dispara reglas con trigger on_join cuando un miembro entra al server."""
        guild = member.guild
        evaluator, _ = await self._ensure_guild(guild)

        async with evaluator._lock:
            rules = list(evaluator._rules.get(str(guild.id), []))

        for rule in rules:
            if not rule.get("enabled"):
                continue
            if evaluator._safe_trigger_type(rule) != "on_join":
                continue

            # Evaluar condición de usuario si existe
            trigger = rule.get("trigger", {})
            filters = trigger.get("filters", {})
            target_user = filters.get("user_id") or filters.get("user_name")
            if target_user:
                if str(member.id) != str(target_user) and member.name.lower() != str(target_user).lower() and member.display_name.lower() != str(target_user).lower():
                    continue

            try:
                await self._dispatch_join(rule, guild, member)
                logger.info("Listener on_join: regla '{}' disparada para {}", rule.get("id"), member)
            except Exception as exc:
                logger.error("Listener on_join: error en regla '{}': {}", rule.get("id"), exc)

    async def _dispatch_join(self, rule: dict, guild: discord.Guild, member: discord.Member) -> None:
        """Ejecuta acciones de una regla on_join."""
        for action in rule.get("actions", []):
            atype = action.get("type", "")
            try:
                if atype == "assign_role":
                    role_id = action.get("role_id")
                    role_name = action.get("role_name")
                    role = None
                    if role_id:
                        role = guild.get_role(int(role_id))
                    elif role_name:
                        role = discord.utils.get(guild.roles, name=role_name)
                    if role and role < guild.me.top_role:
                        await member.add_roles(role, reason=f"Listener on_join: {rule.get('id')}")
                elif atype == "send_text":
                    ch_id = action.get("channel_id")
                    text = (action.get("text") or "").replace("{user}", member.mention).replace("{name}", member.display_name)
                    if ch_id and text:
                        channel = guild.get_channel(int(ch_id))
                        if channel:
                            await channel.send(text[:2000])
                elif atype == "send_embed":
                    ch_id = action.get("channel_id")
                    if ch_id:
                        channel = guild.get_channel(int(ch_id))
                        if channel:
                            color_raw = action.get("color", "A855F7").lstrip("#")
                            try:
                                color_int = int(color_raw, 16)
                            except ValueError:
                                color_int = 0xA855F7
                            desc = (action.get("description") or "").replace("{user}", member.mention).replace("{name}", member.display_name)
                            embed = discord.Embed(
                                title=action.get("title", ""),
                                description=desc,
                                color=discord.Color(color_int),
                            )
                            await channel.send(embed=embed)
            except Exception as exc:
                logger.error("_dispatch_join: error en acción '{}': {}", atype, exc)


async def setup(bot) -> None:
    await bot.add_cog(ListenersCog(bot))
"""utils/discord_tools.py — Tool dispatcher and ToolExecutor.

Esta es la columna vertebral del bridge entre el LLM y las acciones de
Discord. Define la clase ``ToolExecutor`` con un handler ``_do_<name>()``
por cada tool declarada en ``TOOL_DECLARATIONS``. El LLM emite tool calls,
y el dispatcher las ejecuta secuencialmente con timeouts, permission gates
y memoria.

Módulos asociados (extraídos durante el refactor de mayo 2026):
- utils.tools._declarations: las 137 declarations + helpers _str/_int/_bool/_decl
- utils.tools._helpers:      helpers privados (_parse_hex_color, _safe_int, etc.)
- utils.tools._constants:    constantes de configuración + _fix_json

Histórico: la versión pre-refactor del monolito de 5423 líneas vive en
``deprecated/utils_old/discord_tools_monolith.py`` como referencia.
"""
from __future__ import annotations

# ── Stdlib ────────────────────────────────────────────────────────────────
import asyncio
import datetime
import io
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Sequence

# ── Third-party ───────────────────────────────────────────────────────────
import discord
from google.genai import types

# ── Project (módulos hermanos extraídos del monolito) ─────────────────────
from utils.tools._constants import (
    SKILLS_DIR,
    _PERM_CONCURRENCY,
    _DEFAULT_TOOL_TIMEOUT,
    _TOOL_TIMEOUTS,
    _DB_REQUIRED_TOOLS,
    _MOD_TOOLS,
    _fix_json,
)
from utils.tools._declarations import (
    _str,
    _int,
    _bool,
    _decl,
    TOOL_DECLARATIONS,
    YOUKAI_TOOL,
    DJINN_TOOL,
)
from utils.tools._helpers import (
    _parse_hex_color,
    _member_avatar_url,
    _safe_perm_name,
    _parse_duration,
    _safe_int,
    _ts_to_date,
)

logger = logging.getLogger("djinn.tools")





# ── Constantes ────────────────────────────────────────────────────────────────

FORBIDDEN: frozenset[str] = frozenset({
    "delete_channel", "delete_category", "delete_all_channels",
    "mass_ban", "nuke_server", "delete_all_roles",
    # SEC-01 (Wave 1, 2026-05-15): execute_code eliminado por permitir RCE
    # via prompt injection. Listado aquí como defensa en profundidad por si
    # alguien reintroduce el handler — el sandbox basado en filtros de string
    # es trivialmente bypassable. Ver .code-review/04-report.md SEC-01.
    "execute_code",
})




# ── JSON fixer para outputs malformados del LLM ──────────────────────────────

# Tools que requieren self.db (guard centralizado en dispatcher)

# FIX 5: Cache global de TemplateEngine para evitar recreación por mensaje
_TEMPLATE_ENGINE_CACHE: Any = None


def _dashboard_record(name: str, elapsed: float, status: str, summary: str = ""):
    """Envía un registro al dashboard buffer (no-op si no está cargado)."""
    try:
        from cogs.dashboard import dashboard_buffer
        dashboard_buffer.record(name, elapsed, status, summary)
    except Exception:
        pass  # Dashboard no cargado o error — nunca romper el bot




def _memory_record(name: str, args: dict, result: dict):
    """Registra acciones de mod en server memory (no-op si no cargado)."""
    if name not in _MOD_TOOLS:
        return
    if not result.get("success"):
        return
    try:
        from cogs.server_memory import record_fact
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M")
        user = result.get("banned") or result.get("kicked") or result.get("muted") or result.get("unmuted") or result.get("user") or args.get("user_id", "?")
        reason = args.get("reason", "")
        action = name.replace("_user", "").upper()
        fact = f"{ts} {action}: {user}"
        if reason:
            fact += f" — {reason[:80]}"
        if name == "warn_user":
            total = result.get("total_warnings", "?")
            fact += f" (total warns: {total})"
        record_fact(fact)
    except Exception:
        pass


# ── Helpers de Schema ─────────────────────────────────────────────────────────


# ── Helpers de módulo ─────────────────────────────────────────────────────────


class ToolExecutor:
    _scheduled_tasks: Dict[str, asyncio.Task] = {}
    _seal_tasks: Dict[str, asyncio.Task] = {}
    _seal_mod_messages: Dict[str, int] = {}

    def __init__(self, guild: discord.Guild, channel: discord.abc.Messageable, 
                 db, bot=None, public_mode: bool = False, public_user_id: int = 0,
                 author_id: int = 0) -> None:
        self.guild    = guild
        self.channel  = channel
        self.db       = db
        self._bot_ref = bot
        self.public_mode = public_mode
        self.public_user_id = public_user_id
        self._author_id = author_id

    # ── Dispatcher ───────────────────────────────────────────────────────

    async def execute(self, call: types.FunctionCall) -> Dict[str, Any]:
        name = call.name or ""
        args = call.args or {}
        return await self._dispatch(name, args)

    async def execute_by_name(self, name: str, args: dict) -> Dict[str, Any]:
        return await self._dispatch(name, args)

    # FIX 5: Pre-check de permisos del bot ANTES de ejecutar
    async def _dispatch(self, name: str, args: dict) -> Dict[str, Any]:
        if name in FORBIDDEN:
            logger.warning("ToolExecutor: función prohibida: %s", name)
            return {"error": f"Function '{name}' is permanently disabled for safety."}

        # SEC-04 (Wave 2, F0.4): permission layer — verifica que el USUARIO que
        # originó el mensaje tenga el permiso de Discord requerido por la tool
        # (defensa contra prompt injection: el LLM no debería ejecutar acciones
        # de moderación a petición de un usuario sin esos permisos).
        # Por defecto en MODO LOG-ONLY: solo registra. Para hacerlo enforce,
        # exportar FAIRY_TOOL_PERMS_ENFORCE=1.
        try:
            actor = None
            # A1 (review): el actor es el usuario que originó el mensaje. En la
            # ruta principal llega como author_id; en la ruta public como
            # public_user_id. Usamos cualquiera de los dos para que el check
            # corra también en la ruta principal (antes solo corría en public).
            _actor_id = self.public_user_id or self._author_id
            if _actor_id and self.guild is not None:
                actor = self.guild.get_member(int(_actor_id))
            if actor is not None:
                from utils.security import member_has_tool_permission
                ok, missing = member_has_tool_permission(actor, name)
                if not ok:
                    enforce = os.environ.get("FAIRY_TOOL_PERMS_ENFORCE", "0") == "1"
                    logger.warning(
                        "tool_executed_without_perm: user_id=%s tool=%s required=%s enforce=%s",
                        _actor_id, name, missing, enforce,
                    )
                    if enforce:
                        return {
                            "error": (
                                f"Permiso insuficiente: para usar '{name}' el usuario "
                                f"que solicitó la acción necesita el permiso de Discord "
                                f"'{missing}'."
                            ),
                            "required_perm": missing,
                            "user_id": str(_actor_id),
                        }
        except Exception as exc:  # defensa en profundidad — nunca bloquear por bug del check
            logger.warning("Permission check falló para tool %s: %s", name, exc)

        handler = getattr(self, f"_do_{name}", None)
        if handler is None:
            logger.warning("ToolExecutor: función desconocida: %s", name)
            return {"error": f"Unknown function '{name}'."}

        # DB guard: fail fast si la tool requiere DB y no está disponible
        if name in _DB_REQUIRED_TOOLS and not self.db:
            return {"error": f"Database unavailable. Tool '{name}' requires DB access."}

        # FIX 5: Verificar permisos del bot antes de ejecutar
        perm_check = self._check_bot_permissions(name)
        if perm_check:
            return perm_check

        t0 = time.perf_counter()
        timeout = _TOOL_TIMEOUTS.get(name, _DEFAULT_TOOL_TIMEOUT)
        try:
            result = await asyncio.wait_for(handler(**args), timeout=timeout)
            if not isinstance(result, dict):
                result = {"result": result}
            elapsed = time.perf_counter() - t0
            logger.info("ToolExecutor: ✅ %s (%.2fs) → %s", name, elapsed, str(result)[:120])
            _dashboard_record(name, elapsed, "ok", str(result)[:60])
            # Feed server memory with mod actions
            _memory_record(name, args, result)
            return result
        except asyncio.TimeoutError:
            elapsed = time.perf_counter() - t0
            logger.error("ToolExecutor: ⏱️ %s TIMEOUT after %.1fs", name, elapsed)
            _dashboard_record(name, elapsed, "timeout")
            return {"error": f"Tool '{name}' timed out after {timeout}s. Try a smaller scope or simpler query."}
        except discord.Forbidden as exc:
            _dashboard_record(name, time.perf_counter() - t0, "error", "Forbidden")
            return {"error": (
                f"Missing Discord permissions for '{name}'. "
                f"Ensure the bot role is above target's highest role. Detail: {exc.text}"
            )}
        except discord.NotFound:
            _dashboard_record(name, time.perf_counter() - t0, "error", "NotFound")
            return {"error": "Target not found (user, channel, or message does not exist)."}
        except discord.HTTPException as exc:
            _dashboard_record(name, time.perf_counter() - t0, "error", f"HTTP {exc.status}")
            return {"error": f"Discord API error ({exc.status}): {exc.text}"}
        except Exception as exc:
            _dashboard_record(name, time.perf_counter() - t0, "error", type(exc).__name__)
            logger.exception("ToolExecutor: error inesperado en %s", name)
            return {"error": f"Unexpected error in '{name}': {type(exc).__name__}: {exc}"}

    # FIX 5: Pre-check de permisos del bot
    def _check_bot_permissions(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Devuelve error dict si el bot no tiene los permisos necesarios, None si OK."""
        me = self.guild.me
        if not me:
            return {"error": "Bot not found in guild."}

        perm_map = {
            "ban_user": "ban_members",
            "kick_user": "kick_members",
            "mute_user": "moderate_members",
            "unmute_user": "moderate_members",
            "mass_timeout": "moderate_members",
            "softban_user": "ban_members",
            "unban_user": "ban_members",
            "purge_messages": "manage_messages",
            "lock_channel": "manage_channels",
            "unlock_channel": "manage_channels",
            "set_slowmode": "manage_channels",
            "rename_channel": "manage_channels",
            "set_channel_topic": "manage_channels",
            "create_channel": "manage_channels",
            "move_channel": "manage_channels",
            "clone_channel": "manage_channels",
            "set_channel_permissions": "manage_channels",
            "pin_message": "manage_messages",
            "unpin_message": "manage_messages",
            "create_thread": "manage_threads",
            "archive_thread": "manage_threads",
            "assign_role": "manage_roles",
            "remove_role": "manage_roles",
            "create_role": "manage_roles",
            "bulk_assign_role": "manage_roles",
            "sync_role_permissions": "manage_roles",
            "create_reaction_role": "manage_roles",
            "seal_user": "manage_roles",  # Also needs manage_channels, checked at runtime
            "unseal_user": "manage_roles",
            "create_event": "manage_events",
            "delete_event": "manage_events",
            "create_invite": "create_instant_invite",
            "get_audit_log": "view_audit_log",
            "curse_user": "manage_webhooks",    # Also needs manage_messages, checked at runtime
            "uncurse_user": "manage_webhooks",
            "wash_mouth": "manage_webhooks",     # Also needs manage_messages, checked at runtime
            "unwash_mouth": "manage_webhooks",
        }

        required = perm_map.get(tool_name)
        if not required:
            return None  # No perm check needed

        if not getattr(me.guild_permissions, required, False):
            return {
                "error": (
                    f"Bot lacks required permission '{required}' for tool '{tool_name}'. "
                    f"Please grant this permission to the bot's role."
                )
            }
        return None

    # ── Helpers de resolución ─────────────────────────────────────────────

    def _get_member(self, user_id: Any) -> Optional[discord.Member]:
        uid = _safe_int(user_id)
        return self.guild.get_member(uid) if uid else None

    def _resolve_channel(self, channel_id: Any = None) -> discord.abc.Messageable:
        if channel_id:
            cid = _safe_int(channel_id)
            if cid:
                ch = self.guild.get_channel(cid)
                if ch:
                    return ch
        return self.channel

    def _get_role(self, role_id: Any) -> Optional[discord.Role]:
        rid = _safe_int(role_id)
        return self.guild.get_role(rid) if rid else None

    def _mod_roles(self) -> list[discord.Role]:
        return [
            r for r in self.guild.roles
            if r.permissions.administrator or r.permissions.manage_guild
            or r.permissions.ban_members   or r.permissions.kick_members
        ]

    # ── Helpers de validación ──

    def _require_member(self, user_id: Any) -> tuple[Optional[discord.Member], Optional[dict]]:
        m = self._get_member(user_id)
        return (m, None) if m else (None, {"error": f"Member {user_id} not found in server."})

    def _require_role(self, role_id: Any) -> tuple[Optional[discord.Role], Optional[dict]]:
        r = self._get_role(role_id)
        return (r, None) if r else (None, {"error": f"Role {role_id} not found."})

    def _require_duration(self, duration: str) -> tuple[Optional[datetime.timedelta], Optional[dict]]:
        try:
            return _parse_duration(str(duration)), None
        except ValueError as e:
            return None, {"error": str(e)}

    # ── Helper: permisos en paralelo con semáforo ──────────────────────

    async def _batch_set_permissions(
        self,
        channels: Sequence[discord.abc.GuildChannel],
        target: discord.Role | discord.Member,
        *,
        reason: str = "",
        **overwrite_kwargs: Optional[bool],
    ) -> tuple[int, int]:
        sem     = asyncio.Semaphore(_PERM_CONCURRENCY)
        ok_ref  = [0]
        err_ref = [0]

        async def _one(ch: discord.abc.GuildChannel) -> None:
            async with sem:
                try:
                    await ch.set_permissions(target, reason=reason, **overwrite_kwargs)
                    ok_ref[0] += 1
                except (discord.Forbidden, discord.HTTPException):
                    err_ref[0] += 1

        await asyncio.gather(*[_one(ch) for ch in channels])
        return ok_ref[0], err_ref[0]

    # ── MODERACIÓN ────────────────────────────────────────────────────────

    async def _do_ban_user(self, user_id, reason="No reason provided", delete_days=0, **_):
        member, err = self._require_member(user_id)
        if err: return err
        await member.ban(reason=reason, delete_message_days=max(0, min(7, int(delete_days or 0))))
        await self.db.log_action(self.guild.id, "ban", target_id=member.id, details={"reason": reason})
        return {"success": True, "banned": str(member), "user_id": str(member.id)}

    async def _do_kick_user(self, user_id, reason="No reason provided", **_):
        member, err = self._require_member(user_id)
        if err: return err
        await member.kick(reason=reason)
        await self.db.log_action(self.guild.id, "kick", target_id=member.id, details={"reason": reason})
        return {"success": True, "kicked": str(member)}

    async def _do_mute_user(self, user_id, duration="1h", reason="No reason provided", **_):
        member, err = self._require_member(user_id)
        if err: return err
        if member.bot:
            return {"error": "Cannot mute bots."}
        td, err = self._require_duration(str(duration))
        if err: return err
        until = discord.utils.utcnow() + td
        await member.timeout(until, reason=reason)
        await self.db.log_action(self.guild.id, "mute", target_id=member.id,
                                 details={"duration": str(duration), "reason": reason})
        return {"success": True, "muted": str(member), "until": until.isoformat()}

    async def _do_unmute_user(self, user_id, reason="Unmuted by Fairy", **_):
        member, err = self._require_member(user_id)
        if err: return err
        await member.timeout(None, reason=reason)
        await self.db.log_action(self.guild.id, "unmute", target_id=member.id)
        return {"success": True, "unmuted": str(member)}

    async def _do_warn_user(self, user_id, reason, **_):
        member, err = self._require_member(user_id)
        if err: return err
        total, _ = await asyncio.gather(
            self.db.add_warning(self.guild.id, member.id, 0, reason),
            self.db.add_infraction(self.guild.id, member.id),
        )
        auto_action = None
        if total >= 3:
            try:
                await member.timeout(discord.utils.utcnow() + datetime.timedelta(hours=1),
                                     reason=f"Auto-timeout: {total} warnings")
                auto_action = "timeout_1h"
            except discord.Forbidden:
                auto_action = "timeout_failed_permissions"
        return {"success": True, "user": str(member), "total_warnings": total, "auto_action": auto_action}

    async def _do_get_warnings(self, user_id, **_):
        uid = _safe_int(user_id)
        if uid is None:
            return {"error": "Invalid user_id."}
        warns  = await self.db.get_warnings(self.guild.id, uid)
        member = self._get_member(uid)
        return {
            "user": str(member) if member else f"User {uid}",
            "total": len(warns),
            "warnings": [{"reason": w["reason"], "timestamp": w["timestamp"]} for w in warns],
        }

    async def _do_clear_warnings(self, user_id, **_):
        uid = _safe_int(user_id)
        if uid is None:
            return {"error": "Invalid user_id."}
        await self.db.clear_warnings(self.guild.id, uid)
        member = self._get_member(uid)
        return {"success": True, "user": str(member) if member else f"User {uid}"}

    async def _do_unban_user(self, user_id: str, reason: str = "Unbanned by Fairy", **_):
        uid = _safe_int(user_id)
        if uid is None:
            return {"error": "user_id inválido."}
        try:
            ban_entry = await self.guild.fetch_ban(discord.Object(id=uid))
        except discord.NotFound:
            return {"error": f"El usuario {uid} no está baneado actualmente."}
        await self.guild.unban(ban_entry.user, reason=reason)
        await self.db.log_action(self.guild.id, "unban", target_id=uid, details={"reason": reason})
        return {"success": True, "unbanned": str(ban_entry.user), "user_id": str(uid)}

    async def _do_softban_user(self, user_id: str, delete_days: int = 1,
                               reason: str = "Softban by Fairy", **_):
        member, err = self._require_member(user_id)
        if err: return err
        days = max(1, min(7, int(delete_days or 1)))
        await member.ban(reason=f"[Softban] {reason}", delete_message_days=days)
        await self.guild.unban(member, reason=f"[Softban unban] {reason}")
        await self.db.log_action(self.guild.id, "softban", target_id=member.id,
                                 details={"reason": reason, "delete_days": days})
        return {"success": True, "softbanned": str(member), "messages_deleted_days": days}

    async def _do_get_infractions_summary(self, hours: int = 24, **_):
        hrs = max(1, min(720, int(hours or 24)))
        try:
            summary = await self.db.get_infractions_summary(self.guild.id, hours=hrs)
            return {"period_hours": hrs, **summary}
        except AttributeError:
            from collections import Counter
            entries = []
            async for entry in self.guild.audit_logs(limit=100):
                if (discord.utils.utcnow() - entry.created_at).total_seconds() / 3600 <= hrs:
                    entries.append(entry.action.name)
            counts = Counter(entries)
            return {"period_hours": hrs, "bans": counts.get("ban", 0),
                    "kicks": counts.get("kick", 0), "mutes": counts.get("member_update", 0),
                    "total_actions": len(entries), "breakdown": dict(counts)}

    async def _do_mass_timeout(self, user_ids: str, duration: str = "1h",
                               reason: str = "Mass timeout by Fairy", **_):
        raw_ids = [uid.strip() for uid in str(user_ids).split(",") if uid.strip()]
        if not raw_ids:
            return {"error": "user_ids está vacío."}
        td, err = self._require_duration(str(duration))
        if err: return err
        until = discord.utils.utcnow() + td
        ok, failed = [], []
        sem = asyncio.Semaphore(8)

        async def _timeout_one(uid_str: str) -> None:
            async with sem:
                member = self._get_member(uid_str)
                if not member:
                    failed.append(uid_str); return
                if member.bot:
                    failed.append(f"{uid_str}(bot)"); return
                try:
                    await member.timeout(until, reason=reason)
                    ok.append(str(member))
                except discord.Forbidden:
                    failed.append(str(member))

        await asyncio.gather(*[_timeout_one(uid) for uid in raw_ids])
        await self.db.log_action(self.guild.id, "mass_timeout", target_id=0,
                                 details={"users": ok, "reason": reason, "until": until.isoformat()})
        return {"success": True, "timed_out": ok, "failed": failed,
                "total_ok": len(ok), "until": until.isoformat()}

    async def _do_watch_user(self, user_id: str, reason: str = "", **_):
        member, err = self._require_member(user_id)
        if err: return err
        await self.db.set_watch(self.guild.id, member.id, True, reason or "")
        return {"success": True, "watching": str(member), "user_id": str(member.id), "reason": reason}

    async def _do_unwatch_user(self, user_id: str, **_):
        member, err = self._require_member(user_id)
        if err: return err
        await self.db.set_watch(self.guild.id, member.id, False, "")
        return {"success": True, "unwatched": str(member)}

    async def _do_list_watched_users(self, **_):
        rows = await self.db.get_watched_users(self.guild.id)
        result = []
        for r in rows:
            member = self._get_member(r.get("user_id", 0))
            result.append({
                "user_id":      str(r.get("user_id", "")),
                "display_name": member.display_name if member else f"User {r.get('user_id', '')}",
                "reason":       r.get("reason", ""),
                "since":        r.get("since", ""),
            })
        return {"count": len(result), "watched_users": result}

    async def _do_case_note(self, user_id: str, note: str, **_):
        member, err = self._require_member(user_id)
        if err: return err
        await self.db.add_case_note(self.guild.id, member.id, note)
        return {"success": True, "user": str(member), "note_added": note}

    async def _do_get_case_notes(self, user_id: str, **_):
        uid = _safe_int(user_id)
        if uid is None:
            return {"error": "Invalid user_id."}
        member = self._get_member(uid)
        notes  = await self.db.get_case_notes(self.guild.id, uid)
        return {"user": str(member) if member else f"User {uid}", "count": len(notes), "notes": notes}

    async def _do_antiraid_scan(self, hours: str = "0.5", min_messages: int = 5, **_):
        try:
            hrs = max(0.1, float(hours or 0.5))
        except (ValueError, TypeError):
            hrs = 0.5
        min_msg  = max(1, int(min_messages or 5))
        cutoff   = discord.utils.utcnow() - datetime.timedelta(hours=hrs)
        new_acct = discord.utils.utcnow() - datetime.timedelta(days=7)
        new_members = [m for m in self.guild.members if m.joined_at and m.joined_at > cutoff and not m.bot]

        async def _scan_one(member: discord.Member) -> Optional[dict]:
            rows = await self.db.search_messages(guild_id=self.guild.id, user_id=member.id,
                                                 hours=max(1, int(hrs * 2)), limit=50)
            if len(rows) < min_msg:
                return None
            contents     = [r["content"] for r in rows if r.get("content")]
            unique_ratio = len(set(contents)) / max(len(contents), 1)
            return {
                "user_id":              str(member.id), "username": str(member),
                "joined_at":            member.joined_at.isoformat(),
                "account_age_days":     (discord.utils.utcnow() - member.created_at).days,
                "messages_in_window":   len(rows),
                "unique_message_ratio": round(unique_ratio, 2),
                "is_new_account":       member.created_at > new_acct,
                "sample_messages":      contents[:3],
                "raid_score":           round((1 - unique_ratio) * len(rows), 1),
            }

        results    = await asyncio.gather(*[_scan_one(m) for m in new_members])
        suspects   = sorted([r for r in results if r], key=lambda x: x["raid_score"], reverse=True)
        raid_likely = len(suspects) >= 3 or any(s["raid_score"] > 10 for s in suspects)
        return {
            "scan_window_hours":   hrs, "new_joins_in_window": len(new_members),
            "suspects":            suspects, "raid_likely": raid_likely,
            "recommended_action": (
                "Usa mass_timeout con los user_ids de sospechosos y lock_channel en canales afectados."
                if raid_likely else "Sin señales claras de raid."
            ),
        }

    # ── GESTIÓN DE CANAL ──────────────────────────────────────────────────

    async def _do_purge_messages(self, count, channel_id=None, user_id=None, **_):
        ch    = self._resolve_channel(channel_id)
        count = max(1, min(100, int(count)))
        check = None
        if user_id:
            uid = _safe_int(user_id)
            if uid:
                check = lambda m: m.author.id == uid
        deleted = await ch.purge(limit=count, check=check)
        return {"success": True, "deleted": len(deleted)}

    async def _do_lock_channel(self, channel_id=None, reason="Locked by Fairy", **_):
        ch = self._resolve_channel(channel_id)
        if not isinstance(ch, discord.TextChannel):
            return {"error": "Target is not a text channel."}
        ow = ch.overwrites_for(self.guild.default_role)
        ow.send_messages = False
        await ch.set_permissions(self.guild.default_role, overwrite=ow, reason=reason)
        return {"success": True, "locked": ch.name}

    async def _do_unlock_channel(self, channel_id=None, **_):
        ch = self._resolve_channel(channel_id)
        if not isinstance(ch, discord.TextChannel):
            return {"error": "Target is not a text channel."}
        ow = ch.overwrites_for(self.guild.default_role)
        ow.send_messages = None
        await ch.set_permissions(self.guild.default_role, overwrite=ow)
        return {"success": True, "unlocked": ch.name}

    async def _do_set_slowmode(self, seconds, channel_id=None, **_):
        ch      = self._resolve_channel(channel_id)
        seconds = max(0, min(21600, int(seconds)))
        if isinstance(ch, discord.TextChannel):
            await ch.edit(slowmode_delay=seconds)
        return {"success": True, "slowmode_seconds": seconds}

    async def _do_rename_channel(self, new_name, channel_id=None, **_):
        ch = self._resolve_channel(channel_id)
        old_name = getattr(ch, "name", "unknown")
        await ch.edit(name=new_name)
        return {"success": True, "old_name": old_name, "new_name": new_name}

    async def _do_set_channel_topic(self, topic: str = "", channel_id: str = "", **_):
        ch = self._resolve_channel(channel_id)
        if not isinstance(ch, discord.TextChannel):
            return {"error": "El tema solo puede establecerse en canales de texto."}
        old_topic = ch.topic or ""
        new_topic = topic.strip() or None
        await ch.edit(topic=new_topic)
        return {"success": True, "channel": ch.name,
                "old_topic": old_topic or "(vacío)", "new_topic": new_topic or "(borrado)"}

    async def _do_create_channel(self, name: str, type: str = "text",
                                 category_id: str = "", topic: str = "", reason: str = "", **_):
        category = None
        if category_id:
            cid = _safe_int(category_id)
            category = self.guild.get_channel(cid) if cid else None
            if not isinstance(category, discord.CategoryChannel):
                return {"error": f"El canal {category_id} no es una categoría válida."}
        channel_type = (type or "text").lower().strip()
        if channel_type == "voice":
            ch = await self.guild.create_voice_channel(name=name, category=category, reason=reason or None)
        elif channel_type == "text":
            ch = await self.guild.create_text_channel(
                name=name, category=category, topic=topic or None, reason=reason or None)
        else:
            return {"error": f"Tipo de canal '{type}' no soportado. Usa 'text' o 'voice'."}
        return {"success": True, "channel_id": str(ch.id), "name": ch.name,
                "type": channel_type, "category": category.name if category else None}

    async def _do_move_channel(self, channel_id: str, category_id: str = "", **_):
        cid = _safe_int(channel_id)
        ch  = self.guild.get_channel(cid) if cid else None
        if not ch:
            return {"error": f"Canal {channel_id} no encontrado."}
        category = None
        if category_id:
            cat_id   = _safe_int(category_id)
            category = self.guild.get_channel(cat_id) if cat_id else None
            if not isinstance(category, discord.CategoryChannel):
                return {"error": f"El canal {category_id} no es una categoría válida."}
        await ch.edit(category=category)
        return {"success": True, "channel": ch.name,
                "new_category": category.name if category else "(sin categoría)"}

    async def _do_clone_channel(self, channel_id: str, new_name: str = "", **_):
        cid = _safe_int(channel_id)
        ch  = self.guild.get_channel(cid) if cid else None
        if not ch:
            return {"error": f"Canal {channel_id} no encontrado."}
        cloned = await ch.clone(name=new_name.strip() or f"{ch.name}-copy")
        return {"success": True, "original": ch.name, "clone_id": str(cloned.id),
                "clone_name": cloned.name, "category": cloned.category.name if cloned.category else None}

    async def _do_get_channel_permissions(self, channel_id: str, **_):
        cid = _safe_int(channel_id)
        ch  = self.guild.get_channel(cid) if cid else None
        if not ch:
            return {"error": f"Canal {channel_id} no encontrado."}
        result = []
        for target, overwrite in ch.overwrites.items():
            allow, deny = overwrite.pair()
            result.append({
                "target": str(target), "target_id": str(target.id),
                "type":   "role" if isinstance(target, discord.Role) else "member",
                "allow":  [name for name, val in iter(allow) if val],
                "deny":   [name for name, val in iter(deny)  if val],
            })
        return {"channel": ch.name, "channel_id": str(ch.id), "overwrites": result}

    async def _do_set_channel_permissions(self, channel_id: str = "", target_id: str = "",
                                          role_id: str = "",
                                          allow_perms: str = "", deny_perms: str = "",
                                          reset_perms: str = "", **_):
        cid = _safe_int(channel_id)
        ch = self.guild.get_channel(cid) if cid else None
        if not ch: return {"error": f"Canal {channel_id} no encontrado."}
        # Resolve target: try role first, then member (support legacy role_id param)
        tid = _safe_int(target_id or role_id)
        target = self._get_role(str(tid)) if tid else None
        if not target and tid:
            target = self.guild.get_member(tid)
        if not target: return {"error": f"Rol/miembro {target_id or role_id} no encontrado."}
        ow, errors = ch.overwrites_for(target), []
        for perm_str, value in [(allow_perms, True), (deny_perms, False), (reset_perms, None)]:
            for perm in (p.strip() for p in perm_str.split(",") if p.strip()):
                if _safe_perm_name(perm):
                    setattr(ow, perm, value)
                else:
                    errors.append(f"Permiso inválido: '{perm}'")
        await ch.set_permissions(target, overwrite=ow)
        name = target.name if hasattr(target, "name") else target.display_name
        result: dict = {"success": True, "channel": ch.name, "target": name}
        if errors:
            result["warnings"] = errors
        return result

    async def _do_list_categories(self, **_):
        categories = [
            {"category_id": str(cat.id), "name": cat.name, "position": cat.position,
             "channels": [{"id": str(ch.id), "name": ch.name, "type": str(ch.type)}
                          for ch in cat.channels]}
            for cat in self.guild.categories
        ]
        uncategorized = [
            {"id": str(ch.id), "name": ch.name, "type": str(ch.type)}
            for ch in self.guild.channels
            if ch.category is None and not isinstance(ch, discord.CategoryChannel)
        ]
        return {"total_categories": len(categories), "categories": categories,
                "uncategorized": uncategorized}

    async def _do_archive_thread(self, thread_id: str, archive: bool = True, **_):
        tid    = _safe_int(thread_id)
        thread = self.guild.get_thread(tid) if tid else None
        if thread is None and tid:
            try:
                thread = await self.guild.fetch_channel(tid)
            except (discord.NotFound, discord.HTTPException):
                pass
        if not thread:
            return {"error": f"Hilo {thread_id} no encontrado."}
        if not isinstance(thread, discord.Thread):
            return {"error": f"El canal {thread_id} no es un hilo."}
        await thread.edit(archived=bool(archive))
        return {"success": True, "thread": thread.name, "archived": bool(archive)}

    async def _do_send_message(self, channel_id, content, ping_everyone=False, **_):
        ch   = self._resolve_channel(channel_id)
        text = "@everyone " + content if ping_everyone else content
        if isinstance(ch, discord.ForumChannel):
            name   = (text[:90] + "...") if len(text) > 90 else text
            thread = await ch.create_thread(name=name, content=text)
            return {"success": True, "message_id": str(thread.id)}
        msg = await ch.send(text)
        return {"success": True, "message_id": str(msg.id)}

    async def _do_cross_guild_send(self, guild_id: str, channel_id: str, content: str, **_):
        """SYSTEM OVERRIDE: envía a cualquier guild/canal donde el bot esté."""
        gid = _safe_int(guild_id)
        cid = _safe_int(channel_id)
        guild = self._bot_ref.get_guild(gid) if gid else None
        if not guild:
            return {"error": f"Guild {guild_id} no encontrado o el bot no está ahí."}
        ch = guild.get_channel(cid)
        if not ch:
            return {"error": f"Canal {channel_id} no encontrado en {guild.name}."}
        msg = await ch.send(content)
        return {"success": True, "guild": guild.name, "channel": ch.name, "message_id": str(msg.id)}

    async def _do_list_guilds(self, **_):
        """SYSTEM OVERRIDE: lista todos los servidores del bot."""
        guilds = [{"name": g.name, "id": str(g.id), "members": g.member_count}
                  for g in self._bot_ref.guilds]
        return {"guilds": guilds, "total": len(guilds)}

    async def _do_find_cross_guild_channel(self, guild_id: str, name: str, **_):
        """SYSTEM OVERRIDE: busca canales por nombre en otro servidor."""
        gid = _safe_int(guild_id)
        guild = self._bot_ref.get_guild(gid) if gid else None
        if not guild:
            return {"error": f"Guild {guild_id} no encontrado."}
        query = name.lower()
        matches = [{"name": ch.name, "id": str(ch.id), "type": str(ch.type)}
                   for ch in guild.channels if query in ch.name.lower()]
        return {"guild": guild.name, "matches": matches[:20]}

    async def _do_add_reaction(self, message_id, emoji, channel_id=None, **_):
        ch = self._resolve_channel(channel_id)
        try:
            msg = await ch.fetch_message(int(message_id))
            await msg.add_reaction(emoji)
            return {"success": True, "emoji": emoji, "message_id": str(message_id)}
        except discord.HTTPException as exc:
            return {"error": f"Could not add reaction: {exc.text}"}

    async def _do_pin_message(self, message_id, channel_id=None, **_):
        ch  = self._resolve_channel(channel_id)
        msg = await ch.fetch_message(int(message_id))
        await msg.pin()
        return {"success": True, "pinned_message_id": str(message_id)}

    async def _do_unpin_message(self, message_id, channel_id=None, **_):
        ch  = self._resolve_channel(channel_id)
        msg = await ch.fetch_message(int(message_id))
        await msg.unpin()
        return {"success": True, "unpinned_message_id": str(message_id)}

    async def _do_create_thread(self, message_id, thread_name, channel_id=None, auto_archive=1440, **_):
        ch = self._resolve_channel(channel_id)
        if not isinstance(ch, discord.TextChannel):
            return {"error": "Threads can only be created in text channels."}
        msg            = await ch.fetch_message(int(message_id))
        valid_archives = [60, 1440, 4320, 10080]
        archive        = min(valid_archives, key=lambda x: abs(x - int(auto_archive or 1440)))
        thread         = await msg.create_thread(name=thread_name, auto_archive_duration=archive)
        return {"success": True, "thread_id": str(thread.id), "thread_name": thread.name}

    # ── DESCUBRIMIENTO DE CANALES Y MENSAJES ───────────────────────────



    # ── CANALES ─────────────────────────────────────────────────────────────

    async def _do_find_channel(self, name: str, **_):
        """Busca canales por nombre parcial (case-insensitive, Unicode-normalized)."""
        import unicodedata
        query = str(name).strip().lower()
        if not query:
            return {"error": "Proporciona un nombre de canal para buscar."}

        def _normalize(text: str) -> str:
            """Normaliza Unicode fancy chars a ASCII equivalente."""
            # NFKD descompone chars como 𝔾→G, ❰→(, etc.
            decomposed = unicodedata.normalize("NFKD", text)
            # Quitar diacríticos y non-letter/digit/space
            ascii_approx = "".join(
                c for c in decomposed
                if unicodedata.category(c)[0] in ("L", "N", "Z")  # Letter, Number, Separator
            ).lower()
            return ascii_approx

        norm_query = _normalize(query)

        matches = []
        for ch in self.guild.channels:
            ch_lower = ch.name.lower()
            norm_ch = _normalize(ch.name)
            # Match en nombre original O en versión normalizada
            if query in ch_lower or norm_query in norm_ch:
                cat = ch.category.name if ch.category else None
                topic = getattr(ch, "topic", None)
                matches.append({
                    "channel_id":  str(ch.id),
                    "name":        ch.name,
                    "type":        str(ch.type),
                    "category":    cat,
                    "topic":       topic or "",
                    "position":    ch.position,
                })
        if not matches:
            return {"query": name, "matches": [],
                    "tip": "No se encontraron canales. Usa list_categories para ver todos."}
        return {"query": name, "count": len(matches), "matches": matches[:30]}

    async def _do_get_message(self, message_id: str, channel_id: str = "", **_):
        """Obtiene el contenido de un mensaje específico por ID."""
        ch = self._resolve_channel(channel_id or None)
        try:
            msg = await ch.fetch_message(int(message_id))
        except (discord.NotFound, discord.HTTPException):
            return {"error": f"Mensaje {message_id} no encontrado."}
        attachments = [{"filename": a.filename, "url": str(a.url), "size": a.size}
                       for a in msg.attachments]
        reactions = {}
        for r in msg.reactions:
            reactions[str(r.emoji)] = r.count
        return {
            "message_id":   str(msg.id),
            "author":       str(msg.author),
            "author_id":    str(msg.author.id),
            "content":      msg.content,
            "channel":      getattr(ch, "name", str(channel_id)),
            "channel_id":   str(msg.channel.id),
            "timestamp":    msg.created_at.isoformat(),
            "edited":       msg.edited_at.isoformat() if msg.edited_at else None,
            "attachments":  attachments,
            "reactions":    reactions,
            "pinned":       msg.pinned,
            "jump_url":     msg.jump_url,
        }

    async def _do_get_message_context(self, message_id: str, before_limit: int = 150, after_limit: int = 150, **_):
        msg_id = _safe_int(message_id)
        if not msg_id:
            return {"error": "Formato de message_id inválido."}

        try:
            b_limit = min(max(int(before_limit), 1), 500)
        except Exception:
            b_limit = 150

        try:
            a_limit = min(max(int(after_limit), 1), 500)
        except Exception:
            a_limit = 150

        # 1. Buscar el canal del mensaje objetivo en SQLite
        async with self.db._db.execute(
            "SELECT channel_id FROM messages WHERE id = ?", (msg_id,)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return {"error": f"Mensaje con ID {msg_id} no encontrado en la base de datos."}
            channel_id = row["channel_id"]

        # 2. Obtener mensajes anteriores en el mismo canal
        async with self.db._db.execute(
            f"""SELECT m.id, m.user_id, m.content, m.timestamp,
                      COALESCE(NULLIF(m.username,''), p.username, p.display_name, CAST(m.user_id AS TEXT)) AS username
               FROM messages m
               LEFT JOIN user_profiles p ON p.user_id = m.user_id
               WHERE m.channel_id = ? AND m.id < ?
               ORDER BY m.id DESC LIMIT {b_limit}""",
            (channel_id, msg_id)
        ) as cur:
            before_rows = [dict(r) for r in await cur.fetchall()]
            before_rows.reverse()

        # 3. Obtener el mensaje central
        async with self.db._db.execute(
            """SELECT m.id, m.user_id, m.content, m.timestamp,
                      COALESCE(NULLIF(m.username,''), p.username, p.display_name, CAST(m.user_id AS TEXT)) AS username
               FROM messages m
               LEFT JOIN user_profiles p ON p.user_id = m.user_id
               WHERE m.id = ?""",
            (msg_id,)
        ) as cur:
            row = await cur.fetchone()
            target_row = dict(row) if row else None

        # 4. Obtener mensajes posteriores en el mismo canal
        async with self.db._db.execute(
            f"""SELECT m.id, m.user_id, m.content, m.timestamp,
                      COALESCE(NULLIF(m.username,''), p.username, p.display_name, CAST(m.user_id AS TEXT)) AS username
               FROM messages m
               LEFT JOIN user_profiles p ON p.user_id = m.user_id
               WHERE m.channel_id = ? AND m.id > ?
               ORDER BY m.id ASC LIMIT {a_limit}""",
            (channel_id, msg_id)
        ) as cur:
            after_rows = [dict(r) for r in await cur.fetchall()]

        # Combinar
        total_rows = before_rows + ([target_row] if target_row else []) + after_rows
        
        ch = self._resolve_channel(str(channel_id))
        channel_name = ch.name if hasattr(ch, "name") else "unknown"

        return {
            "channel_name": channel_name,
            "channel_id": str(channel_id),
            "target_message_id": str(msg_id),
            "count_before": len(before_rows),
            "count_after": len(after_rows),
            "total_count": len(total_rows),
            "context_messages": [
                {
                    "message_id": str(r["id"]),
                    "username": r["username"],
                    "user_id": str(r["user_id"]),
                    "content": r["content"],
                    "timestamp": r["timestamp"],
                    "is_target": (r["id"] == msg_id)
                }
                for r in total_rows
            ]
        }

    # ── ROLES ─────────────────────────────────────────────────────────────

    async def _do_assign_role(self, user_id, role_id, **_):
        member, err = self._require_member(user_id)
        if err: return err
        role, err = self._require_role(role_id)
        if err: return err
        await member.add_roles(role)
        return {"success": True, "user": str(member), "role": role.name}

    async def _do_remove_role(self, user_id, role_id, **_):
        member, err = self._require_member(user_id)
        if err: return err
        role, err = self._require_role(role_id)
        if err: return err
        await member.remove_roles(role)
        return {"success": True, "user": str(member), "role": role.name}

    async def _do_create_role(self, name, color=None, mentionable=False, hoist=False, **_):
        color_obj = discord.Color.default()
        if color:
            try:
                color_obj = discord.Color(int(str(color).lstrip("#"), 16))
            except (ValueError, AttributeError):
                pass
        role = await self.guild.create_role(name=name, color=color_obj,
                                            mentionable=bool(mentionable), hoist=bool(hoist))
        return {"success": True, "role_id": str(role.id), "role_name": role.name}

    async def _do_bulk_assign_role(self, role_id: str, user_ids: str, action: str = "add", **_):
        role, err = self._require_role(role_id)
        if err: return err
        action = (action or "add").lower().strip()
        if action not in ("add", "remove"):
            return {"error": "El parámetro 'action' debe ser 'add' o 'remove'."}
        raw_ids = [uid.strip() for uid in str(user_ids).split(",") if uid.strip()]
        if not raw_ids:
            return {"error": "user_ids está vacío."}
        ok, failed = [], []
        sem = asyncio.Semaphore(8)

        async def _one(uid_str: str) -> None:
            async with sem:
                member = self._get_member(uid_str)
                if not member:
                    failed.append(uid_str); return
                try:
                    if action == "add":
                        await member.add_roles(role, reason="bulk_assign_role by Fairy")
                    else:
                        await member.remove_roles(role, reason="bulk_assign_role by Fairy")
                    ok.append(str(member))
                except discord.Forbidden:
                    failed.append(str(member))

        await asyncio.gather(*[_one(uid) for uid in raw_ids])
        return {"success": True, "action": action, "role": role.name,
                "ok": ok, "failed": failed, "total_ok": len(ok)}

    async def _do_get_role_members(self, role_id: str, **_):
        role, err = self._require_role(role_id)
        if err: return err
        return {
            "role": role.name, "role_id": str(role.id), "count": len(role.members),
            "members": [{"user_id": str(m.id), "display_name": m.display_name} for m in role.members],
        }

    async def _do_list_roles(self, **_):
        """Lista todos los roles del servidor con IDs y metadata."""
        roles = []
        for role in sorted(self.guild.roles, key=lambda r: r.position, reverse=True):
            roles.append({
                "role_id":       str(role.id),
                "name":          role.name,
                "color":         f"#{role.color.value:06X}" if role.color.value else "default",
                "position":      role.position,
                "member_count":  len(role.members),
                "hoist":         role.hoist,
                "mentionable":   role.mentionable,
                "managed":       role.managed,
                "is_everyone":   role.is_default(),
                "permissions":   role.permissions.value if role.permissions.value else 0,
            })
        return {
            "total_roles": len(roles),
            "roles": roles,
            "tip": "Usa get_role_members(role_id) para ver los miembros de un rol específico.",
        }

    async def _do_find_role(self, name: str, **_):
        """Busca roles por nombre parcial (case-insensitive)."""
        query = str(name).strip().lower()
        if not query:
            return {"error": "Proporciona un nombre de rol para buscar."}

        # 1. Buscar en Discord
        matches = []
        for role in self.guild.roles:
            if query in role.name.lower():
                matches.append({
                    "role_id":       str(role.id),
                    "name":          role.name,
                    "color":         f"#{role.color.value:06X}" if role.color.value else "default",
                    "position":      role.position,
                    "member_count":  len(role.members),
                    "hoist":         role.hoist,
                    "mentionable":   role.mentionable,
                    "managed":       role.managed,
                    "is_everyone":   role.is_default(),
                })
        if not matches:
            return {
                "query": name,
                "matches": [],
                "tip": "No se encontraron roles. Usa list_roles para ver todos los roles disponibles.",
            }
        return {
            "query": name,
            "count":  len(matches),
            "matches": matches,
            "tip": "Usa get_role_members(role_id) con el role_id de arriba para ver los miembros.",
        }

    async def _do_delete_role(self, role_id: str, reason: str = "", **_):
        """Elimina un rol del servidor."""
        role, err = self._require_role(role_id)
        if err: return err
        if role.is_default():
            return {"error": "No se puede eliminar el rol @everyone."}
        if role.managed:
            return {"error": f"No se puede eliminar el rol gestionado '{role.name}' (es de una integración)."}
        name = role.name
        await role.delete(reason=reason or f"Eliminado por Fairy")
        return {"success": True, "deleted_role": name, "role_id": str(role_id)}

    async def _do_role_info(self, role_id: str, **_):
        """Info detallada de un solo rol."""
        role, err = self._require_role(role_id)
        if err: return err
        online = sum(1 for m in role.members if m.status != discord.Status.offline)
        created = role.created_at
        return {
            "role_id":       str(role.id),
            "name":          role.name,
            "color":         f"#{role.color.value:06X}" if role.color.value else "default",
            "position":      role.position,
            "member_count":  len(role.members),
            "online_count":  online,
            "hoist":         role.hoist,
            "mentionable":   role.mentionable,
            "managed":       role.managed,
            "is_everyone":   role.is_default(),
            "permissions":   role.permissions.value,
            "created_at":    created.isoformat() if created else None,
            "mention":       role.mention,
            "tip": "Usa get_role_members(role_id) para ver la lista completa de miembros.",
        }

    async def _do_bulk_assign_role_all(self, role_id: str, action: str = "add",
                                       ignore_bots: bool = True, **_):
        """Asigna o quita un rol a TODOS los miembros del server a la vez."""
        role, err = self._require_role(role_id)
        if err: return err
        action = (action or "add").lower().strip()
        if action not in ("add", "remove"):
            return {"error": "El parámetro 'action' debe ser 'add' o 'remove'."}
        members = [m for m in self.guild.members
                   if not (ignore_bots and m.bot)
                   and ((action == "add" and role not in m.roles)
                        or (action == "remove" and role in m.roles))]
        if not members:
            verb = "tiene" if action == "remove" else "necesita"
            return {"success": True, "action": action, "role": role.name,
                    "note": f"Ningún miembro {verb} el rol '{role.name}'.",
                    "total_ok": 0, "total_failed": 0}
        ok, failed = [], []
        sem = asyncio.Semaphore(20)
        async def _one(member):
            async with sem:
                try:
                    if action == "add":
                        await member.add_roles(role, reason="bulk_assign_role_all by Fairy")
                    else:
                        await member.remove_roles(role, reason="bulk_assign_role_all by Fairy")
                    ok.append(str(member))
                except discord.Forbidden:
                    failed.append(str(member))
        await asyncio.gather(*[_one(m) for m in members])
        return {"success": True, "action": action, "role": role.name,
                "total_ok": len(ok), "total_failed": len(failed),
                "failed_sample": failed[:5] if failed else []}

    async def _do_create_reaction_role(self, message_id: str, emoji: str, role_id: str,
                                       channel_id: str = "", **_):
        ch        = self._resolve_channel(channel_id)
        role, err = self._require_role(role_id)
        if err: return err
        try:
            msg = await ch.fetch_message(int(message_id))
            await asyncio.gather(
                msg.add_reaction(emoji),
                self.db.add_reaction_role(guild_id=self.guild.id, message_id=int(message_id),
                                          emoji=emoji, role_id=role.id),
            )
            return {"success": True, "message_id": str(message_id), "emoji": emoji, "role": role.name}
        except discord.HTTPException as exc:
            return {"error": f"Error añadiendo reacción: {exc.text}"}

    async def _do_sync_role_permissions(self, source_role_id: str, target_role_id: str,
                                        channel_id: str = "", **_):
        source = self._get_role(source_role_id)
        target = self._get_role(target_role_id)
        if not source: return {"error": f"Rol fuente {source_role_id} no encontrado."}
        if not target: return {"error": f"Rol destino {target_role_id} no encontrado."}
        if channel_id:
            cid = _safe_int(channel_id)
            ch  = self.guild.get_channel(cid) if cid else None
            if not ch:
                return {"error": f"Canal {channel_id} no encontrado."}
            await ch.set_permissions(target, overwrite=ch.overwrites_for(source),
                                     reason=f"Sync perms from {source.name}")
            return {"success": True, "synced_in_channel": ch.name,
                    "source": source.name, "target": target.name}
        await target.edit(permissions=source.permissions,
                          reason=f"Sync base perms from {source.name}")
        return {"success": True, "synced_base_permissions": True,
                "source": source.name, "target": target.name}

    # ── MENSAJERÍA ENRIQUECIDA ────────────────────────────────────────────

    async def _do_send_embed(self, channel_id: str, description: str, title: str = "",
                             color: str = "", fields_json: str = "", footer_text: str = "",
                             footer_icon_user_id: str = "", author_name: str = "",
                             author_icon_user_id: str = "", thumbnail_user_id: str = "",
                             thumbnail_url: str = "", image_url: str = "",
                             timestamp: bool = False, content: str = "", **_):
        ch    = self._resolve_channel(channel_id)
        embed = discord.Embed(
            title       = title or None,
            description = description or None,
            color       = discord.Color(_parse_hex_color(color, default=0xA855F7)),
        )
        if timestamp:
            embed.timestamp = discord.utils.utcnow()
        if author_name:
            m = self._get_member(author_icon_user_id) if author_icon_user_id else None
            embed.set_author(name=author_name, icon_url=_member_avatar_url(m))
        if thumbnail_user_id:
            url = _member_avatar_url(self._get_member(thumbnail_user_id))
            if url:
                embed.set_thumbnail(url=url)
        elif thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        if image_url:
            embed.set_image(url=image_url)
        if footer_text:
            m = self._get_member(footer_icon_user_id) if footer_icon_user_id else None
            embed.set_footer(text=footer_text, icon_url=_member_avatar_url(m))
        if fields_json:
            try:
                fields = json.loads(fields_json)
                if not isinstance(fields, list):
                    return {"error": "fields_json debe ser un array JSON."}
                for i, f in enumerate(fields[:25]):
                    name   = str(f.get("name", f"Campo {i+1}"))
                    value  = str(f.get("value", ""))
                    inline = bool(f.get("inline", False))
                    if name and value:
                        embed.add_field(name=name, value=value, inline=inline)
            except json.JSONDecodeError as exc:
                return {"error": f"fields_json no es JSON válido: {exc}"}
        if isinstance(ch, discord.ForumChannel):
            name   = (description[:90] + "...") if len(description) > 90 else description
            thread = await ch.create_thread(name=name, content=content or None, embed=embed)
            return {"success": True, "message_id": str(thread.id), "fields": len(embed.fields)}
        msg = await ch.send(content=content or None, embed=embed)
        return {"success": True, "message_id": str(msg.id),
                "channel": getattr(ch, "name", str(channel_id)), "fields": len(embed.fields)}

    async def _do_send_dm(self, user_id: str, content: str, embed_title: str = "",
                          embed_color: str = "", **_):
        member, err = self._require_member(user_id)
        if err: return err
        if member.bot:
            return {"error": "No se puede enviar DM a un bot."}
        try:
            if embed_title:
                embed = discord.Embed(
                    title=embed_title, description=content,
                    color=discord.Color(_parse_hex_color(embed_color, default=0xA855F7)),
                )
                embed.set_footer(text="Mensaje de Fairy ✨")
                await member.send(embed=embed)
            else:
                await member.send(content)
        except discord.Forbidden:
            return {"error": f"{member.display_name} tiene los DMs desactivados."}
        return {"success": True, "sent_to": str(member), "user_id": str(member.id)}

    # ── INFORMACIÓN Y DB ──────────────────────────────────────────────────

    async def _do_get_user_info(self, user_id, **_):
        uid = _safe_int(user_id)
        if uid is None:
            return {"error": "Invalid user_id."}
        member = self._get_member(uid)
        if not member:
            return {"error": f"Member {uid} not found in server."}
        warns, trust = await asyncio.gather(
            self.db.count_warnings(self.guild.id, member.id),
            self.db.get_trust(self.guild.id, member.id),
        )
        joined_ts = int(member.joined_at.timestamp()) if member.joined_at else 0
        days_in   = (time.time() - joined_ts) // 86400 if joined_ts else 0
        return {
            "user_id": str(member.id), "username": str(member),
            "display_name": member.display_name,
            "roles": [r.name for r in member.roles[1:]],
            "joined_days_ago": int(days_in),
            "account_created": str(member.created_at.date()),
            "warnings": warns,
            "message_count": trust["message_count"] if trust else 0,
            "infractions":   trust["infractions"]   if trust else 0,
        }

    async def _do_get_server_info(self, **_):
        g = self.guild
        return {
            "name": g.name, "guild_id": str(g.id), "member_count": g.member_count,
            "channel_count": len(g.channels), "role_count": len(g.roles),
            "created": str(g.created_at.date()), "owner": str(g.owner),
            "boost_level": g.premium_tier,
        }

    async def _do_get_user_by_name(self, name: str, context: str = "", **_):
        # 1. Buscar en DB + guild
        results = await self.db.search_users_by_name(name, guild_id=self.guild.id)
        if not results:
            name_lower = name.lower()
            for member in self.guild.members:
                if name_lower in member.display_name.lower() or name_lower in member.name.lower():
                    results = [{"user_id": member.id, "username": member.name,
                                "display_name": member.display_name,
                                "last_seen": int(time.time()), "card_json": None}]
                    break
        if not results:
            return {"error": f"No user found matching '{name}'."}
        row = results[0]
        uid = row["user_id"]
        member = self._get_member(uid)
        card_summary = {}
        card_raw = row.get("card_json")
        if card_raw and isinstance(card_raw, str):
            try:
                card = json.loads(card_raw)
                profile = card.get("profile", {})
                pers = card.get("personality", {})
                stats = card.get("stats", {})
                social = card.get("social", {})
                card_summary = {
                    "archetype": profile.get("archetype", "Unknown"),
                    "traits": pers.get("traits", []),
                    "habits": pers.get("habits", []),
                    "aura": stats.get("aura", "Unknown"),
                    "score": stats.get("score", 0),
                    "allies": social.get("allies", []),
                    "avoided": social.get("avoided", []),
                    "fairy_comment": card.get("fairy_comment", ""),
                    "personality_summary": pers.get("summary", ""),
                }
            except (json.JSONDecodeError, AttributeError):
                pass
        since = int(time.time()) - 48 * 3600
        msgs = await self.db.get_user_messages(uid, since, limit=10)
        return {
            "user_id": str(uid),
            "username": row.get("username", ""),
            "display_name": row.get("display_name") or row.get("username", ""),
            "current_nickname": member.nick if member and member.nick else None,
            "avatar_url": _member_avatar_url(member),
            "card": card_summary,
            "recent_messages": [m["content"] for m in msgs if m.get("content")][-8:],
            "note": (
                "Use card.traits, card.archetype, card.aura and recent_messages to craft "
                "a creative, personalized nickname that reflects this user's actual personality."
            ),
        }

    async def _do_batch_user_lookup(self, names: str, context: str = "basic", **_):
        """Look up multiple users in one call. Names are comma-separated."""
        name_list = [n.strip() for n in names.split(",") if n.strip()][:10]
        if not name_list:
            return {"error": "No names provided. Pass comma-separated names."}
        full_mode = (context or "basic").lower() in ("full", "card", "complete")
        results = {}
        for name in name_list:
            try:
                db_hits = await self.db.search_users_by_name(name, guild_id=self.guild.id)
                hit = None
                if db_hits:
                    hit = db_hits[0]
                else:
                    nl = name.lower()
                    for member in self.guild.members:
                        if nl in member.display_name.lower() or nl in member.name.lower():
                            hit = {"user_id": member.id, "username": member.name,
                                   "display_name": member.display_name, "card_json": None}
                            break
                if not hit:
                    results[name] = {"error": f"Not found"}
                    continue
                uid = hit["user_id"]
                member = self._get_member(uid)
                entry = {
                    "user_id": str(uid),
                    "username": hit.get("username", ""),
                    "display_name": hit.get("display_name") or hit.get("username", ""),
                    "avatar_url": _member_avatar_url(member),
                }
                if full_mode:
                    card_raw = hit.get("card_json")
                    if card_raw and isinstance(card_raw, str):
                        try:
                            card = json.loads(card_raw)
                            entry["card"] = {
                                "archetype": card.get("profile", {}).get("archetype", "Unknown"),
                                "traits": card.get("personality", {}).get("traits", []),
                                "aura": card.get("stats", {}).get("aura", "Unknown"),
                            }
                        except (json.JSONDecodeError, AttributeError):
                            pass
                    since = int(time.time()) - 48 * 3600
                    msgs = await self.db.get_user_messages(uid, since, limit=5)
                    entry["recent_messages"] = [m["content"] for m in msgs if m.get("content")][-5:]
                results[name] = entry
            except Exception as exc:
                results[name] = {"error": str(exc)}
        return {"users": results, "found": sum(1 for v in results.values() if "error" not in v)}

    async def _do_search_messages(self, keyword: str = "", user_id: str = "",
                                  channel_id: str = "", hours: int = 8760, limit: int = 50, **_):
        hrs = max(1, min(87600, int(hours or 8760)))
        lim = max(1, min(200, int(limit or 50)))
        rows = await self.db.search_messages(
            guild_id=self.guild.id, keyword=keyword or None,
            user_id=_safe_int(user_id), channel_id=_safe_int(channel_id),
            hours=hrs, limit=lim,
        )
        # Si se alcanzó el límite, obtener conteo real
        total = len(rows)
        if len(rows) >= lim and keyword:
            total = await self.db.count_search_messages(
                guild_id=self.guild.id, keyword=keyword,
                user_id=_safe_int(user_id), channel_id=_safe_int(channel_id),
                hours=hrs,
            )
        return {
            "count": len(rows),
            "total_matches": total,
            "messages": [
                {"message_id": str(r["id"]), "username": r["username"], "user_id": str(r["user_id"]),
                 "channel_id": str(r["channel_id"]), "content": r["content"],
                 "timestamp": r["timestamp"]}
                for r in rows
            ],
        }

    async def _do_get_server_activity(self, hours: int = 24, **_):
        hrs  = max(1, min(168, int(hours or 24)))
        rows = await self.db.get_server_activity(self.guild.id, hours=hrs)
        return {
            "period_hours": hrs,
            "active_users": [
                {"display_name": r["display_name"], "user_id": str(r["user_id"]),
                 "message_count": r["message_count"]}
                for r in rows
            ],
        }

    async def _do_get_user_card(self, user_id, **_):
        uid = _safe_int(user_id)
        if uid is None:
            return {"error": "Invalid user_id."}
        card_data = await self.db.get_card(uid)
        if not card_data:
            return {"error": f"No card found for user {uid}. Card is generated hourly."}
        member = self._get_member(uid)
        return {
            "user_id":      str(uid),
            "display_name": member.display_name if member else f"User {uid}",
            "card":         card_data["card_json"],
            "updated_at":   card_data["updated_at"],
        }

    async def _do_get_channel_summary(self, channel_id=None, hours: int = 24, **_):
        ch   = self._resolve_channel(channel_id)
        hrs  = max(1, min(168, int(hours or 24)))
        rows = await self.db.search_messages(
            guild_id=self.guild.id,
            channel_id=ch.id if hasattr(ch, "id") else None,
            hours=hrs, limit=100,
        )
        if not rows:
            return {"summary": "No messages found in the specified window.", "channel": str(ch)}
        user_counts: dict[str, int] = {}
        for r in rows:
            name = r["username"] or str(r["user_id"])
            user_counts[name] = user_counts.get(name, 0) + 1
        top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        return {
            "channel": str(ch), "period_hours": hrs, "total_messages": len(rows),
            "top_users":     [{"name": n, "messages": c} for n, c in top_users],
            "sample_topics": [r["content"][:80] for r in rows[:5] if r.get("content")],
        }

    async def _do_get_leaderboard(self, limit: int = 10, hours: int = 0, **_):
        lim = max(1, min(20, int(limit or 10)))
        hrs = max(0, int(hours or 0))
        try:
            if hrs > 0:
                rows = await self.db.get_server_activity(self.guild.id, hours=hrs, limit=lim)
            else:
                rows = await self.db.get_leaderboard(self.guild.id, limit=lim)
        except TypeError:
            rows = await self.db.get_server_activity(self.guild.id, hours=hrs or 24 * 365)
            rows = rows[:lim]
        leaderboard = []
        for i, r in enumerate(rows, start=1):
            member = self._get_member(r["user_id"])
            leaderboard.append({
                "rank":          i,
                "display_name":  r.get("display_name") or (member.display_name if member else f"User {r['user_id']}"),
                "user_id":       str(r["user_id"]),
                "message_count": r["message_count"],
                "avatar_url":    _member_avatar_url(member),
            })
        return {"period": f"últimas {hrs}h" if hrs else "histórico total", "leaderboard": leaderboard}

    async def _do_list_bans(self, limit: int = 20, **_):
        bans = []
        async for ban_entry in self.guild.bans(limit=max(1, min(50, int(limit or 20)))):
            bans.append({"user_id": str(ban_entry.user.id),
                         "username": str(ban_entry.user), "reason": ban_entry.reason or ""})
        return {"count": len(bans), "bans": bans}

    async def _do_get_voice_members(self, channel_id: str = "", **_):
        if channel_id:
            cid      = _safe_int(channel_id)
            ch       = self.guild.get_channel(cid) if cid else None
            channels = [ch] if isinstance(ch, discord.VoiceChannel) else []
        else:
            channels = list(self.guild.voice_channels)
        result = []
        for vc in channels:
            members_info = [
                {"user_id": str(m.id), "display_name": m.display_name,
                 "muted":     m.voice.mute     or m.voice.self_mute   if m.voice else False,
                 "deafened":  m.voice.deaf     or m.voice.self_deaf   if m.voice else False,
                 "streaming": m.voice.self_stream                      if m.voice else False}
                for m in vc.members
            ]
            if members_info or channel_id:
                result.append({"channel_id": str(vc.id), "channel_name": vc.name,
                               "member_count": len(members_info), "members": members_info})
        return {"total_in_voice": sum(c["member_count"] for c in result), "channels": result}

    async def _do_list_emojis(self, **_):
        return {
            "count": len(self.guild.emojis),
            "emojis": [
                {"id": str(e.id), "name": e.name, "animated": e.animated,
                 "usage": f"<{'a' if e.animated else ''}:{e.name}:{e.id}>"}
                for e in self.guild.emojis
            ],
        }

    async def _do_get_active_threads(self, **_):
        threads = self.guild.threads
        return {
            "count": len(threads),
            "threads": [
                {"thread_id": str(t.id), "name": t.name, "channel_id": str(t.parent_id),
                 "member_count": t.member_count or 0, "message_count": t.message_count or 0,
                 "archived": t.archived,
                 "created_at": t.created_at.isoformat() if t.created_at else None}
                for t in threads
            ],
        }

    # ── ANÁLISIS E INTELIGENCIA ───────────────────────────────────────────

    async def _do_detect_newcomers(self, hours: int = 24, **_):
        hrs    = max(1, min(720, int(hours or 24)))
        cutoff = discord.utils.utcnow() - datetime.timedelta(hours=hrs)
        newcomers = sorted(
            [m for m in self.guild.members if m.joined_at and m.joined_at > cutoff],
            key=lambda m: m.joined_at, reverse=True,
        )
        return {
            "period_hours": hrs, "count": len(newcomers),
            "newcomers": [
                {"user_id": str(m.id), "username": str(m), "display_name": m.display_name,
                 "joined_at": m.joined_at.isoformat(),
                 "account_age_days": (discord.utils.utcnow() - m.created_at).days,
                 "is_new_account": (discord.utils.utcnow() - m.created_at).days < 7}
                for m in newcomers[:50]
            ],
        }

    async def _do_find_inactive_members(self, days: int = 30, limit: int = 50, **_):
        days  = max(1, int(days or 30))
        limit = max(1, min(200, int(limit or 50)))
        try:
            active_ids = set(await self.db.get_active_user_ids(self.guild.id, hours=days * 24))
        except (AttributeError, TypeError):
            rows       = await self.db.search_messages(guild_id=self.guild.id, hours=days * 24, limit=500)
            active_ids = {r["user_id"] for r in rows}
        inactive = [m for m in self.guild.members if not m.bot and m.id not in active_ids]
        return {
            "days": days, "total_inactive": len(inactive),
            "inactive_members": [
                {"user_id": str(m.id), "display_name": m.display_name,
                 "joined": m.joined_at.date().isoformat() if m.joined_at else "unknown"}
                for m in inactive[:limit]
            ],
        }

    async def _do_sentiment_snapshot(self, hours: int = 6, **_):
        hrs  = max(1, min(48, int(hours or 6)))
        rows = await self.db.search_messages(guild_id=self.guild.id, hours=hrs, limit=100)
        return {
            "period_hours": hrs, "message_count": len(rows),
            "sample": [r["content"] for r in rows if r.get("content")][:60],
            "instruction": (
                "Analiza los mensajes anteriores y describe: "
                "1) el tono general (positivo/negativo/neutro), "
                "2) temas predominantes, "
                "3) cualquier tensión o conflicto notable."
            ),
        }

    async def _do_compare_user_activity(self, user_id_1: str, user_id_2: str, hours: int = 168, **_):
        hrs  = max(1, min(720, int(hours or 168)))
        u1   = self._get_member(user_id_1)
        u2   = self._get_member(user_id_2)
        r1, r2 = await asyncio.gather(
            self.db.search_messages(guild_id=self.guild.id, user_id=_safe_int(user_id_1), hours=hrs, limit=50),
            self.db.search_messages(guild_id=self.guild.id, user_id=_safe_int(user_id_2), hours=hrs, limit=50),
        )
        return {
            "period_hours": hrs,
            "user_1": {"display_name": u1.display_name if u1 else user_id_1, "user_id": str(user_id_1),
                       "message_count": len(r1),
                       "sample": [m["content"][:60] for m in r1[:3] if m.get("content")]},
            "user_2": {"display_name": u2.display_name if u2 else user_id_2, "user_id": str(user_id_2),
                       "message_count": len(r2),
                       "sample": [m["content"][:60] for m in r2[:3] if m.get("content")]},
        }

    async def _do_get_peak_hours(self, **_):
        rows        = await self.db.search_messages(guild_id=self.guild.id, hours=24 * 30, limit=2000)
        hour_counts = [0] * 24
        for r in rows:
            try:
                ts   = r.get("timestamp", "")
                hour = (datetime.datetime.utcfromtimestamp(ts).hour
                        if isinstance(ts, (int, float))
                        else datetime.datetime.fromisoformat(str(ts)).hour)
                hour_counts[hour] += 1
            except (ValueError, TypeError, OSError):
                pass
        peak = sorted(range(24), key=lambda h: hour_counts[h], reverse=True)
        return {
            "analysis_days": 30,
            "peak_hours": [{"hour_utc": h, "label": f"{h:02d}:00 UTC",
                            "message_count": hour_counts[h]} for h in peak[:5]],
            "all_hours":  [{"hour_utc": h, "count": hour_counts[h]} for h in range(24)],
        }

    async def _do_filter_members(self, role_id: str = "", search_name: str = "",
                                 joined_after_hours: int = 0, joined_before_days: int = 0,
                                 is_online: bool = False, limit: int = 50, **_):
        """Filtra miembros del servidor por múltiples criterios combinables."""
        lim = max(1, min(200, int(limit or 50)))
        now = discord.utils.utcnow()
        members = list(self.guild.members)
        if role_id:
            role = self._get_role(role_id)
            if not role:
                return {"error": f"Rol {role_id} no encontrado."}
            members = [m for m in members if role in m.roles]
        if search_name:
            q = str(search_name).lower()
            members = [m for m in members if q in m.display_name.lower() or q in m.name.lower()]
        if joined_after_hours:
            cutoff = now - datetime.timedelta(hours=int(joined_after_hours))
            members = [m for m in members if m.joined_at and m.joined_at > cutoff]
        if joined_before_days:
            cutoff = now - datetime.timedelta(days=int(joined_before_days))
            members = [m for m in members if m.joined_at and m.joined_at < cutoff]
        if is_online:
            members = [m for m in members if m.status != discord.Status.offline]
        result = []
        for m in members[:lim]:
            result.append({
                "user_id":       str(m.id),
                "display_name":  m.display_name,
                "username":      str(m),
                "avatar_url":    _member_avatar_url(m),
                "joined_at":     m.joined_at.isoformat() if m.joined_at else None,
                "is_bot":        m.bot,
                "is_online":     str(m.status),
                "top_role":      m.top_role.name if m.top_role != self.guild.default_role else "@everyone",
                "role_count":    len(m.roles) - 1,
            })
        return {"total_matching": len(members), "showing": len(result), "members": result}

    async def _do_server_dashboard(self, **_):
        """Dashboard completo del servidor en una sola llamada."""
        g = self.guild
        now = discord.utils.utcnow()
        online = sum(1 for m in g.members if m.status != discord.Status.offline)
        joins_24h = sum(1 for m in g.members if m.joined_at and (now - m.joined_at).total_seconds() < 86400)
        top_roles = sorted(
            [r for r in g.roles if not r.is_default() and not r.managed],
            key=lambda r: len(r.members), reverse=True,
        )[:10]
        from collections import Counter
        ch_counter = Counter()
        recent = await self.db.search_messages(guild_id=g.id, hours=168, limit=500)
        for r in recent:
            ch_counter[r.get("channel_id", 0)] += 1
        top_channels = []
        for ch_id, count in ch_counter.most_common(5):
            ch = g.get_channel(ch_id)
            top_channels.append({"channel_id": str(ch_id),
                                 "name": ch.name if ch else f"#{ch_id}",
                                 "messages_7d": count})
        return {
            "server_name":      g.name,
            "guild_id":         str(g.id),
            "total_members":    g.member_count,
            "online_now":       online,
            "joins_last_24h":   joins_24h,
            "channels":         len(g.channels),
            "roles":            len(g.roles),
            "boost_level":      g.premium_tier,
            "created":          str(g.created_at.date()),
            "owner":            str(g.owner),
            "top_roles":        [{"role_id": str(r.id), "name": r.name,
                                   "members": len(r.members)} for r in top_roles],
            "top_channels_7d":  top_channels,
        }

    # ── UTILIDADES DE CONTENIDO ───────────────────────────────────────────

    async def _do_translate_message(self, message_id: str, target_language: str,
                                    channel_id: str = "", **_):
        ch = self._resolve_channel(channel_id)
        try:
            msg = await ch.fetch_message(int(message_id))
        except (discord.NotFound, discord.HTTPException):
            return {"error": f"Mensaje {message_id} no encontrado."}
        return {
            "message_content": msg.content, "author": str(msg.author),
            "channel": getattr(ch, "name", str(channel_id)),
            "target_language": target_language,
            "instruction": f"Traduce el mensaje anterior al {target_language} y responde con la traducción.",
        }

    async def _do_summarize_thread(self, thread_id: str, limit: int = 100, **_):
        tid    = _safe_int(thread_id)
        thread = self.guild.get_thread(tid) if tid else None
        if thread is None and tid:
            try:
                thread = await self.guild.fetch_channel(tid)
            except (discord.NotFound, discord.HTTPException):
                pass
        if not thread:
            return {"error": f"Hilo {thread_id} no encontrado."}
        if not isinstance(thread, discord.Thread):
            return {"error": f"El canal {thread_id} no es un hilo."}
        lim  = max(10, min(200, int(limit or 100)))
        msgs = [
            f"[{msg.author.display_name}]: {msg.content[:300]}"
            async for msg in thread.history(limit=lim, oldest_first=True)
            if msg.content
        ]
        return {
            "thread_name": thread.name, "thread_id": str(thread.id),
            "messages_read": len(msgs), "content": msgs,
            "instruction": "Resume el hilo anterior de forma clara y concisa.",
        }

    async def _do_generate_rules(self, **_):
        g = self.guild
        return {
            "server_name": g.name, "member_count": g.member_count,
            "channel_count": len(g.channels),
            "sample_channels": [{"name": ch.name, "type": str(ch.type)} for ch in g.channels[:20]],
            "roles": [r.name for r in g.roles[1:] if not r.managed][:15],
            "boost_level": g.premium_tier,
            "instruction": (
                "Genera unas reglas completas y bien estructuradas para este servidor de Discord. "
                "Incluye: respeto mutuo, spam, NSFW, autopromoción, uso de bots, spoilers, "
                "idioma principal, consecuencias por infracción y cualquier regla "
                "que parezca adecuada para el tipo de comunidad."
            ),
        }

    async def _do_schedule_message(self, channel_id: str, content: str, delay_minutes: int, **_):
        delay     = max(1, min(10080, int(delay_minutes or 60)))
        ch        = self._resolve_channel(channel_id)
        send_time = discord.utils.utcnow() + datetime.timedelta(minutes=delay)
        task_id   = f"sched_{self.guild.id}_{int(time.time() * 1000)}"

        async def _send_later() -> None:
            await asyncio.sleep(delay * 60)
            try:
                await ch.send(content)
                logger.info("schedule_message: ✅ enviado [%s]", task_id)
            except Exception as exc:
                logger.error("schedule_message: error enviando [%s]: %s", task_id, exc)
            finally:
                ToolExecutor._scheduled_tasks.pop(task_id, None)

        ToolExecutor._scheduled_tasks[task_id] = asyncio.create_task(_send_later())
        return {"success": True, "task_id": task_id,
                "channel": getattr(ch, "name", str(channel_id)),
                "send_at_utc": send_time.isoformat(), "delay_minutes": delay}

    async def _do_cancel_scheduled_message(self, task_id: str, **_):
        task = ToolExecutor._scheduled_tasks.get(task_id)
        if not task:
            return {"error": f"No hay mensaje programado con task_id '{task_id}'."}
        task.cancel()
        ToolExecutor._scheduled_tasks.pop(task_id, None)
        return {"success": True, "cancelled": task_id}

    async def _do_fetch_url_preview(self, url: str, channel_id: str = "", **_):
        # SEC-02 (Wave 2, F0.2): bloqueo SSRF antes de cualquier petición.
        from utils.security import is_url_safe
        ok, reason = is_url_safe(url)
        if not ok:
            logger.warning("fetch_url_preview bloqueado por SSRF guard: %s (%s)", url, reason)
            return {"error": f"URL bloqueada: {reason}"}
        try:
            import aiohttp
            from html.parser import HTMLParser

            class _OGParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.og: dict[str, str] = {}
                def handle_starttag(self, tag, attrs):
                    if tag != "meta":
                        return
                    d    = dict(attrs)
                    prop = d.get("property", d.get("name", ""))
                    cont = d.get("content", "")
                    if prop and cont:
                        self.og[prop] = cont

            # A2 (review): seguir redirects manualmente revalidando cada salto
            # con is_url_safe — allow_redirects=True permitía que un host público
            # redirigiera (302) a 127.0.0.1/169.254.169.254 evadiendo el guard.
            from urllib.parse import urljoin
            async with aiohttp.ClientSession() as session:
                current = url
                html = None
                for _hop in range(5):
                    async with session.get(current, timeout=aiohttp.ClientTimeout(total=10),
                                           headers={"User-Agent": "YoukaiBot/1.0 (Discord bot)"},
                                           allow_redirects=False) as resp:
                        if resp.status in (301, 302, 303, 307, 308):
                            loc = resp.headers.get("Location", "")
                            if not loc:
                                return {"error": "Redirect sin cabecera Location."}
                            current = urljoin(current, loc)
                            ok2, reason2 = is_url_safe(current)
                            if not ok2:
                                logger.warning("fetch_url_preview redirect bloqueado por SSRF: %s (%s)", current, reason2)
                                return {"error": f"Redirect a URL bloqueada: {reason2}"}
                            continue
                        if resp.status != 200:
                            return {"error": f"HTTP {resp.status} al acceder a la URL."}
                        html = await resp.text(errors="replace")
                        break
                if html is None:
                    return {"error": "Demasiados redirects."}

            parser = _OGParser()
            parser.feed(html[:60000])
            og       = parser.og
            og_title = og.get("og:title")       or og.get("title",       "")
            og_desc  = og.get("og:description") or og.get("description", "")
            og_image = og.get("og:image",   "")
            og_site  = og.get("og:site_name", "")
            if channel_id:
                ch    = self._resolve_channel(channel_id)
                embed = discord.Embed(title=og_title[:256] if og_title else url,
                                      description=og_desc[:4096] if og_desc else None,
                                      url=url, color=discord.Color(0x5865F2))
                if og_image: embed.set_image(url=og_image)
                if og_site:  embed.set_footer(text=og_site)
                msg = await ch.send(embed=embed)
                return {"success": True, "message_id": str(msg.id),
                        "title": og_title, "description": og_desc, "image": og_image}
            return {"title": og_title, "description": og_desc,
                    "image": og_image, "site_name": og_site, "url": url}
        except ImportError:
            return {"error": "aiohttp no está instalado. Ejecuta: pip install aiohttp"}
        except Exception as exc:
            return {"error": f"No se pudo obtener la URL: {exc}"}

    async def _do_weather(self, location: str, **_):
        # SEC-02 (Wave 2, F0.2): el `location` se interpola en la URL; validamos
        # la URL final para evitar abuso (e.g. location="@127.0.0.1/foo").
        weather_url = f"https://wttr.in/{location}?format=j1"
        from utils.security import is_url_safe
        ok, reason = is_url_safe(weather_url)
        if not ok:
            logger.warning("weather bloqueado por SSRF guard: %s (%s)", weather_url, reason)
            return {"error": f"location no válida: {reason}"}
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(weather_url,
                                       headers={"User-Agent": "YoukaiBot/1.0"},
                                       timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return {"error": f"Servicio de clima devolvió {resp.status}."}
                    data = await resp.json(content_type=None)
            c = data["current_condition"][0]
            w = data.get("weather", [{}])[0]
            return {
                "location": location, "temp_c": c.get("temp_C", "?"), "temp_f": c.get("temp_F", "?"),
                "feels_like_c": c.get("FeelsLikeC", "?"),
                "description":  c.get("weatherDesc", [{}])[0].get("value", "?"),
                "humidity_pct": c.get("humidity", "?"), "wind_kmph": c.get("windspeedKmph", "?"),
                "wind_dir":     c.get("winddir16Point", "?"), "uv_index": c.get("uvIndex", "?"),
                "max_c_today":  w.get("maxtempC", "?"), "min_c_today": w.get("mintempC", "?"),
            }
        except ImportError:
            return {"error": "aiohttp no está instalado. Ejecuta: pip install aiohttp"}
        except Exception as exc:
            return {"error": f"No se pudo obtener el clima: {exc}"}

    async def _do_time_in(self, timezone: str, **_):
        try:
            import aiohttp
            tz = timezone.strip().replace(" ", "_")
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://worldtimeapi.org/api/timezone/{tz}",
                                       timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 404:
                        return {"error": f"Zona horaria '{timezone}' no encontrada. "
                                         "Usa formato IANA como 'America/New_York'."}
                    if resp.status != 200:
                        return {"error": f"worldtimeapi devolvió {resp.status}."}
                    data = await resp.json()
            raw_dt     = data.get("datetime", "")
            dt_display = raw_dt[:19].replace("T", " ") if raw_dt else "?"
            days       = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
            dow        = data.get("day_of_week")
            return {
                "timezone":    data.get("timezone", tz), "datetime": dt_display,
                "utc_offset":  data.get("utc_offset", "?"),
                "day_of_week": days[int(dow)] if isinstance(dow, int) and 0 <= dow <= 6 else str(dow),
                "week_number": data.get("week_number", "?"),
                "dst_active":  data.get("dst", False),
            }
        except ImportError:
            return {"error": "aiohttp no está instalado. Ejecuta: pip install aiohttp"}
        except Exception as exc:
            return {"error": f"No se pudo obtener la hora: {exc}"}

    # ── GRÁFICOS ──────────────────────────────────────────────────────────

    async def _do_render_template(self, template: str, data: str,
                                  channel_id: str = "", filename: str = "", **_):
        """Renderiza un template SVG pre-construido con datos JSON → PNG."""
        ch = self._resolve_channel(channel_id)
        try:
            # FIX 5: Cache global de TemplateEngine
            global _TEMPLATE_ENGINE_CACHE
            if _TEMPLATE_ENGINE_CACHE is None:
                from utils.template_engine import TemplateEngine
                _TEMPLATE_ENGINE_CACHE = TemplateEngine()
            engine = _TEMPLATE_ENGINE_CACHE

            try:
                parsed = json.loads(data) if isinstance(data, str) else data
            except json.JSONDecodeError as e:
                return {"error": f"JSON inválido en data: {e}. Asegúrate de enviar JSON válido."}

            png_data = await engine.render_to_png(template, parsed)
            fn = (filename.strip() or f"{template}.png")
            if not fn.endswith(".png"):
                fn = fn.rsplit(".", 1)[0] + ".png"
            msg = await ch.send(file=discord.File(io.BytesIO(png_data), filename=fn))
            return {"success": True, "message_id": str(msg.id),
                    "format": "png", "filename": fn, "template": template,
                    "note": f"Renderizado con template '{template}' (~50ms)"}

        except ValueError as e:
            schema = engine.get_schema(template) if _TEMPLATE_ENGINE_CACHE else None
            schema_hint = ""
            if schema:
                req = schema.get("required", [])
                opt = schema.get("optional", [])
                schema_hint = (
                    f" | Schema: requires {req}"
                    + (f", optional {opt}" if opt else "")
                    + ". Provide ALL required fields as JSON keys."
                )
            return {"error": f"Template error: {e}{schema_hint}"}
        except Exception as exc:
            logger.warning("render_template falló: %s", exc)
            return {"error": f"Error renderizando template '{template}': {exc}"}

    # ── INTEGRACIÓN EXTERNA ───────────────────────────────────────────────

    async def _do_create_github_issue(self, title: str, body: str, repo: str = "",
                                      labels: str = "", **_):
        try:
            import aiohttp
        except ImportError:
            return {"error": "aiohttp no está instalado. Ejecuta: pip install aiohttp"}
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            return {"error": "GITHUB_TOKEN no está configurado en las variables de entorno."}
        repo = repo.strip() or os.environ.get("GITHUB_DEFAULT_REPO", "")
        if not repo:
            return {"error": "Repositorio no especificado. Usa 'owner/repo' o configura GITHUB_DEFAULT_REPO."}
        labels_list = [lbl.strip() for lbl in labels.split(",") if lbl.strip()] if labels else []
        payload     = {"title": title, "body": body}
        if labels_list:
            payload["labels"] = labels_list
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://api.github.com/repos/{repo}/issues",
                headers={"Authorization": f"token {token}",
                         "Accept": "application/vnd.github.v3+json",
                         "User-Agent": "YoukaiBot/1.0"},
                json=payload, timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                if resp.status == 201:
                    return {"success": True, "issue_number": data["number"],
                            "url": data["html_url"], "title": data["title"]}
                return {"error": f"GitHub API error {resp.status}: {data.get('message', 'Unknown error')}"}

    async def _do_edit_message(self, message_id: str, new_content: str,
                               channel_id: str = "", **_):
        """Edita un mensaje existente del bot."""
        ch = self._resolve_channel(channel_id or None)
        try:
            msg = await ch.fetch_message(int(message_id))
        except (discord.NotFound, discord.HTTPException):
            return {"error": f"Mensaje {message_id} no encontrado."}
        if msg.author.id != self.guild.me.id:
            return {"error": "Solo puedo editar mis propios mensajes."}
        await msg.edit(content=str(new_content))
        return {"success": True, "message_id": str(message_id),
                "channel": getattr(ch, "name", str(channel_id))}

    async def _do_create_reminder(self, user_id: str, text: str,
                                  delay_minutes: int = 60, **_):
        """Crea un recordatorio que enviará DM al usuario."""
        member, err = self._require_member(user_id)
        if err: return err
        delay = max(1, min(10080, int(delay_minutes or 60)))
        reminder_id = f"rem_{self.guild.id}_{member.id}_{int(time.time() * 1000)}"
        async def _send_reminder():
            await asyncio.sleep(delay * 60)
            try:
                await member.send(f"⏰ **Recordatorio:** {text}")
                logger.info("create_reminder: ✅ enviado [%s] a %s", reminder_id, member)
            except discord.Forbidden:
                logger.info("create_reminder: ❌ DMs cerrados para %s", member)
            except Exception as exc:
                logger.error("create_reminder: error [%s]: %s", reminder_id, exc)
        asyncio.create_task(_send_reminder())
        return {"success": True, "reminder_id": reminder_id,
                "user": str(member), "delay_minutes": delay,
                "text": text[:200],
                "note": f"Te enviaré un DM en {delay} minuto(s)."}

    async def _do_broadcast(self, role_id: str, content: str,
                            embed_title: str = "", **_):
        """Envía un mensaje por DM a todos los miembros de un rol."""
        role, err = self._require_role(role_id)
        if err: return err
        members = [m for m in role.members if not m.bot]
        if not members:
            return {"error": f"El rol '{role.name}' no tiene miembros (humanos)."}
        sem = asyncio.Semaphore(15)
        ok, failed = [], []
        async def _send_one(member):
            async with sem:
                try:
                    if embed_title:
                        embed = discord.Embed(
                            title=embed_title, description=content,
                            color=discord.Color(0xA855F7),
                        )
                        embed.set_footer(text=f"Anuncio de {self.guild.name}")
                        await member.send(embed=embed)
                    else:
                        await member.send(content)
                    ok.append(str(member))
                except discord.Forbidden:
                    failed.append(str(member))
        await asyncio.gather(*[_send_one(m) for m in members])
        return {"success": True, "role": role.name,
                "sent": len(ok), "failed": len(failed),
                "failed_dms_closed": failed[:5] if failed else []}

    # ── MISCÉLANEA ────────────────────────────────────────────────────────

    async def _do_set_nickname(self, user_id, nickname="", **_):
        member, err = self._require_member(user_id)
        if err: return err
        if member.id == self.guild.owner_id:
            return {"error": "Cannot change the server owner's nickname."}
        nick_value = nickname.strip() if nickname else None
        await member.edit(nick=nick_value)
        return {"success": True, "user": str(member),
                "new_nickname": nick_value or "(reset to username)"}

    async def _do_move_to_voice(self, user_id, channel_id, **_):
        member, err = self._require_member(user_id)
        if err: return err
        if not member.voice:
            return {"error": f"{member.display_name} is not in a voice channel."}
        cid = _safe_int(channel_id)
        ch  = self.guild.get_channel(cid) if cid else None
        if not ch or not isinstance(ch, discord.VoiceChannel):
            return {"error": f"Channel {channel_id} is not a valid voice channel."}
        await member.move_to(ch)
        return {"success": True, "user": str(member), "moved_to": ch.name}

    async def _do_create_poll(self, question, answers, channel_id=None,
                              duration_h=24, multiple=False, **_):
        ch   = self._resolve_channel(channel_id)
        opts = [a.strip() for a in str(answers).split(",") if a.strip()][:10]
        if len(opts) < 2:
            return {"error": "A poll requires at least 2 options."}
        poll = discord.Poll(
            question=str(question)[:300],
            duration=datetime.timedelta(hours=max(1, min(168, int(duration_h or 24)))),
            multiple=bool(multiple),
        )
        for opt in opts:
            poll.add_answer(text=opt)
        msg = await ch.send(poll=poll)
        return {"success": True, "message_id": str(msg.id), "options": opts}

    # ── EVENTOS ───────────────────────────────────────────────────────────

    async def _do_create_event(self, name: str, start_time: str, end_time: str = "",
                               description: str = "", voice_channel_id: str = "",
                               location: str = "", **_):
        try:
            start = datetime.datetime.fromisoformat(start_time)
            if start.tzinfo is None:
                start = start.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            return {"error": f"start_time inválido: '{start_time}'. Usa ISO 8601."}
        end = None
        if end_time:
            try:
                end = datetime.datetime.fromisoformat(end_time)
                if end.tzinfo is None:
                    end = end.replace(tzinfo=datetime.timezone.utc)
            except ValueError:
                return {"error": f"end_time inválido: '{end_time}'."}
        if voice_channel_id:
            cid = _safe_int(voice_channel_id)
            ch  = self.guild.get_channel(cid) if cid else None
            if not ch or not isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
                return {"error": f"Canal {voice_channel_id} no es canal de voz/escenario."}
            entity_type = (discord.EntityType.stage_instance
                           if isinstance(ch, discord.StageChannel) else discord.EntityType.voice)
            event = await self.guild.create_scheduled_event(
                name=name, start_time=start, end_time=end,
                description=description or None, channel=ch, entity_type=entity_type,
            )
        elif location:
            if not end:
                return {"error": "end_time es requerido para eventos externos."}
            event = await self.guild.create_scheduled_event(
                name=name, start_time=start, end_time=end, description=description or None,
                entity_type=discord.EntityType.external, location=location,
            )
        else:
            return {"error": "Proporciona voice_channel_id o location."}
        return {"success": True, "event_id": str(event.id), "event_name": event.name,
                "start_time": event.start_time.isoformat(),
                "url": f"https://discord.com/events/{self.guild.id}/{event.id}"}

    async def _do_delete_event(self, event_id: str, **_):
        eid = _safe_int(event_id)
        if eid is None:
            return {"error": "event_id inválido."}
        try:
            event = await self.guild.fetch_scheduled_event(eid)
        except discord.NotFound:
            return {"error": f"Evento {event_id} no encontrado."}
        name = event.name
        await event.delete()
        return {"success": True, "deleted_event": name, "event_id": str(event_id)}

    async def _do_list_events(self, **_):
        events = await self.guild.fetch_scheduled_events()
        return {
            "count": len(events),
            "events": [
                {"event_id": str(e.id), "name": e.name,
                 "start_time": e.start_time.isoformat(),
                 "end_time": e.end_time.isoformat() if e.end_time else None,
                 "status": str(e.status), "interested": e.subscriber_count or 0,
                 "description": e.description or ""}
                for e in events
            ],
        }

    # ── INVITACIONES ──────────────────────────────────────────────────────

    async def _do_create_invite(self, channel_id: str = "", max_age: int = 86400,
                                max_uses: int = 0, temporary: bool = False, **_):
        ch = self._resolve_channel(channel_id)
        if not isinstance(ch, (discord.TextChannel, discord.VoiceChannel, discord.StageChannel)):
            return {"error": "No se puede crear una invitación para este tipo de canal."}
        invite = await ch.create_invite(max_age=max(0, int(max_age or 86400)),
                                        max_uses=max(0, int(max_uses or 0)),
                                        temporary=bool(temporary))
        return {"success": True, "invite_url": invite.url, "channel": ch.name,
                "max_age": invite.max_age, "max_uses": invite.max_uses,
                "temporary": bool(temporary)}

    # ── AUDITORÍA ─────────────────────────────────────────────────────────

    _AUDIT_ACTION_MAP: dict[str, discord.AuditLogAction] = {
        "ban":            discord.AuditLogAction.ban,
        "unban":          discord.AuditLogAction.unban,
        "kick":           discord.AuditLogAction.kick,
        "role_update":    discord.AuditLogAction.role_update,
        "role_create":    discord.AuditLogAction.role_create,
        "role_delete":    discord.AuditLogAction.role_delete,
        "channel_create": discord.AuditLogAction.channel_create,
        "channel_delete": discord.AuditLogAction.channel_delete,
        "member_update":  discord.AuditLogAction.member_update,
        "message_delete": discord.AuditLogAction.message_delete,
        "invite_create":  discord.AuditLogAction.invite_create,
    }

    async def _do_get_audit_log(self, limit: int = 10, action: str = "", **_):
        lim    = max(1, min(25, int(limit or 10)))
        kwargs: dict = {"limit": lim}
        if action:
            resolved = self._AUDIT_ACTION_MAP.get(action.lower())
            if resolved is None:
                return {"error": f"Acción '{action}' no reconocida. Opciones: {', '.join(self._AUDIT_ACTION_MAP)}."}
            kwargs["action"] = resolved
        entries = [
            {"action": entry.action.name, "user": str(entry.user),
             "target": str(entry.target) if entry.target else None,
             "reason": entry.reason or "", "timestamp": entry.created_at.isoformat()}
            async for entry in self.guild.audit_logs(**kwargs)
        ]
        return {"count": len(entries), "entries": entries}

    # ── SKILLS ────────────────────────────────────────────────────────────

    async def _do_read_skill(self, skill_name: str = "list", **_):
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "", skill_name.strip())
        if not safe_name or safe_name == "list":
            try:
                files = sorted(f.replace(".md", "") for f in os.listdir(SKILLS_DIR)
                               if f.endswith(".md") and not f.startswith("_"))
            except OSError:
                files = []
            return {"available_skills": files, "usage": "read_skill(skill_name='nombre')"}
        skill_path = os.path.join(SKILLS_DIR, f"{safe_name}.md")
        if not os.path.isfile(skill_path):
            try:
                available = [f.replace(".md", "") for f in os.listdir(SKILLS_DIR) if f.endswith(".md")]
            except OSError:
                available = []
            return {"error": f"Skill '{safe_name}' no encontrada.", "available_skills": available}
        try:
            with open(skill_path, "r", encoding="utf-8") as fh:
                content = fh.read()
            return {"skill": safe_name, "content": content}
        except OSError as exc:
            return {"error": f"No se pudo leer la skill: {exc}"}

    # ── LISTENERS ─────────────────────────────────────────────────────────

    async def _do_create_listener(self, rule_json: str, description: str = "", **_):
        import uuid
        try:
            rule = json.loads(rule_json)
        except json.JSONDecodeError:
            # Reparar JSON malformado del LLM
            try:
                from json_repair import loads as jr_loads
                rule = jr_loads(rule_json)
                if not isinstance(rule, dict):
                    return {"error": "rule_json reparado no es un objeto JSON válido."}
            except Exception as exc:
                return {"error": f"rule_json no es JSON válido (incluso tras reparación): {exc}"}

        # ── Normalización de schema (corrige patrones comunes del LLM) ──
        rule = self._normalize_listener_schema(rule)

        # ── Validación de schema ──────────────────────────────────────
        errors = self._validate_listener_schema(rule)
        if errors:
            return {"error": "Schema inválido", "issues": errors}

        # ── Auto-resolución de IDs (nombres → IDs reales) ────────────
        rule = self._resolve_listener_ids(rule)

        # ── Public mode restrictions ─────────────────────────────────
        if getattr(self, 'public_mode', False):
            # Charge 1000cr to create a rule
            if self.public_user_id:
                info = await self.db.get_credits(self.public_user_id, self.guild.id)
                if info["balance"] < 1000:
                    return {"error": f"Crear una regla cuesta 1,000 créditos. Tu saldo: {info['balance']}."}
                # Max 1 active rule — delete existing if any
                all_rules = await self.db.get_listeners(self.guild.id)
                user_rules = [r for r in all_rules if r.get("created_by") == self.public_user_id and r.get("enabled")]
                for old in user_rules:
                    await self.db.delete_listener(self.guild.id, old["id"])
                    try:
                        await self._bot_ref.notify_listener_change('unload', self.guild.id, rule_id=old["id"])
                    except Exception:
                        pass
                rule["created_by"] = self.public_user_id
            # Force 6h cooldown minimum
            limits = rule.setdefault("limits", {})
            limits["cooldown_seconds"] = max(limits.get("cooldown_seconds", 0), 21600)
            # Block destructive actions
            _BLOCKED = {"ban_user", "kick_user", "mute_user", "delete_message",
                        "purge_messages", "warn_user", "seal_user", "remove_role", "assign_role"}
            actions = rule.get("actions", [])
            for act in actions:
                if act.get("type") in _BLOCKED:
                    return {"error": f"Acción '{act['type']}' no permitida para usuarios públicos."}
            # Deduct 1000cr (refund the 300cr call cost so total is 1000, not 1300)
            if self.public_user_id:
                await self.db.spend_credits(self.public_user_id, self.guild.id, 700, reason="shop")

        if not rule.get("id"):
            rule["id"] = f"rule_{uuid.uuid4().hex[:8]}"
        rule.setdefault("guild_id", str(self.guild.id))
        rule.setdefault("enabled", True)
        rule.setdefault("created_at", datetime.datetime.utcnow().isoformat())
        if description:
            rule["description"] = description
        await self.db.save_listener(self.guild.id, rule)
        try:
            await self._bot_ref.notify_listener_change('load', self.guild.id, rule=rule)
        except Exception:
            pass
        return {"success": True, "rule_id": rule["id"], "name": rule.get("name", ""),
                "status": "Protocolo vinculado. La llave ha girado."}

    def _normalize_listener_schema(self, rule: dict) -> dict:
        """Corrige patrones comunes que el LLM genera mal."""
        # trigger.user_id → trigger.filters.only_user_ids
        trigger = rule.get("trigger", {})
        if isinstance(trigger, dict):
            uid = trigger.pop("user_id", None) or trigger.pop("user_ids", None)
            if uid:
                filters = trigger.setdefault("filters", {})
                if isinstance(uid, str):
                    uid = [uid]
                filters.setdefault("only_user_ids", uid)
            # Asegurar ignore_bots por defecto
            filters = trigger.setdefault("filters", {})
            filters.setdefault("ignore_bots", True)

        # cooldown (top-level) → limits.cooldown_seconds
        cd = rule.pop("cooldown", None) or rule.pop("cooldown_seconds", None)
        if cd:
            limits = rule.setdefault("limits", {})
            limits.setdefault("cooldown_seconds", int(cd))

        # actions[].content → actions[].text
        for action in rule.get("actions", []):
            # Skip impersonate: en esa acción `content` es el template literal.
            if isinstance(action, dict) and action.get("type") == "impersonate":
                continue
            if isinstance(action, dict) and "content" in action and "text" not in action:
                action["text"] = action.pop("content")
            # actions[].message → actions[].text
            if isinstance(action, dict) and "message" in action and "text" not in action:
                action["text"] = action.pop("message")
            # Normalizar action type aliases
            if isinstance(action, dict):
                # Aplanar params: {type: X, params: {content: Y}} → {type: X, text: Y}
                params = action.pop("params", None)
                if isinstance(params, dict):
                    for k, v in params.items():
                        action.setdefault(k, v)
                _ACTION_ALIASES = {
                    "send_dm": "dm_user", "send_message": "reply_text",
                    "reply": "reply_text", "respond": "reply_text",
                    "timeout": "mute_user", "mute": "mute_user",
                    "ban": "ban_user", "kick": "kick_user",
                    "warn": "warn_user", "delete": "delete_message",
                    "react": "add_reaction", "pin": "pin_message",
                }
                atype = action.get("type", "")
                if atype in _ACTION_ALIASES:
                    action["type"] = _ACTION_ALIASES[atype]

        return rule

    def _validate_listener_schema(self, rule: dict) -> list:
        """Valida estructura mínima de una regla. Retorna lista de errores."""
        errors = []
        # Trigger
        trigger = rule.get("trigger")
        if not isinstance(trigger, dict):
            # Auto-fix: asumir on_message si falta
            rule["trigger"] = {"type": "on_message", "filters": {"ignore_bots": True}}
            trigger = rule["trigger"]
        else:
            valid_triggers = {"on_message", "on_join", "on_leave", "on_schedule",
                              "on_reaction_add", "on_voice_join", "on_voice_leave", "on_member_update"}
            if trigger.get("type") not in valid_triggers:
                errors.append(f"trigger.type inválido: '{trigger.get('type')}'. Válidos: {valid_triggers}")

        # Condition
        cond = rule.get("condition")
        if not isinstance(cond, dict):
            # Auto-fix: si no hay condition, asumir "none" (siempre se activa)
            rule["condition"] = {"type": "none"}
            cond = rule["condition"]
        else:
            # Alias: "always" → "none"
            if cond.get("type") in ("always", "all", "any"):
                cond["type"] = "none"
            valid_conds = {"none", "exact", "contains", "starts_with", "ends_with",
                           "regex", "scored", "rate", "semantic"}
            if cond.get("type") not in valid_conds:
                errors.append(f"condition.type inválido: '{cond.get('type')}'. Válidos: {valid_conds}")
            # Validar que conditions con valores los tengan
            if cond.get("type") in ("exact", "contains", "starts_with", "ends_with"):
                if not cond.get("values"):
                    errors.append(f"condition type '{cond['type']}' requiere 'values' (array de strings)")
            if cond.get("type") == "regex":
                if not cond.get("patterns"):
                    errors.append("condition type 'regex' requiere 'patterns' (array de regex)")
                else:
                    for p in cond.get("patterns", []):
                        try:
                            re.compile(p)
                        except re.error as e:
                            errors.append(f"regex inválido '{p}': {e}")
            if cond.get("type") == "scored":
                if not cond.get("scoring_rules"):
                    errors.append("condition type 'scored' requiere 'scoring_rules'")
            if cond.get("type") == "rate":
                if not cond.get("max_count"):
                    errors.append("condition type 'rate' requiere 'max_count'")

        # Actions
        actions = rule.get("actions")
        # Auto-fix: si es un dict suelto, envolverlo en array
        if isinstance(actions, dict):
            actions = [actions]
            rule["actions"] = actions
        if not isinstance(actions, list) or not actions:
            errors.append("'actions' debe ser un array no vacío")
        else:
            from cogs.listeners import ActionDispatcher
            for i, a in enumerate(actions):
                if not isinstance(a, dict):
                    errors.append(f"actions[{i}] debe ser un dict")
                elif a.get("type") not in ActionDispatcher.ALLOWED_ACTION_TYPES:
                    errors.append(f"actions[{i}].type '{a.get('type')}' no es válido. Válidos: {sorted(ActionDispatcher.ALLOWED_ACTION_TYPES)}")

        return errors

    def _resolve_listener_ids(self, rule: dict) -> dict:
        """Resuelve nombres de canales/roles a IDs reales usando fuzzy match."""
        import unicodedata

        def _norm(s: str) -> str:
            s = unicodedata.normalize("NFKD", s)
            return "".join(c for c in s if unicodedata.category(c)[0] in ("L", "N", "Z")).lower().strip()

        def _resolve_channel(val) -> str:
            """Si val no es un ID numérico, buscar por nombre."""
            s = str(val).strip().lstrip("#")
            if s.isdigit() and len(s) > 10:
                return s  # ya es ID
            norm_val = _norm(s)
            for ch in self.guild.text_channels:
                if _norm(ch.name) == norm_val or str(ch.id) == s:
                    return str(ch.id)
            # Fuzzy: partial match
            for ch in self.guild.text_channels:
                if norm_val in _norm(ch.name) or _norm(ch.name) in norm_val:
                    return str(ch.id)
            return s  # devolver original si no se resuelve

        def _resolve_role(val) -> str:
            s = str(val).strip().lstrip("@")
            if s.isdigit() and len(s) > 10:
                return s
            norm_val = _norm(s)
            for role in self.guild.roles:
                if _norm(role.name) == norm_val or str(role.id) == s:
                    return str(role.id)
            for role in self.guild.roles:
                if norm_val in _norm(role.name) or _norm(role.name) in norm_val:
                    return str(role.id)
            return s

        # Resolver en trigger.filters
        trigger = rule.get("trigger", {})
        if isinstance(trigger, dict):
            filters = trigger.get("filters", {})
            if isinstance(filters, dict):
                for key in ("channel_ids", "ignore_channel_ids"):
                    if key in filters and isinstance(filters[key], list):
                        filters[key] = [_resolve_channel(v) for v in filters[key]]
                for key in ("only_role_ids", "ignore_role_ids"):
                    if key in filters and isinstance(filters[key], list):
                        filters[key] = [_resolve_role(v) for v in filters[key]]

        # Resolver en actions
        for action in rule.get("actions", []):
            if isinstance(action, dict):
                if "channel_id" in action:
                    action["channel_id"] = _resolve_channel(action["channel_id"])
                if "role_id" in action:
                    action["role_id"] = _resolve_role(action["role_id"])

        return rule

    async def _do_list_listeners(self, filter: str = "all", trigger_type: str = "",
                                  search: str = "", limit: int = 25, offset: int = 0,
                                  verbose: bool = False, **_):
        """Lista reglas automáticas con búsqueda, paginación y modo light/verbose.

        Parámetros:
            filter: 'all'/'active'/'inactive' — filtra por estado.
            trigger_type: filtra por tipo de trigger (opcional).
            search: substring (case-insensitive) sobre nombre o rule_id. Si se
                    provee, ignora la paginación y devuelve TODOS los matches
                    en formato verbose (asume que es búsqueda dirigida).
            limit: máximo de reglas a devolver (default 25).
            offset: desde dónde empezar (default 0).
            verbose: si True, incluye trigger/condition/actions completas;
                     si False (default), solo rule_id + name + enabled +
                     trigger_type — versión liviana para no truncar con 20+ reglas.

        Devuelve `total` (cuántas reglas matchean filtros antes de paginar) y
        `showing` (cuántas devolvió). Si `total > showing`, hay más — el LLM
        debe ajustar offset/search para encontrarlas.
        """
        # FIX (2026-05-16): _safe_get debe estar definida ANTES del primer uso.
        # Antes la def aparecía DESPUÉS del filtro por trigger_type, causando
        # NameError si se invocaba con trigger_type != "".
        def _safe_get(obj, key, default="?"):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return default

        rules = await self.db.get_listeners(self.guild.id)
        if filter == "active":
            rules = [r for r in rules if r.get("enabled")]
        elif filter == "inactive":
            rules = [r for r in rules if not r.get("enabled")]
        if trigger_type:
            rules = [r for r in rules if _safe_get(r.get("trigger"), "type", "") == trigger_type]

        # Búsqueda por substring en nombre o rule_id.
        search_clean = (search or "").strip().lower()
        if search_clean:
            rules = [r for r in rules
                     if search_clean in (r.get("name") or "").lower()
                     or search_clean in (r.get("id") or "").lower()]
            # Búsqueda dirigida: devuelve TODO en verbose, sin paginar
            verbose = True
            limit = max(limit, len(rules)) or 1
            offset = 0

        total = len(rules)

        # Sanitizar paginación
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(100, int(limit or 25)))
        except (ValueError, TypeError):
            offset, limit = 0, 25

        page = rules[offset:offset + limit]

        if verbose:
            payload = [
                {"rule_id":        r.get("id"),
                 "name":           r.get("name", ""),
                 "enabled":        r.get("enabled", True),
                 "trigger":        _safe_get(r.get("trigger"), "type", "?"),
                 "condition_type": _safe_get(r.get("condition"), "type", "?"),
                 "actions":        [a.get("type") if isinstance(a, dict) else str(a)
                                    for a in (r.get("actions") if isinstance(r.get("actions"), list) else [])],
                 "trigger_count":  r.get("trigger_count", 0),
                 "last_triggered": r.get("last_triggered")}
                for r in page
            ]
        else:
            # Modo light: solo lo esencial. Cabe ~80 reglas en 4000 chars.
            payload = [
                {"rule_id":      r.get("id"),
                 "name":         r.get("name", ""),
                 "enabled":      r.get("enabled", True),
                 "trigger_type": _safe_get(r.get("trigger"), "type", "?")}
                for r in page
            ]

        result = {
            "total":   total,
            "showing": len(page),
            "rules":   payload,
        }
        if total > len(page):
            result["more_available"] = True
            result["hint"] = (
                f"Mostrando {len(page)} de {total}. "
                f"Para ver más usá offset={offset + limit} o search='nombre' para "
                f"filtrar por nombre directamente."
            )
        return result

    async def _do_toggle_listener(self, rule_id: str, enabled: bool, **_):
        existed = await self.db.toggle_listener(self.guild.id, rule_id, bool(enabled))
        if not existed:
            return {"error": f"Regla '{rule_id}' no encontrada."}
        try:
            await self._bot_ref.notify_listener_change('toggle', self.guild.id, rule_id=rule_id, enabled=bool(enabled))
        except Exception:
            pass
        return {"success": True, "rule_id": rule_id, "enabled": bool(enabled),
                "status": "Sello alterado." if enabled else "Protocolo suspendido."}

    async def _do_delete_listener(self, rule_id: str, **_):
        existed = await self.db.delete_listener(self.guild.id, rule_id)
        if not existed:
            return {"error": f"Regla '{rule_id}' no encontrada."}
        try:
            await self._bot_ref.notify_listener_change('unload', self.guild.id, rule_id=rule_id)
        except Exception:
            pass
        return {"success": True, "deleted": rule_id,
                "status": "Inscripción borrada. Como si nunca existiera."}

    async def _do_edit_listener(self, rule_id: str, patch_json: str, **_):
        try:
            patch = json.loads(patch_json)
        except json.JSONDecodeError:
            try:
                from json_repair import loads as jr_loads
                patch = jr_loads(patch_json)
                if not isinstance(patch, dict):
                    return {"error": "patch_json reparado no es un objeto JSON válido."}
            except Exception as exc:
                return {"error": f"patch_json no es JSON válido (incluso tras reparación): {exc}"}
        ok = await self.db.patch_listener(self.guild.id, rule_id, patch)
        if not ok:
            return {"error": f"Regla '{rule_id}' no encontrada."}
        try:
            rule = await self.db.get_listener(self.guild.id, rule_id)
            if rule:
                await self._bot_ref.notify_listener_change('load', self.guild.id, rule=rule)
        except Exception:
            pass
        return {"success": True, "rule_id": rule_id, "patched_fields": list(patch.keys()),
                "status": "Protocolo reescrito."}

    async def _do_test_listener(self, rule_id: str, test_text: str, **_):
        rule = await self.db.get_listener(self.guild.id, rule_id)
        if not rule:
            return {"error": f"Regla '{rule_id}' no encontrada."}
        import re as _re
        raw_cond = rule.get("condition", {"type": "none"})
        cond = raw_cond if isinstance(raw_cond, dict) else {"type": "none"}
        t    = cond.get("type", "none")
        cs   = cond.get("case_sensitive", False)
        txt  = test_text if cs else test_text.lower()
        matched, score, patterns = False, 0.0, []
        if t == "none":
            matched = True
        elif t in ("exact", "contains", "starts_with", "ends_with"):
            for v in cond.get("values", []):
                needle = v if cs else v.lower()
                hit = (
                    (t == "exact"       and txt == needle)          or
                    (t == "contains"    and needle in txt)          or
                    (t == "starts_with" and txt.startswith(needle)) or
                    (t == "ends_with"   and txt.endswith(needle))
                )
                if hit:
                    matched = True; patterns.append(v); break
        elif t == "regex":
            flags = 0 if cs else _re.IGNORECASE
            for p in cond.get("patterns", []):
                if _re.search(p, test_text, flags):
                    matched = True; patterns.append(p); break
        elif t == "scored":
            if cond.get("require_subject"):
                if not any(_re.search(p, test_text, _re.IGNORECASE)
                           for p in cond.get("subject_patterns", [])):
                    return {"would_trigger": False, "score": 0.0,
                            "reason": "Sujeto no encontrado",
                            "actions_that_would_run": []}
            for sr in cond.get("scoring_rules", []):
                if _re.search(sr["pattern"], test_text, _re.IGNORECASE):
                    score += sr["weight"]; patterns.append(sr["pattern"])
            matched = score >= cond.get("score_threshold", 3.0)
        elif t == "rate":
            return {"would_trigger": "N/A (rate depende del historial en tiempo real)",
                    "condition_type": "rate"}
        return {
            "would_trigger":          matched,
            "score":                  round(score, 2),
            "matched_patterns":       patterns,
            "actions_that_would_run": [a.get("type") if isinstance(a, dict) else str(a)
                                        for a in rule.get("actions") if isinstance(rule.get("actions"), list)],
        }

    async def _do_get_listener_stats(self, rule_id: str, hours: int = 24, **_):
        return await self.db.get_listener_stats(
            self.guild.id, rule_id, hours=max(1, min(168, int(hours or 24))))

    # ── SELLO ─────────────────────────────────────────────────────────────

    # FIX 6: Race condition en seal_user — transacción atómica de roles
    async def _do_seal_user(self, user_id: str, duration: str = "1h",
                            reason: str = "", mod_channel_id: str = "", **_):
        # Public mode: can only seal yourself
        if self.public_mode:
            uid = _safe_int(user_id)
            if uid != self.public_user_id:
                return {"error": "En modo público solo puedes sellarte a ti mismo."}
        # Orphan cleanup
        for msg_key in list(ToolExecutor._seal_mod_messages):
            parts = msg_key.split(":", 1)
            if len(parts) == 2 and parts[0] == str(self.guild.id):
                sealed_uid = ToolExecutor._seal_mod_messages[msg_key]
                corresponding_seal_key = f"seal_{self.guild.id}_{sealed_uid}"
                if corresponding_seal_key not in ToolExecutor._seal_tasks:
                    ToolExecutor._seal_mod_messages.pop(msg_key, None)

        member, err = self._require_member(user_id)
        if err: return err
        if member.bot:
            return {"error": "No se puede sellar a un bot."}
        if member.id == self.guild.owner_id:
            return {"error": "No se puede sellar al dueño del servidor."}

        reason_text = reason.strip() or "Sellado por Fairy"
        td, err = self._require_duration(str(duration or "1h"))
        if err: return err
        release_at = discord.utils.utcnow() + td
        mod_roles  = self._mod_roles()

        # FIX 6: Guardar roles originales ANTES de cualquier modificación
        original_role_ids = [
            r.id for r in member.roles
            if r != self.guild.default_role and not r.managed
        ]

        # FIX 6: Crear rol sellado PRIMERO (antes de quitar roles)
        # Así si algo falla, el usuario no queda sin roles
        sealed_role = await self.guild.create_role(
            name="🔒 Sellado", permissions=discord.Permissions.none(),
            color=discord.Color(0x808080), reason=f"Seal: {reason_text}",
        )

        # Overwrites del canal sellado
        overwrites: dict = {
            self.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            sealed_role: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                attach_files=False, embed_links=False, use_external_emojis=False,
            ),
            self.guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True,
                manage_messages=True, read_message_history=True,
            ),
        }
        for mr in mod_roles:
            overwrites[mr] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True, manage_messages=True,
            )

        # Crear canal sellado
        safe_uname   = re.sub(r"[^a-z0-9\-]", "", member.name.lower())[:20] or "user"
        seal_channel = await self.guild.create_text_channel(
            name=f"🔒sellado-{safe_uname}", overwrites=overwrites,
            reason=f"Canal de sello para {member}",
        )

        # FIX 6: Ahora sí — quitar roles originales y asignar sellado en una operación
        roles_to_remove = [r for rid in original_role_ids if (r := self._get_role(rid))]
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove, reason=f"Seal: {reason_text}")
            except discord.HTTPException as exc:
                logger.warning("seal: error quitando roles de %s: %s", member, exc)
                # Continuar de todos modos — el rol sellado ya existe

        await member.add_roles(sealed_role, reason=f"Seal: {reason_text}")

        # Denegar view_channel en todos los demás canales
        channels_to_deny = [
            ch for ch in self.guild.channels
            if ch.id != seal_channel.id and not isinstance(ch, discord.CategoryChannel)
        ]
        denied_ok, denied_fail = await self._batch_set_permissions(
            channels_to_deny, sealed_role, view_channel=False,
            reason="Seal: ocultar canales al rol sellado",
        )
        logger.info("seal: %d canales denegados, %d fallidos para %s", denied_ok, denied_fail, member)

        # Guardar en DB
        await self.db.store_seal(
            guild_id=self.guild.id, user_id=member.id, sealed_role_id=sealed_role.id,
            seal_channel_id=seal_channel.id, original_role_ids=original_role_ids,
            release_at=release_at.isoformat(), reason=reason_text,
        )

        # Mensaje en canal sellado
        await seal_channel.send(
            f"🔒 **{member.mention}** — has sido sellado temporalmente.\n"
            f"**Razón:** {reason_text}\n"
            f"**Liberación automática:** <t:{int(release_at.timestamp())}:R>\n\n"
            f"Solo los moderadores y tú podéis ver este canal.\n"
            f"Puedes escribir aquí si quieres comunicarte con el equipo de moderación."
        )

        # Embed para mods
        mod_ch = self._resolve_channel(mod_channel_id or None)
        embed  = discord.Embed(
            title=f"🔒 Usuario Sellado",
            description=f"{member.mention} (`{member.id}`) ha sido sellado.",
            color=discord.Color(0xFF6B35), timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=_member_avatar_url(member))
        embed.add_field(name="Razón",           value=reason_text,                            inline=False)
        embed.add_field(name="Canal sellado",   value=seal_channel.mention,                   inline=True)
        embed.add_field(name="Liberación auto", value=f"<t:{int(release_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Duración",        value=str(duration or "1h"),                  inline=True)
        embed.add_field(name="Roles guardados", value=str(len(original_role_ids)),             inline=True)
        embed.set_footer(text="✅ Reacciona para liberar  •  🔒 Para mantener el sello")

        mod_msg = await mod_ch.send(embed=embed)
        await asyncio.gather(mod_msg.add_reaction("✅"), mod_msg.add_reaction("🔒"))

        # Tracking
        tracking_key = f"{self.guild.id}:{mod_msg.id}"
        ToolExecutor._seal_mod_messages[tracking_key] = member.id
        try:
            await self.db.update_seal_mod_message(
                guild_id=self.guild.id, user_id=member.id,
                mod_message_id=mod_msg.id, mod_channel_id=mod_ch.id if hasattr(mod_ch, "id") else 0,
            )
        except AttributeError:
            pass

        # Auto-liberación
        seal_key = f"seal_{self.guild.id}_{member.id}"

        async def _auto_release() -> None:
            await asyncio.sleep(td.total_seconds())
            try:
                await self._release_seal(
                    user_id=member.id, original_role_ids=original_role_ids,
                    sealed_role_id=sealed_role.id, seal_channel_id=seal_channel.id,
                )
                ToolExecutor._seal_mod_messages.pop(tracking_key, None)
                logger.info("seal: auto-liberado %s (%s)", member, member.id)
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.error("seal: error en auto-liberacion de %s: %s", member.id, exc)
            finally:
                ToolExecutor._seal_tasks.pop(seal_key, None)
                ToolExecutor._seal_mod_messages.pop(tracking_key, None)

        if seal_key in ToolExecutor._seal_tasks:
            ToolExecutor._seal_tasks[seal_key].cancel()
        ToolExecutor._seal_tasks[seal_key] = asyncio.create_task(_auto_release())

        return {
            "success":         True,
            "sealed_user":     str(member),
            "user_id":         str(member.id),
            "seal_channel":    seal_channel.name,
            "seal_channel_id": str(seal_channel.id),
            "sealed_role_id":  str(sealed_role.id),
            "release_at":      release_at.isoformat(),
            "mod_message_id":  str(mod_msg.id),
            "roles_saved":     len(original_role_ids),
            "channels_denied": denied_ok,
        }

    async def _do_unseal_user(self, user_id: str, **_):
        uid = _safe_int(user_id)
        if uid is None:
            return {"error": "user_id inválido."}
        seal_key = f"seal_{self.guild.id}_{uid}"
        if seal_key in ToolExecutor._seal_tasks:
            ToolExecutor._seal_tasks.pop(seal_key).cancel()
        try:
            seal_data = await self.db.get_seal(self.guild.id, uid)
        except AttributeError:
            seal_data = None
        if seal_data:
            await self._release_seal(
                user_id=uid,
                original_role_ids=seal_data.get("original_role_ids", []),
                sealed_role_id=seal_data.get("sealed_role_id"),
                seal_channel_id=seal_data.get("seal_channel_id"),
            )
            mod_msg_id = seal_data.get("mod_message_id")
            if mod_msg_id:
                ToolExecutor._seal_mod_messages.pop(f"{self.guild.id}:{mod_msg_id}", None)
            member = self._get_member(uid)
            return {"success": True, "unsealed": str(member) if member else f"User {uid}",
                    "user_id": str(uid)}
        # Fallback
        member = self._get_member(uid)
        if not member:
            return {"error": f"Member {uid} not found. No seal data in DB either."}
        sealed_role = discord.utils.get(member.roles, name="🔒 Sellado")
        if not sealed_role:
            return {"error": f"{member.display_name} no parece estar sellado actualmente."}
        await member.remove_roles(sealed_role, reason="Unseal manual")
        try:
            await sealed_role.delete(reason="Unseal: limpieza de rol sellado")
        except (discord.Forbidden, discord.HTTPException):
            pass
        return {"success": True, "unsealed": str(member),
                "warning": "No había datos en DB; solo se quitó el rol sellado. "
                           "Los roles originales NO fueron restaurados."}

    async def _do_list_sealed_users(self, **_):
        try:
            rows = await self.db.fetch(
                "SELECT user_id, reason, release_at, seal_channel_id FROM user_seals WHERE guild_id=?",
                (self.guild.id,)
            )
        except Exception:
            rows = []
        if not rows:
            return {"sealed_users": [], "total": 0, "message": "No hay usuarios sellados actualmente."}
        result = []
        for row in rows:
            uid = row["user_id"] if isinstance(row, dict) else row[0]
            reason = row["reason"] if isinstance(row, dict) else row[1]
            release = row["release_at"] if isinstance(row, dict) else row[2]
            ch_id = row["seal_channel_id"] if isinstance(row, dict) else row[3]
            member = self._get_member(int(uid)) if uid else None
            result.append({
                "user": member.display_name if member else f"ID:{uid}",
                "user_id": str(uid),
                "reason": reason or "Sin razón",
                "release_at": release or "indefinido",
                "channel_id": str(ch_id) if ch_id else None,
            })
        return {"sealed_users": result, "total": len(result)}

    async def _release_seal(self, user_id: int, original_role_ids: list,
                            sealed_role_id: Any, seal_channel_id: Any) -> None:
        member      = self._get_member(user_id)
        sealed_role = self._get_role(sealed_role_id) if sealed_role_id else None
        cid         = _safe_int(seal_channel_id)
        seal_ch     = self.guild.get_channel(cid) if cid else None

        if member and sealed_role and sealed_role in member.roles:
            try:
                await member.remove_roles(sealed_role, reason="Seal released")
            except (discord.Forbidden, discord.HTTPException) as exc:
                logger.warning("release_seal: no se pudo quitar rol sellado: %s", exc)

        if member and original_role_ids:
            roles_to_restore = [
                r for rid in original_role_ids
                if (r := self._get_role(rid)) and not r.managed and r != self.guild.default_role
            ]
            if roles_to_restore:
                try:
                    await member.add_roles(*roles_to_restore, reason="Seal released: restoring roles")
                except (discord.Forbidden, discord.HTTPException) as exc:
                    logger.warning("release_seal: error restaurando roles: %s", exc)

        if seal_ch:
            try:
                await seal_ch.send(
                    "🔓 El sello ha sido levantado. "
                    + (f"{member.mention} ha sido liberado." if member else "")
                    + "\nEste canal se eliminará en **10 segundos**."
                )
                await asyncio.sleep(10)
                await seal_ch.delete(reason="Seal released: channel cleanup")
            except (discord.Forbidden, discord.HTTPException, discord.NotFound) as exc:
                logger.warning("release_seal: error eliminando canal sellado: %s", exc)

        if sealed_role:
            try:
                await sealed_role.delete(reason="Seal released: cleanup")
            except (discord.Forbidden, discord.HTTPException) as exc:
                logger.warning("release_seal: no se pudo eliminar rol sellado: %s", exc)

        try:
            await self.db.remove_seal(self.guild.id, user_id)
        except AttributeError:
            pass

    @classmethod
    async def handle_seal_reaction(
        cls,
        guild: discord.Guild,
        message_id: int,
        emoji_str: str,
        reactor: discord.Member,
        db,
    ) -> bool:
        tracking_key = f"{guild.id}:{message_id}"
        sealed_uid   = cls._seal_mod_messages.get(tracking_key)

        if sealed_uid is None:
            try:
                seal_data = await db.get_seal_by_mod_message(guild.id, message_id)
                if seal_data:
                    sealed_uid = seal_data.get("user_id")
                    if sealed_uid:
                        cls._seal_mod_messages[tracking_key] = sealed_uid
            except AttributeError:
                pass

        if sealed_uid is None:
            return False

        normalized = emoji_str.strip()
        if normalized != "✅":
            return normalized == "🔒"

        logger.info("handle_seal_reaction: %s liberando sello de uid=%s en guild=%s",
                    reactor, sealed_uid, guild.id)
        try:
            seal_data = await db.get_seal(guild.id, sealed_uid)
        except AttributeError:
            seal_data = None

        executor = ToolExecutor(guild, guild.system_channel or guild.text_channels[0], db)
        if seal_data:
            await executor._release_seal(
                user_id=sealed_uid,
                original_role_ids=seal_data.get("original_role_ids", []),
                sealed_role_id=seal_data.get("sealed_role_id"),
                seal_channel_id=seal_data.get("seal_channel_id"),
            )
        else:
            member = guild.get_member(sealed_uid)
            if member:
                sealed_role = discord.utils.get(member.roles, name="🔒 Sellado")
                if sealed_role:
                    await member.remove_roles(sealed_role, reason=f"Liberado por {reactor}")
                    try:
                        await sealed_role.delete(reason="Unseal via reaction")
                    except (discord.Forbidden, discord.HTTPException):
                        pass

        cls._seal_mod_messages.pop(tracking_key, None)
        task = cls._seal_tasks.get(f"seal_{guild.id}_{sealed_uid}")
        if task:
            task.cancel()
            cls._seal_tasks.pop(f"seal_{guild.id}_{sealed_uid}", None)
        return True

    # ── DATA MASTERY ──────────────────────────────────────────────────────

    async def _do_search_messages_semantic(
        self, query: str, hours: int = 8760, limit: int = 50,
        user_id: str = "", channel_id: str = "",
        semantic_weight: str = "0.5", min_score: str = "0.0", **_,
    ):
        hrs  = max(1, min(87600, int(hours or 8760)))
        lim  = max(1, min(200,  int(limit or 50)))
        sw   = max(0.0, min(1.0, float(semantic_weight or 0.5)))
        ms   = max(0.0, float(min_score or 0.0))
        query_embedding = None
        if sw > 0.0 and self._bot_ref and getattr(self._bot_ref, "embedder", None):
            embedder = self._bot_ref.embedder
            if getattr(embedder, "available", False):
                try:
                    loop = asyncio.get_running_loop()
                    query_embedding = await loop.run_in_executor(None, embedder.encode, query)
                    if hasattr(query_embedding, "tolist"):
                        query_embedding = query_embedding.tolist()
                except Exception:
                    query_embedding = None
        rows = await self.db.hybrid_search_messages(
            guild_id=self.guild.id, query=query, hours=hrs, limit=lim,
            user_id=_safe_int(user_id), channel_id=_safe_int(channel_id),
            semantic_weight=sw if query_embedding is not None else 0.0,
            min_score=ms, query_embedding=query_embedding,
        )
        mode = "hybrid" if (sw > 0.0 and query_embedding is not None) else "fts5_only"
        return {
            "query": query, "mode": mode, "count": len(rows),
            "messages": [
                {"message_id": str(r["id"]), "username": r["username"], "user_id": str(r["user_id"]),
                 "channel_id": str(r["channel_id"]), "content": r["content"],
                 "timestamp": r["timestamp"], "rrf_score": r.get("rrf_score", 0)}
                for r in rows
            ],
        }

    async def _do_aggregate_messages(
        self, group_by: str = "user", hours: int = 168, limit: int = 20,
        user_id: str = "", channel_id: str = "",
        start_ts: str = "", end_ts: str = "", agg_type: str = "messages", **_,
    ):
        rows = await self.db.aggregate_messages(
            guild_id=self.guild.id, group_by=group_by or "user",
            hours=max(1, min(8760, int(hours or 168))),
            limit=max(1, min(100, int(limit or 20))),
            user_id=_safe_int(user_id), channel_id=_safe_int(channel_id),
            start_ts=start_ts.strip() or None, end_ts=end_ts.strip() or None,
            agg_type=agg_type or "messages",
        )
        if (group_by or "user") == "user":
            for row in rows:
                if "user_id" in row:
                    member = self._get_member(row["user_id"])
                    if member:
                        row["display_name"] = member.display_name
        return {"group_by": group_by or "user", "agg_type": agg_type or "messages",
                "count": len(rows), "results": rows}

    async def _do_paginate_messages(
        self, hours: int = 168, limit: int = 100, offset: int = 0,
        user_id: str = "", channel_id: str = "",
        start_ts: str = "", end_ts: str = "", order: str = "desc", **_,
    ):
        res = await self.db.paginate_messages(
            guild_id=self.guild.id,
            hours=max(1, min(8760, int(hours or 168))),
            limit=max(1, min(200, int(limit or 100))),
            offset=max(0, int(offset or 0)),
            user_id=_safe_int(user_id), channel_id=_safe_int(channel_id),
            start_ts=start_ts.strip() or None, end_ts=end_ts.strip() or None,
            order=order or "desc",
        )
        if "messages" in res:
            for m in res["messages"]:
                if "id" in m:
                    m["message_id"] = str(m["id"])
                    m["user_id"] = str(m["user_id"])
                    m["channel_id"] = str(m["channel_id"])
        return res

    async def _do_profile_sample(self, user_id: str, sample_size: int = 300, **_):
        """Muestra inteligente de mensajes: 50% temporal uniforme + 50% semántica."""
        uid = _safe_int(user_id)
        if uid is None:
            return {"error": "user_id inválido."}
        size = max(50, min(500, int(sample_size or 300)))
        gid = self.guild.id

        count_row = await self.db.fetchone(
            "SELECT COUNT(*) as c FROM messages WHERE guild_id=? AND user_id=? AND length(content)>15",
            (gid, uid),
        )
        total = count_row["c"] if count_row else 0
        if total == 0:
            return {"error": "Usuario sin mensajes.", "total": 0}

        # ── 50% temporal: mensajes uniformemente espaciados ──
        temporal_size = size // 2
        step = max(1, total // temporal_size)
        temporal_rows = await self.db.fetch(
            "SELECT content, timestamp FROM ("
            "  SELECT content, timestamp, ROW_NUMBER() OVER (ORDER BY timestamp) as rn"
            "  FROM messages WHERE guild_id=? AND user_id=? AND length(content)>15"
            ") WHERE rn % ? = 0 LIMIT ?",
            (gid, uid, step, temporal_size),
        )

        # ── 50% inteligente: búsqueda semántica de mensajes con personalidad ──
        smart_size = size - len(temporal_rows)
        smart_rows = []

        # Intentar búsqueda semántica con el embed_engine existente
        embedder = getattr(self._bot_ref, "embedder", None)
        used_semantic = False
        if embedder and getattr(embedder, "_model", None):
            try:
                import asyncio
                loop = asyncio.get_running_loop()
                # Query diseñado para atraer mensajes con señal de personalidad
                personality_query = (
                    "opinión personal, sentimientos, gustos, humor, "
                    "experiencias, planes, quejas, entusiasmo, recomendaciones"
                )
                query_emb = await loop.run_in_executor(None, embedder.encode, personality_query)
                if hasattr(query_emb, "tolist"):
                    query_emb = query_emb.tolist()

                # Buscar mensajes del usuario más similares semánticamente
                # Usa FTS5 + scoring como fallback si vec no tiene datos del user
                candidates = await self.db.fetch(
                    "SELECT content, timestamp FROM messages "
                    "WHERE guild_id=? AND user_id=? AND length(content)>30 "
                    "ORDER BY length(content) DESC LIMIT ?",
                    (gid, uid, smart_size * 4),
                )
                if candidates:
                    # Score cada candidato contra el query de personalidad
                    texts = [r["content"] for r in candidates]
                    embs = await loop.run_in_executor(None, embedder.encode, texts)
                    import numpy as np
                    query_np = np.array(query_emb, dtype=np.float32)
                    embs_np = np.array(embs, dtype=np.float32)
                    # Cosine similarity
                    norms = np.linalg.norm(embs_np, axis=1, keepdims=True)
                    norms[norms == 0] = 1
                    embs_norm = embs_np / norms
                    query_norm = query_np / (np.linalg.norm(query_np) or 1)
                    scores = embs_norm @ query_norm
                    # Top-K por score
                    top_idx = np.argsort(scores)[::-1][:smart_size * 2]
                    smart_rows = [candidates[i] for i in top_idx]
                    used_semantic = True
            except Exception:
                pass  # fallback a heurístico

        # Fallback heurístico si semántica no disponible
        if not smart_rows:
            smart_rows = await self.db.fetch(
                "SELECT content, timestamp FROM ("
                "  SELECT content, timestamp,"
                "    length(content) + "
                "    (CASE WHEN content LIKE '%?%' THEN 20 ELSE 0 END) + "
                "    (CASE WHEN content LIKE '%!%' THEN 10 ELSE 0 END) + "
                "    (CASE WHEN content LIKE '%jaja%' OR content LIKE '%xd%' OR content LIKE '%lol%' THEN 15 ELSE 0 END) + "
                "    (CASE WHEN length(content) > 100 THEN 30 ELSE 0 END) + "
                "    (CASE WHEN content LIKE '%creo%' OR content LIKE '%opino%' OR content LIKE '%pienso%' THEN 25 ELSE 0 END)"
                "    AS relevance_score"
                "  FROM messages WHERE guild_id=? AND user_id=? AND length(content)>30"
                "  ORDER BY relevance_score DESC"
                "  LIMIT ?"
                ")",
                (gid, uid, smart_size * 2),
            )

        # Dedup: quitar mensajes que ya están en temporal_rows
        temporal_contents = {r["content"] for r in temporal_rows}
        smart_unique = [r for r in smart_rows if r["content"] not in temporal_contents][:smart_size]

        # Combinar y ordenar por timestamp
        all_rows = temporal_rows + smart_unique
        all_rows.sort(key=lambda r: r["timestamp"])

        member = self._get_member(uid)
        return {
            "user_id": str(uid),
            "display_name": member.display_name if member else str(uid),
            "total_messages": total,
            "sample_size": len(all_rows),
            "temporal_count": len(temporal_rows),
            "smart_count": len(smart_unique),
            "smart_method": "semantic" if used_semantic else "heuristic",
            "coverage": f"{_ts_to_date(all_rows[0]['timestamp'])} → {_ts_to_date(all_rows[-1]['timestamp'])}" if all_rows else "",
            "messages": [{"content": r["content"], "timestamp": _ts_to_date(r["timestamp"])} for r in all_rows],
        }

    async def _do_get_loan_info(self, user_id: str = "", mode: str = "status", **_):
        """Consulta deudas, score crediticio, morosos o historial de pagos."""
        gid = self.guild.id
        if mode == "morosos":
            rows = await self.db.fetch(
                "SELECT l.user_id, l.remaining_debt, l.missed_installments, l.created_at, "
                "ls.score FROM loans l LEFT JOIN loan_scores ls "
                "ON l.user_id=ls.user_id AND l.guild_id=ls.guild_id "
                "WHERE l.guild_id=? AND l.status='active' AND l.missed_installments>0 "
                "ORDER BY l.remaining_debt DESC LIMIT 20", (gid,),
            )
            morosos = []
            for r in rows:
                m = self._get_member(r["user_id"])
                morosos.append({"user": m.display_name if m else str(r["user_id"]),
                                "debt": r["remaining_debt"], "misses": r["missed_installments"],
                                "score": r["score"] or 500})
            return {"morosos": morosos, "total": len(morosos)}

        uid = _safe_int(user_id)
        if not uid:
            return {"error": "Necesito user_id para mode 'status' o 'historial'."}

        if mode == "historial":
            rows = await self.db.fetch(
                "SELECT amount_due, amount_paid, success, collected_at FROM loan_payments "
                "WHERE user_id=? AND guild_id=? ORDER BY collected_at DESC LIMIT 15", (uid, gid),
            )
            return {"user_id": str(uid), "payments": [dict(r) for r in rows]}

        # Default: status
        score_data = await self.db.get_loan_score(uid, gid)
        active = await self.db.get_active_loan(uid, gid)
        result = {"user_id": str(uid), "score": score_data["score"],
                  "total_loans": score_data["total_loans"],
                  "missed_payments": score_data["missed_payments"],
                  "blacklisted": bool(score_data["blacklisted"])}
        if active:
            result["active_loan"] = {
                "remaining_debt": active["remaining_debt"],
                "installment_amt": active["installment_amt"],
                "paid": active["paid_installments"],
                "total_installments": active["num_installments"],
                "misses": active["missed_installments"],
                "next_collection": active["next_collection"],
            }
        return result

    # ── Loan helpers (compartidos por list_morosos/get_user_debt/leaderboard) ──
    @staticmethod
    def _loan_tier(score: int) -> str:
        """Score → tier label."""
        if score >= 800:
            return "S"
        if score >= 600:
            return "A"
        if score >= 400:
            return "B"
        if score >= 200:
            return "C"
        return "D"

    def _loan_user_label(self, user_id: int) -> str:
        """Display name si está en el guild, else mention fallback."""
        m = self._get_member(user_id)
        return m.display_name if m else f"<@{user_id}>"

    @staticmethod
    def _days_since(iso_ts: str) -> int:
        """Días desde un timestamp ISO (UTC)."""
        if not iso_ts:
            return 0
        try:
            ts = datetime.datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            return max(0, (now - ts).days)
        except Exception:
            return 0

    @staticmethod
    def _hours_until(iso_ts: str) -> int:
        """Horas hasta un timestamp ISO futuro (0 si ya pasó)."""
        if not iso_ts:
            return 0
        try:
            ts = datetime.datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            return max(0, int((ts - now).total_seconds() / 3600))
        except Exception:
            return 0

    async def _do_list_morosos(self, sort: str = "debt_desc", min_debt: int = 0,
                                only_late: str = "yes", limit: int = 25, **_):
        """Lista deudores con datos completos para tabla rica."""
        gid = self.guild.id
        sort_map = {
            "debt_desc": "l.remaining_debt DESC",
            "debt_asc": "l.remaining_debt ASC",
            "misses_desc": "l.missed_installments DESC, l.remaining_debt DESC",
            "days_desc": "l.created_at ASC",
            "score_asc": "ls.score ASC, l.remaining_debt DESC",
        }
        order = sort_map.get((sort or "debt_desc").lower(), sort_map["debt_desc"])

        try:
            lim = max(1, min(50, int(limit or 25)))
        except (ValueError, TypeError):
            lim = 25
        try:
            min_d = max(0, int(min_debt or 0))
        except (ValueError, TypeError):
            min_d = 0
        only_late_bool = (only_late or "yes").lower() in ("yes", "y", "true", "1")

        where = "l.guild_id = ? AND l.status = 'active'"
        params: list = [gid]
        if only_late_bool:
            where += " AND l.missed_installments >= 1"
        if min_d > 0:
            where += " AND l.remaining_debt >= ?"
            params.append(min_d)

        query = (
            "SELECT l.user_id, l.principal, l.total_owed, l.remaining_debt, "
            "l.installment_amt, l.paid_installments, l.num_installments, "
            "l.missed_installments, l.consecutive_misses, l.created_at, "
            "l.next_collection, l.interest_rate, "
            "ls.score, ls.blacklisted, ls.total_loans, ls.defaults_count "
            "FROM loans l "
            "LEFT JOIN loan_scores ls ON l.user_id = ls.user_id AND l.guild_id = ls.guild_id "
            f"WHERE {where} ORDER BY {order} LIMIT ?"
        )
        params.append(lim)

        try:
            rows = await self.db.fetch(query, tuple(params))
        except Exception as exc:
            return {"ok": False, "error": f"DB error: {exc}"}

        morosos = []
        for r in rows:
            uid = r["user_id"]
            score = r["score"] if r["score"] is not None else 500
            morosos.append({
                "user_id": str(uid),
                "name": self._loan_user_label(uid),
                "debt": r["remaining_debt"],
                "principal": r["principal"],
                "total_owed": r["total_owed"],
                "installment": r["installment_amt"],
                "paid": r["paid_installments"],
                "of": r["num_installments"],
                "progress_pct": int(r["paid_installments"] * 100 / r["num_installments"]) if r["num_installments"] else 0,
                "misses": r["missed_installments"],
                "consec_miss": r["consecutive_misses"],
                "interest_rate_pct": int(round((r["interest_rate"] or 0) * 100)),
                "score": score,
                "tier": self._loan_tier(score),
                "total_loans": r["total_loans"] or 0,
                "defaults": r["defaults_count"] or 0,
                "days_since_loan": self._days_since(r["created_at"]),
                "hours_to_next_collection": self._hours_until(r["next_collection"]),
                "blacklisted": bool(r["blacklisted"]) if r["blacklisted"] is not None else False,
            })

        return {
            "ok": True,
            "guild_id": str(gid),
            "total": len(morosos),
            "filters": {"sort": sort, "min_debt": min_d, "only_late": only_late_bool, "limit": lim},
            "morosos": morosos,
        }

    async def _do_get_user_debt(self, user_id: str, **_):
        """Estado completo de la deuda + score + tier de un usuario."""
        uid = _safe_int(user_id)
        if not uid:
            return {"ok": False, "error": "user_id inválido"}
        gid = self.guild.id
        try:
            score_data = await self.db.get_loan_score(uid, gid)
            active = await self.db.get_active_loan(uid, gid)
        except Exception as exc:
            return {"ok": False, "error": f"DB error: {exc}"}

        score_val = score_data.get("score", 500) if score_data else 500
        out = {
            "ok": True,
            "user_id": str(uid),
            "name": self._loan_user_label(uid),
            "score": score_val,
            "tier": self._loan_tier(score_val),
            "total_loans": (score_data or {}).get("total_loans", 0),
            "paid_on_time": (score_data or {}).get("paid_on_time", 0),
            "missed_payments": (score_data or {}).get("missed_payments", 0),
            "defaults_count": (score_data or {}).get("defaults_count", 0),
            "blacklisted": bool((score_data or {}).get("blacklisted", 0)),
            "has_active_loan": bool(active),
        }
        if active:
            out["active_loan"] = {
                "principal": active["principal"],
                "total_owed": active["total_owed"],
                "remaining_debt": active["remaining_debt"],
                "interest_rate_pct": int(round((active["interest_rate"] or 0) * 100)),
                "installment_amt": active["installment_amt"],
                "paid_installments": active["paid_installments"],
                "num_installments": active["num_installments"],
                "missed_installments": active["missed_installments"],
                "consecutive_misses": active["consecutive_misses"],
                "next_collection": active["next_collection"],
                "created_at": active["created_at"],
                "days_since_loan": self._days_since(active["created_at"]),
                "hours_to_next_collection": self._hours_until(active["next_collection"]),
                "progress_pct": int(active["paid_installments"] * 100 / active["num_installments"]) if active["num_installments"] else 0,
            }
        return out

    async def _do_get_loan_leaderboard(self, mode: str, limit: int = 10, **_):
        """Rankings del sistema de préstamos."""
        try:
            lim = max(1, min(25, int(limit or 10)))
        except (ValueError, TypeError):
            lim = 10
        gid = self.guild.id
        mode = (mode or "").lower()

        try:
            if mode == "biggest_debtors":
                rows = await self.db.fetch(
                    "SELECT user_id, remaining_debt, missed_installments, num_installments, paid_installments "
                    "FROM loans WHERE guild_id=? AND status='active' "
                    "ORDER BY remaining_debt DESC LIMIT ?", (gid, lim))
                users = [{
                    "user_id": str(r["user_id"]),
                    "name": self._loan_user_label(r["user_id"]),
                    "value": r["remaining_debt"],
                    "label": "deuda",
                    "extra": {"misses": r["missed_installments"],
                              "progress": f"{r['paid_installments']}/{r['num_installments']}"},
                } for r in rows]
            elif mode == "best_payers":
                rows = await self.db.fetch(
                    "SELECT user_id, score, total_loans, paid_on_time, missed_payments "
                    "FROM loan_scores WHERE guild_id=? AND total_loans > 0 AND blacklisted=0 "
                    "ORDER BY score DESC, paid_on_time DESC LIMIT ?", (gid, lim))
                users = [{
                    "user_id": str(r["user_id"]),
                    "name": self._loan_user_label(r["user_id"]),
                    "value": r["score"],
                    "label": "score",
                    "extra": {"tier": self._loan_tier(r["score"]),
                              "loans": r["total_loans"],
                              "on_time": r["paid_on_time"],
                              "missed": r["missed_payments"]},
                } for r in rows]
            elif mode == "worst_defaulters":
                rows = await self.db.fetch(
                    "SELECT user_id, defaults_count, missed_payments, score, total_loans "
                    "FROM loan_scores WHERE guild_id=? AND defaults_count > 0 "
                    "ORDER BY defaults_count DESC, missed_payments DESC LIMIT ?", (gid, lim))
                users = [{
                    "user_id": str(r["user_id"]),
                    "name": self._loan_user_label(r["user_id"]),
                    "value": r["defaults_count"],
                    "label": "defaults",
                    "extra": {"missed": r["missed_payments"],
                              "score": r["score"],
                              "loans": r["total_loans"]},
                } for r in rows]
            elif mode == "top_borrowers":
                rows = await self.db.fetch(
                    "SELECT user_id, total_loans, score, paid_on_time, missed_payments "
                    "FROM loan_scores WHERE guild_id=? AND total_loans > 0 "
                    "ORDER BY total_loans DESC LIMIT ?", (gid, lim))
                users = [{
                    "user_id": str(r["user_id"]),
                    "name": self._loan_user_label(r["user_id"]),
                    "value": r["total_loans"],
                    "label": "préstamos",
                    "extra": {"score": r["score"],
                              "tier": self._loan_tier(r["score"]),
                              "on_time": r["paid_on_time"]},
                } for r in rows]
            elif mode == "longest_active":
                rows = await self.db.fetch(
                    "SELECT user_id, remaining_debt, created_at, missed_installments "
                    "FROM loans WHERE guild_id=? AND status='active' "
                    "ORDER BY created_at ASC LIMIT ?", (gid, lim))
                users = [{
                    "user_id": str(r["user_id"]),
                    "name": self._loan_user_label(r["user_id"]),
                    "value": self._days_since(r["created_at"]),
                    "label": "días",
                    "extra": {"debt": r["remaining_debt"],
                              "misses": r["missed_installments"]},
                } for r in rows]
            else:
                return {
                    "ok": False,
                    "error": f"mode inválido: '{mode}'",
                    "valid_modes": ["biggest_debtors", "best_payers", "worst_defaulters",
                                    "top_borrowers", "longest_active"],
                }
        except Exception as exc:
            return {"ok": False, "error": f"DB error: {exc}"}

        return {"ok": True, "mode": mode, "limit": lim, "total": len(users), "users": users}

    async def _do_get_loan_stats(self, **_):
        """Estadísticas globales del sistema crediticio del servidor."""
        gid = self.guild.id
        try:
            active = await self.db.fetchone(
                "SELECT COUNT(*) AS c, COALESCE(SUM(remaining_debt), 0) AS total_debt, "
                "COALESCE(SUM(principal), 0) AS total_principal "
                "FROM loans WHERE guild_id=? AND status='active'", (gid,))
            morosos = await self.db.fetchone(
                "SELECT COUNT(*) AS c FROM loans "
                "WHERE guild_id=? AND status='active' AND missed_installments >= 1", (gid,))
            completed = await self.db.fetchone(
                "SELECT COUNT(*) AS c, COALESCE(SUM(total_owed), 0) AS total_collected "
                "FROM loans WHERE guild_id=? AND status IN ('paid', 'completed')", (gid,))
            defaulted = await self.db.fetchone(
                "SELECT COUNT(*) AS c FROM loans WHERE guild_id=? AND status='defaulted'", (gid,))
            scores = await self.db.fetchone(
                "SELECT AVG(score) AS avg_score, COUNT(*) AS users "
                "FROM loan_scores WHERE guild_id=?", (gid,))
            blacklisted = await self.db.fetchone(
                "SELECT COUNT(*) AS c FROM loan_scores WHERE guild_id=? AND blacklisted=1", (gid,))
            payments = await self.db.fetchone(
                "SELECT COUNT(*) AS total, COALESCE(SUM(success), 0) AS ok, "
                "COALESCE(SUM(amount_paid), 0) AS paid_credits "
                "FROM loan_payments WHERE guild_id=?", (gid,))
        except Exception as exc:
            return {"ok": False, "error": f"DB error: {exc}"}

        active = active or {"c": 0, "total_debt": 0, "total_principal": 0}
        morosos = morosos or {"c": 0}
        completed = completed or {"c": 0, "total_collected": 0}
        defaulted = defaulted or {"c": 0}
        scores = scores or {"avg_score": None, "users": 0}
        blacklisted = blacklisted or {"c": 0}
        payments = payments or {"total": 0, "ok": 0, "paid_credits": 0}

        avg_score = int(scores["avg_score"]) if scores["avg_score"] is not None else 500
        total_payments = payments["total"] or 0
        success_payments = payments["ok"] or 0
        success_rate = int(success_payments * 100 / total_payments) if total_payments else 0

        return {
            "ok": True,
            "active": {
                "count": active["c"],
                "total_debt": active["total_debt"],
                "total_principal": active["total_principal"],
                "interest_circulating": (active["total_debt"] - active["total_principal"])
                    if active["total_debt"] >= active["total_principal"] else 0,
            },
            "morosos": morosos["c"],
            "completed": {"count": completed["c"], "total_collected": completed["total_collected"]},
            "defaulted": defaulted["c"],
            "users_with_score": scores["users"] or 0,
            "avg_score": avg_score,
            "avg_tier": self._loan_tier(avg_score),
            "blacklisted": blacklisted["c"],
            "payments": {
                "total": total_payments,
                "successful": success_payments,
                "missed": total_payments - success_payments,
                "success_rate_pct": success_rate,
                "total_paid_credits": payments["paid_credits"] or 0,
            },
        }

    async def _do_get_loan_history(self, user_id: str, limit: int = 10, **_):
        """Historial de pagos (cobros) de un usuario."""
        uid = _safe_int(user_id)
        if not uid:
            return {"ok": False, "error": "user_id inválido"}
        try:
            lim = max(1, min(30, int(limit or 10)))
        except (ValueError, TypeError):
            lim = 10
        gid = self.guild.id
        try:
            rows = await self.db.fetch(
                "SELECT loan_id, amount_due, amount_paid, success, "
                "balance_before, balance_after, collected_at "
                "FROM loan_payments WHERE user_id=? AND guild_id=? "
                "ORDER BY collected_at DESC LIMIT ?", (uid, gid, lim))
        except Exception as exc:
            return {"ok": False, "error": f"DB error: {exc}"}

        payments = [{
            "loan_id": r["loan_id"],
            "amount_due": r["amount_due"],
            "amount_paid": r["amount_paid"],
            "success": bool(r["success"]),
            "balance_before": r["balance_before"],
            "balance_after": r["balance_after"],
            "collected_at": r["collected_at"],
        } for r in rows]
        success_count = sum(1 for p in payments if p["success"])

        return {
            "ok": True,
            "user_id": str(uid),
            "name": self._loan_user_label(uid),
            "total": len(payments),
            "success_count": success_count,
            "missed_count": len(payments) - success_count,
            "payments": payments,
        }

    # ── Treasury (Y O U K A I · B A N K) ──────────────────────────────────

    async def _do_get_treasury_balance(self, **_):
        """Estado completo del banco/pool del servidor."""
        try:
            stats = await self.db.get_treasury_stats(self.guild.id)
        except Exception as exc:
            return {"ok": False, "error": f"DB error: {exc}"}
        # Etiqueta de salud
        bal = stats["balance"]
        if bal < 600:
            health = "critical"
        elif bal < 1500:
            health = "low"
        elif bal < 3000:
            health = "stable"
        else:
            health = "healthy"

        outstanding = stats["outstanding_debt"]
        collected = stats["total_collected"]
        disbursed = stats["total_disbursed"]
        lost = stats["total_lost_defaults"]
        operating = collected - disbursed  # resultado operativo = cuotas - capital prestado

        # Resumen en una frase para que el LLM no tenga que recalcularlo.
        # Formato: estado + balance + nota sobre operación.
        if operating > 0:
            op_note = f"banco gana {operating:,} cr en operaciones"
        elif operating < 0:
            op_note = (
                f"banco está {-operating:,} cr abajo en operaciones "
                f"(préstamos vivos cuyas cuotas todavía no terminaron)"
            )
        else:
            op_note = "operaciones equilibradas"
        summary = (
            f"Banco {health}: {bal:,} cr en caja, {outstanding:,} cr prestados afuera, {op_note}."
        )

        return {
            "ok": True,
            "summary": summary,
            # Estado actual
            "balance": bal,
            "outstanding_debt": outstanding,
            "bootstrap_amount": stats["bootstrap_amount"],
            # Acumulados de operaciones (NO incluyen el bootstrap)
            "total_collected": collected,        # cuotas + depósitos staff
            "total_disbursed": disbursed,         # préstamos + grants
            "total_lost_defaults": lost,
            # Operating result = cuotas - préstamos. Positivo = banco gana en intereses.
            "operating_result": operating,
            # Alias retrocompat (era el nombre viejo, mantengo para no romper).
            "net_profit": operating,
            "health": health,
            "breakdown": stats["breakdown"],
        }

    async def _do_get_treasury_history(self, limit: int = 15, reason_filter: str = "", **_):
        """Movimientos del banco con filtro opcional por razón."""
        try:
            lim = max(1, min(50, int(limit or 15)))
        except (ValueError, TypeError):
            lim = 15
        rf = (reason_filter or "").strip() or None
        try:
            rows = await self.db.get_treasury_history(self.guild.id, limit=lim, reason_filter=rf)
        except Exception as exc:
            return {"ok": False, "error": f"DB error: {exc}"}

        movements = []
        for r in rows:
            target_name = None
            if r.get("user_id"):
                m = self._get_member(r["user_id"])
                target_name = m.display_name if m else None
            staff_name = None
            if r.get("by_staff_id"):
                m = self._get_member(r["by_staff_id"])
                staff_name = m.display_name if m else None
            movements.append({
                "amount": r["amount"],
                "balance_after": r["balance_after"],
                "reason": r["reason"],
                "metadata": r.get("metadata"),
                "user_id": str(r["user_id"]) if r.get("user_id") else None,
                "user_name": target_name,
                "by_staff_id": str(r["by_staff_id"]) if r.get("by_staff_id") else None,
                "by_staff_name": staff_name,
                "created_at": r["created_at"],
            })
        return {
            "ok": True,
            "total": len(movements),
            "filter": rf,
            "movements": movements,
        }

    async def _do_treasury_grant_credits(self, user_id: str, amount: int, reason: str, **_):
        """STAFF: entrega créditos del pool a un usuario.

        Permission gate: el dispatcher debe haber validado manage_guild antes.
        Si el banco no tiene fondos suficientes, retorna ok=False sin debitar.
        """
        uid = _safe_int(user_id)
        if not uid:
            return {"ok": False, "error": "user_id inválido"}
        try:
            amt = int(amount)
        except (ValueError, TypeError):
            return {"ok": False, "error": "amount inválido"}
        if amt <= 0:
            return {"ok": False, "error": "amount debe ser > 0"}
        if amt > 50000:
            return {"ok": False, "error": "amount máximo: 50000"}
        reason = (reason or "").strip()
        if len(reason) < 3 or len(reason) > 200:
            return {"ok": False, "error": "reason debe tener 3-200 chars"}

        gid = self.guild.id
        executor_id = getattr(self, "actor_id", None) or getattr(self, "_actor_id", None)
        meta = json.dumps({
            "target": str(uid),
            "by_tool": True,
            "by_user": str(executor_id) if executor_id else None,
            "razon": reason,
        })
        try:
            ok, new_bal = await self.db.spend_from_treasury(
                gid, amt, "staff_grant",
                metadata_json=meta, user_id=uid,
                by_staff_id=executor_id,
            )
            if not ok:
                treasury = await self.db.get_treasury(gid)
                return {
                    "ok": False,
                    "error": "fondos insuficientes",
                    "balance_required": amt,
                    "balance_available": treasury["balance"],
                }
            await self.db.add_credits(uid, gid, amt)
        except Exception as exc:
            return {"ok": False, "error": f"DB error: {exc}"}

        return {
            "ok": True,
            "user_id": str(uid),
            "user_name": self._loan_user_label(uid),
            "amount_granted": amt,
            "reason": reason,
            "treasury_balance_after": new_bal,
        }

    async def _do_treasury_deposit(self, amount: int, reason: str, **_):
        """STAFF: deposita créditos al pool del banco."""
        try:
            amt = int(amount)
        except (ValueError, TypeError):
            return {"ok": False, "error": "amount inválido"}
        if amt <= 0:
            return {"ok": False, "error": "amount debe ser > 0"}
        if amt > 1_000_000:
            return {"ok": False, "error": "amount máximo: 1,000,000"}
        reason = (reason or "").strip()
        if len(reason) < 3 or len(reason) > 200:
            return {"ok": False, "error": "reason debe tener 3-200 chars"}

        gid = self.guild.id
        executor_id = getattr(self, "actor_id", None) or getattr(self, "_actor_id", None)
        meta = json.dumps({
            "by_tool": True,
            "by_user": str(executor_id) if executor_id else None,
            "razon": reason,
        })
        try:
            new_bal = await self.db.add_to_treasury(
                gid, amt, "staff_deposit",
                metadata_json=meta, user_id=None,
                by_staff_id=executor_id,
            )
        except Exception as exc:
            return {"ok": False, "error": f"DB error: {exc}"}

        return {
            "ok": True,
            "amount_deposited": amt,
            "reason": reason,
            "treasury_balance_after": new_bal,
        }

    async def _do_get_user_timeline(self, user_id: str, days: int = 14, **_):
        uid = _safe_int(user_id)
        if uid is None:
            return {"error": "user_id inválido."}
        return await self.db.get_user_timeline(
            guild_id=self.guild.id, user_id=uid, days=max(1, min(90, int(days or 14))))

    async def _do_query_pattern_analysis(
        self, mode: str, hours: int = 168, days: int = 7,
        min_overlap: int = 3, sensitivity: str = "2.0",
        min_previous_messages: int = 10, **_,
    ):
        # cooccurrence uses Python buckets — fast even at 30 days
        max_hours = 720 if mode == "cooccurrence" else 720
        return await self.db.query_pattern_analysis(
            guild_id=self.guild.id, mode=mode,
            hours=max(1, min(max_hours, int(hours or 720))),
            days=max(1, min(90, int(days or 7))),
            min_overlap=max(1, int(min_overlap or 3)),
            sensitivity=max(0.5, float(sensitivity or 2.0)),
            min_previous_messages=max(1, int(min_previous_messages or 10)),
        )

    async def _do_investigate_topic(
        self, query: str, hours: int = 8760, max_users: int = 5,
        include_stats: str = "yes", **_,
    ):
        hrs = max(1, min(8760, int(hours or 8760)))
        max_u = max(1, min(10, int(max_users or 5)))
        want_stats = (include_stats or "yes").lower().startswith("y")

        query_embedding = None
        if self._bot_ref and getattr(self._bot_ref, "embedder", None):
            embedder = self._bot_ref.embedder
            if getattr(embedder, "available", False):
                try:
                    loop = asyncio.get_running_loop()
                    query_embedding = await loop.run_in_executor(None, embedder.encode, query)
                    if hasattr(query_embedding, "tolist"):
                        query_embedding = query_embedding.tolist()
                except Exception:
                    query_embedding = None

        search_results = await self.db.hybrid_search_messages(
            guild_id=self.guild.id, query=query, hours=hrs, limit=20,
            semantic_weight=0.5 if query_embedding else 0.0,
            min_score=0.0, query_embedding=query_embedding,
        )

        user_ids_seen = set()
        user_profiles = {}
        for msg in search_results:
            uid = msg.get("user_id")
            if uid and uid not in user_ids_seen and len(user_ids_seen) < max_u:
                user_ids_seen.add(uid)
                member = self._get_member(uid)
                user_profiles[str(uid)] = {
                    "username": msg.get("username", ""),
                    "display_name": member.display_name if member else msg.get("username", ""),
                    "message_count": sum(1 for m in search_results if m.get("user_id") == uid),
                    "sample_messages": [m["content"] for m in search_results
                                       if m.get("user_id") == uid and m.get("content")][:3],
                }

        stats = {}
        if want_stats:
            try:
                agg = await self.db.aggregate_messages(
                    guild_id=self.guild.id, group_by="user",
                    hours=hrs, limit=max_u,
                )
                stats = {"top_posters": [
                    {"user_id": str(r.get("user_id", "")),
                     "messages": r.get("message_count", 0)}
                    for r in agg[:max_u]
                ]}
            except Exception:
                stats = {"error": "Could not aggregate stats"}

        return {
            "query": query,
            "time_window_hours": hrs,
            "messages_found": len(search_results),
            "relevant_users": user_profiles,
            "server_stats": stats,
            "top_messages": [
                {"user": m.get("username", "?"), "content": m.get("content", "")[:200],
                 "timestamp": m.get("timestamp", 0)}
                for m in search_results[:8]
            ],
            "hint": "Use this data directly to answer. No need for more tool calls.",
        }

    # ── GRAPH ANALYSIS (Sherlock Kai) ──────────────────────────────────────

    async def _do_analyze_social_graph(self, hours: int = 720, **_):
        from utils.graph_analyzer import GraphAnalyzer
        ga = GraphAnalyzer(self.db)
        result = await ga.build_social_graph(self.guild.id, hours=max(1, int(hours or 720)))
        return result

    async def _do_find_communities(self, min_size: int = 3, hours: int = 720, **_):
        from utils.graph_analyzer import GraphAnalyzer
        ga = GraphAnalyzer(self.db)
        result = await ga.find_communities(
            self.guild.id, min_size=max(1, int(min_size or 3)),
            hours=max(1, int(hours or 720)),
        )
        return result

    async def _do_trace_influence_path(self, user_a_id: str, user_b_id: str,
                                       max_depth: int = 4, **_):
        from utils.graph_analyzer import GraphAnalyzer
        ga = GraphAnalyzer(self.db)
        result = await ga.trace_influence(
            self.guild.id, user_a_id=str(user_a_id), user_b_id=str(user_b_id),
            max_depth=max(1, min(10, int(max_depth or 4))),
        )
        return result

    async def _do_detect_coordinated_activity(
        self, hours: int = 24, similarity_threshold: str = "0.7", **_
    ):
        from utils.graph_analyzer import GraphAnalyzer
        ga = GraphAnalyzer(self.db)
        result = await ga.detect_coordinated_activity(
            self.guild.id, hours=max(1, int(hours or 24)),
            similarity_threshold=max(0.0, min(1.0, float(similarity_threshold or 0.7))),
        )
        return result

    async def _do_correlate_user_behavior(
        self, user_a_id: str, user_b_id: str, hours: int = 720, **_
    ):
        from utils.graph_analyzer import GraphAnalyzer
        ga = GraphAnalyzer(self.db)
        result = await ga.correlate_behavior(
            self.guild.id, user_a_id=str(user_a_id), user_b_id=str(user_b_id),
            hours=max(1, min(8760, int(hours or 720))),
        )
        return result

    async def _do_run_anomaly_scan(self, hours: int = 168, sensitivity: str = "2.0", **_):
        from utils.graph_analyzer import GraphAnalyzer
        ga = GraphAnalyzer(self.db)
        result = await ga.anomaly_scan(
            self.guild.id, hours=max(1, int(hours or 168)),
            sensitivity=max(0.5, float(sensitivity or 2.0)),
        )
        return result

    # ── ZZZ BUILD CARD ────────────────────────────────────────────────────

    async def _do_zzz_build_card(self, uid: str, agente: str = "", **_):
        """Genera build card de ZZZ via renderer custom."""
        import aiohttp
        api = "http://140.84.187.50:8000"
        uid_int = int(uid)

        if agente:
            from utils.zzz_card_renderer import render_build_card
            png = await render_build_card(uid_int, agente)
            if png:
                import discord, io
                channel = self._resolve_channel(None) or self.guild.text_channels[0]
                file = discord.File(io.BytesIO(png), filename="build.png")
                embed = discord.Embed(color=0x00D4FF)
                embed.set_image(url="attachment://build.png")
                msg = await channel.send(embed=embed, file=file)
                return {"success": True, "message_id": str(msg.id), "agent": agente, "uid": uid_int}
            else:
                return {"error": f"Agente '{agente}' no encontrado en showcase de UID {uid}"}
        else:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{api}/uid/{uid_int}/evaluar",
                                       timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return {"error": f"UID {uid} no encontrado o showcase privado"}
                    data = await resp.json()
            evals = data.get("evaluaciones", [])
            return {"uid": uid_int, "nick": data.get("nick", "?"),
                    "agentes": [{"nombre": ag["nombre"], "level": ag["level"],
                                 "weapon": ag["weapon"], "score": ag["evaluacion"]["calidad_pct"],
                                 "grade": "SS" if ag["evaluacion"]["calidad_pct"] >= 95 else
                                          "S" if ag["evaluacion"]["calidad_pct"] >= 90 else
                                          "A" if ag["evaluacion"]["calidad_pct"] >= 80 else "B"}
                                for ag in evals]}

    # ── WEB BROWSING ──────────────────────────────────────────────────────

    _USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:132.0) Gecko/20100101 Firefox/132.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    ]

    _CAPTCHA_PATTERNS = [
        "captcha", "verify you are human", "are you a robot",
        "cf-turnstile", "h-captcha", "recaptcha", "g-recaptcha",
        "cloudflare", "checking your browser", "ddos-guard",
        "please wait while we verify", "just a moment",
        "enable javascript", "browser check", "security check",
    ]

    async def _do_web_fetch(self, url: str, selector: str = "",
                            wait: str = "5", **_):
        import random

        wait_sec = max(1, min(20, int(wait or 5)))
        ua = random.choice(self._USER_AGENTS)

        cmd = [
            "obscura", "fetch",
            "--dump", "text",
            "--wait", str(wait_sec),
            "--wait-until", "networkidle",
            "--user-agent", ua,
            "--stealth",
        ]
        if selector and selector.strip():
            cmd.extend(["--selector", selector.strip()])

        url = url.strip()
        if not url.startswith(("http://", "https://")):
            return {"error": f"URL inválida: '{url}'. Debe comenzar con http:// o https://"}

        # SEC-02 (Wave 2, F0.2): bloqueo SSRF — incluso para subprocess, evitamos
        # que el browser headless descargue desde IPs internas o cloud metadata.
        from utils.security import is_url_safe
        ok, reason = is_url_safe(url)
        if not ok:
            logger.warning("web_fetch bloqueado por SSRF guard: %s (%s)", url, reason)
            return {"error": f"URL bloqueada: {reason}"}

        cmd.append(url)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=45
            )
            stdout_text = stdout.decode("utf-8", errors="replace").strip()
            stderr_text = stderr.decode("utf-8", errors="replace").strip()

            if proc.returncode != 0:
                return {"error": f"obscura falló (exit {proc.returncode}): {stderr_text[:300]}"}

            text_lower = stdout_text.lower()
            for pattern in self._CAPTCHA_PATTERNS:
                if pattern in text_lower:
                    return {
                        "error": f"La página requiere verificación anti-bot (detectado: '{pattern}').",
                        "url": url,
                        "suggestion": "Este sitio tiene protección Cloudflare/CAPTCHA. "
                                       "Prueba con otra fuente o pídele al usuario que busque manualmente."
                    }

            if not stdout_text:
                return {"error": "La página no devolvió contenido textual.", "url": url,
                        "suggestion": "La página puede requerir JavaScript o tener contenido solo en imágenes."}

            max_chars = 8000
            truncated = len(stdout_text) > max_chars
            if truncated:
                stdout_text = stdout_text[:max_chars] + "\n\n[... TRUNCATED ...]"

            return {
                "success": True,
                "url": url,
                "content": stdout_text,
                "length": len(stdout_text),
                "truncated": truncated,
                "note": f"Extraído con obscura (stealth, networkidle, {wait_sec}s wait, UA rotado)"
            }

        except asyncio.TimeoutError:
            return {"error": f"Timeout: la página tardó más de 45s en responder.", "url": url}
        except FileNotFoundError:
            return {"error": "obscura no está instalado en el sistema. Instálalo para habilitar web browsing."}
        except Exception as exc:
            return {"error": f"Error fetching '{url}': {type(exc).__name__}: {exc}"}
    
    
    # ── ORQUESTACIÓN ─────────────────────────────────────────────────
    # Workflows predefinidos que orquestan múltiples tools en secuencia
    
    WORKFLOWS: dict[str, list[dict]] = {
        "antiraid_lockdown": [
            {"tool": "mass_timeout", "args_map": {"user_ids": "user_ids", "duration": "duration", "reason": "reason"}},
            {"tool": "lock_channel",  "args_map": {"channel_id": "channel_id", "reason": "reason"}},
            {"tool": "send_embed",    "args_map": {"channel_id": "mod_channel_id", "title": "Antiraid Lockdown",
                                         "description": "Se aplicó lockdown por sospecha de raid. Usuarios silenciados y canales bloqueados."}},
        ],
        "welcome_sequence": [
            {"tool": "assign_role",   "args_map": {"user_id": "user_id", "role_id": "welcome_role_id"}},
            {"tool": "send_dm",       "args_map": {"user_id": "user_id", "content": "¡Bienvenido! Aquí tienes la info básica..."}},
            {"tool": "send_embed",   "args_map": {"channel_id": "welcome_channel_id", "title": "Nuevo miembro",
                                         "description": "¡Dadle la bienvenida a {user_name}!"}},
        ],
        "cleanup_inactive": [
            {"tool": "find_inactive_members", "args_map": {"days": "days", "limit": "limit"}},
            {"tool": "bulk_assign_role_all", "args_map": {"role_id": "remove_role_id", "action": "'remove'"}},
            {"tool": "send_message", "args_map": {"channel_id": "log_channel_id",
                                         "content": "Limpieza completada: {count} miembros procesados."}},
        ],
        "mod_alert": [
            {"tool": "send_embed", "args_map": {"channel_id": "alert_channel_id", "title": "🚨 Alerta de Moderación",
                                         "description": "Se detectó: {alert_text}", "color": "'#FF6B35'"}},
        ],
    }
    
    async def _do_run_workflow(self, workflow_id: str, params_json: str = "{}", **_):
        """Ejecuta un workflow predefinido orquestando múltiples tools."""
        # FIX (2026-05-16): WORKFLOWS es atributo de clase; sin `self.` causaba
        # NameError. Bug latente — el tool `run_workflow` nunca había funcionado.
        if workflow_id not in self.WORKFLOWS:
            return {"error": f"Workflow '{workflow_id}' no encontrado. "
                              f"Disponibles: {list(self.WORKFLOWS.keys())}"}
        try:
            params = json.loads(params_json) if params_json else {}
        except json.JSONDecodeError as exc:
            return {"error": f"params_json no es JSON válido: {exc}"}
    
        steps = self.WORKFLOWS[workflow_id]
        results = []
        for i, step in enumerate(steps):
            tool_name = step.get("tool", "")
            args_map  = step.get("args_map", {})
            resolved  = {k: params.get(v.strip("'\"") if isinstance(v, str) else v)
                         for k, v in args_map.items()}
            try:
                result = await self.execute_by_name(tool_name, resolved)
                results.append({"step": i, "tool": tool_name, "success": True, "result": result})
                if isinstance(result, dict) and result.get("error"):
                    return {"success": False, "workflow_id": workflow_id,
                            "failed_at_step": i, "failed_tool": tool_name,
                            "error": result["error"], "completed_steps": i, "results": results}
            except Exception as exc:
                return {"success": False, "workflow_id": workflow_id,
                        "failed_at_step": i, "failed_tool": tool_name,
                        "error": f"Excepción en step {i}: {exc}", "completed_steps": i, "results": results}
        return {"success": True, "workflow_id": workflow_id, "steps_executed": len(steps), "results": results}
    
    
    # ── BÚSQUEDA INTELIGENTE ────────────────────────────────────────────
    
    async def _do_smart_search(self, query: str, scope: str = "all", hours: int = 72, **_):
        """Búsqueda universal que decide automáticamente qué buscar."""
        q = (query or "").lower()
        detected = scope if scope != "all" else None
    
        if not detected:
            if any(w in q for w in ["canal", "#", "channel"]):
                detected = "channels"
            elif any(w in q for w in ["rol", "role", "@"]):
                detected = "roles"
            elif any(w in q for w in ["usuario", "user", "miembro", "persona", "nick"]):
                detected = "users"
            else:
                detected = "messages"
    
        if detected == "channels":
            result = await self._do_find_channel(name=query)
            result["detected_scope"] = "channels"
            return result
        elif detected == "roles":
            result = await self._do_find_role(name=query)
            result["detected_scope"] = "roles"
            return result
        elif detected == "users":
            # Try DB first, then guild members
            result = await self._do_get_user_by_name(name=query, context="basic")
            if "error" in result:
                # Fallback: search in guild members
                matches = []
                for m in self.guild.members:
                    if query.lower() in m.display_name.lower() or query.lower() in m.name.lower():
                        matches.append({"user_id": str(m.id), "display_name": m.display_name, "username": str(m)})
                return {"query": query, "detected_scope": "users", "count": len(matches), "matches": matches[:20]}
            result["detected_scope"] = "users"
            return result
        else:  # messages
            try:
                result = await self._do_search_messages_semantic(query=query, hours=hours, limit=150)
                result["detected_scope"] = "messages (semantic)"
            except Exception:
                result = await self._do_search_messages(query=query, hours=hours, limit=150)
                result["detected_scope"] = "messages (keyword)"
            return result
    
    
    # ── COMPONENTES INTERACTIVOS ─────────────────────────────────────────
    
    class _FairyButton(discord.ui.Button):
        def __init__(self, label: str, style: str, custom_id: str, emoji: str = ""):
            style_map = {
                "green":  discord.ButtonStyle.green,
                "red":    discord.ButtonStyle.red,
                "grey":   discord.ButtonStyle.grey,
                "blurple": discord.ButtonStyle.blurple,
            }
            super().__init__(
                label=label,
                style=style_map.get(style, discord.ButtonStyle.blurple),
                custom_id=custom_id,
                emoji=emoji if emoji else None,
            )
    
        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_message(
                f"Acción registrada: {self.label}", ephemeral=True
            )
    
    
    async def _do_interactive_component(self, channel_id: str, component_type: str,
                                       content: str, actions_json: str,
                                       timeout_minutes: int = 15, **_):
        """Crea botones, menus o modals en un canal."""
        ch = self._resolve_channel(channel_id)
        try:
            actions = json.loads(actions_json) if actions_json else []
        except json.JSONDecodeError as exc:
            return {"error": f"actions_json no es JSON válido: {exc}"}
    
        timeout = max(1, min(60, int(timeout_minutes or 15))) * 60
    
        if component_type == "buttons":
            view = discord.ui.View(timeout=timeout)
            for i, act in enumerate(actions[:25]):  # Discord max 25 components
                label    = act.get("label", f"Botón {i+1}")
                style    = act.get("style", "blurple")
                cust_id  = act.get("custom_id", f"fairy_btn_{i}_{int(time.time())}")
                emoji    = act.get("emoji", "")
                view.add_item(self._FairyButton(label=label, style=style, custom_id=cust_id, emoji=emoji))
            msg = await ch.send(content=content or "Selecciona una opción:", view=view)
            return {"success": True, "message_id": str(msg.id), "component_type": "buttons",
                    "active_minutes": timeout // 60, "buttons": len(actions)}
        else:
            return {"error": f"component_type '{component_type}' aún no implementado. Usa 'buttons'."}
    
    
    # ── CÓDIGO SEGURO ───────────────────────────────────────────────────
    # REMOVIDO 2026-05-15 (SEC-01, Wave 1): el handler `_do_execute_code` y
    # su `SAFE_BUILTINS` fueron eliminados por permitir RCE via prompt
    # injection. El sandbox basado en exec() con filtros de string es
    # bypassable con __subclasses__()/__class__.__mro__. Si la feature debe
    # reintroducirse, usar subprocess aislado (nsjail/firejail/bubblewrap),
    # sin red ni filesystem, con timeouts y límites de memoria.
    # Ver .code-review/04-report.md SEC-01.


    # ── BACKUP DEL SERVIDOR ───────────────────────────────────────────────
    
    async def _do_backup_server(self, include_roles: bool = True,
                              include_channels: bool = True,
                              include_emojis: bool = True,
                              filename: str = "", **_):
        """Crea un snapshot JSON completo del estado del servidor."""
        g = self.guild
        snapshot: dict = {
            "server_info": {
                "name": g.name, "guild_id": str(g.id), "owner_id": str(g.owner_id),
                "boost_level": g.premium_tier, "created_at": g.created_at.isoformat(),
            },
            "roles": [], "categories": [], "channels": [], "emojis": [],
        }
    
        if include_roles:
            for role in sorted(g.roles, key=lambda r: r.position, reverse=True):
                if role.is_default():
                    continue
                snapshot["roles"].append({
                    "role_id": str(role.id), "name": role.name,
                    "color": f"#{role.color.value:06X}" if role.color.value else "default",
                    "hoist": role.hoist, "mentionable": role.mentionable,
                    "managed": role.managed, "position": role.position,
                    "permissions": role.permissions.value,
                })
    
        if include_channels:
            snapshot["categories"] = [
                {"category_id": str(cat.id), "name": cat.name, "position": cat.position}
                for cat in sorted(g.categories, key=lambda c: c.position)
            ]
            for ch in g.channels:
                if isinstance(ch, discord.CategoryChannel):
                    continue
                overwrites = []
                for target, ow in ch.overwrites.items():
                    allow, deny = ow.pair()
                    overwrites.append({
                        "target_type": "role" if isinstance(target, discord.Role) else "member",
                        "target_id": str(target.id),
                        "target_name": target.name if hasattr(target, "name") else str(target),
                        "allow": [n for n, v in iter(allow) if v],
                        "deny":  [n for n, v in iter(deny)  if v],
                    })
                ch_data: dict = {
                    "channel_id": str(ch.id), "name": ch.name,
                    "type": str(ch.type), "position": ch.position,
                    "category_id": str(ch.category.id) if ch.category else None,
                    "overwrites": overwrites,
                }
                if isinstance(ch, discord.TextChannel):
                    ch_data["topic"] = ch.topic or ""
                    ch_data["slowmode_delay"] = ch.slowmode_delay
                    ch_data["nsfw"] = ch.nsfw
                snapshot["channels"].append(ch_data)
    
        if include_emojis:
            snapshot["emojis"] = [
                {"emoji_id": str(e.id), "name": e.name, "animated": e.animated,
                 "url": str(e.url) if e.url else ""}
                for e in g.emojis
            ]
    
        json_str    = json.dumps(snapshot, indent=2, ensure_ascii=False, default=str)
        fn          = filename.strip() or f"backup_{g.id}_{int(time.time())}.json"
        msg         = await self.channel.send(file=discord.File(io.BytesIO(json_str.encode()), filename=fn))
        return {
            "success": True, "filename": fn, "message_id": str(msg.id),
            "roles_backed_up": len(snapshot["roles"]),
            "channels_backed_up": len(snapshot["channels"]),
            "emojis_backed_up": len(snapshot["emojis"]),
        }

    # ── Maldición (Curse Tool) ───────────────────────────────────────────

    async def _do_curse_user(self, user_id: str, duration: str = "1h",
                             reason: str = "", **_):
        """Aplica una maldición a un usuario."""
        member, err = self._require_member(user_id)
        if err:
            return err
        if member.bot:
            return {"error": "No se puede maldecir a un bot."}
        if member.id == self.guild.owner_id:
            return {"error": "No se puede maldecir al dueño del servidor."}

        td, err = self._require_duration(duration)
        if err:
            return err

        release_at = discord.utils.utcnow() + td
        release_at_str = release_at.isoformat()

        # Guardar en DB
        if self.db:
            await self.db.add_curse(
                guild_id=self.guild.id,
                user_id=member.id,
                release_at=release_at_str,
                reason=reason or "Maldición de Fairy",
                created_by=None,
                display_name=member.display_name,
            )
            await self.db.log_action(
                self.guild.id, "curse", target_id=member.id,
                details={"reason": reason, "duration": duration},
            )

        return {
            "success": True,
            "cursed_user": str(member),
            "user_id": str(member.id),
            "duration": duration,
            "release_at": release_at_str,
        }

    async def _do_uncurse_user(self, user_id: str, **_):
        """Libera a un usuario de la maldición."""
        member = self._get_member(user_id)
        removed = False
        if self.db:
            removed = await self.db.remove_curse(self.guild.id, int(user_id))
            if removed:
                await self.db.log_action(
                    self.guild.id, "uncurse", target_id=int(user_id),
                )
        msg = str(member) if member else f"User {user_id}"
        if removed:
            return {"success": True, "uncursed": msg, "was_cursed": True}
        return {"success": True, "uncursed": msg, "was_cursed": False}

    async def _do_list_cursed_users(self, **_):
        """Lista todas las maldiciones activas en el servidor."""
        if not self.db:
            return {"error": "DB no disponible"}
        curses = await self.db.get_active_curses(self.guild.id)
        result = []
        for c in curses:
            m = self._get_member(c["user_id"])
            result.append({
                "user_id": str(c["user_id"]),
                "display_name": m.display_name if m else "Unknown",
                "release_at": c["release_at"],
                "reason": c.get("reason", ""),
            })
        return {"count": len(result), "cursed_users": result}

    async def _do_wash_mouth(self, user_id: str, duration: str = "1h",
                             reason: str = "", **_):
        """Aplica un lavado de boca a un usuario."""
        member, err = self._require_member(user_id)
        if err:
            return err
        if member.bot:
            return {"error": "No se puede lavar la boca a un bot."}
        if member.id == self.guild.owner_id:
            return {"error": "No se puede lavar la boca al dueno del servidor."}
        td, err = self._require_duration(duration)
        if err:
            return err
        release_at = discord.utils.utcnow() + td
        release_at_str = release_at.isoformat()
        if self.db:
            await self.db.add_mouth_wash(
                guild_id=self.guild.id,
                user_id=member.id,
                release_at=release_at_str,
                reason=reason or "Lavado de boca por Fairy",
                created_by=None,
                display_name=member.display_name,
            )
            await self.db.log_action(
                self.guild.id, "mouth_wash", target_id=member.id,
                details={"reason": reason, "duration": duration},
            )
        return {
            "success": True,
            "washed_user": str(member),
            "user_id": str(member.id),
            "duration": duration,
            "release_at": release_at_str,
        }

    async def _do_unwash_mouth(self, user_id: str, **_):
        """Libera a un usuario del lavado de boca."""
        member = self._get_member(user_id)
        removed = False
        if self.db:
            removed = await self.db.remove_mouth_wash(self.guild.id, int(user_id))
            if removed:
                await self.db.log_action(
                    self.guild.id, "unwash_mouth", target_id=int(user_id),
                )
        msg = str(member) if member else f"User {user_id}"
        if removed:
            return {"success": True, "unwashed": msg, "was_washed": True}
        return {"success": True, "unwashed": msg, "was_washed": False}

    async def _do_list_mouth_washed(self, **_):
        """Lista todos los lavados de boca activos en el servidor."""
        if not self.db:
            return {"error": "DB no disponible"}
        washes = await self.db.get_active_mouth_washes(self.guild.id)
        result = []
        for w in washes:
            m = self._get_member(w["user_id"])
            result.append({
                "user_id": str(w["user_id"]),
                "display_name": m.display_name if m else "Unknown",
                "release_at": w["release_at"],
                "reason": w.get("reason", ""),
            })
        return {"count": len(result), "mouth_washed_users": result}

    # ── MACRO-TOOLS ──────────────────────────────────────────────────────

    async def _do_send_user_content_to_channel(self, user_name: str,
                                                channel_name: str,
                                                content_type: str = "avatar", **_):
        """Macro: busca usuario + canal + envía embed con avatar/banner."""
        # Resolver usuario
        user_result = await self._do_get_user_by_name(name=user_name, context="basic")
        if "error" in user_result:
            return user_result

        # Resolver canal
        ch_result = await self._do_find_channel(name=channel_name)
        if not ch_result.get("matches"):
            return {"error": f"Canal '{channel_name}' no encontrado."}

        channel_id = ch_result["matches"][0]["channel_id"]
        ch = self._resolve_channel(channel_id)

        # Obtener URL
        uid = int(user_result["user_id"])
        member = self._get_member(uid)
        display = user_result.get("display_name", user_name)

        if content_type == "banner":
            if member and member.banner:
                url = member.banner.url
            else:
                return {"error": f"{display} no tiene banner."}
        else:
            url = user_result.get("avatar_url", "")
            if not url and member:
                url = member.display_avatar.url

        if not url:
            return {"error": f"No se encontró {content_type} de {display}."}

        # Enviar embed
        import discord
        embed = discord.Embed(title=f"{content_type.capitalize()} de {display}")
        embed.set_image(url=url)
        msg = await ch.send(embed=embed)
        return {"success": True, "message_id": str(msg.id),
                "channel": ch.name, "user": display, "content_type": content_type}

    async def _do_bulk_channel_action(self, channel_ids: str, action: str,
                                       value: str = "0", **_):
        """Macro: ejecuta lock/unlock/slowmode en múltiples canales."""
        ids = [cid.strip() for cid in str(channel_ids).split(",") if cid.strip()]
        if not ids:
            return {"error": "No se proporcionaron channel_ids."}

        action = action.lower().strip()
        results = []
        for cid in ids[:20]:  # máx 20 canales
            ch = self._resolve_channel(cid)
            if not hasattr(ch, "set_permissions"):
                results.append({"channel_id": cid, "error": "No es canal de texto"})
                continue
            try:
                if action == "lock":
                    await ch.set_permissions(self.guild.default_role, send_messages=False)
                elif action == "unlock":
                    await ch.set_permissions(self.guild.default_role, send_messages=True)
                elif action == "slowmode":
                    await ch.edit(slowmode_delay=int(value or 0))
                results.append({"channel_id": cid, "name": ch.name, "success": True})
            except Exception as e:
                results.append({"channel_id": cid, "error": str(e)})

        ok = sum(1 for r in results if r.get("success"))
        return {"action": action, "total": len(ids), "success": ok, "results": results}

    # ── Knowledge Base Tools ──────────────────────────────────────────────

    async def _do_knowledge_search(self, query: str, limit: str = "5", **_):
        """Search the knowledge base."""
        lim = min(int(limit or 5), 10)
        results = await self.db.kb_search(self.guild.id, query, limit=lim)
        if not results:
            return {"results": [], "count": 0, "hint": "No se encontró nada. Intenta con otros términos."}
        return {
            "count": len(results),
            "results": [
                {"key": r["key"], "content": r["content"][:400], "tags": r.get("tags", "")}
                for r in results
            ],
        }

    async def _do_knowledge_store(self, key: str, content: str, tags: str = "", **_):
        """Store new knowledge entry."""
        if len(content) > 500:
            content = content[:500]
        key = key.strip().lower().replace(" ", "_")[:80]
        # Check if exists
        existing = await self.db.kb_get(self.guild.id, key)
        if existing:
            return {"error": f"La key '{key}' ya existe. Usa knowledge_update para modificarla."}
        row_id = await self.db.kb_store(
            self.guild.id, key, content, tags=tags, scope="guild",
            author_id=self._author_id or 0,
        )
        return {"success": True, "id": row_id, "key": key, "message": f"Guardado: '{key}'"}

    async def _do_knowledge_update(self, key: str, content: str, tags: str = "", **_):
        """Update existing knowledge entry."""
        if len(content) > 500:
            content = content[:500]
        key = key.strip().lower().replace(" ", "_")[:80]
        updated = await self.db.kb_update(
            self.guild.id, key, content, tags=tags if tags else None,
        )
        if not updated:
            return {"error": f"No existe entrada con key '{key}'. Usa knowledge_store para crear una nueva."}
        return {"success": True, "key": key, "message": f"Actualizado: '{key}'"}

    async def _do_knowledge_delete(self, key: str, **_):
        """Delete knowledge entry."""
        key = key.strip().lower().replace(" ", "_")[:80]
        deleted = await self.db.kb_delete(self.guild.id, key)
        if not deleted:
            return {"error": f"No existe entrada con key '{key}'."}
        return {"success": True, "key": key, "message": f"Eliminado: '{key}'"}

    # ── Birthday Tools ────────────────────────────────────────────────────

    async def _do_register_birthday(self, user_id: str, day: str, month: str, name: str = "", **_):
        """Register a birthday via the Birthdays cog."""
        cog = self._bot_ref.get_cog("Birthdays") if self._bot_ref else None
        if not cog:
            return {"error": "Sistema de cumpleaños no disponible."}
        try:
            uid = int(user_id)
            d, m = int(day), int(month)
        except (ValueError, TypeError):
            return {"error": "user_id, day y month deben ser números."}
        return await cog.register_birthday(self.guild.id, uid, d, m, name)

    async def _do_get_birthdays(self, month: str = "", **_):
        """Get birthdays list."""
        cog = self._bot_ref.get_cog("Birthdays") if self._bot_ref else None
        if not cog:
            return {"error": "Sistema de cumpleaños no disponible."}
        if month:
            try:
                m = int(month)
            except ValueError:
                return {"error": "month debe ser un número 1-12."}
            rows = await cog.get_birthdays_month(self.guild.id, m)
        else:
            rows = await cog.get_all_birthdays(self.guild.id)
        if not rows:
            return {"count": 0, "birthdays": [], "message": "No hay cumpleaños registrados."}
        return {
            "count": len(rows),
            "birthdays": [
                {"user_id": r["user_id"], "day": r["day"], "month": r["month"], "name": r.get("name", "")}
                for r in rows
            ],
        }

    # ── Shop / Redeemables Tools ──────────────────────────────────────────

    async def _do_shop_create(self, name: str, price: str, type: str,
                              description: str = "", payload: str = "{}",
                              stock: str = "-1", duration_hours: str = "0",
                              category: str = "", **_):
        """Create a shop item (staff only)."""
        if not self._is_staff():
            return {"error": "Solo staff puede crear items."}
        try:
            p = int(price)
            s = int(stock or -1)
            dh = int(duration_hours or 0)
        except ValueError:
            return {"error": "price, stock y duration_hours deben ser números."}
        if p < 1:
            return {"error": "El precio debe ser >= 1."}
        item_type = type
        if item_type not in ("role", "coupon"):
            return {"error": "type debe ser 'role' o 'coupon'."}
        item_id = await self.db.shop_create(
            self.guild.id, name, p, item_type, description=description,
            payload=payload, stock=s, duration_hours=dh,
            category=category, created_by=self._author_id or 0,
        )
        dur_info = f", duración: {dh}h (acumulable)" if dh > 0 else ", permanente"
        return {"success": True, "item_id": item_id, "name": name, "price": p,
                "type": item_type, "duration_hours": dh, "category": category, "info": dur_info}

    async def _do_shop_list(self, show_all: str = "", category: str = "", offset: str = "0", limit: str = "20", search: str = "", **_):
        """List shop items with pagination and search."""
        active_only = show_all.lower() not in ("true", "1", "si", "sí")
        off = max(0, int(offset or 0))
        lim = min(50, int(limit or 20))
        q = "SELECT * FROM shop_items WHERE guild_id = ?"
        params: list = [self.guild.id]
        if active_only:
            q += " AND active = 1"
        if category:
            q += " AND category = ?"
            params.append(category)
        q += " ORDER BY name"
        items = await self.db.fetch(q, tuple(params))
        # Unicode-normalized search (matches "Vivian" to "𝕍𝕚𝕧𝕚𝕒𝕟")
        if search:
            import unicodedata
            needle = unicodedata.normalize("NFKC", search).lower()
            items = [i for i in items if needle in unicodedata.normalize("NFKC", i["name"]).lower()]
        items = items[off:off + lim]
        if not items:
            return {"count": 0, "items": [], "message": "No hay items." if off == 0 else "No más items."}
        return {
            "count": len(items),
            "offset": off,
            "items": [
                {"id": i["id"], "name": i["name"], "price": i["price"],
                 "type": i["type"], "description": i["description"][:100],
                 "stock": i["stock"], "redeemed": i["redeemed_count"], "active": bool(i["active"]),
                 "duration_hours": i.get("duration_hours", 0), "category": i.get("category", "")}
                for i in items
            ],
        }

    async def _do_shop_redeem(self, item_id: str, user_id: str, **_):
        """Redeem a shop item for a user."""
        try:
            iid, uid = int(item_id), int(user_id)
        except ValueError:
            return {"error": "item_id y user_id deben ser números."}
        ok, msg = await self.db.shop_redeem(self.guild.id, uid, iid)
        if not ok:
            return {"error": msg}
        # Refund the 300cr LLM call cost since user is spending on the shop
        await self.db.add_credits(uid, self.guild.id, 300)
        # Apply reward
        item = await self.db.shop_get(iid)
        import json
        payload = json.loads(item["payload"] or "{}")
        reward_msg = msg

        if item["type"] == "role":
            role_ids = payload.get("role_ids", [])
            member = self.guild.get_member(uid)
            if member and role_ids:
                for rid in role_ids:
                    role = self.guild.get_role(int(rid))
                    if role:
                        try:
                            await member.add_roles(role)
                        except Exception:
                            pass
                reward_msg += f" Roles asignados: {len(role_ids)}"

        elif item["type"] == "coupon":
            import discord, hashlib, time
            # Generate verification code
            raw = f"{uid}:{item_id}:{int(time.time())}:youkai_cert"
            code = hashlib.sha256(raw.encode()).hexdigest()[:12].upper()
            code_fmt = f"{code[:4]}-{code[4:8]}-{code[8:]}"

            em = discord.Embed(
                title=f"🎟️ Cupón: {item['name']}",
                description=payload.get("message", "Cupón canjeado"),
                color=0xE9C46A,
            )
            em.add_field(name="Usuario", value=f"<@{uid}>", inline=True)
            em.add_field(name="Precio pagado", value=f"{item['price']:,} cr", inline=True)
            em.add_field(name="Código de verificación", value=f"`{code_fmt}`", inline=False)
            em.set_footer(text=f"Certificado Y O U K A I · ID: {item_id}-{uid}")

            # Send to user
            member = self.guild.get_member(uid)
            if member:
                try:
                    await member.send(embed=em)
                except Exception:
                    pass

            # Send to Aris
            aris = self.guild.get_member(239550977638793217)
            if aris:
                try:
                    await aris.send(embed=em)
                except Exception:
                    pass
            reward_msg += f" Cupón certificado enviado. Código: {code_fmt}"

        return {"success": True, "message": reward_msg, "item": item["name"], "price": item["price"]}

    async def _do_shop_manage(self, item_id: str, action: str, fields: str = "{}", **_):
        """Manage shop items (staff only)."""
        if not self._is_staff():
            return {"error": "Solo staff puede gestionar items."}
        try:
            iid = int(item_id)
        except ValueError:
            return {"error": "item_id debe ser número."}

        if action == "toggle":
            item = await self.db.shop_get(iid)
            if not item:
                return {"error": "Item no encontrado."}
            new_state = not bool(item["active"])
            await self.db.shop_toggle(iid, new_state)
            return {"success": True, "item_id": iid, "active": new_state}
        elif action == "delete":
            ok = await self.db.shop_delete(iid)
            return {"success": ok, "message": "Eliminado." if ok else "No encontrado."}
        elif action == "update":
            import json
            try:
                f = json.loads(fields) if fields else {}
            except Exception:
                return {"error": "fields debe ser JSON válido."}
            ok = await self.db.shop_update(iid, **f)
            return {"success": ok, "message": "Actualizado." if ok else "Sin cambios."}
        return {"error": f"Acción '{action}' no válida. Usa: toggle, delete, update."}

    async def _do_shop_bulk_create(self, role_query: str, price: str,
                                    duration_hours: str = "0", description: str = "", **_):
        """Bulk create shop items from matching roles."""
        if not self._is_staff():
            return {"error": "Solo staff puede crear items."}
        try:
            p = int(price)
            dh = int(duration_hours or 0)
        except ValueError:
            return {"error": "price y duration_hours deben ser números."}
        query = role_query.strip().lower()
        matches = [r for r in self.guild.roles if query in r.name.lower() and not r.is_default() and not r.managed]
        if not matches:
            return {"error": f"No se encontraron roles con '{role_query}'."}
        import json
        created = []
        for role in matches:
            payload = json.dumps({"role_ids": [str(role.id)]})
            item_id = await self.db.shop_create(
                self.guild.id, role.name, p, "role", description=description,
                payload=payload, stock=-1, duration_hours=dh, created_by=self._author_id or 0,
            )
            created.append({"id": item_id, "name": role.name})
        return {"success": True, "created": len(created), "price": p,
                "duration_hours": dh, "items": created[:10],
                "note": f"({len(created)} total)" if len(created) > 10 else ""}

    async def _do_economy_stats(self, **_):
        """Get economy stats."""
        stats = await self.db.economy_stats(self.guild.id)
        # Add treasury info
        try:
            row = await self.db.fetchone(
                "SELECT balance, total_collected, total_disbursed, total_lost_defaults "
                "FROM guild_treasury WHERE guild_id=?", (self.guild.id,)
            )
            if row:
                stats["treasury"] = {
                    "pool": row["balance"],
                    "collected": row["total_collected"],
                    "disbursed": row["total_disbursed"],
                    "lost": row["total_lost_defaults"],
                }
        except Exception:
            pass
        return stats

    def _is_staff(self) -> bool:
        """Check if the message author is staff (manage_guild or owner)."""
        if not self._author_id:
            return False
        member = self.guild.get_member(self._author_id)
        if not member:
            return False
        return member.guild_permissions.manage_guild or member.id == self.guild.owner_id

    # ── Music Tools ───────────────────────────────────────────────────────

    async def _do_play_music(self, query: str, user_id: str, **_):
        """Play music via Lavalink."""
        cog = self._bot_ref.get_cog("MusicCog") if self._bot_ref else None
        if not cog:
            return {"error": "Sistema de música no disponible."}
        try:
            uid = int(user_id)
        except (ValueError, TypeError):
            return {"error": "user_id debe ser un número."}
        member = self.guild.get_member(uid)
        if not member:
            try:
                member = await self.guild.fetch_member(uid)
            except Exception:
                pass
        if not member or not member.voice or not member.voice.channel:
            return {"error": "El usuario no está en un canal de voz."}
        try:
            requester = f"@{member.display_name}"
            logger.info("play_music: user=%s (id=%s)", requester, uid)
            return await cog.play_track(self.guild, member.voice.channel, query, requester, uid)
        except Exception as e:
            return {"error": f"Error reproduciendo: {str(e)[:100]}"}

    async def _do_music_queue(self, **_):
        """Get current music queue."""
        cog = self._bot_ref.get_cog("MusicCog") if self._bot_ref else None
        if not cog:
            return {"error": "Sistema de música no disponible."}
        return cog.get_queue_info(self.guild)


# ── Exportaciones del módulo ──────────────────────────────────────────────────
__all__ = ["DJINN_TOOL", "YOUKAI_TOOL", "ToolExecutor", "FORBIDDEN"]
"""Cog: DreamQuest — La Travesía Onírica a Kadath.

Motor determinista de aventura de texto. El JSON y las plantillas de voz son
el "blueprint" autor-generado; en runtime este cog solo lee, evalúa y avanza.

- Sin HP de combate.
- Sin eventos aleatorios que castiguen por explorar.
- 12 finales, ninguno temprano (todos requieren Acto 4+).
- Voces únicas por personaje basadas en los perfiles destilados de data/personas.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.kadath_gamestate import (
    CHARACTER_DATA,
    PASSIVE_META,
    SERVER_NPCS,
    STATS,
    STAT_EMOJI,
    STAT_NAMES_ES,
    GameState,
    collect_ending_memories,
    get_item_lore,
    initial_npc_trust_from_persona,
    load_player_persona,
    pick_npc_memory_line,
    pick_npc_reaction_to_player,
    pick_voice_line,
    resolve_node_text,
    state_tag,
    untrustworthy_filter,
)

logger = logging.getLogger("djinn.kadath")

# ── Paths anclados al módulo (sobreviven a cwd distintos) ────────────────────

_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
WORLD_PATH: Path = _PROJECT_ROOT / "data" / "kadath_world.json"
SAVES_DIR: Path = _PROJECT_ROOT / "data" / "kadath_saves"


# ── Paleta de color por estado mental ────────────────────────────────────────

COLOR_CALM     = 0x3A8DDE
COLOR_AWE      = 0x7D5FFF
COLOR_TENSE    = 0xE6B800
COLOR_HORROR   = 0xB00020
COLOR_ENDING   = 0x111111

CHARACTER_EMOJI: Dict[str, str] = {
    "ARIS":     "🔮",
    "LAW":      "🎵",
    "HARU":     "🌀",
    "ELYKO":    "♟️",
    "XOFT":     "🩸",
    "XOKRAM":   "💰",
    "DARAZIEL": "📐",
}


def _mood_color(state: GameState) -> int:
    tag = state_tag(state)
    return {
        "awe":    COLOR_AWE,
        "calm":   COLOR_CALM,
        "tense":  COLOR_TENSE,
        "horror": COLOR_HORROR,
    }.get(tag, COLOR_CALM)


# ── Costo e invocación del DM ────────────────────────────────────────────────

COST_KADATH = 600  # créditos del servidor para iniciar una nueva travesía


# ── Character Select ─────────────────────────────────────────────────────────

class CharacterSelectView(discord.ui.View):
    """Menú de selección al comenzar una nueva travesía."""

    def __init__(self, cog: "DreamQuestCog", user_id: int, *, timeout: float = 90.0):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user_id = user_id

        options: List[discord.SelectOption] = []
        for cid, data in CHARACTER_DATA.items():
            emoji = CHARACTER_EMOJI.get(cid, "⚔️")
            options.append(discord.SelectOption(
                label=f"{cid.title()} — {data['class']}",
                value=cid,
                emoji=emoji,
                description=data["title"][:100],
            ))

        select = discord.ui.Select(
            placeholder="🌌 ¿Quién desciende al sueño?",
            options=options,
            custom_id="kadath_char_select",
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.user_id:
            try:
                await interaction.response.send_message(
                    "🌌 Esta elección no te pertenece.", ephemeral=True)
            except discord.HTTPException:
                pass
            return

        try:
            character_id = interaction.data["values"][0]
            state = GameState.create(self.user_id, character_id)

            # Eje 7: inyectar arquetipo destilado del jugador si existe perfil
            persona = self.cog.get_persona(self.user_id)
            if persona:
                if persona.get("arquetipo"):
                    state.player_archetype = persona["arquetipo"]
                # Trust inicial: aliados/enemigos del jugador real
                initial_trust = initial_npc_trust_from_persona(persona)
                for npc, delta in initial_trust.items():
                    state.modify_npc_trust(npc, delta)

            world = self.cog.load_world()

            # Asegurar que el nodo raíz existe.
            root = world.get(state.current_node)
            if not root:
                # Intentar encontrar un nodo marcado como "is_start"
                for nid, n in world.items():
                    if n.get("is_start"):
                        state.current_node = nid
                        state.zone = n.get("zone", state.zone)
                        root = n
                        break
            if not root:
                await interaction.response.send_message(
                    "🌀 El tejido del sueño está roto. Avisa al Arquitecto.",
                    ephemeral=True)
                return

            state.zone = root.get("zone", state.zone)
            self.cog.save_game(state)

            view = KadathView(state, root, world, self.cog)
            embed = self.cog._build_embed(state, root)
            await interaction.response.edit_message(
                content=None, embed=embed, view=view)
        except Exception as e:
            logger.error("Error en selección de personaje: %s", e, exc_info=True)
            try:
                await interaction.response.send_message(
                    f"⚠️ Error al iniciar: `{e}`", ephemeral=True)
            except discord.HTTPException:
                pass

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True


# ── KadathView ───────────────────────────────────────────────────────────────

_STYLE_MAP: Dict[str, discord.ButtonStyle] = {
    "primary":   discord.ButtonStyle.primary,
    "secondary": discord.ButtonStyle.secondary,
    "info":      discord.ButtonStyle.secondary,
    "success":   discord.ButtonStyle.success,
    "warning":   discord.ButtonStyle.danger,
    "danger":    discord.ButtonStyle.danger,
}


class KadathView(discord.ui.View):
    """Renderiza los botones del nodo actual."""

    def __init__(self, state: GameState, node: Dict[str, Any],
                 world: Dict[str, Any], cog: "DreamQuestCog",
                 *, timeout: float = 300.0):
        super().__init__(timeout=timeout)
        self.state = state
        self.node = node
        self.world = world
        self.cog = cog
        self._handled = False
        self._lock = asyncio.Lock()

        cid = state.character_id
        paths: List[Dict[str, Any]] = list(node.get("paths", []) or [])

        # ── Pasiva DARAZIEL: hidden_paths siempre visibles ────────────
        if cid == "DARAZIEL":
            for h in (node.get("hidden_paths") or []):
                if isinstance(h, dict):
                    paths.append({
                        **h,
                        "label": f"✦ {h.get('label', 'Ruta oculta')}",
                        "style": h.get("style", "info"),
                    })

        # ── Pasiva DARAZIEL: fallback_target como salida extra ────────
        if cid == "DARAZIEL":
            ft = node.get("fallback_target")
            if ft and ft in world and not any(p.get("target") == ft for p in paths):
                paths.append({
                    "label": f"📐 Replegar: {world[ft].get('zone', ft)}"[:80],
                    "target": ft,
                    "style": "secondary",
                })

        # ── Pasiva XOFT: opción 'Provocar' si hay primary_npc ─────────
        if cid == "XOFT":
            npc = node.get("primary_npc") or node.get("hostile_npc")
            nid = node.get("id") or state.current_node
            if npc and not state.has_flag(f"xoft_provoked:{nid}") and not any(
                p.get("target") and "provocar" in (p.get("label", "").lower())
                for p in paths
            ):
                trust_delta = -2 if node.get("hostile_npc") else 2
                paths.append({
                    "label": f"🩸 Provocar a {npc}"[:80],
                    "target": nid,
                    "style": "warning",
                    "effects": {},
                    "_is_xoft_provoke": True,
                    "_npc": npc,
                    "_trust_delta": trust_delta,
                })

        # ── Pasiva ELYKO: ha eliminado el "ver deltas gratis". Ahora ELYKO
        # solo ve el resultado de rutas que YA tomó en una visita anterior
        # (renderizado en _build_embed, no aquí). Esta sección se vacía
        # intencionalmente: los tradeoffs de ELYKO viven en apply_passives.

        # ── Botones de rutas ──────────────────────────────────────────
        row_idx = 0
        any_visible = False
        for i, path in enumerate(paths):
            conds = path.get("conditions") or {}

            # HARU: no puede elegir rutas 'success' en nodos 'horror'
            if (cid == "HARU" and node.get("tone") == "horror"
                    and path.get("style") == "success"):
                # La risa absurda le cierra el camino noble
                label = f"🚫 {path.get('label', '?')} (la risa te aleja)"
                btn = discord.ui.Button(
                    label=label[:80], style=discord.ButtonStyle.secondary,
                    row=row_idx // 3, disabled=True,
                    custom_id=f"kadath_haru_blocked_{i}_{row_idx}",
                )
                self.add_item(btn)
                row_idx += 1
                continue

            if not state.meets_conditions(conds):
                if not path.get("show_locked"):
                    continue
                label = f"🔒 {path.get('label', '?')}"
                btn = discord.ui.Button(
                    label=label[:80], style=discord.ButtonStyle.secondary,
                    row=row_idx // 3, disabled=True,
                    custom_id=f"kadath_locked_{i}_{row_idx}",
                )
                self.add_item(btn)
                row_idx += 1
                continue

            label = path.get("label", f"Camino {i+1}")

            style = _STYLE_MAP.get(path.get("style", "primary"),
                                   discord.ButtonStyle.primary)
            target = path.get("target", "")
            any_visible = True

            btn = discord.ui.Button(
                label=label[:80], style=style, row=row_idx // 3,
                custom_id=f"kadath_path_{i}_{row_idx}",
            )
            btn.callback = self._make_path_callback(target, path)
            self.add_item(btn)
            row_idx += 1

        # ── Botón de info/stats (siempre presente) ────────────────────
        info_btn = discord.ui.Button(
            label=f"🎒 {len(state.inventory)}/{state.item_slots}  ·  📊 stats",
            style=discord.ButtonStyle.secondary,
            row=4,
            custom_id="kadath_info",
        )
        info_btn.callback = self._make_info_callback()
        self.add_item(info_btn)

        # ── Si no hay rutas visibles y no es ending → salida de emergencia ──
        if not any_visible and not node.get("is_ending"):
            # 1) fallback_target explícito del nodo
            fallback_target = node.get("fallback_target")
            # 2) si no, intenta volver al último nodo visitado distinto del actual
            if not fallback_target or fallback_target not in world:
                current_nid = node.get("id") or state.current_node
                for prev in reversed(state.visited):
                    if prev != current_nid and prev in world:
                        fallback_target = prev
                        break
            # 3) último recurso: cualquier hub conocido con "hub" en el id
            if not fallback_target:
                for nid in world:
                    if "hub" in nid and nid in state.visited:
                        fallback_target = nid
                        break

            if fallback_target and fallback_target in world:
                zone_name = world[fallback_target].get("zone", "atrás")
                eb = discord.ui.Button(
                    label=f"🌀 Marcharte — {zone_name}"[:80],
                    style=discord.ButtonStyle.secondary,
                    row=0,
                    custom_id="kadath_fallback",
                )
                eb.callback = self._make_path_callback(
                    fallback_target,
                    {"label": "Marcharte", "style": "secondary",
                     "effects": {"favor": -1}}  # marcharse sin hacer nada cuesta
                )
                self.add_item(eb)

    # ── Callbacks ─────────────────────────────────────────────────────

    def _is_owner(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.state.user_id

    async def _deny(self, interaction: discord.Interaction, msg: str) -> None:
        try:
            await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            pass

    def _make_path_callback(self, target: str, path: Dict[str, Any]):
        async def cb(interaction: discord.Interaction) -> None:
            if not self._is_owner(interaction):
                await self._deny(interaction, "🌌 Esta no es tu travesía.")
                return
            async with self._lock:
                if self._handled:
                    return
                self._handled = True
            try:
                await interaction.response.defer()
            except discord.HTTPException:
                return

            # Caso especial: XOFT Provocar (no transición, solo efecto en NPC)
            if path.get("_is_xoft_provoke"):
                npc = path.get("_npc")
                trust_delta = int(path.get("_trust_delta", 0))
                if npc:
                    self.state.modify_npc_trust(npc, trust_delta)
                nid = self.node.get("id") or self.state.current_node
                self.state.add_flag(f"xoft_provoked:{nid}")
                hint = (self.node.get("ability_hints") or {}).get("XOFT") or \
                       (self.node.get("ability_hints") or {}).get("provocacion") or \
                       f"la máscara de {npc} se agrieta un segundo."
                self.cog.save_game(self.state)
                embed = self.cog._build_embed(self.state, self.node)
                embed.add_field(
                    name=f"🩸 Provocas a {npc}",
                    value=f"> *{hint}*\n\nTrust ({npc}): {self.state.npc_trust.get(npc, 0):+d}"[:1024],
                    inline=False,
                )
                new_view = KadathView(self.state, self.node, self.world, self.cog)
                try:
                    await interaction.edit_original_response(embed=embed, view=new_view)
                except discord.HTTPException:
                    await interaction.followup.send(embed=embed, view=new_view)
                return

            await self.cog._advance_to_node(interaction, self.state, target, path)
        return cb

    def _make_info_callback(self):
        async def cb(interaction: discord.Interaction) -> None:
            if not self._is_owner(interaction):
                await self._deny(interaction, "🌌 Información privada del soñador.")
                return
            embed = self.cog._build_stats_embed(self.state)
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except discord.HTTPException:
                pass
        return cb

    async def on_timeout(self) -> None:
        for child in self.children:
            try:
                child.disabled = True
            except Exception:
                pass


# ── Cog ──────────────────────────────────────────────────────────────────────

class DreamQuestCog(commands.Cog):
    """El motor de la Travesía Onírica a Kadath."""

    def __init__(self, bot) -> None:
        self.bot = bot
        self._world_cache: Optional[Dict[str, Any]] = None
        self._world_mtime: float = 0.0
        self._save_locks: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._persona_cache: Dict[int, Optional[Dict[str, Any]]] = {}
        # Usuarios a los que ya se les envió el recordatorio de "sólo botones"
        self._dm_reminded: set = set()
        SAVES_DIR.mkdir(parents=True, exist_ok=True)

    def get_persona(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Cache de persona del jugador (se carga una vez por sesión)."""
        if user_id not in self._persona_cache:
            self._persona_cache[user_id] = load_player_persona(user_id, _PROJECT_ROOT)
        return self._persona_cache[user_id]

    async def _open_dm(self, user: discord.User) -> Optional[discord.DMChannel]:
        """Abre/obtiene el DM del usuario. Devuelve None si está cerrado."""
        try:
            dm = user.dm_channel or await user.create_dm()
            return dm
        except (discord.Forbidden, discord.HTTPException):
            return None

    async def _is_staff(self, interaction: discord.Interaction) -> bool:
        """True si el usuario tiene nivel de MOD o superior en el servidor.

        El staff no paga por iniciar aventuras porque no gana créditos pasivamente.
        """
        if not interaction.guild:
            return False
        member = interaction.user
        if not isinstance(member, discord.Member):
            return False
        db = getattr(self.bot, "db", None)
        if db is None:
            return False
        try:
            from utils.security import get_perm_level, PermLevel
            level = await get_perm_level(member, db)
            return level >= PermLevel.MOD
        except Exception as e:
            logger.warning("No pude chequear staff para %s: %s", member.id, e)
            return False

    async def _charge_kadath(
        self, interaction: discord.Interaction, amount: int = COST_KADATH,
    ) -> bool:
        """Intenta cobrar el costo de Kadath al guild actual. True si OK.

        Staff (MOD+) pasa gratis.
        """
        if not interaction.guild:
            return False
        # Staff: gratis
        if await self._is_staff(interaction):
            return True
        db = getattr(self.bot, "db", None)
        if db is None:
            # Sin DB disponible: no cobramos (dev mode)
            return True
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        info = await db.get_credits(user_id, guild_id)
        if info["balance"] < amount:
            return False
        await db.spend_credits(user_id, guild_id, amount)
        return True

    async def _refund_kadath(
        self, interaction: discord.Interaction, amount: int = COST_KADATH,
    ) -> None:
        """Reembolsa el costo si algo salió mal después de cobrar.

        Staff (MOD+) nunca pagó, así que no se les reembolsa nada.
        """
        if not interaction.guild:
            return
        if await self._is_staff(interaction):
            return
        db = getattr(self.bot, "db", None)
        if db is None:
            return
        await db.add_credits(interaction.user.id, interaction.guild.id, amount)

    # ── Listener DM: bloquea cualquier interacción que no sea botón ──────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """En DMs, el bot NO responde a texto. Sólo botones del embed.

        Aquí únicamente enviamos un recordatorio UNA vez por partida si el
        usuario intenta escribir algo, para que sepa cómo continuar.
        """
        # Solo en DMs; solo de humanos; solo si hay partida guardada
        if message.author.bot or message.guild is not None:
            return
        user_id = message.author.id
        if not self._save_path(user_id).exists():
            return
        # Una sola vez por proceso (se resetea al reiniciar el bot)
        if user_id in self._dm_reminded:
            return
        self._dm_reminded.add(user_id)
        try:
            await message.channel.send(
                "🌌 *En la Travesía, sólo respondo a los botones del embed.*\n"
                "Si no ves tu última escena, usa `/aventura continuar` en el "
                "servidor y te la envío de nuevo.",
            )
        except discord.HTTPException:
            pass

    # ── Persistencia ─────────────────────────────────────────────────────

    def _save_path(self, user_id: int) -> Path:
        return SAVES_DIR / f"{user_id}.json"

    def load_game(self, user_id: int) -> Optional[GameState]:
        path = self._save_path(user_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return GameState.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Save corrupto para %s: %s", user_id, e)
            return None

    def save_game(self, state: GameState) -> None:
        path = self._save_path(state.user_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(state.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        tmp.replace(path)

    def load_world(self) -> Dict[str, Any]:
        """Carga (y cachea por mtime) el JSON del mundo."""
        try:
            mtime = WORLD_PATH.stat().st_mtime
        except FileNotFoundError:
            logger.error("kadath_world.json no encontrado: %s", WORLD_PATH)
            return {}

        if self._world_cache is not None and mtime == self._world_mtime:
            return self._world_cache

        try:
            self._world_cache = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
            self._world_mtime = mtime
            logger.info("Mundo Kadath cargado: %d nodos", len(self._world_cache))
            return self._world_cache
        except json.JSONDecodeError as e:
            logger.error("kadath_world.json corrupto: %s", e)
            return {}

    # ── Render ───────────────────────────────────────────────────────────

    def _build_embed(self, state: GameState, node: Dict[str, Any]) -> discord.Embed:
        color = COLOR_ENDING if node.get("is_ending") else _mood_color(state)
        zone = node.get("zone", state.zone)

        # Diálogo del personaje: primero mira el específico del nodo; si no,
        # usa la plantilla determinista por tag emocional.
        cid = state.character_id
        node_dialogue: Dict[str, str] = node.get("character_dialogue", {}) or {}
        specific = node_dialogue.get(cid.lower())
        if specific:
            line = specific
        else:
            tag = node.get("tone") or state_tag(state)
            line = pick_voice_line(cid, node.get("id", state.current_node), tag)

        description = f"> *\"{line}\"*\n\n"
        # Eje 1 — text_variants por estado + Eje 5 — narrador no confiable
        node_text = resolve_node_text(state, node)
        node_text = untrustworthy_filter(node_text, state)
        description += node_text

        embed = discord.Embed(title=f"🌌 {zone}", description=description[:4000], color=color)

        cdata = CHARACTER_DATA.get(cid, {})
        emoji = CHARACTER_EMOJI.get(cid, "⚔️")
        embed.set_author(
            name=f"{emoji} {cid.title()} — {cdata.get('title', cdata.get('class', '?'))}"
        )

        # Bonus de clase (si el nodo tiene y aplica a esta clase)
        class_bonus: Dict[str, str] = node.get("class_bonus", {}) or {}
        my_class = cdata.get("class", "")
        bonus_txt = class_bonus.get(my_class) or class_bonus.get(my_class.replace("Ú","U").replace("Ó","O"))
        if bonus_txt:
            embed.add_field(
                name=f"🎯 Ventaja del {my_class}",
                value=bonus_txt[:1024],
                inline=False,
            )

        # Pistas automáticas por pasiva (ARIS/XOFT/DARAZIEL)
        hints: Dict[str, str] = node.get("ability_hints", {}) or {}
        revealed_hints: List[str] = []
        if cid == "ARIS":
            hint = hints.get("ARIS") or hints.get("lectura")
            if hint:
                revealed_hints.append(f"👁️ *{hint}*")
        if cid == "XOFT":
            hint = hints.get("XOFT") or hints.get("provocacion")
            if hint:
                revealed_hints.append(f"🩸 *{hint}*")
        if cid == "DARAZIEL":
            hint = hints.get("DARAZIEL") or hints.get("geometria")
            if hint:
                revealed_hints.append(f"📐 *{hint}*")
        if cid == "ELYKO":
            # ELYKO ve la memoria de visitas previas — cuántas veces y qué recuerda.
            nid_ = node.get("id") or state.current_node
            visits = state.visit_counts.get(nid_, 0)
            if visits >= 2:
                revealed_hints.append(
                    f"♟️ *Ya estuve aquí {visits-1} vez(es). Recuerdo el patrón: "
                    f"las consecuencias de mis elecciones pasadas siguen presentes en el estado actual.*"
                )
            else:
                revealed_hints.append(
                    "♟️ *Primera vez. Sin datos previos. Memorizo, ciego.*"
                )
        if revealed_hints:
            embed.add_field(
                name=f"⚡ {PASSIVE_META[cid]['name']}",
                value="\n".join(revealed_hints)[:1024],
                inline=False,
            )

        # Imagen de escena (opcional)
        image_url = node.get("embed_image")
        if image_url:
            embed.set_image(url=image_url)

        # Pie: stats compactos
        stats_short = (
            f"{STAT_EMOJI['voluntad']}{state.voluntad} "
            f"{STAT_EMOJI['lucidez']}{state.lucidez} "
            f"{STAT_EMOJI['favor']}{state.favor} "
            f"{STAT_EMOJI['corrupcion']}{state.corrupcion} "
            f"{STAT_EMOJI['lore']}{state.lore} "
            f"{STAT_EMOJI['memoria']}{state.memoria}"
        )
        act_label = f"Acto {state.act}"
        turn = f"T{state.turns_played}"
        embed.set_footer(text=f"{act_label}  ·  {stats_short}  ·  {turn}")

        # Avisos contextuales (no spam; solo en umbrales)
        warnings = []
        if state.voluntad <= 20:
            warnings.append("🛡️ Tu Voluntad flaquea — el sueño quiere disolverte.")
        if state.lucidez <= 20:
            warnings.append("🧠 Tu Lucidez se quiebra en los bordes.")
        if state.corrupcion >= 75:
            warnings.append("👁️ Nyarlathotep susurra tu nombre.")
        if state.memoria <= 20:
            warnings.append("🪞 Olvidas quién eras al despertar.")
        if warnings:
            embed.add_field(
                name="🔮 Susurros del Abismo",
                value="\n".join(warnings)[:1024],
                inline=False,
            )

        return embed

    def _build_stats_embed(self, state: GameState) -> discord.Embed:
        cdata = CHARACTER_DATA[state.character_id]
        emoji = CHARACTER_EMOJI.get(state.character_id, "⚔️")
        embed = discord.Embed(
            title=f"{emoji} {state.character_id.title()}",
            description=cdata.get("description", ""),
            color=_mood_color(state),
        )

        def _bar(val: int, width: int = 12) -> str:
            filled = int(round(val / 100 * width))
            return "█" * filled + "░" * (width - filled)

        stats_lines = []
        for s in STATS:
            v = getattr(state, s)
            stats_lines.append(f"{STAT_EMOJI[s]} **{STAT_NAMES_ES[s]}** `{_bar(v)}` {v}")
        embed.add_field(name="📊 Estado Interno", value="\n".join(stats_lines), inline=False)

        ab_line = (
            f"⚡ **{PASSIVE_META[state.character_id]['name']}** (pasiva)\n"
            f"*{PASSIVE_META[state.character_id]['short']}*\n\n"
            + "\n".join(f"• {eff}" for eff in PASSIVE_META[state.character_id]["effects"])
        )
        embed.add_field(name="Pasiva", value=ab_line[:1024], inline=False)

        if state.inventory:
            # Cada item muestra su nombre bonito + short. Si tiene lore,
            # se agrega una línea descriptiva por debajo.
            lines = []
            for item_id in state.inventory:
                meta = get_item_lore(item_id)
                if meta:
                    lines.append(f"**{meta['name']}** — *{meta['short']}*")
                else:
                    lines.append(f"`{item_id}`")
            inv_txt = "\n".join(lines)
        else:
            inv_txt = "*vacío*"
        embed.add_field(
            name=f"🎒 Inventario ({len(state.inventory)}/{state.item_slots})",
            value=inv_txt[:1024],
            inline=False,
        )

        if state.flags:
            # Oculta flags técnicos internos del display público
            public_flags = [
                f for f in sorted(state.flags)
                if not f.startswith("passive:") and not f.startswith("xoft_provoked:")
            ]
            if public_flags:
                embed.add_field(name="🏳️ Flags", value=", ".join(public_flags)[:1024], inline=False)

        if state.npc_trust:
            npc_lines = [f"{npc}: {v:+d}" for npc, v in sorted(state.npc_trust.items())]
            embed.add_field(name="🤝 NPCs", value="\n".join(npc_lines)[:1024], inline=False)

        if state.contracts_closed:
            embed.add_field(
                name="📜 Contratos cerrados",
                value=", ".join(state.contracts_closed)[:1024],
                inline=False,
            )

        embed.set_footer(text=f"Acto {state.act} · Turno {state.turns_played} · nodo {state.current_node}")
        return embed

    # ── Avance ───────────────────────────────────────────────────────────

    async def _advance_to_node(self, interaction: discord.Interaction,
                               state: GameState, target: str,
                               path_info: Dict[str, Any]) -> None:
        world = self.load_world()
        target_node = world.get(target)
        if not target_node:
            try:
                await interaction.followup.send(
                    f"🌀 El nodo `{target}` no existe en el tejido del sueño.",
                    ephemeral=True)
            except discord.HTTPException:
                pass
            return

        async with self._save_locks[state.user_id]:
            # 1) Aplicar efectos propios de la arista (path.effects) y consumos/otorgamientos de arista
            path_effects = dict(path_info.get("effects") or {})
            # Pasamos el estilo para que HARU pueda aplicar su pasiva en rutas danger
            path_effects["_style"] = path_info.get("style")
            state.apply_effects(path_effects)

            edge_consume = path_info.get("consume_item")
            if isinstance(edge_consume, str):
                state.take_item(edge_consume)
            elif isinstance(edge_consume, list):
                for it in edge_consume:
                    state.take_item(it)

            edge_give = path_info.get("give_item")
            if isinstance(edge_give, str):
                state.give_item(edge_give)
            elif isinstance(edge_give, list):
                for it in edge_give:
                    state.give_item(it)

            for fl in path_info.get("set_flags", []) or []:
                state.add_flag(fl)

            # 2) Entrar al nodo: advance + on_enter effects (solo primera visita)
            state.advance_turn(target)
            state.zone = target_node.get("zone", state.zone)
            state.act = int(target_node.get("act", state.act))

            # Anti-farm: on_enter solo primera visita
            state.apply_on_enter_once(
                target, target_node.get("on_enter") or {},
                style=path_info.get("style"),
            )

            # Pasivas del personaje (solo primera visita)
            state.apply_passives_on_node({**target_node, "id": target})

            # Umbrales de Insight / Corrupción: aplicar costos y capturar eventos
            threshold_events = state.process_thresholds()

            # 3) Item / flags / contratos otorgados por el nodo
            give_item = target_node.get("give_item")
            if isinstance(give_item, str):
                state.give_item(give_item)
            elif isinstance(give_item, list):
                for it in give_item:
                    state.give_item(it)

            consume_item = target_node.get("consume_item")
            if isinstance(consume_item, str):
                state.take_item(consume_item)
            elif isinstance(consume_item, list):
                for it in consume_item:
                    state.take_item(it)

            for fl in target_node.get("set_flags", []) or []:
                state.add_flag(fl)
            for fl in target_node.get("clear_flags", []) or []:
                state.flags.discard(fl)

            contract = target_node.get("close_contract")
            if contract:
                state.add_contract(contract)

            trust_changes = target_node.get("npc_trust") or {}
            for npc, delta in trust_changes.items():
                state.modify_npc_trust(npc, int(delta))

            # 4) ¿Es ending? Si sí, chequear si cumple prereqs.
            ending_id: Optional[str] = None
            if target_node.get("is_ending"):
                ending_id = target
            else:
                # Chequear forced_ending (p.ej. corrupción >= 100 en acto 5)
                force_ending = target_node.get("force_ending_if") or {}
                if force_ending and state.meets_conditions(force_ending):
                    ending_id = target_node.get("forced_ending_target")

            self.save_game(state)

        if ending_id:
            await self._render_ending(interaction, state, ending_id)
            return

        embed = self._build_embed(state, target_node)

        # Inyectar eventos narrativos de umbrales cruzados (insight/corruption)
        for ev in threshold_events:
            cost_txt = "  ".join(
                f"{STAT_EMOJI[s]}{v:+d}" for s, v in ev["cost"].items() if s in STAT_EMOJI
            )
            embed.add_field(
                name=ev["title"],
                value=f"{ev['narrative']}\n\n*Costo permanente:* {cost_txt}"[:1024],
                inline=False,
            )

        # Inyectar reacción contextual de NPCs.
        # Prioridad: Eje 4 (memoria específica por flag) > persona del jugador.
        npc_id = target_node.get("primary_npc") or target_node.get("hostile_npc")
        if npc_id:
            # Eje 4: el NPC recuerda flags específicos del jugador
            memory = pick_npc_memory_line(npc_id, state)
            if memory:
                npc_meta = SERVER_NPCS.get(npc_id) or {}
                display_name = npc_meta.get("dream_title") or npc_id.replace("_", " ").title()
                embed.add_field(
                    name=f"🎭 {display_name} (te recuerda)",
                    value=memory[:1024],
                    inline=False,
                )
            elif npc_id in SERVER_NPCS:
                # Fallback: reacción por arquetipo de persona del jugador
                persona = self.get_persona(interaction.user.id)
                reaction = pick_npc_reaction_to_player(npc_id, persona, target)
                if reaction:
                    embed.add_field(
                        name=f"🎭 {SERVER_NPCS[npc_id]['dream_title']}",
                        value=reaction[:1024],
                        inline=False,
                    )

        view = KadathView(state, target_node, world, self)
        try:
            await interaction.followup.send(embed=embed, view=view)
        except discord.HTTPException as e:
            logger.error("Error al enviar nodo %s: %s", target, e, exc_info=True)

    async def _render_ending(self, interaction: discord.Interaction,
                             state: GameState, ending_id: str) -> None:
        world = self.load_world()
        ending_node = world.get(ending_id, {})

        embed = discord.Embed(
            title=f"💀 {ending_node.get('zone', 'Final')}",
            description=ending_node.get(
                "text", "*El sueño se cierra y el mundo despierta sin ti.*"
            )[:4000],
            color=COLOR_ENDING,
        )
        cdata = CHARACTER_DATA.get(state.character_id, {})
        emoji = CHARACTER_EMOJI.get(state.character_id, "⚔️")
        embed.set_author(
            name=f"{emoji} {state.character_id.title()} — {cdata.get('title','?')}"
        )

        # Epílogo único por personaje, si el ending lo define.
        char_dialogue = ending_node.get("character_dialogue", {}) or {}
        my_line = char_dialogue.get(state.character_id.lower())
        if my_line:
            embed.add_field(name="🎭 Epílogo", value=f"> *\"{my_line}\"*"[:1024], inline=False)

        # Eje 3 — Epílogos dinámicos: los flags importantes del run aparecen
        # como recuerdos concretos del viaje.
        memories = collect_ending_memories(state, limit=6)
        if memories:
            memory_block = "\n".join(f"· {m}" for m in memories)
            embed.add_field(
                name="🪞 Recuerdos del viaje",
                value=memory_block[:1024],
                inline=False,
            )

        # Epitafio real del jugador (si el ending es oscuro)
        dark_endings = {"ending_vacio", "ending_olvido", "ending_trono_caos"}
        if ending_id in dark_endings:
            persona = self.get_persona(state.user_id)
            if persona and persona.get("como_moriria"):
                embed.add_field(
                    name="⚰️ Epitafio",
                    value=f"*{persona['como_moriria']}*"[:1024],
                    inline=False,
                )

        # Tarjeta de estadísticas finales
        stats_line = "  ·  ".join(
            f"{STAT_EMOJI[s]} {getattr(state, s)}" for s in STATS
        )
        embed.add_field(name="📊 Travesía", value=stats_line, inline=False)
        embed.set_footer(
            text=f"Acto {state.act} · {state.turns_played} turnos · "
                 f"{len(state.visited)} nodos visitados"
        )

        # Borra el save
        try:
            self._save_path(state.user_id).unlink(missing_ok=True)
        except OSError:
            pass

        try:
            await interaction.followup.send(embed=embed)
            await interaction.followup.send(
                "🌌 **Has despertado.** Usa `/aventura comenzar` para iniciar "
                "otra travesía con otro viajero.",
                ephemeral=True,
            )
        except discord.HTTPException as e:
            logger.error("Error al renderizar ending: %s", e)

    # ── Comando /aventura ────────────────────────────────────────────────

    @app_commands.command(
        name="aventura",
        description=(
            "🌌 Travesía Onírica a Kadath. Cuesta 600 créditos iniciar. "
            "La partida se juega en tus DMs."
        ),
    )
    @app_commands.describe(
        accion="'comenzar' nueva (-600 créditos), 'continuar' retomar, 'estado' ver stats, 'rendirse' borrar partida",
    )
    @app_commands.choices(accion=[
        app_commands.Choice(name="🌅 Comenzar nueva travesía (-600 cr)", value="comenzar"),
        app_commands.Choice(name="🔄 Continuar travesía", value="continuar"),
        app_commands.Choice(name="📊 Ver estado interno", value="estado"),
        app_commands.Choice(name="💀 Rendirse al vacío", value="rendirse"),
    ])
    async def aventura(self, interaction: discord.Interaction,
                       accion: str = "continuar") -> None:
        user = interaction.user
        user_id = user.id

        # ── RENDIRSE ────────────────────────────────────────────────
        if accion == "rendirse":
            path = self._save_path(user_id)
            if path.exists():
                path.unlink(missing_ok=True)
                await interaction.response.send_message(
                    "💀 Has despertado. Tu partida se disolvió en el amanecer.",
                    ephemeral=True)
            else:
                await interaction.response.send_message(
                    "No tienes travesía activa.", ephemeral=True)
            return

        # ── ESTADO ──────────────────────────────────────────────────
        if accion == "estado":
            state = self.load_game(user_id)
            if not state:
                await interaction.response.send_message(
                    "No tienes travesía activa. Usa `/aventura comenzar` "
                    "en un servidor (cuesta 600 créditos).",
                    ephemeral=True)
                return
            await interaction.response.send_message(
                embed=self._build_stats_embed(state), ephemeral=True)
            return

        # ── COMENZAR / CONTINUAR necesitan partida en DM ────────────

        # Intenta abrir el DM del usuario PRIMERO (si está cerrado, no sigue)
        dm = await self._open_dm(user)
        if dm is None:
            await interaction.response.send_message(
                "🌌 No puedo enviarte DMs. Abre tus mensajes directos del "
                "servidor en *Ajustes de Privacidad* y vuelve a intentarlo.",
                ephemeral=True)
            return

        # ── COMENZAR ────────────────────────────────────────────────
        if accion == "comenzar":
            # Solo se inicia desde un servidor (para cobrar créditos)
            if not interaction.guild:
                await interaction.response.send_message(
                    "🌌 Las travesías se inician desde un servidor, para "
                    "poder cobrar los 600 créditos. Luego se juegan en tus DMs.",
                    ephemeral=True)
                return

            # Chequeo + cobro atómico
            charged = await self._charge_kadath(interaction, COST_KADATH)
            if not charged:
                db = getattr(self.bot, "db", None)
                balance = 0
                if db is not None:
                    info = await db.get_credits(user_id, interaction.guild.id)
                    balance = info["balance"]
                await interaction.response.send_message(
                    f"💰 Créditos insuficientes. Cuesta **{COST_KADATH}** iniciar "
                    f"una travesía. Tienes **{balance}**.",
                    ephemeral=True)
                return

            # Envía el select al DM
            view = CharacterSelectView(self, user_id)
            is_staff = await self._is_staff(interaction)
            cost_line = (
                f"**(cortesía del staff — gratis)**"
                if is_staff
                else f"Se descontaron {COST_KADATH} créditos del servidor "
                     f"**{interaction.guild.name}**."
            )
            try:
                await dm.send(
                    "🌌 **La Travesía Onírica aguarda.**\n"
                    f"{cost_line}\n\n"
                    "Cada viajero sueña distinto. Elige el tuyo:",
                    view=view,
                )
            except (discord.Forbidden, discord.HTTPException) as e:
                # Reembolsar
                await self._refund_kadath(interaction, COST_KADATH)
                logger.warning("No pude enviar DM a %s: %s", user_id, e)
                await interaction.response.send_message(
                    "🌌 No pude enviar el DM. Se reembolsaron los créditos.",
                    ephemeral=True)
                return

            confirm_line = (
                "🌌 Tu travesía aguarda en tus DMs. (cortesía del staff)"
                if is_staff
                else f"🌌 Tu travesía aguarda en tus DMs. (−{COST_KADATH} créditos del servidor)"
            )
            await interaction.response.send_message(confirm_line, ephemeral=True)
            return

        # ── CONTINUAR ───────────────────────────────────────────────
        # Continuar NO cuesta — solo retoma la partida existente en el DM.
        state = self.load_game(user_id)
        if not state:
            await interaction.response.send_message(
                "🌌 No tienes partida guardada. Usa `/aventura comenzar` "
                f"en un servidor para iniciar una (cuesta {COST_KADATH} créditos).",
                ephemeral=True)
            return

        world = self.load_world()
        node = world.get(state.current_node)
        if not node:
            await interaction.response.send_message(
                f"🌀 El nodo `{state.current_node}` ya no existe en el mundo. "
                "Usa `/aventura rendirse` para iniciar una nueva.",
                ephemeral=True)
            return

        view = KadathView(state, node, world, self)
        embed = self._build_embed(state, node)
        try:
            await dm.send(embed=embed, view=view)
        except (discord.Forbidden, discord.HTTPException) as e:
            logger.warning("No pude enviar DM a %s: %s", user_id, e)
            await interaction.response.send_message(
                "🌌 No pude enviar el DM. Abre tus mensajes directos y vuelve a intentarlo.",
                ephemeral=True)
            return

        await interaction.response.send_message(
            "🌌 Tu travesía continúa en tus DMs.",
            ephemeral=True)


# ── Setup ────────────────────────────────────────────────────────────────────

async def setup(bot) -> None:
    await bot.add_cog(DreamQuestCog(bot))

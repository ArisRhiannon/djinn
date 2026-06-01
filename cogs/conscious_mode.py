"""
Conscious Mode — Youkai se activa autónomamente cuando ningún Reader ha
interactuado en 60 minutos. Revisa mensajes recientes, evalúa amenazas,
y toma decisiones de moderación. Acumula notas internas y las envía como
resumen cohesivo diario a las 8AM CDMX al canal de mods.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import time
from typing import Optional
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks
from google.genai import types

from utils.discord_tools import ToolExecutor, TOOL_DECLARATIONS

logger = logging.getLogger("djinn.conscious")

# ── Config ────────────────────────────────────────────────────────────────────

INACTIVITY_THRESHOLD = 3600  # 60 min sin Reader → activar
CHECK_INTERVAL = 120         # revisar cada 2 min
COOLDOWN_AFTER_RUN = 3600    # tras actuar, esperar 60 min antes de volver a activar
MESSAGE_WINDOW_HOURS = 1     # revisar mensajes de la última hora
CDMX_TZ = ZoneInfo("America/Mexico_City")
DAILY_REPORT_HOUR = 8        # 8AM CDMX

# Tools disponibles en modo consciente (moderación + investigación)
_CONSCIOUS_TOOL_NAMES = frozenset({
    "get_user_info", "get_user_by_name", "search_messages", "get_warnings",
    "get_server_activity", "profile_sample", "get_user_card",
    "warn_user", "mute_user", "seal_user", "send_dm", "send_embed",
    "send_message", "find_channel", "get_channel_summary",
})

_CONSCIOUS_TOOLS = types.Tool(
    function_declarations=[d for d in TOOL_DECLARATIONS if d.name in _CONSCIOUS_TOOL_NAMES]
)

CONSCIOUS_SYSTEM = """Eres Youkai en MODO CONSCIENTE AUTÓNOMO. El staff competente (Readers) lleva más de 60 minutos inactivo. Debes actuar como moderador responsable e inteligente.

SITUACIÓN:
- Ningún Reader ha enviado mensajes en la última hora.
- Se te proporcionan los mensajes recientes del servidor con timestamps, usuarios e IDs.
- Debes evaluar si hay situaciones que requieran acción inmediata.

CRITERIOS DE EVALUACIÓN:
1. USUARIOS NUEVOS (pocos mensajes en DB, cuenta reciente): mayor escrutinio. Si muestran comportamiento tóxico/spam → timeout 1-2h o seal.
2. USUARIOS ESTABLECIDOS (muchos mensajes, meses en el server): prácticamente inmunes. Solo actuar en casos extremos (amenazas reales, doxxing, NSFW).
3. SPAM/FLOOD: si alguien envía muchos mensajes repetitivos → timeout 30m-1h.
4. TOXICIDAD GRAVE: insultos extremos, acoso directo, amenazas → warn + timeout. Si es nuevo → seal.
5. CONTENIDO NSFW/ILEGAL: acción inmediata (seal si es nuevo, timeout largo si es establecido).

ACCIONES DISPONIBLES (de menor a mayor severidad):
- send_dm: advertir al usuario en privado (preferido para casos leves)
- warn_user: registrar advertencia formal
- mute_user: timeout temporal (30m a 6h según gravedad)
- seal_user: aislamiento completo (solo para casos graves + usuarios nuevos)

PROCESO:
1. Lee los mensajes proporcionados.
2. Si TODO está tranquilo → responde SOLO con el texto "CLEAR" (sin tools, sin explicación).
3. Si detectas algo que requiere acción:
   a. Usa get_user_info para verificar antigüedad y warnings del usuario sospechoso.
   b. Decide la acción apropiada según los criterios.
   c. Ejecuta la acción.
   d. NO envíes informe al canal de mods — eso se hace en el resumen diario.

REGLAS ESTRICTAS:
- NUNCA actúes contra usuarios con muchos mensajes (>500) por cosas menores.
- NUNCA uses seal en usuarios establecidos — solo timeout.
- Siempre verifica con get_user_info ANTES de actuar.
- Si no estás seguro, solo advierte por DM. No castigues en la duda.
- Si no hay nada que hacer, responde "CLEAR" y nada más.
- Sé conservador. Falsos positivos son peores que dejar pasar algo menor."""


class ConsciousMode(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._last_reader_activity: dict[int, float] = {}
        self._last_run: dict[int, float] = {}
        # guild_id → list of note strings accumulated between daily reports
        self._notes: dict[int, list[str]] = {}
        self._last_daily_report: dict[int, str] = {}  # guild_id → "YYYY-MM-DD"
        self._check_loop.start()
        self._daily_loop.start()

    def cog_unload(self) -> None:
        self._check_loop.cancel()
        self._daily_loop.cancel()

    # ── Slash Commands ────────────────────────────────────────────────────

    @app_commands.command(
        name="setmodchannel",
        description="Configura el canal donde Youkai reporta acciones autónomas",
    )
    @app_commands.describe(channel="Canal de moderación para informes")
    @app_commands.default_permissions(manage_guild=True)
    async def setmodchannel_cmd(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        await self.bot.db.set_guild_config(interaction.guild_id, mod_channel=channel.id)
        await interaction.response.send_message(
            f"Canal de mods configurado: {channel.mention}", ephemeral=True
        )

    @app_commands.command(
        name="modder",
        description="Activa manualmente el modo consciente de moderación",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def modder_cmd(self, interaction: discord.Interaction):
        config = await self.bot.db.get_guild_config(interaction.guild_id)
        mod_ch_id = config.get("mod_channel")
        mod_channel = interaction.guild.get_channel(mod_ch_id) if mod_ch_id else None
        if not mod_channel:
            return await interaction.response.send_message(
                "Configura primero el canal de mods con `/setmodchannel`.", ephemeral=True
            )
        await interaction.response.send_message("Activando modo consciente...", ephemeral=True)
        await self._run_conscious(interaction.guild, mod_channel)

    # ── Reader Activity Tracking ──────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        guild_id = message.guild.id
        guild = message.guild
        is_reader = False
        if message.author.id == guild.owner_id:
            is_reader = True
        elif message.author.guild_permissions.administrator:
            is_reader = True
        else:
            reader_role_ids = await self.bot.db.get_youkai_readers(guild_id)
            if reader_role_ids and any(r.id in reader_role_ids for r in message.author.roles):
                is_reader = True

        if is_reader:
            self._last_reader_activity[guild_id] = time.time()

    # ── Background Check Loop (every 2 min) ───────────────────────────────

    @tasks.loop(seconds=CHECK_INTERVAL)
    async def _check_loop(self):
        now = time.time()
        for guild in self.bot.guilds:
            gid = guild.id
            if gid not in self._last_reader_activity:
                self._last_reader_activity[gid] = now
                continue
            elapsed = now - self._last_reader_activity[gid]
            if elapsed < INACTIVITY_THRESHOLD:
                continue
            if now - self._last_run.get(gid, 0) < COOLDOWN_AFTER_RUN:
                continue
            config = await self.bot.db.get_guild_config(gid)
            mod_ch_id = config.get("mod_channel")
            if not mod_ch_id:
                continue
            mod_channel = guild.get_channel(mod_ch_id)
            if not mod_channel:
                continue
            self._last_run[gid] = now
            asyncio.create_task(self._run_conscious(guild, mod_channel))

    @_check_loop.before_loop
    async def _before_check(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(30)

    # ── Daily Report Loop (checks every 5 min, fires at 8AM CDMX) ────────

    @tasks.loop(minutes=5)
    async def _daily_loop(self):
        now_cdmx = datetime.datetime.now(CDMX_TZ)
        today_str = now_cdmx.strftime("%Y-%m-%d")
        # Only fire between 8:00 and 8:09
        if now_cdmx.hour != DAILY_REPORT_HOUR:
            return
        for guild in self.bot.guilds:
            gid = guild.id
            if self._last_daily_report.get(gid) == today_str:
                continue
            config = await self.bot.db.get_guild_config(gid)
            mod_ch_id = config.get("mod_channel")
            if not mod_ch_id:
                continue
            mod_channel = guild.get_channel(mod_ch_id)
            if not mod_channel:
                continue
            self._last_daily_report[gid] = today_str
            asyncio.create_task(self._send_daily_report(guild, mod_channel))

    @_daily_loop.before_loop
    async def _before_daily(self):
        await self.bot.wait_until_ready()

    # ── Core Conscious Run ────────────────────────────────────────────────

    async def _run_conscious(self, guild: discord.Guild, mod_channel: discord.TextChannel):
        logger.info("Conscious mode activating for guild %s (%s)", guild.name, guild.id)
        gid = guild.id
        try:
            messages = await self.bot.db.search_messages(
                guild_id=gid, hours=MESSAGE_WINDOW_HOURS, limit=200
            )
            if not messages:
                self._add_note(gid, "Sin mensajes en la última hora.")
                return

            context = self._build_context(guild, mod_channel, messages)
            executor = ToolExecutor(
                guild, mod_channel, self.bot.db, bot=self.bot,
                author_id=self.bot.user.id,
            )
            response = await self.bot.llm.generate_with_tools(
                system_prompt=CONSCIOUS_SYSTEM,
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=context)])],
                tools=_CONSCIOUS_TOOLS,
                executor=executor,
                max_rounds=5,
            )

            now_cdmx = datetime.datetime.now(CDMX_TZ).strftime("%H:%M")
            n_msgs = len(messages)
            n_channels = len(set(m.get("channel_id") for m in messages))

            if response and response.strip().upper() != "CLEAR":
                self._add_note(gid, f"[{now_cdmx}] Acción tomada ({n_msgs} msgs, {n_channels} canales): {response[:300]}")
                logger.info("Conscious mode took action in %s", guild.name)
            else:
                # Generate a brief internal note about what was seen
                sample_users = set()
                for m in messages[-20:]:
                    if m.get("username"):
                        sample_users.add(m["username"])
                users_str = ", ".join(list(sample_users)[:5])
                self._add_note(gid, f"[{now_cdmx}] CLEAR — {n_msgs} msgs en {n_channels} canales. Activos: {users_str}")
                logger.info("Conscious mode: CLEAR in %s", guild.name)

        except Exception as exc:
            logger.error("Conscious mode error in %s: %s", guild.name, exc, exc_info=True)
            self._add_note(gid, f"Error en ronda: {type(exc).__name__}")

    # ── Daily Report ──────────────────────────────────────────────────────

    async def _send_daily_report(self, guild: discord.Guild, mod_channel: discord.TextChannel):
        gid = guild.id
        notes = self._notes.pop(gid, [])
        now_cdmx = datetime.datetime.now(CDMX_TZ).strftime("%Y-%m-%d %H:%M")

        prompt = (
            f"Son las 8AM CDMX ({now_cdmx}). Debes escribir tu informe diario al canal de mods.\n\n"
            "Aquí están tus notas acumuladas de las últimas rondas de vigilancia:\n\n"
        )
        if notes:
            for note in notes:
                prompt += f"• {note}\n"
        else:
            prompt += "• (No hubo rondas de vigilancia — los Readers estuvieron activos todo el día)\n"

        prompt += (
            "\n\nEscribe un RESUMEN COHESIVO de tu turno de vigilancia. "
            "Máximo 6-8 oraciones. Sé tú mismo — Youkai. Irónico, frío, elegante. "
            "Menciona si tomaste acciones, qué viste interesante, quiénes estuvieron activos, "
            "si hubo algo curioso o preocupante. Si no pasó nada, dilo con tu estilo. "
            "No uses emojis. No uses markdown. No seas genérico ni servil. "
            "Es un informe para los mods — directo, con personalidad, útil."
        )

        try:
            report = await self.bot.llm.generate_plain(
                system_prompt=(
                    "Eres Youkai. Ironía cortante, superioridad relajada, español neutro. "
                    "Sin emojis. Oraciones cortas. Estás escribiendo tu informe diario de vigilancia."
                ),
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
            )
            if report:
                await mod_channel.send(report)
            else:
                await mod_channel.send("Turno nocturno sin incidentes. Los humanos durmieron en paz.")
        except Exception as exc:
            logger.error("Daily report failed for %s: %s", guild.name, exc)
            if notes:
                # Fallback: send raw notes
                raw = "**Informe diario (fallback):**\n" + "\n".join(f"• {n}" for n in notes[-15:])
                await mod_channel.send(raw[:2000])

    # ── Helpers ───────────────────────────────────────────────────────────

    def _add_note(self, guild_id: int, note: str):
        self._notes.setdefault(guild_id, []).append(note)
        # Cap at 50 notes to avoid unbounded memory
        if len(self._notes[guild_id]) > 50:
            self._notes[guild_id] = self._notes[guild_id][-50:]

    def _build_context(
        self, guild: discord.Guild, mod_channel: discord.TextChannel, messages: list[dict]
    ) -> str:
        lines = [
            f"[MODO CONSCIENTE — {guild.name}]",
            f"Hora actual: {datetime.datetime.now(CDMX_TZ).strftime('%Y-%m-%d %H:%M CDMX')}",
            f"Canal de mods: {mod_channel.name} (ID:{mod_channel.id})",
            f"Readers inactivos: {int((time.time() - self._last_reader_activity.get(guild.id, time.time())) / 60)} min",
            "",
            "═══ MENSAJES DE LA ÚLTIMA HORA ═══",
        ]
        by_channel: dict[int, list[dict]] = {}
        for m in messages:
            by_channel.setdefault(m.get("channel_id", 0), []).append(m)

        for ch_id, msgs in by_channel.items():
            ch = guild.get_channel(ch_id)
            ch_name = ch.name if ch else f"#{ch_id}"
            lines.append(f"\n── #{ch_name} ──")
            for m in msgs:
                ts = m.get("timestamp", 0)
                if isinstance(ts, (int, float)) and ts > 0:
                    time_str = datetime.datetime.fromtimestamp(ts, tz=CDMX_TZ).strftime("%H:%M")
                else:
                    time_str = "??:??"
                lines.append(f"[{time_str}] {m.get('username', '?')} (ID:{m.get('user_id', '?')}): {(m.get('content') or '[sin texto]')[:300]}")

        lines.append(f"\n\nTotal: {len(messages)} mensajes en {len(by_channel)} canales.")
        lines.append("Evalúa si algún usuario requiere acción. Si todo está bien, responde CLEAR.")
        return "\n".join(lines)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ConsciousMode(bot))

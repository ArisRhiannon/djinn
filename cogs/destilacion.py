"""
Cog: Destilación — Destilador de personalidades + visualización pública.

Comandos:
  /destilación [rol]  — Solo owner (239550977638793217) o admins.
                         Destila a todos los miembros con ese rol.
  /card [usuario]     — Público. Muestra la destilación de un usuario.
"""

from __future__ import annotations

import asyncio
import discord
import time
from discord import app_commands
from discord.ext import commands
from typing import Optional
from loguru import logger

from utils.destilador import Destilador

# ── IDs con acceso a /destilación ──────────────────────────────────────────

_OWNER_ID = 239550977638793217


def _can_distill(interaction: discord.Interaction) -> bool:
    """Solo el owner específico o admins del servidor."""
    if interaction.user.id == _OWNER_ID:
        return True
    # Check administrator permission (not just mod roles)
    if isinstance(interaction.user, discord.Member):
        if interaction.user.guild_permissions.administrator:
            return True
    return False


# ── Colores por energía predominante ───────────────────────────────────────

_ENERGY_COLORS: dict[str, int] = {
    "hiperactivo": 0xFF6B35,
    "contenido": 0x74B9FF,
    "esporádico": 0x636E72,
    "calculado": 0x2C3E50,
    "intenso": 0xE74C3C,
    "tranquilo": 0x00CEC9,
    "caótico": 0xF5A623,
    "reservado": 0x5B2D8E,
}


def _energy_color(energia: str) -> int:
    energia_lower = energia.lower()
    for key, color in _ENERGY_COLORS.items():
        if key in energia_lower:
            return color
    return 0x7289DA  # Discord blurple fallback


# ── Embed builder ──────────────────────────────────────────────────────────

_FIELD_LIMIT = 1024

def _truncate_field(value: str, limit: int = _FIELD_LIMIT) -> str:
    """Trunca un field value al límite de Discord, añadiendo '…' si corta."""
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _build_destilacion_embed(target: discord.Member, dest: dict) -> discord.Embed:
    """Construye el embed de destilación a partir del JSON guardado."""
    superficie = dest.get("superficie", {})
    estructura = dest.get("estructura", {})
    esencia = dest.get("esencia", {})
    msg_count = dest.get("mensaje_count", "?")
    dest_at = dest.get("destilado_at", 0)

    energia = superficie.get("energia", "desconocida")
    color = _energy_color(energia)

    # ── Título + descripción ───────────────────────────────────────────
    nombre = superficie.get("nombre", target.display_name)
    registro = superficie.get("registro", "—")
    mascara = superficie.get("mascara", "—")
    ritmo = superficie.get("ritmo", "—")
    rasgos_sup = superficie.get("rasgos_superficiales", [])

    embed = discord.Embed(
        title=f"◆ {nombre}",
        description=(
            f"**Registro:** {registro}\n"
            f"**Máscara:** {mascara}\n"
            f"**Ritmo:** {ritmo}"
        ),
        color=color,
    )
    embed.set_thumbnail(url=target.display_avatar.url)

    # ── Superficie ─────────────────────────────────────────────────────
    if rasgos_sup:
        sup_val = " • ".join(f"`{r}`" for r in rasgos_sup)
        embed.add_field(
            name="◈ Superficie",
            value=_truncate_field(sup_val),
            inline=False,
        )

    # ── Estructura ─────────────────────────────────────────────────────
    patron = estructura.get("patron_mental", "—")
    contras = estructura.get("contradicciones", [])
    importancias = estructura.get("importancias_reales", [])
    mecanismos = estructura.get("mecanismos", "—")
    din_social = estructura.get("dinamica_social", "—")
    est_resumen = estructura.get("estructura_resumen", "")

    est_val = f"**Patrón mental:** {patron}\n"
    if contras:
        est_val += f"**Contradicciones:** {' • '.join(f'`{c}`' for c in contras)}\n"
    if importancias:
        est_val += f"**Le importa de verdad:** {' • '.join(f'`{i}`' for i in importancias)}\n"
    est_val += f"**Coping:** {mecanismos}\n"
    est_val += f"**Dinámica social:** {din_social}"
    if est_resumen:
        est_val += f"\n*{est_resumen}*"

    embed.add_field(name="◈ Estructura", value=_truncate_field(est_val), inline=False)

    # ── Esencia ────────────────────────────────────────────────────────
    nucleo = esencia.get("nucleo", "—")
    narrativa_int = esencia.get("narrativa_interna", "—")
    distintivo = esencia.get("distintivo", "—")
    ausencias = esencia.get("ausencias", "—")
    esencia_narr = esencia.get("esencia_narrativa", "")
    esencia_resumen = esencia.get("esencia_resumen", "")

    es_val = f"**Núcleo:** {nucleo}\n"
    es_val += f"**Narrativa interna:** {narrativa_int}\n"
    es_val += f"**Distintivo:** {distintivo}\n"
    es_val += f"**Ausencias:** {ausencias}"
    if esencia_resumen:
        es_val += f"\n\n**≫** *{esencia_resumen}*"

    embed.add_field(name="◈ Esencia", value=_truncate_field(es_val), inline=False)

    # ── Narrativa expandida (si existe) ────────────────────────────────
    if esencia_narr and len(esencia_narr) > 100:
        embed.add_field(name="◈ Destilación", value=_truncate_field(esencia_narr), inline=False)

    # ── Footer ─────────────────────────────────────────────────────────
    date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(dest_at)) if dest_at else "?"
    embed.set_footer(
        text=f"Destilado: {date_str} · {msg_count} mensajes analizados · El Destilador"
    )
    return embed


# ── Cog ────────────────────────────────────────────────────────────────────

class DestilacionCog(commands.Cog, name="Destilacion"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._destilador: Optional[Destilador] = None
        self._distill_lock = asyncio.Lock()
        self._progress_msg: Optional[discord.Message] = None

    def _get_destilador(self) -> Destilador:
        """Lazy-init del Destilador (necesita LLM client)."""
        if self._destilador is None:
            if self.bot.llm is None:
                raise RuntimeError("LLM no disponible — no se puede destilar")
            self._destilador = Destilador(self.bot.llm)
        return self._destilador

    # ── /destilación ───────────────────────────────────────────────────

    @app_commands.command(
        name="destilación",
        description="Destila las personalidades de los miembros con un rol. (Owner/Admin)",
    )
    @app_commands.describe(rol="Rol cuyos miembros serán destilados")
    @app_commands.guild_only()
    async def destilacion(
        self,
        interaction: discord.Interaction,
        rol: discord.Role,
    ) -> None:
        # ── Auth check ─────────────────────────────────────────────────
        if not _can_distill(interaction):
            await interaction.response.send_message(
                "⛔ Solo el owner o administradores pueden ejecutar destilación.",
                ephemeral=True,
            )
            return

        # ── Lock check (no destilaciones simultáneas) ───────────────────
        if self._distill_lock.locked():
            await interaction.response.send_message(
                "⏳ Ya hay una destilación en curso. Espera a que termine.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=False)

        # Collect members with the role
        members = rol.members
        if not members:
            await interaction.followup.send(
                f"El rol **{discord.utils.escape_markdown(rol.name)}** no tiene miembros.", ephemeral=True
            )
            return

        # Get user IDs with enough messages in DB
        guild_id = interaction.guild_id
        member_ids = {m.id for m in members}
        eligible_ids = await self.bot.db.get_guild_member_ids(
            guild_id, min_messages=10
        )
        # Only destilar members who both have the role AND have enough messages
        target_ids = [uid for uid in eligible_ids if uid in member_ids]

        if not target_ids:
            await interaction.followup.send(
                f"Ningún miembro con **{discord.utils.escape_markdown(rol.name)}** tiene suficientes mensajes "
                "en la base de datos (mínimo 10).",
                ephemeral=True,
            )
            return

        # Send initial progress message
        progress_embed = discord.Embed(
            title="⚗️ Destilación en progreso",
            description=(
                f"**Rol:** {discord.utils.escape_markdown(rol.name)}\n"
                f"**Miembros a destilar:** {len(target_ids)}\n"
                f"**Fase actual:** Iniciando…\n"
                f"**Progreso:** 0/{len(target_ids)}"
            ),
            color=0x5B2D8E,
        )
        self._progress_msg = await interaction.followup.send(embed=progress_embed)

        # ── Run destillation ───────────────────────────────────────────
        async with self._distill_lock:
            destilador = self._get_destilador()
            total = len(target_ids)
            completed = 0

            async def _on_progress(phase: str, user_id: int) -> None:
                nonlocal completed
                # Contar usuario como completado cuando termina la última fase (esencia)
                if phase == "esencia":
                    completed += 1
                try:
                    member = interaction.guild.get_member(user_id)
                    name = member.display_name if member else f"User {user_id}"
                    phase_names = {
                        "superficie": "🟦 Superficie",
                        "estructura": "🟧 Estructura",
                        "esencia": "🟥 Esencia",
                    }
                    if self._progress_msg:
                        updated = discord.Embed(
                            title="⚗️ Destilación en progreso",
                            description=(
                                f"**Rol:** {discord.utils.escape_markdown(rol.name)}\n"
                                f"**Actual:** {name} — {phase_names.get(phase, phase)}\n"
                                f"**Progreso:** {completed}/{total} usuarios"
                            ),
                            color=0x5B2D8E,
                        )
                        await self._progress_msg.edit(embed=updated)
                except Exception:
                    pass  # Progress updates are non-critical

            try:
                resultados = await destilador.destilar_guild(
                    guild_id=guild_id,
                    user_ids=target_ids,
                    db=self.bot.db,
                    progress_callback=_on_progress,
                    message_limit=600,
                )
            except Exception as exc:
                logger.error("Destilación falló: {}", exc)
                if self._progress_msg:
                    err_embed = discord.Embed(
                        title="❌ Destilación falló",
                        description=f"Error: {exc}",
                        color=0xE74C3C,
                    )
                    await self._progress_msg.edit(embed=err_embed)
                return

        # ── Final embeds ───────────────────────────────────────────────
        if not resultados:
            if self._progress_msg:
                await self._progress_msg.edit(
                    embed=discord.Embed(
                        title="⚠️ Destilación vacía",
                        description="No se pudieron destilar personalidades.",
                        color=0xF5A623,
                    )
                )
            return

        # Update progress to done
        done_embed = discord.Embed(
            title="✅ Destilación completa",
            description=(
                f"**Rol:** {discord.utils.escape_markdown(rol.name)}\n"
                f"**Destilados:** {len(resultados)}/{total}\n"
                f"Usa `/card` para ver cualquier destilación."
            ),
            color=0x00CEC9,
        )
        if self._progress_msg:
            try:
                await self._progress_msg.edit(embed=done_embed)
            except Exception:
                pass

        # Send individual embeds for each destilado
        for uid, result in resultados.items():
            member = interaction.guild.get_member(uid)
            if not member:
                continue
            try:
                embed = _build_destilacion_embed(member, result)
                await interaction.channel.send(embed=embed)
                await asyncio.sleep(0.5)  # Don't spam
            except Exception as exc:
                logger.warning("Destilación: error enviando embed de {}: {}", uid, exc)

    # ── /card ──────────────────────────────────────────────────────────

    @app_commands.command(
        name="card",
        description="Muestra la destilación de personalidad de un usuario.",
    )
    @app_commands.describe(user="Usuario cuya destilación quieres ver (por defecto: tú)")
    @app_commands.guild_only()
    async def card(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=False)
        target = user or interaction.user

        card_data = await self.bot.db.get_card(target.id)

        if not card_data:
            await interaction.followup.send(
                f"**{target.display_name}** aún no ha sido destilado. "
                "Un administrador necesita ejecutar `/destilación` primero.",
                ephemeral=True,
            )
            return

        # card_data["card_json"] contains the destilación dict
        dest = card_data.get("card_json", {})
        if not dest or not isinstance(dest, dict):
            await interaction.followup.send(
                f"**{target.display_name}** tiene datos de destilación corruptos. "
                "Necesita ser re-destilado.",
                ephemeral=True,
            )
            return

        embed = _build_destilacion_embed(target, dest)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DestilacionCog(bot))
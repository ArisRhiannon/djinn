"""
Cog: ZZZ Event Calendar.

- /zzz_calendario set <canal>: Configura el canal donde se postea el calendario
- /zzz_calendario refresh: Fuerza un refresh manual del calendario
- Loop automático cada 10 min: re-render + edit message

Persistencia (guild_config):
  zzz_calendar_ch         INTEGER  — canal de destino
  zzz_calendar_msg_id     INTEGER  — message_id del calendario actual (para editar)
"""
from __future__ import annotations

import io
import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.zzz_calendar.data import load_calendar
from utils.zzz_calendar.renderer import render_calendar

logger = logging.getLogger("djinn.zzz_calendar")

CONFIG_PATH = Path(__file__).parent.parent / "utils" / "zzz_calendar" / "config.json"
UPDATE_INTERVAL_MIN = 10


class ZZZCalendar(commands.Cog):
    """Calendario de eventos de Zenless Zone Zero."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._update_loop.start()

    def cog_unload(self) -> None:
        self._update_loop.cancel()

    # ── Helpers ────────────────────────────────────────────────────────────

    async def _build_image(self) -> tuple[discord.File, discord.Embed]:
        """Genera la imagen + embed para postear/editar."""
        cal = load_calendar(CONFIG_PATH)
        png_bytes = await render_calendar(cal)

        file = discord.File(io.BytesIO(png_bytes), filename="zzz_calendar.png")

        embed = discord.Embed(
            title=f"📅 ZZZ — {cal.title} (v{cal.version})",
            description=f"Calendario de eventos del **{cal.start.strftime('%d %B')}** al "
                        f"**{cal.end.strftime('%d %B %Y')}**.\n"
                        f"_Actualizado automáticamente cada {UPDATE_INTERVAL_MIN} minutos._",
            color=0xFFA546,
        )
        embed.set_image(url="attachment://zzz_calendar.png")
        embed.set_footer(text="Datos: hoyoverse-api · Imágenes: rorin labs · Curado: Youkai")
        return file, embed

    async def _post_or_update(self, guild: discord.Guild) -> str:
        """Postea calendario nuevo o edita el existente. Retorna status."""
        config = await self.bot.db.get_guild_config(guild.id)
        ch_id = config.get("zzz_calendar_ch") if config else None
        if not ch_id:
            return "no_channel"

        channel = guild.get_channel(ch_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return "channel_invalid"

        msg_id = config.get("zzz_calendar_msg_id") if config else None

        try:
            file, embed = await self._build_image()
        except Exception as e:
            logger.exception("Failed to render calendar: %s", e)
            return "render_failed"

        # Try to edit existing
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(attachments=[file], embed=embed)
                return "updated"
            except (discord.NotFound, discord.Forbidden):
                logger.info("Old calendar message %s gone — posting new", msg_id)

        # Post new
        try:
            msg = await channel.send(file=file, embed=embed)
            await self.bot.db.set_guild_config(guild.id, zzz_calendar_msg_id=msg.id)
            return "posted"
        except discord.Forbidden:
            return "no_perms"

    # ── Slash commands ─────────────────────────────────────────────────────

    group = app_commands.Group(
        name="zzz_calendario",
        description="Calendario de eventos de Zenless Zone Zero",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @group.command(name="set", description="Configura el canal donde se publicará el calendario")
    @app_commands.describe(canal="Canal donde se postea (se actualiza cada 10 min)")
    async def set_channel(self, interaction: discord.Interaction, canal: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        db = self.bot.db
        await db.init_guild(interaction.guild_id)
        # Reset old message_id when switching channels
        await db.set_guild_config(
            interaction.guild_id,
            zzz_calendar_ch=canal.id,
            zzz_calendar_msg_id=None,
        )
        # Post immediately
        status = await self._post_or_update(interaction.guild)
        if status in ("posted", "updated"):
            await interaction.followup.send(
                f"✅ Calendario configurado en {canal.mention}.\n"
                f"Se actualizará automáticamente cada {UPDATE_INTERVAL_MIN} minutos.",
                ephemeral=True,
            )
        elif status == "no_perms":
            await interaction.followup.send(
                f"⚠️ No tengo permisos para postear en {canal.mention}.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"⚠️ Error: `{status}`. Revisa permisos y configuración.",
                ephemeral=True,
            )

    @group.command(name="refresh", description="Fuerza una actualización inmediata del calendario")
    async def refresh(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        status = await self._post_or_update(interaction.guild)
        msg = {
            "no_channel": "❌ No hay canal configurado. Usa `/zzz_calendario set` primero.",
            "channel_invalid": "❌ El canal configurado ya no existe.",
            "render_failed": "❌ Error al renderizar la imagen.",
            "no_perms": "❌ Sin permisos para postear/editar.",
            "posted": "✅ Calendario posteado.",
            "updated": "✅ Calendario actualizado.",
        }.get(status, f"⚠️ Estado desconocido: {status}")
        await interaction.followup.send(msg, ephemeral=True)

    @group.command(name="off", description="Desactiva el calendario en este servidor")
    async def off(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.bot.db.set_guild_config(
            interaction.guild_id,
            zzz_calendar_ch=None,
            zzz_calendar_msg_id=None,
        )
        await interaction.followup.send(
            "✅ Calendario desactivado en este servidor.",
            ephemeral=True,
        )

    # ── Background loop ────────────────────────────────────────────────────

    @tasks.loop(minutes=UPDATE_INTERVAL_MIN)
    async def _update_loop(self) -> None:
        """Cada N min: re-renderiza y edita el calendario en cada guild configurado."""
        for guild in self.bot.guilds:
            try:
                config = await self.bot.db.get_guild_config(guild.id)
                if not config or not config.get("zzz_calendar_ch"):
                    continue
                status = await self._post_or_update(guild)
                if status not in ("updated", "posted"):
                    logger.warning("ZZZ calendar update for %s: %s", guild.id, status)
            except Exception as e:
                logger.exception("Calendar loop error for guild %s: %s", guild.id, e)

    @_update_loop.before_loop
    async def _before_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ZZZCalendar(bot))

"""
Cog: Birthdays — registro y anuncio mensual de cumpleaños.

- LLM tool: register_birthday (registra 1 o más cumpleaños)
- /cumpleaños canal <canal>: configura canal de anuncios
- Loop: 1ro de cada mes a 08:30 CDMX (14:30 UTC) anuncia cumpleaños del mes
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

logger = logging.getLogger("youkai.birthdays")

# CDMX = UTC-6 (sin horario de verano desde 2022 en México)
CDMX_OFFSET = timedelta(hours=-6)
ANNOUNCE_HOUR_UTC = 14  # 08:30 CDMX = 14:30 UTC
ANNOUNCE_MINUTE = 30

MONTHS_ES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]


class Birthdays(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._monthly_announce.start()

    def cog_unload(self) -> None:
        self._monthly_announce.cancel()

    # ── Slash command ─────────────────────────────────────────────────────

    @app_commands.command(name="cumpleaños", description="Configura el canal de anuncios de cumpleaños")
    @app_commands.describe(canal="Canal donde se anunciarán los cumpleaños del mes")
    @app_commands.default_permissions(administrator=True)
    async def set_birthday_channel(self, interaction: discord.Interaction, canal: discord.TextChannel):
        db = self.bot.db
        await db.init_guild(interaction.guild_id)
        await db.set_guild_config(interaction.guild_id, birthday_ch=canal.id)
        await interaction.response.send_message(
            f"✅ Canal de cumpleaños configurado: {canal.mention}\n"
            f"El 1ro de cada mes a las 8:30 AM (CDMX) se anunciarán los cumpleaños del mes.",
            ephemeral=True,
        )

    # ── Monthly announcement loop ────────────────────────────────────────

    @tasks.loop(time=time(hour=ANNOUNCE_HOUR_UTC, minute=ANNOUNCE_MINUTE, tzinfo=timezone.utc))
    async def _monthly_announce(self) -> None:
        """Runs daily at 14:30 UTC (08:30 CDMX). Only acts on day 1."""
        now = datetime.now(timezone.utc) + CDMX_OFFSET
        if now.day != 1:
            return

        month = now.month
        logger.info("Birthday announcement: month %d", month)

        for guild in self.bot.guilds:
            try:
                await self._announce_for_guild(guild, month)
            except Exception as e:
                logger.error("Birthday announce error guild %s: %s", guild.id, e)

    @_monthly_announce.before_loop
    async def _before_monthly(self) -> None:
        await self.bot.wait_until_ready()

    async def _announce_for_guild(self, guild: discord.Guild, month: int) -> None:
        config = await self.bot.db.get_guild_config(guild.id)
        ch_id = config.get("birthday_ch") if config else None
        if not ch_id:
            return

        channel = guild.get_channel(ch_id)
        if not channel:
            return

        # Get birthdays for this month
        rows = await self.bot.db.fetch(
            "SELECT user_id, day, name FROM birthdays "
            "WHERE guild_id = ? AND month = ? ORDER BY day",
            (guild.id, month),
        )
        if not rows:
            return

        # Build announcement
        lines = []
        for row in rows:
            member = guild.get_member(row["user_id"])
            display = member.mention if member else (row["name"] or f"<@{row['user_id']}>")
            lines.append(f"🎂 **{row['day']} de {MONTHS_ES[month]}** — {display}")

        embed = discord.Embed(
            title=f"🎉 Cumpleaños de {MONTHS_ES[month]}",
            description="\n".join(lines),
            color=0xFF69B4,
        )
        embed.set_footer(text=f"{len(rows)} cumpleaños este mes • ¡Felicidades a todos!")

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

    # ── LLM Tool handler (called from ToolExecutor) ──────────────────────

    async def register_birthday(self, guild_id: int, user_id: int,
                                 day: int, month: int, name: str = "") -> dict:
        """Register a birthday. Called by the LLM tool."""
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return {"error": "Fecha inválida. Día debe ser 1-31, mes 1-12."}

        db = self.bot.db
        async with db.write_lock:
            await db._db.execute(
                "INSERT OR REPLACE INTO birthdays (guild_id, user_id, day, month, name) "
                "VALUES (?, ?, ?, ?, ?)",
                (guild_id, user_id, day, month, name),
            )
            await db._safe_commit()

        return {
            "success": True,
            "message": f"Cumpleaños registrado: {name or user_id} → {day}/{month}",
        }

    async def get_birthdays_month(self, guild_id: int, month: int) -> list[dict]:
        """Get all birthdays for a month."""
        return await self.bot.db.fetch(
            "SELECT user_id, day, month, name FROM birthdays "
            "WHERE guild_id = ? AND month = ? ORDER BY day",
            (guild_id, month),
        )

    async def get_all_birthdays(self, guild_id: int) -> list[dict]:
        """Get all registered birthdays."""
        return await self.bot.db.fetch(
            "SELECT user_id, day, month, name FROM birthdays "
            "WHERE guild_id = ? ORDER BY month, day",
            (guild_id,),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Birthdays(bot))

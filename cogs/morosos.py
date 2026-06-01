"""
Morosos Cog — Shaming system for loan deadbeats.

- /morosos_canal: set the public shaming channel
- On startup: checks active morosos, creates/assigns "sucio moroso" role
- When someone becomes moroso: auto-assigns role + escalating announcement
- Announcements get progressively more unhinged with each consecutive miss
"""
import asyncio
import logging
import random
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

_ROLE_NAME = "sucio moroso"
_ROLE_COLOR = discord.Color(0x000000)  # negro total

# ── Escalating messages (more unhinged as consecutive_misses grows) ──────

_MSGS_LEVEL_1 = [
    "⚠️ {user} no pagó su cuota. Qué vergüenza.",
    "🚨 {user} se olvidó de pagar. O eso dice.",
    "📢 {user} tiene una deuda pendiente. Tómalo como advertencia.",
]

_MSGS_LEVEL_2 = [
    "🔴 {user} lleva 2 cuotas sin pagar. ¿Alguien le presta dignidad?",
    "💀 {user} sigue sin pagar. A este paso le van a embargar el avatar.",
    "🗣️ ATENCIÓN: {user} es oficialmente un SUCIO MOROSO reincidente.",
]

_MSGS_LEVEL_3 = [
    "🚨🚨🚨 ALERTA MÁXIMA: {user} lleva 3 FALLOS. Este individuo es un peligro financiero para la sociedad.",
    "⚰️ Aquí yace la dignidad de {user}. Murió ahogada en deudas impagadas. F.",
    "📣 SE BUSCA: {user}. Crimen: ser un moroso de mierda. Recompensa: que pague lo que debe.",
]

_MSGS_LEVEL_4 = [
    "💩 {user} lleva {misses} cuotas sin pagar. En este punto ya no es moroso, es un estilo de vida.",
    "🤡 BREAKING NEWS: {user} descubrió un hack infinito de dinero — no pagar nunca. Deuda: ${debt}.",
    "🚽 {user} tiene más deudas que neuronas funcionales. {misses} cuotas impagadas y contando.",
    "☠️ Si la vergüenza fuera dinero, {user} seguiría en bancarrota. PAGA TU DEUDA DE ${debt} RATA.",
    "🐀 {user} es la rata más grande de este server. {misses} cuotas. ${debt} de deuda. CERO dignidad.",
]

_IMGS_PROMPTS = [
    "wanted poster moroso deadbeat cartoon style",
    "shame walk game of thrones meme",
    "clown makeup meme financial disaster",
    "rat stealing money cartoon",
    "dumpster fire with money burning",
]


def _get_shame_message(user_mention: str, consecutive_misses: int, debt: int) -> str:
    """Pick an escalating message based on how many misses."""
    if consecutive_misses <= 1:
        pool = _MSGS_LEVEL_1
    elif consecutive_misses == 2:
        pool = _MSGS_LEVEL_2
    elif consecutive_misses == 3:
        pool = _MSGS_LEVEL_3
    else:
        pool = _MSGS_LEVEL_4

    msg = random.choice(pool)
    return msg.format(user=user_mention, misses=consecutive_misses, debt=debt)


class Morosos(commands.Cog):
    """Public shaming system for loan deadbeats."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        # Run moroso check after bot is ready
        asyncio.create_task(self._startup_check())

    # ── Slash command: set moroso channel ─────────────────────────────────

    @app_commands.command(name="morosos_canal", description="Establece el canal de exposición pública de morosos")
    @app_commands.describe(canal="Canal donde se expondrán los morosos")
    @app_commands.default_permissions(administrator=True)
    async def set_moroso_channel(self, interaction: discord.Interaction, canal: discord.TextChannel):
        db = self.bot.db
        await db.init_guild(interaction.guild_id)
        await db.set_guild_config(interaction.guild_id, moroso_ch=canal.id)
        await interaction.response.send_message(
            f"✅ Canal de morosos configurado: {canal.mention}\n"
            f"Los sucios morosos serán expuestos ahí.",
            ephemeral=True,
        )

    # ── Role management ───────────────────────────────────────────────────

    async def _ensure_role(self, guild: discord.Guild) -> discord.Role | None:
        """Get or create the moroso role, cache ID in DB."""
        db = self.bot.db
        config = await db.get_guild_config(guild.id)
        if not config:
            await db.init_guild(guild.id)
            config = await db.get_guild_config(guild.id)

        role_id = config.get("moroso_role_id") if config else None

        # Try to find existing role by ID
        if role_id:
            role = guild.get_role(role_id)
            if role:
                return role

        # Try to find by name
        role = discord.utils.get(guild.roles, name=_ROLE_NAME)
        if role:
            await db.set_guild_config(guild.id, moroso_role_id=role.id)
            return role

        # Create it
        try:
            role = await guild.create_role(
                name=_ROLE_NAME,
                color=_ROLE_COLOR,
                mentionable=True,
                reason="Sistema de morosos — rol automático",
            )
            await db.set_guild_config(guild.id, moroso_role_id=role.id)
            logger.info("Created moroso role %s in guild %s", role.id, guild.id)
            return role
        except discord.Forbidden:
            logger.warning("Cannot create moroso role in guild %s — missing perms", guild.id)
            return None

    # ── Startup check ─────────────────────────────────────────────────────

    async def _startup_check(self) -> None:
        """On bot start, assign moroso role to all active deadbeats."""
        await self.bot.wait_until_ready()
        await asyncio.sleep(5)  # let DB init

        db = self.bot.db
        rows = await db.fetch(
            "SELECT user_id, guild_id, consecutive_misses, remaining_debt "
            "FROM loans WHERE consecutive_misses > 0 AND status = 'active'"
        )
        if not rows:
            return

        # Group by guild
        by_guild: dict[int, list] = {}
        for r in rows:
            by_guild.setdefault(r["guild_id"], []).append(r)

        for guild_id, loans in by_guild.items():
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            role = await self._ensure_role(guild)
            if not role:
                continue

            for loan in loans:
                member = guild.get_member(loan["user_id"])
                if member and role not in member.roles:
                    try:
                        await member.add_roles(role, reason="Moroso detectado al iniciar")
                    except discord.Forbidden:
                        pass

        logger.info("Moroso startup check: processed %d active morosos", len(rows))

    # ── Public API: called by loan_shark when someone misses a payment ────

    async def on_new_moroso(self, guild_id: int, user_id: int, consecutive_misses: int, debt: int) -> None:
        """Called when a user misses a payment. Assigns role + shames."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        member = guild.get_member(user_id)
        if not member:
            return

        # Assign role
        role = await self._ensure_role(guild)
        if role and role not in member.roles:
            try:
                await member.add_roles(role, reason=f"Moroso: {consecutive_misses} cuotas impagadas")
            except discord.Forbidden:
                pass

        # Post shame in moroso channel
        config = await self.bot.db.get_guild_config(guild_id)
        ch_id = config.get("moroso_ch") if config else None
        if not ch_id:
            return

        channel = guild.get_channel(ch_id)
        if not channel:
            return

        msg = _get_shame_message(member.mention, consecutive_misses, debt)
        try:
            await channel.send(msg)
        except discord.Forbidden:
            pass

    # ── Remove role when debt is paid ─────────────────────────────────────

    async def on_moroso_cleared(self, guild_id: int, user_id: int) -> None:
        """Called when a moroso pays off or gets current. Removes role."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        member = guild.get_member(user_id)
        if not member:
            return

        config = await self.bot.db.get_guild_config(guild_id)
        role_id = config.get("moroso_role_id") if config else None
        if not role_id:
            return

        role = guild.get_role(role_id)
        if role and role in member.roles:
            try:
                await member.remove_roles(role, reason="Deuda saldada")
            except discord.Forbidden:
                pass


async def setup(bot) -> None:
    await bot.add_cog(Morosos(bot))

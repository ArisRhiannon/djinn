"""
Cog: Moderation — Slash commands de moderación.
Restricción DURA: ningún comando borra canales, categorías o realiza bans masivos.

Cambio respecto a la versión anterior:
  - `import datetime` movido al top level (estaba dentro de varios métodos).
"""

from __future__ import annotations
import datetime
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.security import PermLevel, require_level, target_is_protected, can_mod
from utils.audit_log import send_audit


def parse_duration(duration_str: str) -> int:
    """'10m' → 600, '2h' → 7200, '1d' → 86400. Retorna -1 si inválido."""
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    m = re.match(r"^(\d+)([smhd])$", duration_str.strip().lower())
    if not m:
        return -1
    return int(m.group(1)) * units[m.group(2)]


class ModerationCog(commands.Cog, name="Moderación"):
    def __init__(self, bot):
        self.bot = bot

    # ── /ban ────────────────────────────────────────────────────────────────

    @app_commands.command(name="ban", description="Banea a un usuario del servidor")
    @app_commands.describe(
        user="Usuario a banear",
        reason="Razón del ban",
        delete_days="Días de mensajes a eliminar (0-7)",
    )
    @app_commands.guild_only()
    @require_level(PermLevel.MOD)
    async def ban(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = "Sin razón especificada",
        delete_days: app_commands.Range[int, 0, 7] = 0,
    ):
        await interaction.response.defer()

        if target_is_protected(interaction.user, user):
            await interaction.followup.send(
                "No puedo banear a ese usuario — está protegido por jerarquía de roles.",
                ephemeral=True,
            )
            return

        try:
            await user.ban(
                reason=f"[Youkai] {reason} — por {interaction.user}",
                delete_message_days=delete_days,
            )
            response = self.bot.embedder.get_response(
                "usuario baneado exitosamente", user=user.mention, reason=reason
            )
            await interaction.followup.send(response)
            await send_audit(
                interaction.guild, self.bot.db, "ban",
                actor=interaction.user, target=user, reason=reason,
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "No tengo permisos para banear a ese usuario.", ephemeral=True
            )

    # ── /kick ───────────────────────────────────────────────────────────────

    @app_commands.command(name="kick", description="Expulsa a un usuario (puede volver)")
    @app_commands.describe(user="Usuario a expulsar", reason="Razón")
    @app_commands.guild_only()
    @require_level(PermLevel.MOD)
    async def kick(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = "Sin razón especificada",
    ):
        await interaction.response.defer()

        if target_is_protected(interaction.user, user):
            await interaction.followup.send(
                "Jerarquía de roles protege a ese usuario.", ephemeral=True
            )
            return

        try:
            await user.kick(reason=f"[Youkai] {reason} — por {interaction.user}")
            response = self.bot.embedder.get_response(
                "usuario expulsado del servidor", user=user.mention, reason=reason
            )
            await interaction.followup.send(response)
            await send_audit(
                interaction.guild, self.bot.db, "kick",
                actor=interaction.user, target=user, reason=reason,
            )
        except discord.Forbidden:
            await interaction.followup.send("Sin permisos para expulsar.", ephemeral=True)

    # ── /unmute ─────────────────────────────────────────────────────────────

    @app_commands.command(name="unmute", description="Quita el silencio/timeout a un usuario")
    @app_commands.describe(user="Usuario", reason="Razón")
    @app_commands.guild_only()
    @require_level(PermLevel.MOD)
    async def unmute(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str = "Silencio levantado",
    ):
        await interaction.response.defer()
        try:
            await user.timeout(None, reason=f"[Youkai] {reason}")
            response = self.bot.embedder.get_response(
                "timeout removido usuario libre", user=user.mention
            )
            await interaction.followup.send(response)
            await send_audit(
                interaction.guild, self.bot.db, "unmute",
                actor=interaction.user, target=user, reason=reason,
            )
        except discord.Forbidden:
            await interaction.followup.send("Sin permisos.", ephemeral=True)

    # ── /warn ───────────────────────────────────────────────────────────────

    @app_commands.command(name="warn", description="Emite una advertencia formal a un usuario")
    @app_commands.describe(user="Usuario", reason="Razón de la advertencia")
    @app_commands.guild_only()
    @require_level(PermLevel.MOD)
    async def warn(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str,
    ):
        await interaction.response.defer()
        total = await self.bot.db.add_warning(
            interaction.guild.id, user.id, interaction.user.id, reason
        )
        await self.bot.db.add_infraction(interaction.guild.id, user.id)

        response = self.bot.embedder.get_response(
            "advertencia registrada para usuario", user=user.mention, reason=reason
        )
        await interaction.followup.send(f"{response} (Total: {total} advertencias)")

        # Auto-escalation
        max_warns = self.bot.config.max_warn_before_action
        if total >= max_warns:
            try:
                until = discord.utils.utcnow() + datetime.timedelta(hours=1)
                await user.timeout(
                    until, reason=f"[Youkai] Auto-timeout: {total} advertencias"
                )
                await interaction.channel.send(
                    f"⚠️ {user.mention} ha alcanzado {total} advertencias — "
                    f"timeout automático de 1h aplicado."
                )
            except Exception as exc:
                logger.error("mod: auto-timeout failed for {}: {}", user, exc)

        await send_audit(
            interaction.guild, self.bot.db, "warn",
            actor=interaction.user, target=user,
            reason=reason, extra={"total_warns": total},
        )

    # ── /warnings ───────────────────────────────────────────────────────────

    @app_commands.command(name="warnings", description="Muestra las advertencias de un usuario")
    @app_commands.describe(user="Usuario a consultar")
    @app_commands.guild_only()
    @require_level(PermLevel.MOD)
    async def warnings(self, interaction: discord.Interaction, user: discord.Member):
        warns = await self.bot.db.get_warnings(interaction.guild.id, user.id)
        if not warns:
            await interaction.response.send_message(
                f"{user.mention} no tiene advertencias registradas.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"⚠️ Advertencias de {user.display_name}",
            color=0xFBB848,
        )
        for i, w in enumerate(warns[:10], 1):
            ts = datetime.datetime.fromtimestamp(w["timestamp"]).strftime("%Y-%m-%d %H:%M")
            embed.add_field(
                name=f"#{i} — {ts}",
                value=w.get("reason", "Sin razón") or "Sin razón",
                inline=False,
            )
        embed.set_footer(text=f"Total: {len(warns)} advertencias")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /clearwarnings ──────────────────────────────────────────────────────

    @app_commands.command(
        name="clearwarnings", description="Limpia todas las advertencias de un usuario"
    )
    @app_commands.describe(user="Usuario")
    @app_commands.guild_only()
    @require_level(PermLevel.ADMIN)
    async def clearwarnings(self, interaction: discord.Interaction, user: discord.Member):
        await self.bot.db.clear_warnings(interaction.guild.id, user.id)
        await interaction.response.send_message(
            f"✅ Advertencias de {user.mention} eliminadas.", ephemeral=True
        )

    # ── /purge ───────────────────────────────────────────────────────────────

    @app_commands.command(name="purge", description="Elimina mensajes recientes del canal")
    @app_commands.describe(
        count="Cantidad de mensajes (1-100)",
        user="Filtrar solo mensajes de este usuario (opcional)",
    )
    @app_commands.guild_only()
    @require_level(PermLevel.MOD)
    async def purge(
        self,
        interaction: discord.Interaction,
        count: app_commands.Range[int, 1, 100],
        user: Optional[discord.Member] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        try:
            check = (lambda m: m.author == user) if user else None
            deleted = await interaction.channel.purge(limit=count, check=check)
            response = self.bot.embedder.get_response(
                "mensajes eliminados del canal", count=len(deleted)
            )
            await interaction.followup.send(response, ephemeral=True)
            await send_audit(
                interaction.guild, self.bot.db, "purge",
                actor=interaction.user,
                extra={"deleted": len(deleted), "channel": interaction.channel.name},
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "Sin permisos para eliminar mensajes.", ephemeral=True
            )

    # ── /slowmode ────────────────────────────────────────────────────────────

    @app_commands.command(name="slowmode", description="Activa el modo lento en un canal")
    @app_commands.describe(
        seconds="Segundos entre mensajes (0 para desactivar)",
        channel="Canal (por defecto el actual)",
    )
    @app_commands.guild_only()
    @require_level(PermLevel.MOD)
    async def slowmode(
        self,
        interaction: discord.Interaction,
        seconds: app_commands.Range[int, 0, 21600],
        channel: Optional[discord.TextChannel] = None,
    ):
        target_ch = channel or interaction.channel
        await target_ch.edit(slowmode_delay=seconds)
        if seconds == 0:
            response = self.bot.embedder.get_response(
                "slowmode desactivado canal normal", channel=target_ch.mention
            )
        else:
            response = self.bot.embedder.get_response(
                "slowmode activado canal",
                channel=target_ch.mention, duration=f"{seconds}s",
            )
        await interaction.response.send_message(response, ephemeral=True)

    # ── /lock ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="lock", description="Bloquea un canal (miembros no pueden escribir)")
    @app_commands.describe(channel="Canal (por defecto el actual)", reason="Razón")
    @app_commands.guild_only()
    @require_level(PermLevel.MOD)
    async def lock(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        reason: str = "Canal bloqueado temporalmente",
    ):
        target_ch = channel or interaction.channel
        overwrite = target_ch.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False
        await target_ch.set_permissions(
            interaction.guild.default_role, overwrite=overwrite, reason=reason
        )
        response = self.bot.embedder.get_response(
            "canal bloqueado miembros no pueden escribir", channel=target_ch.mention
        )
        await interaction.response.send_message(response)
        await send_audit(
            interaction.guild, self.bot.db, "lock",
            actor=interaction.user, reason=reason,
        )

    # ── /unlock ───────────────────────────────────────────────────────────────

    @app_commands.command(name="unlock", description="Desbloquea un canal")
    @app_commands.describe(channel="Canal (por defecto el actual)")
    @app_commands.guild_only()
    @require_level(PermLevel.MOD)
    async def unlock(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ):
        target_ch = channel or interaction.channel
        overwrite = target_ch.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = None
        await target_ch.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        response = self.bot.embedder.get_response(
            "canal desbloqueado miembros pueden escribir", channel=target_ch.mention
        )
        await interaction.response.send_message(response)
        await send_audit(
            interaction.guild, self.bot.db, "unlock",
            actor=interaction.user,
        )

    # ── /nick ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="nick", description="Cambia el apodo de un usuario")
    @app_commands.describe(user="Usuario", nickname="Nuevo apodo (vacío para resetear)")
    @app_commands.guild_only()
    @require_level(PermLevel.MOD)
    async def nick(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        nickname: Optional[str] = None,
    ):
        try:
            await user.edit(nick=nickname)
            msg = (
                f"✅ Apodo de {user.mention} reseteado."
                if not nickname
                else f"✅ Apodo de {user.mention} cambiado a `{nickname}`."
            )
            await interaction.response.send_message(msg, ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                "Sin permisos para cambiar el apodo.", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(ModerationCog(bot))

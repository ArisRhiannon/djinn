"""
Cog: Admin — Configuración de Fairy.
Solo accesible por owner del servidor o miembros con permiso Administrator.

Correcciones respecto a la versión anterior:
  - Estado del LLM leído desde orchestrator.client.ready (correcto).
  - Estado del TTS leído desde TTSEngine.available (property correcta).
"""

from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from utils.security import PermLevel, require_level, get_perm_level


class AdminCog(commands.Cog, name="Admin"):
    """Comandos de configuración de Fairy (requiere Administrador)."""

    def __init__(self, bot):
        self.bot = bot

    fairy_group = app_commands.Group(
        name="fairy",
        description="Configuración de Fairy",
        guild_only=True,
    )

    # ── /fairy setup ───────────────────────────────────────────────────────

    @fairy_group.command(name="setup", description="Configuración inicial de Fairy")
    @require_level(PermLevel.ADMIN)
    async def setup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.bot.db.init_guild(interaction.guild.id)

        embed = discord.Embed(
            title="⚡ Fairy — Configuración inicial",
            description=(
                "Fairy está lista para este servidor.\n\n"
                "**Próximos pasos recomendados:**\n"
                "1. `/fairy readers add @rol` — define qué roles pueden hablarle a Youkai\n"
                "2. `/fairy auditlog #canal` — configura dónde se registran las acciones\n"
                "3. `/fairy welcome #canal mensaje` — mensaje de bienvenida (opcional)\n"
                "4. `/fairy automod on` — activa la moderación automática\n\n"
                "Por defecto **nadie** puede usar lenguaje natural con Fairy hasta que "
                "configures los readers."
            ),
            color=0x5865F2,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /fairy readers ─────────────────────────────────────────────────────

    readers_group = app_commands.Group(
        name="readers",
        description="Gestión de roles que pueden hablarle a Youkai",
        parent=fairy_group,
    )

    @readers_group.command(name="add", description="Permite que un rol use lenguaje natural")
    @app_commands.describe(role="Rol que podrá mencionar a Fairy")
    @require_level(PermLevel.ADMIN)
    async def readers_add(self, interaction: discord.Interaction, role: discord.Role):
        await self.bot.db.add_youkai_reader(interaction.guild.id, role.id)
        await interaction.response.send_message(
            f"✅ `@{role.name}` puede ahora hablarle a Youkai.", ephemeral=True
        )

    @readers_group.command(name="remove", description="Quita el acceso a un rol")
    @app_commands.describe(role="Rol a retirar")
    @require_level(PermLevel.ADMIN)
    async def readers_remove(self, interaction: discord.Interaction, role: discord.Role):
        await self.bot.db.remove_youkai_reader(interaction.guild.id, role.id)
        await interaction.response.send_message(
            f"✅ `@{role.name}` ya no puede hablarle a Youkai.", ephemeral=True
        )

    @readers_group.command(name="list", description="Lista los roles con acceso a Fairy")
    @require_level(PermLevel.MOD)
    async def readers_list(self, interaction: discord.Interaction):
        role_ids = await self.bot.db.get_youkai_readers(interaction.guild.id)
        if not role_ids:
            await interaction.response.send_message(
                "Ningún rol configurado. Usa `/fairy readers add`.", ephemeral=True
            )
            return

        roles = []
        for rid in role_ids:
            role = interaction.guild.get_role(rid)
            roles.append(f"• {role.mention}" if role else f"• `{rid}` (rol eliminado)")

        embed = discord.Embed(
            title="🔐 Youkai Readers",
            description="\n".join(roles),
            color=0x5865F2,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /fairy auditlog ────────────────────────────────────────────────────

    @fairy_group.command(name="auditlog", description="Configura el canal de audit log")
    @app_commands.describe(channel="Canal donde Fairy registrará sus acciones")
    @require_level(PermLevel.ADMIN)
    async def auditlog(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        await self.bot.db.set_guild_config(interaction.guild.id, audit_ch=channel.id)
        await interaction.response.send_message(
            f"✅ Audit log configurado en {channel.mention}.", ephemeral=True
        )

    # ── /fairy autorole ────────────────────────────────────────────────────

    @fairy_group.command(name="autorole", description="Asigna un rol automáticamente a nuevos miembros")
    @app_commands.describe(role="Rol a asignar (vacío para desactivar)")
    @require_level(PermLevel.ADMIN)
    async def autorole(
        self, interaction: discord.Interaction, role: Optional[discord.Role] = None
    ):
        await self.bot.db.set_guild_config(
            interaction.guild.id,
            autorole_id=role.id if role else None,
        )
        msg = (
            f"✅ Auto-rol configurado: `@{role.name}`."
            if role
            else "✅ Auto-rol desactivado."
        )
        await interaction.response.send_message(msg, ephemeral=True)

    # ── /fairy automod ─────────────────────────────────────────────────────

    @fairy_group.command(name="automod", description="Activa/desactiva la moderación automática")
    @app_commands.describe(enabled="on = activar, off = desactivar")
    @app_commands.choices(enabled=[
        app_commands.Choice(name="Activar",    value="on"),
        app_commands.Choice(name="Desactivar", value="off"),
    ])
    @require_level(PermLevel.ADMIN)
    async def automod(self, interaction: discord.Interaction, enabled: str):
        state = 1 if enabled == "on" else 0
        await self.bot.db.set_guild_config(interaction.guild.id, automod_on=state)
        icon = "✅" if state else "⏸️"
        await interaction.response.send_message(
            f"{icon} Automod {'activado' if state else 'desactivado'}.", ephemeral=True
        )

    # ── /fairy ttsrole ─────────────────────────────────────────────────────

    @fairy_group.command(name="ttsrole", description="Configura qué rol puede usar /tts speak")
    @app_commands.describe(role="Rol (vacío = solo moderadores)")
    @require_level(PermLevel.ADMIN)
    async def ttsrole(
        self, interaction: discord.Interaction, role: Optional[discord.Role] = None
    ):
        await self.bot.db.set_guild_config(
            interaction.guild.id, tts_role=role.id if role else None
        )
        msg = (
            f"✅ Rol TTS: `@{role.name}`."
            if role
            else "✅ TTS solo disponible para moderadores."
        )
        await interaction.response.send_message(msg, ephemeral=True)

    # ── /fairy status ──────────────────────────────────────────────────────

    @fairy_group.command(name="status", description="Muestra la configuración actual de Fairy")
    @require_level(PermLevel.MOD)
    async def status(self, interaction: discord.Interaction):
        config    = await self.bot.db.get_guild_config(interaction.guild.id)
        reader_ids = await self.bot.db.get_youkai_readers(interaction.guild.id)

        def ch(cid):
            if not cid:
                return "No configurado"
            c = interaction.guild.get_channel(cid)
            return c.mention if c else f"`{cid}`"

        def role(rid):
            if not rid:
                return "No configurado"
            r = interaction.guild.get_role(rid)
            return r.mention if r else f"`{rid}`"

        reader_roles = [
            (interaction.guild.get_role(rid).mention
             if interaction.guild.get_role(rid) else f"`{rid}`")
            for rid in reader_ids
        ]

        # Comprobar disponibilidad del LLM (Google AI / Orchestrator)
        llm_ready = (
            self.bot.orchestrator is not None
            and getattr(self.bot.orchestrator, "llm", None) is not None
            and self.bot.orchestrator.llm.ready
        )
        tts_ready = self.bot.tts is not None and self.bot.tts.available

        embed = discord.Embed(title="⚡ Fairy — Estado del servidor", color=0x5865F2)
        embed.add_field(name="Audit Log",  value=ch(config.get("audit_ch")),    inline=True)
        embed.add_field(name="Bienvenida", value=ch(config.get("welcome_ch")),  inline=True)
        embed.add_field(name="Auto-rol",   value=role(config.get("autorole_id")), inline=True)
        embed.add_field(
            name="Automod",
            value="✅ Activo" if config.get("automod_on", 1) else "⏸️ Inactivo",
            inline=True,
        )
        embed.add_field(name="Rol TTS", value=role(config.get("tts_role")), inline=True)
        embed.add_field(
            name="LLM (Gemma)", value="✅ Listo" if llm_ready else "❌ No disponible",
            inline=True,
        )
        embed.add_field(
            name="TTS (Piper)", value="✅ Listo" if tts_ready else "❌ No disponible",
            inline=True,
        )
        embed.add_field(
            name=f"Youkai Readers ({len(reader_roles)})",
            value="\n".join(reader_roles) if reader_roles else "Ninguno configurado",
            inline=False,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AdminCog(bot))

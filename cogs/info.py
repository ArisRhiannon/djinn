"""
Cog: Info — Comandos públicos (todos los usuarios).
Sin permisos especiales requeridos.
"""

from __future__ import annotations
import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands


class InfoCog(commands.Cog, name="Info"):
    """Comandos informativos para todos los usuarios."""

    def __init__(self, bot):
        self.bot = bot

    # ── /ping ──────────────────────────────────────────────────────────────

    @app_commands.command(name="ping", description="Latencia del bot")
    async def ping(self, interaction: discord.Interaction):
        latency_ms = round(self.bot.latency * 1000)
        color = 0x57F287 if latency_ms < 100 else (0xFEE75C if latency_ms < 200 else 0xED4245)
        embed = discord.Embed(
            description=f"🏓 `{latency_ms}ms` — {'Óptima' if latency_ms < 100 else 'Acceptable' if latency_ms < 200 else 'Alta'}",
            color=color,
        )
        await interaction.response.send_message(embed=embed)

    # ── /userinfo ──────────────────────────────────────────────────────────

    @app_commands.command(name="userinfo", description="Información de un usuario")
    @app_commands.describe(user="Usuario a consultar (vacío = tú mismo)")
    async def userinfo(
        self, interaction: discord.Interaction, user: Optional[discord.Member] = None
    ):
        member = user or interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("Solo funciona en servidores.", ephemeral=True)
            return

        roles = [r.mention for r in member.roles[1:]][:10]  # Skip @everyone
        warns = await self.bot.db.count_warnings(interaction.guild.id, member.id) if interaction.guild else 0
        trust = await self.bot.db.get_trust(interaction.guild.id, member.id) if interaction.guild else None

        embed = discord.Embed(
            title=f"{member.display_name}",
            color=member.color if member.color != discord.Color.default() else 0x5865F2,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
        embed.add_field(
            name="Cuenta creada",
            value=f"<t:{int(member.created_at.timestamp())}:R>",
            inline=True,
        )
        embed.add_field(
            name="Entró al servidor",
            value=f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Desconocido",
            inline=True,
        )
        if roles:
            embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles), inline=False)
        if warns > 0:
            embed.add_field(name="⚠️ Advertencias", value=str(warns), inline=True)
        if trust:
            embed.add_field(name="Mensajes", value=str(trust.get("message_count", 0)), inline=True)

        embed.set_footer(text=f"Bot: {'Sí' if member.bot else 'No'}")
        await interaction.response.send_message(embed=embed)

    # ── /serverinfo ────────────────────────────────────────────────────────

    @app_commands.command(name="serverinfo", description="Información del servidor")
    @app_commands.guild_only()
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild

        embed = discord.Embed(
            title=guild.name,
            color=0x5865F2,
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="ID", value=f"`{guild.id}`", inline=True)
        embed.add_field(
            name="Creado",
            value=f"<t:{int(guild.created_at.timestamp())}:R>",
            inline=True,
        )
        embed.add_field(name="Dueño", value=f"<@{guild.owner_id}>", inline=True)
        embed.add_field(name="Miembros", value=str(guild.member_count), inline=True)
        embed.add_field(name="Canales de texto", value=str(len(guild.text_channels)), inline=True)
        embed.add_field(name="Canales de voz", value=str(len(guild.voice_channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Emojis", value=str(len(guild.emojis)), inline=True)
        embed.add_field(
            name="Nivel de boost",
            value=f"Nivel {guild.premium_tier} ({guild.premium_subscription_count} boosts)",
            inline=True,
        )

        await interaction.response.send_message(embed=embed)

    # ── /avatar ────────────────────────────────────────────────────────────

    @app_commands.command(name="avatar", description="Muestra el avatar de un usuario")
    @app_commands.describe(user="Usuario (vacío = tú mismo)")
    async def avatar(
        self, interaction: discord.Interaction, user: Optional[discord.User] = None
    ):
        target = user or interaction.user
        embed = discord.Embed(color=0x5865F2)
        embed.set_author(name=target.display_name)
        embed.set_image(url=target.display_avatar.url)
        links = f"[PNG]({target.display_avatar.replace(format='png').url}) | [WEBP]({target.display_avatar.replace(format='webp').url})"
        embed.description = links
        await interaction.response.send_message(embed=embed)

    # ── /roleinfo ──────────────────────────────────────────────────────────

    @app_commands.command(name="roleinfo", description="Información de un rol")
    @app_commands.describe(role="Rol a consultar")
    @app_commands.guild_only()
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        embed = discord.Embed(
            title=f"@{role.name}",
            color=role.color if role.color.value else 0x5865F2,
        )
        embed.add_field(name="ID", value=f"`{role.id}`", inline=True)
        embed.add_field(name="Miembros", value=str(len(role.members)), inline=True)
        embed.add_field(name="Mentionable", value="Sí" if role.mentionable else "No", inline=True)
        embed.add_field(name="Visible en lista", value="Sí" if role.hoist else "No", inline=True)
        embed.add_field(
            name="Color",
            value=str(role.color) if role.color.value else "Por defecto",
            inline=True,
        )
        embed.add_field(
            name="Posición",
            value=str(role.position),
            inline=True,
        )
        await interaction.response.send_message(embed=embed)

    # ── /botinfo ───────────────────────────────────────────────────────────

    @app_commands.command(name="botinfo", description="Información sobre Fairy")
    async def botinfo(self, interaction: discord.Interaction):
        import platform, sys
        embed = discord.Embed(
            title="🌸 Fairy",
            description="Asistente de moderación con lenguaje natural.\nInspirada en la IA de Zenless Zone Zero.",
            color=0xEB459E,
        )
        embed.add_field(name="Versión Python", value=platform.python_version(), inline=True)
        embed.add_field(name="discord.py", value=discord.__version__, inline=True)
        embed.add_field(name="Latencia", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="Servidores", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(
            name="NLP",
            value="✅ Activo" if (self.bot.orchestrator and self.bot.orchestrator.llm.ready) else "❌ No disponible",
            inline=True,
        )
        embed.add_field(
            name="TTS",
            value="✅ Activo" if self.bot.tts and self.bot.tts.available else "❌ No disponible",
            inline=True,
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    # ── /poll ──────────────────────────────────────────────────────────────

    @app_commands.command(name="poll", description="Crea una encuesta rápida")
    @app_commands.describe(
        question="Pregunta de la encuesta",
        options="Opciones separadas por coma (máx 9)",
    )
    async def poll(
        self, interaction: discord.Interaction, question: str, options: str
    ):
        opt_list = [o.strip() for o in options.split(",") if o.strip()][:9]
        if len(opt_list) < 2:
            await interaction.response.send_message(
                "Necesitas al menos 2 opciones separadas por coma.", ephemeral=True
            )
            return

        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
        description = "\n".join(
            f"{emojis[i]} {opt}" for i, opt in enumerate(opt_list)
        )

        embed = discord.Embed(
            title=f"📊 {question}",
            description=description,
            color=0x5865F2,
        )
        embed.set_footer(text=f"Encuesta creada por {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        for i in range(len(opt_list)):
            await msg.add_reaction(emojis[i])

    # ── /help ──────────────────────────────────────────────────────────────

    @app_commands.command(name="help", description="Lista de comandos disponibles")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🌸 Fairy — Comandos",
            color=0xEB459E,
        )
        embed.add_field(
            name="📢 Todos",
            value=(
                "`/ping` `/userinfo` `/serverinfo` `/avatar` "
                "`/roleinfo` `/botinfo` `/poll` `/help`"
            ),
            inline=False,
        )
        embed.add_field(
            name="🛡️ Moderadores",
            value=(
                "`/ban` `/kick` `/mute` `/unmute` `/warn` `/warnings` "
                "`/purge` `/slowmode` `/lock` `/unlock` `/nick` `/announce`"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚙️ Administradores",
            value=(
                "`/fairy setup` `/fairy readers` `/fairy auditlog` "
                "`/fairy welcome` `/fairy autorole` `/fairy automod` "
                "`/fairy ttsrole` `/fairy status` `/clearwarnings`"
            ),
            inline=False,
        )
        embed.add_field(
            name="🎙️ TTS (Voz)",
            value="`/tts join` `/tts leave` `/tts speak` `/tts voice`",
            inline=False,
        )
        embed.add_field(
            name="💬 Lenguaje natural",
            value=(
                "Menciona a Fairy con un comando en español natural.\n"
                "Ejemplo: `@Fairy silencia a @usuario por 30 minutos por flood`\n"
                "_Requiere rol autorizado por el admin._"
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(InfoCog(bot))

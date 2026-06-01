"""
Cog: Role Persistence — Guarda los roles de los usuarios y los restaura cuando regresan.

Excluye roles con permisos administrativos o de moderación por seguridad.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.security import PermLevel, require_level

logger = logging.getLogger("djinn.role_persistence")


class RolePersistenceCog(commands.Cog, name="RolePersistence"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._initial_scan_done = False
        self._scan_task = None

    async def cog_load(self) -> None:
        self._scan_task = asyncio.create_task(self.initial_scan())

    def cog_unload(self) -> None:
        if self._scan_task:
            self._scan_task.cancel()

    def is_safe_role(self, role: discord.Role) -> bool:
        """Determina si un rol es seguro y asignable de forma automática.
        
        Omitimos:
        - El rol por defecto (@everyone).
        - Roles administrados por integraciones o bots.
        - Roles con permisos administrativos o de moderación.
        """
        if role.is_default() or role.managed:
            return False

        perms = role.permissions
        if any([
            perms.administrator,
            perms.kick_members,
            perms.ban_members,
            perms.moderate_members,
            perms.manage_messages,
            perms.manage_roles,
            perms.manage_guild,
            perms.manage_channels,
        ]):
            return False

        return True

    async def initial_scan(self) -> None:
        """Realiza un backup inicial de todos los usuarios de los servidores al iniciar."""
        await self.bot.wait_until_ready()
        # Esperar un momento a que las cachés se estabilicen
        await asyncio.sleep(5)

        db = self.bot.db # type: ignore
        if not db:
            logger.error("RolePersistence: No se encontró base de datos disponible.")
            return

        logger.info("RolePersistence: Iniciando escaneo de roles en todos los servidores...")
        
        for guild in self.bot.guilds:
            logger.info("RolePersistence: Escaneando roles para el servidor %s (%s)", guild.name, guild.id)
            members_data = []
            try:
                async for member in guild.fetch_members(limit=None):
                    if member.bot:
                        continue
                    safe_roles = [role.id for role in member.roles if self.is_safe_role(role)]
                    members_data.append((member.id, safe_roles))
            except Exception as exc:
                logger.error("RolePersistence: Error escaneando miembros para el servidor %s: %s", guild.id, exc)
                continue

            if members_data:
                try:
                    await db.bulk_save_persisted_roles(guild.id, members_data)
                    logger.info(
                        "RolePersistence: Backup inicial completado para %d miembros en %s.",
                        len(members_data), guild.name
                    )
                except Exception as exc:
                    logger.error("RolePersistence: Error guardando backup de roles para %s: %s", guild.name, exc)
                    
        self._initial_scan_done = True
        logger.info("RolePersistence: Escaneo inicial de roles finalizado.")

    # ── Eventos / Listeners ──────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        """Detecta cambios en los roles de los miembros y los guarda."""
        if after.bot:
            return

        # Solo nos interesan cambios de roles
        if before.roles == after.roles:
            return

        db = self.bot.db # type: ignore
        if not db:
            return

        safe_role_ids = [role.id for role in after.roles if self.is_safe_role(role)]

        try:
            await db.save_persisted_roles(after.guild.id, after.id, safe_role_ids)
            logger.debug("RolePersistence: Roles de %s (%s) actualizados: %s", after.name, after.id, safe_role_ids)
        except Exception as exc:
            logger.error("RolePersistence: Error en on_member_update para %s: %s", after.id, exc)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Restaura los roles guardados de un usuario cuando reingresa."""
        if member.bot:
            return

        db = self.bot.db # type: ignore
        if not db:
            return

        guild = member.guild
        try:
            persisted_ids = await db.get_persisted_roles(guild.id, member.id)
            if not persisted_ids:
                logger.info("RolePersistence: No hay roles guardados para %s (%s)", member.name, member.id)
                return

            roles_to_add: List[discord.Role] = []
            for r_id in persisted_ids:
                role = guild.get_role(r_id)
                if not role:
                    continue
                # Doble verificación de seguridad
                if not self.is_safe_role(role):
                    continue
                # Respetar la jerarquía de roles de Discord
                if role >= guild.me.top_role:
                    logger.warning(
                        "RolePersistence: Omitiendo rol %s (%s) por jerarquía superior a la del bot.",
                        role.name, role.id
                    )
                    continue
                roles_to_add.append(role)

            if roles_to_add:
                if not guild.me.guild_permissions.manage_roles:
                    logger.error("RolePersistence: Sin permiso 'Gestionar Roles' para restaurar en %s.", guild.name)
                    return

                try:
                    # Intento de asignación masiva rápida
                    await member.add_roles(*roles_to_add, reason="Restauración automática de roles al reingresar")
                    logger.info(
                        "RolePersistence: Roles restaurados para %s (%s): %s",
                        member.name, member.id, [r.name for r in roles_to_add]
                    )
                except (discord.Forbidden, discord.HTTPException) as exc:
                    logger.warning(
                        "RolePersistence: Fallo en asignación masiva para %s (%s). Intentando uno por uno: %s",
                        member.name, member.id, exc
                    )
                    # Intento uno por uno para maximizar robustez
                    success_names = []
                    for role in roles_to_add:
                        try:
                            await member.add_roles(role, reason="Restauración individual al reingresar")
                            success_names.append(role.name)
                        except Exception as e:
                            logger.error("RolePersistence: Falló asignar rol %s a %s: %s", role.name, member.name, e)
                    if success_names:
                        logger.info("RolePersistence: Roles asignados individualmente a %s: %s", member.name, success_names)
        except Exception as exc:
            logger.error("RolePersistence: Error en on_member_join para %s: %s", member.id, exc)

    # ── Comandos de Administración / Test ─────────────────────────────────────

    @app_commands.command(
        name="role_persistence_backup",
        description="Fuerza un backup manual de los roles de todos los usuarios en este servidor"
    )
    @app_commands.guild_only()
    @require_level(PermLevel.ADMIN)
    async def role_persistence_backup_cmd(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        db = self.bot.db # type: ignore
        guild = interaction.guild
        if not guild or not db:
            await interaction.followup.send("❌ Error: No se puede acceder al servidor o a la base de datos.", ephemeral=True)
            return

        try:
            members_data = []
            async for member in guild.fetch_members(limit=None):
                if member.bot:
                    continue
                safe_roles = [role.id for role in member.roles if self.is_safe_role(role)]
                members_data.append((member.id, safe_roles))

            if members_data:
                await db.bulk_save_persisted_roles(guild.id, members_data)
                await interaction.followup.send(
                    f"✅ Backup completado exitosamente para **{len(members_data)}** miembros en este servidor.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send("⚠️ No se encontraron miembros elegibles para guardar.", ephemeral=True)
        except Exception as e:
            logger.exception("RolePersistence: Error en comando de backup manual")
            await interaction.followup.send(f"❌ Error al realizar backup: {str(e)}", ephemeral=True)

    @app_commands.command(
        name="role_persistence_show",
        description="Muestra los roles persistidos de un usuario específico en la base de datos"
    )
    @app_commands.describe(member="Usuario a consultar")
    @app_commands.guild_only()
    @require_level(PermLevel.ADMIN)
    async def role_persistence_show_cmd(self, interaction: discord.Interaction, member: discord.Member) -> None:
        await interaction.response.defer(ephemeral=True)
        db = self.bot.db # type: ignore
        if not db:
            await interaction.followup.send("❌ Error: Base de datos no disponible.", ephemeral=True)
            return

        try:
            role_ids = await db.get_persisted_roles(interaction.guild_id, member.id)
            if not role_ids:
                await interaction.followup.send(f"ℹ️ No hay roles guardados para **{member.name}** en la BD.", ephemeral=True)
                return

            role_mentions = []
            for r_id in role_ids:
                role = interaction.guild.get_role(r_id)
                if role:
                    role_mentions.append(f"{role.mention} (`{role.name}`)")
                else:
                    role_mentions.append(f"❌ Rol Eliminado (ID: `{r_id}`)")

            embed = discord.Embed(
                title=f"Roles persistidos de {member.name}",
                color=0x3498db,
                description="\n".join(role_mentions)
            )
            embed.set_footer(text=f"ID de Usuario: {member.id}")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.exception("RolePersistence: Error en comando de consulta")
            await interaction.followup.send(f"❌ Error al consultar la BD: {str(e)}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RolePersistenceCog(bot))

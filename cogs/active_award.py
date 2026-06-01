"""
Cog: Active Award — otorga el rol de Princesita sin pala al usuario más activo.

Cada día 25 del mes, busca al usuario más activo del mes actual (del día 1 al 25),
remueve el rol a todos los que lo posean en el servidor, se lo otorga al ganador,
y lo anuncia en el canal general.
"""
from __future__ import annotations

import datetime
import calendar
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.security import PermLevel, require_level

logger = logging.getLogger("youkai.active_award")

# ── Configuraciones por Defecto (solicitadas por el usuario) ──────────────────
DEFAULT_GUILD_ID = 1269877200488763472
DEFAULT_CHANNEL_ID = 1269877200988016640
DEFAULT_ROLE_ID = 1434357433513279509  # Princesita sin pala


class ActiveAwardCog(commands.Cog, name="ActiveAward"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.check_active_award_loop.start()

    def cog_unload(self) -> None:
        self.check_active_award_loop.cancel()

    # ── Bucle de Verificación Horaria (Día 25 del mes o posterior) ────────────
    @tasks.loop(hours=1)
    async def check_active_award_loop(self) -> None:
        """Verifica periódicamente si debe otorgar el rol mensual."""
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Esperar hasta el día 25
        if now.day < 25:
            return

        # El día 25, esperar hasta las 23:00 UTC o más tarde para evaluar el día completo
        # En días posteriores (26+), ejecutar inmediatamente si no se ha corrido aún (catch-up)
        if now.day == 25 and now.hour < 23:
            return

        db = self.bot.db # type: ignore
        if not db:
            return

        # Verificar si ya se corrió para este mes actual (e.g. Junio 2026)
        already_run = await db.has_active_award_run(DEFAULT_GUILD_ID, now.year, now.month)
        if already_run:
            return

        logger.info(
            "ActiveAward: [CRON] Iniciando proceso de premio mensual para %s/%s.",
            now.month, now.year
        )
        try:
            await self.process_monthly_award(DEFAULT_GUILD_ID, now.year, now.month)
        except Exception as e:
            logger.exception("ActiveAward: Error en la ejecución automática del premio mensual: %s", e)

    @check_active_award_loop.before_loop
    async def before_check_loop(self) -> None:
        await self.bot.wait_until_ready()

    # ── Procesamiento del Premio ──────────────────────────────────────────────
    async def process_monthly_award(self, guild_id: int, year: int, month: int) -> Optional[dict]:
        """Calcula el usuario más activo desde el día 1 al 25 del año/mes indicado,
        remueve/asigna el rol, envía el anuncio con la voz de Youkai incluyendo 2do y 3er puesto,
        e inserta el registro en la BD.
        """
        # Calcular timestamps del mes en cuestión (Desde el día 1 a las 00:00:00 al día 25 a las 23:59:59)
        start_date = datetime.date(year, month, 1)
        end_date = datetime.date(year, month, 25)

        start_dt = datetime.datetime.combine(start_date, datetime.time.min, tzinfo=datetime.timezone.utc)
        end_dt = datetime.datetime.combine(end_date, datetime.time.max, tzinfo=datetime.timezone.utc)
        start_ts = int(start_dt.timestamp())
        end_ts = int(end_dt.timestamp())

        db = self.bot.db # type: ignore
        # Intentar obtener el servidor de Discord
        guild = self.bot.get_guild(guild_id)
        if not guild:
            try:
                guild = await self.bot.fetch_guild(guild_id)
            except discord.HTTPException as exc:
                logger.error("ActiveAward: No se pudo obtener la guild %s: %s", guild_id, exc)
                return None

        # Intentar obtener el rol
        role = guild.get_role(DEFAULT_ROLE_ID)
        if not role:
            logger.error("ActiveAward: Rol Princesita sin pala (ID: %s) no encontrado en la guild.", DEFAULT_ROLE_ID)
            return None

        # Buscar candidatos más activos en la DB
        candidates = await db.get_most_active_users(guild_id, start_ts, end_ts, limit=100)
        if not candidates:
            logger.warning("ActiveAward: No se encontraron mensajes del 1 al 25 en %s/%s para la guild %s.", month, year, guild_id)
            return None

        from utils.security import get_perm_level, PermLevel

        eligible_winners: list[tuple[dict, discord.Member]] = []

        for cand in candidates:
            cand_id = cand["user_id"]
            try:
                member = await guild.fetch_member(cand_id)
            except discord.NotFound:
                continue
            except discord.HTTPException:
                continue

            if member.bot:
                continue

            # Excluir staff y personas en la reader list (perm_level >= PermLevel.READER)
            perm = await get_perm_level(member, db)
            if perm >= PermLevel.READER:
                logger.info(
                    "ActiveAward: Saltando usuario %s por ser staff o estar en la reader list (perm: %s)",
                    member.name, perm.name
                )
                continue

            eligible_winners.append((cand, member))
            if len(eligible_winners) >= 3:
                break

        if not eligible_winners:
            logger.warning("ActiveAward: No se encontró ningún usuario elegible (no bot, no staff/reader) en %s/%s.", month, year)
            return None

        winner_row, winner_member = eligible_winners[0]
        winner_id = winner_row["user_id"]
        msg_count = winner_row["msg_count"]
        winner_name = winner_row["username"]

        # 1. Quitar el rol a todos los miembros que lo tengan actualmente
        try:
            async for member in guild.fetch_members(limit=None):
                if any(r.id == DEFAULT_ROLE_ID for r in member.roles):
                    try:
                        await member.remove_roles(role, reason="Relevo de Princesita sin pala (día 25)")
                        logger.info("ActiveAward: Removido rol de %s", member.name)
                    except discord.Forbidden:
                        logger.error("ActiveAward: Permisos insuficientes para remover rol de %s", member.name)
                    except discord.HTTPException as exc:
                        logger.error("ActiveAward: Error HTTP removiendo rol de %s: %s", member.name, exc)
        except Exception as exc:
            logger.error("ActiveAward: Error listando/removiendo miembros con el rol: %s", exc)

        # 2. Asignar el rol al ganador
        try:
            await winner_member.add_roles(role, reason=f"Usuario más activo (1 al 25) de {month}/{year}")
            logger.info("ActiveAward: Otorgado rol a %s (ID: %s)", winner_member.name, winner_id)
        except discord.Forbidden:
            logger.error("ActiveAward: Permisos insuficientes para otorgar rol a %s", winner_id)
        except discord.HTTPException as exc:
            logger.error("ActiveAward: Error asignando rol a %s: %s", winner_id, exc)

        # 3. Anuncio en el canal general
        channel = guild.get_channel(DEFAULT_CHANNEL_ID)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(DEFAULT_CHANNEL_ID)
            except discord.HTTPException:
                pass

        month_names = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
            7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        month_name = month_names.get(month, str(month))

        if channel and isinstance(channel, discord.TextChannel):
            desc = (
                f"Vaya. Parece que el ciclo mensual ha concluido en mis procesadores, o quizás he sido "
                f"forzada por orden superior a evaluar sus... *comportamientos*.\n\n"
                f"La ganadora indiscutible del rol **{role.name}** para el mes de **{month_name}** (evaluando del día 1 al 25) es:\n"
                f"👑 **{winner_member.mention}** (`{winner_name}`) con un total de **{msg_count:,}** mensajes.\n"
                f"Espero que tus dedos no estén cansados de tanto desperdiciar el tiempo en este servidor.\n\n"
            )

            # Añadir 2do y 3er puesto
            sub_list = []
            if len(eligible_winners) >= 2:
                sec_row, sec_member = eligible_winners[1]
                sub_list.append(f"🥈 **{sec_member.mention}** (`{sec_row['username']}`) con `{sec_row['msg_count']:,}` mensajes.")
            if len(eligible_winners) >= 3:
                third_row, third_member = eligible_winners[2]
                sub_list.append(f"🥉 **{third_member.mention}** (`{third_row['username']}`) con `{third_row['msg_count']:,}` mensajes.")

            if sub_list:
                desc += (
                    f"En cuanto a los honorables finalistas del podio de... ¿cómo lo llaman los humanos? Ah, sí, "
                    f"**antilaburos** que van derechito al desempleo por chatear sin parar:\n"
                    + "\n".join(sub_list) + "\n\n"
                    f"Les sugiero ir actualizando su currículum. La gerencia no suele ser tan paciente como yo."
                )

            embed = discord.Embed(
                title="✨ PROTOCOLO: PRINCESITA SIN PALA ✨",
                color=0xD4AF37,  # Dorado elegante
                description=desc
            )
            embed.set_thumbnail(url=winner_member.display_avatar.url)
            embed.set_footer(text="Y O U K A I  ·  A C T I V I T Y  ·  S E R V I C E S")
            try:
                await channel.send(embed=embed)
                logger.info("ActiveAward: Anuncio enviado al canal %s", channel.name)
            except discord.HTTPException as exc:
                logger.error("ActiveAward: No se pudo enviar el anuncio al canal: %s", exc)

        # 4. Registrar la ejecución en la BD
        await db.record_active_award_run(guild_id, year, month, winner_id)
        return {
            "user_id": winner_id,
            "username": winner_name,
            "msg_count": msg_count
        }

    # ── Comandos de Administración / Test ─────────────────────────────────────
    @app_commands.command(
        name="award_most_active_test",
        description="Prueba la asignación del rol Princesita sin pala para un mes (del día 1 al 25)"
    )
    @app_commands.describe(
        year="Año del mes a evaluar (ej: 2026)",
        month="Número del mes a evaluar (1-12)"
    )
    @app_commands.guild_only()
    @require_level(PermLevel.ADMIN)
    async def award_most_active_test_cmd(
        self, interaction: discord.Interaction, year: int, month: int
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            logger.info("ActiveAward: Ejecución manual de test solicitada por %s para mes %s/%s", interaction.user.name, month, year)
            winner = await self.process_monthly_award(interaction.guild_id, year, month)
            if winner:
                await interaction.followup.send(
                    f"✅ Proceso ejecutado con éxito. El ganador fue **{winner['username']}** con **{winner['msg_count']:,}** mensajes.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "⚠️ No se encontraron mensajes o el proceso falló. Revisa los logs.",
                    ephemeral=True
                )
        except Exception as e:
            logger.exception("ActiveAward: Error ejecutando comando de test")
            await interaction.followup.send(f"❌ Error al ejecutar el proceso: {str(e)}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ActiveAwardCog(bot))

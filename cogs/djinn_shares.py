"""Cog: Djinn Shares — Djinn Financial Services™

Sistema DeFi de compra de acciones, retiros y cobro de dividendos.
- /depositar <monto>: Convierte créditos en acciones (1 cr = 1 acción)
- /retirar <monto>: Convierte acciones en créditos (sujeto a liquidez)
- /dividendos: Muestra participación, dividendos acumulados y botón para reclamar
"""

from __future__ import annotations

import logging
import discord
from discord import app_commands
from discord.ext import commands

from utils.loan_engine import calculate_interest

logger = logging.getLogger("djinn.shares")


class ClaimDividendsView(discord.ui.View):
    def __init__(self, bot, user_id: int, guild_id: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.guild_id = guild_id

    @discord.ui.button(label="Reclamar Dividendos", style=discord.ButtonStyle.success, emoji="💰")
    async def claim_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("No puedes reclamar los dividendos de otra persona.", ephemeral=True)
            return

        db = self.bot.db
        try:
            claimed = await db.claim_dividends(self.user_id, self.guild_id)
            if claimed <= 0:
                await interaction.response.send_message("No tienes dividendos acumulados suficientes para reclamar (mínimo 1 crédito).", ephemeral=True)
                return

            await interaction.response.send_message(
                f"✅ ¡Has reclamado **{claimed:,}** créditos de tus dividendos acumulados! Se han sumado a tu balance.",
                ephemeral=True
            )
            # Deshabilitar el botón tras reclamar con éxito
            button.disabled = True
            await interaction.message.edit(view=self)
        except Exception as e:
            logger.error(f"Error claiming dividends: {e}")
            await interaction.response.send_message("Ocurrió un error al reclamar los dividendos.", ephemeral=True)


class DjinnShares(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    # ── /depositar ────────────────────────────────────────────────────────────

    @app_commands.command(
        name="depositar",
        description="Invierte tus créditos en la caja de la guild a cambio de acciones de la tesorería"
    )
    @app_commands.describe(monto="Cantidad de créditos a depositar e invertir")
    @app_commands.guild_only()
    async def depositar(self, interaction: discord.Interaction, monto: app_commands.Range[int, 1, None]) -> None:
        uid, gid = interaction.user.id, interaction.guild.id
        db = self.bot.db

        try:
            new_shares = await db.invest_in_treasury(uid, gid, monto)
            embed = discord.Embed(color=0x2ECC71, title="🏦 Depósito de Inversión Exitoso")
            embed.description = (
                f"Has depositado **{monto:,}** créditos en la tesorería de la guild.\n\n"
                f"📈 **Estado de tu Inversión:**\n"
                f"• Acciones obtenidas: **+{monto:,}** (1 cr = 1 acción)\n"
                f"• Total de tus acciones ahora: **{new_shares:,}** acciones"
            )
            
            bal, cap = await db.get_treasury_liquidity_info(gid)
            tasa = calculate_interest(500, bal, cap)
            embed.description += (
                f"\n\n💧 **Liquidez de la Caja:**\n"
                f"• Balance disponible: **{bal:,}** cr\n"
                f"• Capital total: **{cap:,}** cr\n"
                f"• Tasa base de préstamos (Score 500): **{int(tasa * 100)}%**"
            )
            
            embed.set_footer(text="D J I N N  ·  F I N A N C I A L  ·  S E R V I C E S")
            await interaction.response.send_message(embed=embed)
            logger.info("djinn_shares: user=%s deposited=%s in guild=%s", uid, monto, gid)
        except ValueError as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error investing in treasury: {e}")
            await interaction.response.send_message("❌ Ocurrió un error inesperado al procesar tu depósito.", ephemeral=True)

    # ── /retirar ──────────────────────────────────────────────────────────────

    @app_commands.command(
        name="retirar",
        description="Retira tus créditos invertidos vendiendo tus acciones de la tesorería"
    )
    @app_commands.describe(monto="Cantidad de acciones a vender y retirar")
    @app_commands.guild_only()
    async def retirar(self, interaction: discord.Interaction, monto: app_commands.Range[int, 1, None]) -> None:
        uid, gid = interaction.user.id, interaction.guild.id
        db = self.bot.db

        try:
            remaining_shares = await db.withdraw_from_treasury(uid, gid, monto)
            embed = discord.Embed(color=0xE74C3C, title="💸 Retiro de Inversión Exitoso")
            embed.description = (
                f"Has retirado **{monto:,}** créditos de la tesorería de la guild vendiendo tus acciones.\n\n"
                f"📉 **Estado de tu Inversión:**\n"
                f"• Acciones vendidas: **-{monto:,}**\n"
                f"• Total de tus acciones ahora: **{remaining_shares:,}** acciones"
            )
            
            bal, cap = await db.get_treasury_liquidity_info(gid)
            tasa = calculate_interest(500, bal, cap)
            embed.description += (
                f"\n\n💧 **Liquidez de la Caja:**\n"
                f"• Balance disponible: **{bal:,}** cr\n"
                f"• Capital total: **{cap:,}** cr\n"
                f"• Tasa base de préstamos (Score 500): **{int(tasa * 100)}%**"
            )
            
            embed.set_footer(text="D J I N N  ·  F I N A N C I A L  ·  S E R V I C E S")
            await interaction.response.send_message(embed=embed)
            logger.info("djinn_shares: user=%s withdrew=%s in guild=%s", uid, monto, gid)
        except ValueError as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error withdrawing from treasury: {e}")
            await interaction.response.send_message("❌ Ocurrió un error inesperado al procesar tu retiro.", ephemeral=True)

    # ── /dividendos ───────────────────────────────────────────────────────────

    @app_commands.command(
        name="dividendos",
        description="Consulta tu porcentaje de participación en el banco y dividendos acumulados"
    )
    @app_commands.guild_only()
    async def dividendos(self, interaction: discord.Interaction) -> None:
        uid, gid = interaction.user.id, interaction.guild.id
        db = self.bot.db

        try:
            row_shares = await db.fetchone(
                "SELECT shares, unclaimed_dividends FROM treasury_shares WHERE user_id=? AND guild_id=?",
                (uid, gid)
            )
            user_shares = row_shares["shares"] if row_shares else 0
            unclaimed_dividends = row_shares["unclaimed_dividends"] if row_shares else 0.0

            row_treasury = await db.fetchone(
                "SELECT total_shares, total_dividends_paid FROM guild_treasury WHERE guild_id=?",
                (gid,)
            )
            total_shares = row_treasury["total_shares"] if row_treasury else 0
            total_dividends_paid = row_treasury["total_dividends_paid"] if row_treasury else 0

            ownership = (user_shares / total_shares * 100.0) if total_shares > 0 else 0.0

            embed = discord.Embed(color=0xD4AF37, title="💸 Acciones y Dividendos — Djinn Financial Services™")
            embed.description = (
                f"Invertir en la tesorería te otorga acciones de la caja del servidor. "
                f"Cada vez que un deudor pague los intereses de su préstamo, estos se reparten "
                f"proporcionalmente entre todos los accionistas.\n\n"
                f"📊 **Tu Participación:**\n"
                f"• Acciones (Shares): **{user_shares:,}** / **{total_shares:,}** total\n"
                f"• Porcentaje de Propiedad: **{ownership:.4f}%**\n\n"
                f"💰 **Tus Dividendos:**\n"
                f"• Acumulados listos para reclamar: **{int(unclaimed_dividends):,}** créditos\n"
                f"• Fracción pendiente: **{unclaimed_dividends % 1.0:.4f}**\n"
                f"• Total histórico pagado en el servidor: **{total_dividends_paid:,}** créditos\n"
            )
            embed.set_footer(text="D J I N N  ·  F I N A N C I A L  ·  S E R V I C E S")

            view = ClaimDividendsView(self.bot, uid, gid)
            await interaction.response.send_message(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Error querying dividends: {e}")
            await interaction.response.send_message("❌ Ocurrió un error inesperado al consultar tus dividendos.", ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(DjinnShares(bot))

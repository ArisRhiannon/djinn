"""Cog: Loan Shark — Youkai Financial Services™

Sistema de préstamos agiotista. 100% determinista, sin LLM.
- Botón de préstamo cuando no hay créditos
- Cobro automático cada 24h (persiste en DB)
- Imagen MOROSO estilo Coppel para deudores
"""

from __future__ import annotations

import asyncio
import io
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from PIL import Image, ImageDraw, ImageFont

from utils.loan_engine import (
    MIN_LOAN, LOAN_TIERS, calculate_interest, get_tier_name, get_tier_label,
    compute_loan, available_tiers, msg_offer_title, msg_offer_body,
    msg_accept, msg_already_debt, msg_blacklisted, msg_moroso_title,
    msg_moroso_subtitle, CONSECUTIVE_MISSES_TO_DEFAULT,
)

logger = logging.getLogger("djinn.loan_shark")

_COLOR_LOAN = 0x9B59B6
_COLOR_MOROSO = 0xE63946

# Fonts
_FONT_BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
_FONT_BOLD = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"

# Moroso image only posted at these thresholds (consecutive misses)
_MOROSO_THRESHOLDS = {1, 3, 5, 7, 10, 15, 20, 30}


# ── Imagen MOROSO ─────────────────────────────────────────────────────────────

async def _generate_moroso_image(user: discord.Member, debt: int, days: int, late_fees: int = 0) -> io.BytesIO:
    """Genera imagen estilo cartel de moroso (Coppel México) con Pillow."""
    W, H = 600, 400
    img = Image.new("RGB", (W, H), (10, 10, 15))
    draw = ImageDraw.Draw(img)

    # Fonts
    font_title = ImageFont.truetype(_FONT_BLACK, 42)
    font_sub = ImageFont.truetype(_FONT_BOLD, 18)
    font_data = ImageFont.truetype(_FONT_BOLD, 24)
    font_small = ImageFont.truetype(_FONT_BOLD, 14)

    # Red border
    draw.rectangle([(0, 0), (W - 1, H - 1)], outline=(230, 57, 70), width=4)
    # Top red bar
    draw.rectangle([(0, 0), (W, 60)], fill=(230, 57, 70))
    # Title
    draw.text((W // 2, 30), "⚠ MOROSO ⚠", fill=(255, 255, 255), font=font_title, anchor="mm")

    # Avatar circle
    avatar_x, avatar_y = 100, 180
    try:
        avatar_url = user.display_avatar.with_size(128).url
        async with aiohttp.ClientSession() as session:
            async with session.get(avatar_url) as resp:
                avatar_data = await resp.read()
        av_img = Image.open(io.BytesIO(avatar_data)).resize((120, 120))
        # Circular mask
        mask = Image.new("L", (120, 120), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 119, 119), fill=255)
        img.paste(av_img, (avatar_x - 60, avatar_y - 60), mask)
    except Exception:
        draw.ellipse((avatar_x - 60, avatar_y - 60, avatar_x + 60, avatar_y + 60),
                     fill=(40, 40, 50), outline=(230, 57, 70), width=2)

    # Red circle border around avatar
    draw.ellipse((avatar_x - 62, avatar_y - 62, avatar_x + 62, avatar_y + 62),
                 outline=(230, 57, 70), width=3)

    # User name
    name = user.display_name[:20]
    draw.text((avatar_x, avatar_y + 75), name, fill=(255, 255, 255), font=font_data, anchor="mt")

    # Right side — data
    rx = 350
    draw.text((rx, 100), "DEUDA TOTAL", fill=(150, 150, 150), font=font_small, anchor="mt")
    draw.text((rx, 125), f"${debt:,}", fill=(230, 57, 70), font=font_title, anchor="mt")

    draw.text((rx - 70, 190), "DÍAS DE ATRASO", fill=(150, 150, 150), font=font_small, anchor="mt")
    draw.text((rx - 70, 215), str(days), fill=(255, 214, 10), font=font_data, anchor="mt")

    draw.text((rx + 70, 190), "RECARGOS", fill=(150, 150, 150), font=font_small, anchor="mt")
    draw.text((rx + 70, 215), f"${late_fees:,}", fill=(230, 57, 70), font=font_data, anchor="mt")

    draw.text((rx, 270), "ESTADO", fill=(150, 150, 150), font=font_small, anchor="mt")
    status = "MOROSO" if days < 5 else "MOROSO GRAVE"
    draw.text((rx, 295), status, fill=(230, 57, 70), font=font_data, anchor="mt")

    # Bottom bar
    draw.rectangle([(0, H - 40), (W, H)], fill=(20, 20, 25))
    draw.text((W // 2, H - 20), "Y O U K A I · S E R V I C E S — REGISTRO DE DEUDORES",
              fill=(100, 100, 100), font=font_small, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


# ── Views ─────────────────────────────────────────────────────────────────────

class LoanOfferView(discord.ui.View):
    """Vista con botones de tiers de préstamo. Solo el usuario original puede interactuar."""

    def __init__(self, bot, user_id: int, guild_id: int, score: int, message: Optional[discord.Message] = None,
                 treasury_balance: Optional[int] = None, total_capital: Optional[int] = None):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.guild_id = guild_id
        self.score = score
        self.treasury_balance = treasury_balance
        self.total_capital = total_capital
        self._msg: Optional[discord.Message] = message
        tiers = available_tiers(score)
        for t in tiers:
            terms = compute_loan(t["amount"], score, treasury_balance, total_capital)
            # Keep label under 80 chars
            label = f"${t['amount']} → ${terms['total_owed']} ({terms['installments']}d)"
            btn = discord.ui.Button(label=label, style=discord.ButtonStyle.danger, custom_id=f"loan_{t['amount']}")
            btn.callback = self._make_callback(t["amount"])
            self.add_item(btn)

    def _make_callback(self, amount: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("Este préstamo no es para ti.", ephemeral=True)
                return
            await self._accept_loan(interaction, amount)
        return callback

    async def _accept_loan(self, interaction: discord.Interaction, amount: int):
        db = self.bot.db
        # Double check no active loan
        existing = await db.get_active_loan(self.user_id, self.guild_id)
        if existing:
            await interaction.response.send_message(
                msg_already_debt(self.user_id, existing["remaining_debt"]), ephemeral=True
            )
            return

        # Fetch latest treasury info to ensure accurate dynamic rate calculation at acceptance time
        bal, cap = await db.get_treasury_liquidity_info(self.guild_id)
        terms = compute_loan(amount, self.score, bal, cap)
        # Atomic: verifica treasury y debita en la misma operación
        loan_id = await db.create_loan_with_treasury(
            self.user_id, self.guild_id, interaction.channel_id,
            terms["principal"], terms["rate"], terms["total_owed"],
            terms["installment_amt"], terms["installments"],
        )
        if loan_id is None:
            # Treasury sin fondos
            treasury = await db.get_treasury(self.guild_id)
            await interaction.response.edit_message(
                content=(
                    f"💸 *Youkai revisa su caja...*\n\n"
                    f"No tengo liquidez ahora mismo. Solo me quedan **{treasury['balance']}** créditos en el banco "
                    f"y necesitas **{terms['principal']}**. Vuelve cuando otros morosos paguen."
                ),
                embed=None, view=None,
            )
            return
        # Add credits to user (treasury ya fue debitada)
        new_bal = await db.add_credits(self.user_id, self.guild_id, amount, reason="loan")

        embed = discord.Embed(color=_COLOR_LOAN)
        embed.title = msg_accept(self.user_id)
        embed.description = (
            f"+**{amount}** créditos depositados.\n\n"
            f"📋 **Términos:**\n"
            f"• Deuda total: **{terms['total_owed']}** créditos\n"
            f"• Cuotas: **{terms['installments']}** pagos de **{terms['installment_amt']}**/día\n"
            f"• Primer cobro: <t:{int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp())}:R>\n\n"
            f"📊 Score: **{self.score}**/1000 ({get_tier_name(self.score)} — {get_tier_label(self.score)})"
        )
        embed.set_footer(text="Y O U K A I · S E R V I C E S")
        await interaction.response.edit_message(embed=embed, view=None)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self._msg:
            try:
                await self._msg.edit(view=self)
            except discord.HTTPException:
                pass


# ── Cog ───────────────────────────────────────────────────────────────────────

class LoanShark(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self._collect_lock = asyncio.Lock()

    async def cog_load(self) -> None:
        self.collection_task.start()

    async def cog_unload(self) -> None:
        self.collection_task.cancel()

    # ── Public method for nlp_handler to call ─────────────────────────────

    async def offer_loan(self, message: discord.Message, *, cost: int = 0, balance: int = 0) -> None:
        """Muestra la oferta de préstamo cuando el usuario no tiene créditos."""
        uid, gid = message.author.id, message.guild.id
        db = self.bot.db

        score_data = await db.get_loan_score(uid, gid)
        score = score_data["score"]
        active = await db.get_active_loan(uid, gid)

        if active:
            embed = discord.Embed(color=_COLOR_MOROSO, description=msg_already_debt(uid, active["remaining_debt"]))
            embed.set_footer(text=f"📊 Score: {score}/1000 ({get_tier_name(score)})")
            await message.reply(embed=embed, mention_author=False)
            return

        if score_data["blacklisted"]:
            embed = discord.Embed(color=0x000000, description=msg_blacklisted(uid))
            await message.reply(embed=embed, mention_author=False)
            return

        bal, cap = await db.get_treasury_liquidity_info(gid)
        tasa_actual = calculate_interest(score, bal, cap)

        embed = discord.Embed(color=_COLOR_LOAN)
        embed.title = msg_offer_title(uid)
        embed.description = (
            f"{msg_offer_body(uid)}\n\n"
            f"💳 Saldo: **{balance}** · Costo del request: **{cost}**\n"
            f"📊 Tu score: **{score}**/1000 ({get_tier_name(score)} — {get_tier_label(score)})\n"
            f"📈 Tasa actual: **{int(tasa_actual * 100)}%**"
        )
        expires = int((datetime.now(timezone.utc) + timedelta(seconds=15)).timestamp())
        embed.description += f"\n\n⏳ Se borra <t:{expires}:R>"
        embed.set_footer(text="Solo tú puedes aceptar este trato.")
        view = LoanOfferView(self.bot, uid, gid, score, treasury_balance=bal, total_capital=cap)
        msg = await message.reply(embed=embed, view=view, mention_author=False, delete_after=15)
        view._msg = msg

    # ── Slash: /deuda ─────────────────────────────────────────────────────

    @app_commands.command(name="deuda", description="Consulta tu estado crediticio con Youkai")
    @app_commands.guild_only()
    async def deuda(self, interaction: discord.Interaction) -> None:
        uid, gid = interaction.user.id, interaction.guild.id
        db = self.bot.db
        score_data = await db.get_loan_score(uid, gid)
        active = await db.get_active_loan(uid, gid)
        bal, cap = await db.get_treasury_liquidity_info(gid)
        tasa_actual = calculate_interest(score_data["score"], bal, cap)

        score = score_data["score"]
        embed = discord.Embed(color=_COLOR_LOAN, title="📊 Estado Crediticio")
        embed.add_field(name="Score", value=f"**{score}**/1000 ({get_tier_name(score)} — {get_tier_label(score)})", inline=True)
        embed.add_field(name="Tasa", value=f"{int(tasa_actual*100)}%", inline=True)
        embed.add_field(name="Préstamos", value=str(score_data["total_loans"]), inline=True)

        if active:
            days = (datetime.now(timezone.utc) - datetime.fromisoformat(active["created_at"])).days
            late_fees_str = f" (de los cuales **{active['accrued_late_fees']}** son recargos por mora)" if active.get("accrued_late_fees", 0) > 0 else ""
            embed.add_field(
                name="⚠️ Deuda Activa",
                value=(
                    f"Restante: **{active['remaining_debt']}** créditos{late_fees_str}\n"
                    f"Cuota diaria: **{active['installment_amt']}**\n"
                    f"Pagos: {active['paid_installments']}/{active['num_installments']}\n"
                    f"Próximo cobro: <t:{int(datetime.fromisoformat(active['next_collection']).timestamp())}:R>"
                ),
                inline=False,
            )
        else:
            embed.add_field(name="Deuda", value="Sin deuda activa ✅", inline=False)

        if score_data["blacklisted"]:
            embed.set_footer(text="🚫 BLACKLISTED — No puedes pedir préstamos")
        else:
            embed.set_footer(text="Y O U K A I · S E R V I C E S")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Collection Task ───────────────────────────────────────────────────

    @tasks.loop(minutes=5)
    async def collection_task(self) -> None:
        """Cobra cuotas de préstamos activos cuyo next_collection ya pasó."""
        if self._collect_lock.locked():
            return
        async with self._collect_lock:
            try:
                await self._collect()
            except Exception as e:
                logger.error(f"Loan collection error: {e}")

    @collection_task.before_loop
    async def _before_collection(self) -> None:
        await self.bot.wait_until_ready()

    async def _collect(self) -> None:
        db = self.bot.db
        now = datetime.now(timezone.utc)
        due_loans = await db.get_due_loans(now.isoformat())

        for loan in due_loans:
            uid, gid = loan["user_id"], loan["guild_id"]
            installment = min(loan["installment_amt"], loan["remaining_debt"])

            creds = await db.get_credits(uid, gid)
            balance = creds["balance"]

            if balance >= installment:
                # Success
                new_bal = await db.spend_credits(uid, gid, installment, reason="loan_pay")
                await db.record_loan_payment(
                    loan["id"], uid, gid, installment, installment, True, balance, new_bal
                )
                # Check if fully paid
                remaining = loan["remaining_debt"] - installment
                if remaining <= 0:
                    clean = loan["missed_installments"] == 0
                    await db.complete_loan(loan["id"], uid, gid, clean)
                    # Remove moroso role if they had one
                    morosos_cog = self.bot.get_cog("Morosos")
                    if morosos_cog and loan["missed_installments"] > 0:
                        await morosos_cog.on_moroso_cleared(gid, uid)
            else:
                # Failed
                await db.record_loan_payment(
                    loan["id"], uid, gid, installment, 0, False, balance, balance
                )
                consecutive = loan["consecutive_misses"] + 1
                if consecutive >= CONSECUTIVE_MISSES_TO_DEFAULT:
                    await db.default_loan(loan["id"], uid, gid)
                # Post moroso image only at thresholds
                if consecutive in _MOROSO_THRESHOLDS:
                    await self._post_moroso(loan, consecutive)
                # Notify morosos cog for role + shaming channel
                morosos_cog = self.bot.get_cog("Morosos")
                if morosos_cog:
                    await morosos_cog.on_new_moroso(
                        gid, uid, consecutive, loan["remaining_debt"]
                    )

    async def _post_moroso(self, loan: dict, consecutive_misses: int) -> None:
        """Genera y postea la imagen de MOROSO en el canal del préstamo."""
        try:
            guild = self.bot.get_guild(loan["guild_id"])
            if not guild:
                return
            channel = guild.get_channel(loan["channel_id"])
            if not channel:
                return
            member = guild.get_member(loan["user_id"])
            if not member:
                return

            days = (datetime.now(timezone.utc) - datetime.fromisoformat(loan["created_at"])).days
            late_fees = loan.get("accrued_late_fees", 0)
            img_buf = await _generate_moroso_image(member, loan["remaining_debt"], days, late_fees)

            title = msg_moroso_title(loan["user_id"])
            subtitle = msg_moroso_subtitle(loan["user_id"])

            file = discord.File(img_buf, filename="moroso.png")
            embed = discord.Embed(color=_COLOR_MOROSO, title=title, description=subtitle)
            embed.set_image(url="attachment://moroso.png")
            footer_text = f"Fallos consecutivos: {consecutive_misses} | Deuda: ${loan['remaining_debt']}"
            if late_fees > 0:
                footer_text += f" (de los cuales {late_fees} son recargos por mora)"
            embed.set_footer(text=footer_text)
            await channel.send(embed=embed, file=file)
        except Exception as e:
            logger.error(f"Moroso image error: {e}")


async def setup(bot) -> None:
    await bot.add_cog(LoanShark(bot))

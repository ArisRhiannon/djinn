"""Treasury (Y O U K A I · B A N K)
─────────────────────────────────────────────────────────────────────────────
Sistema de banco/tesorería del servidor.

- Pool inicial bootstrap: 6000 créditos por guild (al primer acceso).
- Préstamos otorgados: salen del pool. Si no hay fondos, no se prestan.
- Cuotas pagadas: vuelven al pool (incluyendo intereses → ganancia neta).
- Defaults: el remanente se pierde (registrado en `total_lost_defaults`).
- Staff puede depositar/entregar manualmente con /banco.
- `/créditos dar` también debita del pool (atajo de Aris/Cisart, max 1200).

Slash commands:
  /banco saldo                       — público, ver pool + stats
  /banco entregar @user monto razón  — staff (manage_guild), entrega del pool
  /banco depositar monto razón       — staff (manage_guild), ingresa al pool
  /banco historial [limit]           — público, transparencia de movimientos
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

logger = logging.getLogger("djinn.treasury")

# Paleta — turquesa para banco normal, ámbar para entregas, azul para depósitos,
# rojo para crítico. Coherente con la del logger Y O U K A I.
_COLOR_BANK = 0x2A9D8F
_COLOR_GRANT = 0xE9C46A
_COLOR_DEPOSIT = 0x457B9D
_COLOR_LOW = 0xF77F00
_COLOR_CRITICAL = 0xE63946

# Etiquetas humanas para los `reason` de los movimientos.
_REASON_LABELS = {
    "bootstrap": "🌱 Capital inicial",
    "loan_disbursed": "📤 Préstamo otorgado",
    "loan_repayment": "📥 Cuota cobrada",
    "loan_default": "💀 Default registrado",
    "staff_grant": "🎁 Entrega del staff",
    "staff_deposit": "💰 Depósito del staff",
    "event_reward": "🏆 Premio de evento",
}


def _fmt_reason(reason: str) -> str:
    return _REASON_LABELS.get(reason, reason)


def _fmt_signed(amount: int) -> str:
    """'+1,234' / '-1,234' / '0' con separador de miles."""
    if amount > 0:
        return f"+{amount:,}"
    if amount < 0:
        return f"{amount:,}"
    return "0"


def _health_for(balance: int) -> tuple[int, str, str]:
    """Mapea balance → (color, etiqueta corta, descripción)."""
    if balance < 600:
        return (_COLOR_CRITICAL, "🔴 Crítico",
                "Sin fondos — no se otorgan préstamos hasta que entren cuotas")
    if balance < 1500:
        return (_COLOR_LOW, "🟠 Bajo",
                "Solo préstamos chicos (tier 1)")
    if balance < 3000:
        return (0xFCBF49, "🟡 Estable",
                "Préstamos chicos y medianos disponibles")
    return (_COLOR_BANK, "🟢 Saludable",
            "Todos los tiers de préstamo disponibles")


class TreasuryCog(commands.Cog):
    """Comandos /banco para staff y público."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    banco = app_commands.Group(
        name="banco",
        description="Tesorería del servidor (Y O U K A I · B A N K)",
        guild_only=True,
    )

    # ── /banco saldo ────────────────────────────────────────────────────
    @banco.command(name="saldo", description="Estado actual del banco del servidor")
    async def saldo(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        gid = interaction.guild.id
        stats = await self.bot.db.get_treasury_stats(gid)

        balance = stats["balance"]
        outstanding = stats["outstanding_debt"]
        bootstrap = stats["bootstrap_amount"]
        collected = stats["total_collected"]
        disbursed = stats["total_disbursed"]
        lost = stats["total_lost_defaults"]
        # operating result = lo que el banco ganó/perdió EN OPERACIÓN
        # (cuotas cobradas - capital prestado). El bootstrap NO cuenta.
        operating = collected - disbursed
        color, health_short, health_desc = _health_for(balance)

        # Bloque principal: lo que importa AHORA (qué hay, qué está prestado)
        snapshot = (
            f"```\n"
            f"💰 En caja AHORA       {balance:>10,} cr\n"
            f"🏃 Prestado afuera     {outstanding:>10,} cr\n"
            f"🏗️ Capital inicial     {bootstrap:>10,} cr\n"
            f"```"
        )

        # Bloque secundario: histórico de operaciones (qué hizo el banco)
        ops = (
            f"```\n"
            f"📥 Cuotas cobradas      {_fmt_signed(collected):>10}\n"
            f"📤 Préstamos otorgados  {_fmt_signed(-disbursed):>10}\n"
            f"💀 Pérdidas (defaults)  {_fmt_signed(-lost):>10}\n"
            f"───────────────────────────────────\n"
            f"📊 Resultado operativo  {_fmt_signed(operating):>10}\n"
            f"```"
        )

        embed = discord.Embed(
            color=color,
            title="🏦 Y O U K A I · B A N K",
            description=snapshot,
        )
        embed.add_field(name=f"Estado · {health_short}", value=health_desc, inline=False)
        embed.add_field(name="Histórico de operaciones", value=ops, inline=False)

        # Info contable para entender el "resultado operativo"
        if collected != 0 or disbursed != 0:
            if operating > 0:
                expl = "✅ El banco gana — las cuotas con interés superan al capital prestado."
            elif operating < 0:
                expl = (
                    "⏳ El banco está en negativo de operación — hay préstamos "
                    "vivos cuyas cuotas todavía no terminaron de volver."
                )
            else:
                expl = "Equilibrio — lo prestado equivale a lo cobrado."
            embed.add_field(name="Lectura", value=expl, inline=False)

        # Top 4 movimientos por volumen
        if stats["breakdown"]:
            top = stats["breakdown"][:4]
            br_lines = []
            for b in top:
                amt = _fmt_signed(b["total"])
                label = _fmt_reason(b["reason"])
                br_lines.append(f"`{amt:>10}` · {label} ({b['count']}×)")
            embed.add_field(
                name="Top movimientos por volumen",
                value="\n".join(br_lines),
                inline=False,
            )

        embed.set_footer(text=f"Pool del servidor · {interaction.guild.name}")
        await interaction.followup.send(embed=embed)

    # ── /banco entregar ─────────────────────────────────────────────────
    @banco.command(
        name="entregar",
        description="(Staff) Entrega créditos del pool a un usuario",
    )
    @app_commands.describe(
        usuario="Receptor de los créditos",
        monto="Cantidad a entregar (sale del pool)",
        razon="Motivo visible en el historial (ej: 'Premio Halloween')",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def entregar(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        monto: app_commands.Range[int, 1, 50000],
        razon: app_commands.Range[str, 3, 100],
    ) -> None:
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "Necesitás `manage_guild` para usar esto.", ephemeral=True
            )
            return

        await interaction.response.defer()
        gid = interaction.guild.id
        meta = json.dumps({
            "target": str(usuario.id),
            "target_name": usuario.display_name,
            "by": str(interaction.user.id),
            "razon": razon,
        })
        ok, new_bal = await self.bot.db.spend_from_treasury(
            gid, monto, "staff_grant",
            metadata_json=meta,
            user_id=usuario.id,
            by_staff_id=interaction.user.id,
        )
        if not ok:
            treasury = await self.bot.db.get_treasury(gid)
            await interaction.followup.send(
                f"❌ Fondos insuficientes. En caja: **{treasury['balance']:,}** cr · "
                f"pediste **{monto:,}** cr.",
                ephemeral=True,
            )
            return

        # Acreditar al usuario.
        new_user_balance = await self.bot.db.add_credits(usuario.id, gid, monto)

        embed = discord.Embed(
            color=_COLOR_GRANT,
            title="🎁 Entrega del Banco",
            description=(
                f"**{interaction.user.display_name}** entregó "
                f"**{monto:,}** cr a {usuario.mention}.\n\n"
                f"📝 *{razon}*"
            ),
        )
        embed.add_field(
            name="Saldo del usuario",
            value=f"**{new_user_balance:,}** cr",
            inline=True,
        )
        embed.add_field(
            name="Pool restante",
            value=f"**{new_bal:,}** cr",
            inline=True,
        )
        embed.set_footer(text="Y O U K A I · B A N K")
        await interaction.followup.send(embed=embed)
        logger.info(
            "treasury: staff_grant guild=%s by=%s to=%s amount=%s razon=%r",
            gid, interaction.user.id, usuario.id, monto, razon,
        )

    # ── /banco depositar ────────────────────────────────────────────────
    @banco.command(
        name="depositar",
        description="(Staff) Ingresa créditos al pool del banco",
    )
    @app_commands.describe(
        monto="Cantidad a depositar al pool",
        razon="Motivo visible en el historial",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def depositar(
        self,
        interaction: discord.Interaction,
        monto: app_commands.Range[int, 1, 1000000],
        razon: app_commands.Range[str, 3, 100],
    ) -> None:
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "Necesitás `manage_guild` para usar esto.", ephemeral=True
            )
            return

        await interaction.response.defer()
        gid = interaction.guild.id
        meta = json.dumps({"by": str(interaction.user.id), "razon": razon})
        new_bal = await self.bot.db.add_to_treasury(
            gid, monto, "staff_deposit",
            metadata_json=meta,
            user_id=None,
            by_staff_id=interaction.user.id,
        )

        embed = discord.Embed(
            color=_COLOR_DEPOSIT,
            title="💰 Depósito al Banco",
            description=(
                f"**{interaction.user.display_name}** ingresó "
                f"**{monto:,}** cr al pool.\n\n"
                f"📝 *{razon}*"
            ),
        )
        embed.add_field(name="Pool actualizado", value=f"**{new_bal:,}** cr", inline=True)
        embed.set_footer(text="Y O U K A I · B A N K")
        await interaction.followup.send(embed=embed)
        logger.info(
            "treasury: staff_deposit guild=%s by=%s amount=%s razon=%r",
            gid, interaction.user.id, monto, razon,
        )

    # ── /banco historial ────────────────────────────────────────────────
    @banco.command(
        name="historial",
        description="Últimos movimientos del banco",
    )
    @app_commands.describe(limit="Cuántos movimientos mostrar (max 25)")
    async def historial(
        self,
        interaction: discord.Interaction,
        limit: app_commands.Range[int, 1, 25] = 10,
    ) -> None:
        await interaction.response.defer()
        gid = interaction.guild.id
        movements = await self.bot.db.get_treasury_history(gid, limit=limit)

        if not movements:
            await interaction.followup.send(
                "Banco recién creado, sin movimientos aún.", ephemeral=True
            )
            return

        # Formato: "MM-DD HH:MM | +1,234 | 🎁 Etiqueta · @usuario"
        lines = []
        for m in movements:
            try:
                ts = datetime.fromisoformat(m["created_at"].replace("Z", "+00:00"))
                date_str = ts.strftime("%m-%d %H:%M")
            except Exception:
                date_str = (m["created_at"] or "")[:16]
            amt = _fmt_signed(m["amount"]) if m["amount"] != 0 else "·"
            label = _fmt_reason(m["reason"])
            extra = ""
            if m["user_id"]:
                u = interaction.guild.get_member(m["user_id"])
                if u:
                    extra = f" · {u.display_name}"
            lines.append(f"`{date_str}` `{amt:>8}` {label}{extra}")

        treasury = await self.bot.db.get_treasury(gid)
        embed = discord.Embed(
            color=_COLOR_BANK,
            title="📜 Historial del Banco",
            description="\n".join(lines),
        )
        embed.set_footer(
            text=f"En caja: {treasury['balance']:,} cr · {len(movements)} movimientos"
        )
        await interaction.followup.send(embed=embed)

    # ── Shop expiry loop ──────────────────────────────────────────────────

    @tasks.loop(minutes=5)
    async def _check_expired_roles(self) -> None:
        """Remove roles from expired shop redemptions."""
        try:
            expired = await self.bot.db.shop_get_expired()
        except Exception:
            return
        import json
        for r in expired:
            try:
                guild = self.bot.get_guild(r["guild_id"])
                if not guild:
                    continue
                member = guild.get_member(r["user_id"])
                payload = json.loads(r["payload"] or "{}")
                role_ids = payload.get("role_ids", [])
                if member and role_ids:
                    for rid in role_ids:
                        role = guild.get_role(int(rid))
                        if role and role in member.roles:
                            await member.remove_roles(role, reason="Shop: rol expirado")
                # Delete the expired redemption record
                await self.bot.db.shop_delete_redemption(r["id"])
                logger.info("Shop expiry: removed roles from %s (item %d)", r["user_id"], r["item_id"])
            except Exception as e:
                logger.debug("Shop expiry error: %s", e)

    @_check_expired_roles.before_loop
    async def _before_expiry_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    cog = TreasuryCog(bot)
    cog._check_expired_roles.start()
    await bot.add_cog(cog)

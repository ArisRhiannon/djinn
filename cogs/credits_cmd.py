"""Cog: Credits — Slash command `/créditos dar` ligado al pool del banco.

Es un atajo rápido para Aris y Cisart (vs `/banco entregar` que requiere
manage_guild y permite hasta 50,000 cr). Cantidades chicas (≤ 1200) sin
fricción de razón obligatoria, pero el dinero **sale del pool del banco**
igual que `/banco entregar` — no se crea de la nada.

Histórico:
- Antes (pre-2026-05-16): `/créditos dar` creaba créditos de la nada con
  `add_credits`, sin tocar el banco. Y existía `/créditos quitar`.
- Ahora: `/créditos dar` debita del pool (`spend_from_treasury`); si no hay
  fondos, falla. Se quitó la opción `quitar` por completo.
"""

from __future__ import annotations

import json
import logging

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("youkai.credits_cmd")

# Owners que pueden usar el atajo (Aris, Cisart). Cualquier otro caso debería
# usar `/banco entregar` con permiso `manage_guild`.
ALLOWED_IDS: set[int] = {239550977638793217, 743759722141974559}

# Cap del atajo: 1,200 cr por uso. Para más, /banco entregar.
MAX_GIVE = 1200


class CreditsCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="créditos",
        description="Atajo: entregar créditos a un usuario (sale del pool del banco)",
    )
    @app_commands.describe(
        usuario="Usuario que recibe los créditos",
        cantidad=f"Cantidad a entregar (máx {MAX_GIVE}; usa /banco entregar para más)",
        razón="Motivo opcional, queda en el historial del banco",
    )
    async def creditos(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        cantidad: app_commands.Range[int, 1, MAX_GIVE],
        razón: app_commands.Range[str, 0, 100] = "",
    ) -> None:
        # Permiso: solo owners hardcodeados. Si nadie autorizado, redirige al banco.
        if interaction.user.id not in ALLOWED_IDS:
            await interaction.response.send_message(
                "⛔ No autorizado. Usá `/banco entregar` si tenés `manage_guild`.",
                ephemeral=True,
            )
            return

        guild_id = interaction.guild_id
        razon_clean = razón.strip() or "Atajo /créditos"

        # Debita del pool del banco — atómico, falla si no hay fondos.
        meta = json.dumps({
            "target": str(usuario.id),
            "target_name": usuario.display_name,
            "by": str(interaction.user.id),
            "razon": razon_clean,
            "via": "credits_shortcut",
        })
        ok, new_pool_balance = await self.bot.db.spend_from_treasury(
            guild_id, cantidad, "staff_grant",
            metadata_json=meta,
            user_id=usuario.id,
            by_staff_id=interaction.user.id,
        )

        if not ok:
            treasury = await self.bot.db.get_treasury(guild_id)
            await interaction.response.send_message(
                f"❌ Banco sin fondos. En caja: **{treasury['balance']:,}** cr · "
                f"pediste **{cantidad:,}** cr.",
                ephemeral=True,
            )
            return

        # Acredita al usuario.
        new_user_balance = await self.bot.db.add_credits(usuario.id, guild_id, cantidad)

        await interaction.response.send_message(
            f"✅ **+{cantidad:,}** cr a {usuario.mention}\n"
            f"-# Saldo del usuario: {new_user_balance:,} · Pool: {new_pool_balance:,} cr restantes",
            ephemeral=True,
        )
        logger.info(
            "credits_cmd: shortcut grant guild=%s by=%s to=%s amount=%s razon=%r",
            guild_id, interaction.user.id, usuario.id, cantidad, razon_clean,
        )


async def setup(bot) -> None:
    await bot.add_cog(CreditsCog(bot))

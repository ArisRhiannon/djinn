"""
/recompensas — Paginated PNG shop display with custom icons.
"""
from __future__ import annotations

import io
import time

import discord
from discord import app_commands
from discord.ext import commands

from utils.shop_renderer import build_entries, render_shop_page, total_pages, ShopEntry

_COOLDOWN: dict[int, float] = {}


class ShopView(discord.ui.View):
    """Pagination buttons for the shop image."""

    def __init__(self, cog: "RecompensasCog", entries: list[ShopEntry], page: int):
        super().__init__(timeout=120)
        self.cog = cog
        self.entries = entries
        self.page = page
        pages = total_pages(entries)
        self.prev_btn.disabled = page <= 0
        self.next_btn.disabled = page >= pages - 1

    async def _update(self, interaction: discord.Interaction, new_page: int):
        self.page = new_page
        pages = total_pages(self.entries)
        self.prev_btn.disabled = new_page <= 0
        self.next_btn.disabled = new_page >= pages - 1
        png = await render_shop_page(self.entries, new_page)
        file = discord.File(io.BytesIO(png), filename="shop.png")
        await interaction.response.edit_message(attachments=[file], view=self)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update(interaction, self.page - 1)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._update(interaction, self.page + 1)


class RecompensasCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="recompensas", description="Ver las recompensas canjeables con créditos")
    async def recompensas(self, interaction: discord.Interaction) -> None:
        now = time.time()
        last = _COOLDOWN.get(interaction.guild_id, 0)
        if now - last < 15:
            remaining = int(15 - (now - last))
            await interaction.response.send_message(
                f"⏳ Espera {remaining}s para volver a usar este comando.", ephemeral=True
            )
            return
        _COOLDOWN[interaction.guild_id] = now

        await interaction.response.defer()

        # Fetch items from DB
        db = self.bot.db  # type: ignore
        rows = await db.fetch(
            "SELECT name, description, price, stock, type, category FROM shop_items "
            "WHERE guild_id = ? AND active = 1 ORDER BY category, price",
            (interaction.guild_id,),
        )

        if not rows:
            await interaction.followup.send("No hay items en la tienda.", ephemeral=True)
            return

        entries = build_entries(rows)
        png = await render_shop_page(entries, 0)
        file = discord.File(io.BytesIO(png), filename="shop.png")

        pages = total_pages(entries)
        view = ShopView(self, entries, 0) if pages > 1 else discord.utils.MISSING
        await interaction.followup.send(file=file, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RecompensasCog(bot))

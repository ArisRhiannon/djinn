"""
Cog: ZZZ Builds — Build cards custom de ZZZ con select menu.
"""
from __future__ import annotations

import io
import logging
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from utils.zzz_card_renderer import render_build_card

logger = logging.getLogger("djinn.zzz_builds")
API_BASE = "http://140.84.187.50:8000"


class ZZZBuildsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _fetch_eval(self, uid: int) -> Optional[dict]:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{API_BASE}/uid/{uid}/evaluar",
                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                return await r.json() if r.status == 200 else None

    @app_commands.command(name="build", description="🎮 Genera una build card de ZZZ")
    @app_commands.describe(
        uid="UID del jugador",
        agente="Nombre del agente (opcional — muestra menú si no se pone)",
    )
    async def build_cmd(self, interaction: discord.Interaction,
                        uid: int, agente: Optional[str] = None) -> None:
        await interaction.response.defer()

        if agente:
            png = await render_build_card(uid, agente)
            if not png:
                await interaction.followup.send(
                    f"No encontré a **{agente}** en el showcase de UID {uid}.",
                    ephemeral=True)
                return
            file = discord.File(io.BytesIO(png), filename="build.png")
            embed = discord.Embed(color=0x00D4FF)
            embed.set_image(url="attachment://build.png")
            await interaction.followup.send(embed=embed, file=file)
        else:
            data = await self._fetch_eval(uid)
            if not data:
                await interaction.followup.send(
                    f"UID {uid} no encontrado o showcase privado.", ephemeral=True)
                return

            evals = data.get("evaluaciones", [])
            if not evals:
                await interaction.followup.send("Showcase vacío.", ephemeral=True)
                return

            # Generate card for first agent by default
            first = evals[0]["nombre"]
            png = await render_build_card(uid, first)
            if not png:
                await interaction.followup.send("Error generando card.", ephemeral=True)
                return

            file = discord.File(io.BytesIO(png), filename="build.png")
            embed = discord.Embed(
                title=f"🎮 {data.get('nick', '???')} — UID {uid}",
                color=0x00D4FF)
            embed.set_image(url="attachment://build.png")

            view = BuildSelectView(self, uid, evals)
            await interaction.followup.send(embed=embed, file=file, view=view)


class BuildSelectView(discord.ui.View):
    def __init__(self, cog: ZZZBuildsCog, uid: int, evals: list, *, timeout: float = 120.0):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.uid = uid
        self.evals = evals

        options = []
        for ag in evals[:25]:
            score = ag["evaluacion"]["calidad_pct"]
            grade = "SS" if score >= 95 else "S" if score >= 90 else "A" if score >= 80 else "B" if score >= 70 else "C"
            options.append(discord.SelectOption(
                label=f"{ag['nombre']} — {grade} {score:.0f}%",
                value=ag["nombre"],
                description=f"Lv.{ag['level']} • {ag['weapon']}",
            ))

        select = discord.ui.Select(
            placeholder="Cambiar agente...",
            options=options,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        agent_name = interaction.data["values"][0]
        await interaction.response.defer()

        png = await render_build_card(self.uid, agent_name)
        if not png:
            await interaction.followup.send(f"Error con {agent_name}.", ephemeral=True)
            return

        file = discord.File(io.BytesIO(png), filename="build.png")
        embed = discord.Embed(
            title=f"🎮 {agent_name}",
            color=0x00D4FF)
        embed.set_image(url="attachment://build.png")

        # Edit the original message with new image
        try:
            await interaction.message.edit(embed=embed, attachments=[file], view=self)
        except discord.HTTPException:
            # Fallback: send new message
            await interaction.followup.send(embed=embed, file=file, view=self)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ZZZBuildsCog(bot))

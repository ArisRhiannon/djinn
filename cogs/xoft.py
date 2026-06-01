"""
Cog: Xoft — Simula a Xoft basándose en su persona densa (14K+ mensajes reales).

Trigger: /xoft [mensaje]
Responde como Xoft usando webhook impersonation.
"""

from __future__ import annotations

from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from google.genai import types
from loguru import logger

_XOFT_USER_ID = 747920937260679269
_PERSONA_PATH = Path(__file__).parent.parent / "data" / "xoft_persona.md"


def _load_persona() -> str:
    try:
        return _PERSONA_PATH.read_text(encoding="utf-8")
    except Exception:
        logger.warning("xoft_persona.md not found")
        return "Eres Xoft. Gamer argentino. Shitposter. Voseo. Sin tildes. Risas caóticas (KSJSKAJ). Muletillas: mano, pije, GG."


_SYSTEM_PROMPT = _load_persona()


class XoftCog(commands.Cog, name="Xoft"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _get_xoft_member(self, guild: discord.Guild):
        try:
            return guild.get_member(_XOFT_USER_ID) or await guild.fetch_member(_XOFT_USER_ID)
        except Exception:
            return None

    async def _generate(self, mensaje: str) -> str:
        if not self.bot.llm:
            return "💔 no hay llm mano"
        try:
            content = types.Content(
                role="user",
                parts=[types.Part.from_text(text=mensaje)]
            )
            response = await self.bot.llm.generate_plain(
                system_prompt=_SYSTEM_PROMPT,
                contents=[content],
                temperature=0.9,
                max_output_tokens=256,
            )
            return response.strip() if response else "gg"
        except Exception:
            logger.exception("Xoft LLM error")
            return "💔 error tecnico mano"

    async def _send_webhook(self, channel, content, name, avatar_url):
        try:
            webhooks = await channel.webhooks()
            wh = next((w for w in webhooks if w.user and w.user.id == self.bot.user.id), None)
            if not wh:
                wh = await channel.create_webhook(name="Xoft")
            return await wh.send(content=content, username=name, avatar_url=avatar_url, wait=True)
        except Exception:
            return None

    @app_commands.command(name="xoft", description="Pregunta qué diría Xoft")
    @app_commands.describe(mensaje="Qué le decís a Xoft")
    async def xoft_command(self, interaction: discord.Interaction, mensaje: str):
        await interaction.response.defer()

        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.followup.send("solo en canales de texto mano", ephemeral=True)
            return

        member = await self._get_xoft_member(interaction.guild)
        name = member.display_name if member else "Xoft Piece"
        avatar = str(member.display_avatar.url) if member and member.display_avatar else ""

        response = await self._generate(mensaje)

        msg = await self._send_webhook(interaction.channel, response, name, avatar)
        if msg:
            await interaction.followup.send("✅", ephemeral=True)
        else:
            await interaction.followup.send(f"**{name}**: {response}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(XoftCog(bot))
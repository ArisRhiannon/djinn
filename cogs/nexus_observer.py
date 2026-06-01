"""
Cog: Nexus Observer — Mapeo dinámico de identidades y relaciones.
Construye el grafo de alias y entidades analizando el flujo de mensajes.
"""

from __future__ import annotations
import discord
from discord.ext import commands
from loguru import logger
import re

from utils.nexus import DjinnNexus

class NexusObserverCog(commands.Cog, name="NexusObserver"):
    def __init__(self, bot):
        self.bot = bot
        self.nexus = bot.nexus

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        # 1. Registro básico: Usuario -> Nombre Canónico
        await self.nexus.update_association(
            alias=message.author.display_name,
            entity_id=str(message.author.id),
            entity_type="user",
            name=message.author.name,
            guild_id=message.guild.id
        )

        # 2. Mapeo de Menciones (Sujeto -> Objeto)
        if message.mentions:
            content = message.content.lower()
            for member in message.mentions:
                mention_str = f"<@{member.id}>"
                if mention_str in content:
                    parts = content.split(mention_str)
                    if len(parts) > 1:
                        prev_words = parts[0].split()
                        if prev_words:
                            alias = prev_words[-1].strip(",.!? ")
                            if len(alias) > 2:
                                await self.nexus.update_association(
                                    alias=alias,
                                    entity_id=str(member.id),
                                    entity_type="user",
                                    name=member.display_name,
                                    guild_id=message.guild.id
                                )

        # 3. Mapeo por Respuestas (Replies)
        if message.reference and message.reference.resolved:
            replied_msg = message.reference.resolved
            if replied_msg.author and not replied_msg.author.bot:
                text = message.content.strip()
                first_word = text.split()[0].strip(",.!? ") if text else ""
                if len(first_word) > 2:
                    await self.nexus.update_association(
                        alias=first_word,
                        entity_id=str(replied_msg.author.id),
                        entity_type="user",
                        name=replied_msg.author.display_name,
                        guild_id=message.guild.id
                    )

async def setup(bot):
    await bot.add_cog(NexusObserverCog(bot))

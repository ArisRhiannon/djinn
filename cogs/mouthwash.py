"""Cog: Lavado de Boca (Mouth Wash Tool) — reescribe mensajes vía LLM local.

Flujo:
  Usuario lavado escribe → on_message listener
    → borrar mensaje original
    → reescribir a versión family-friendly vía MouthWashLLM local
    → reenviar vía webhook con nombre y avatar del usuario original

Comandos: Ninguno (activado vía agent tool wash_mouth/unwash_mouth/list_mouth_washed)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands

from utils.curse_webhook import CurseWebhookManager
from utils.mouth_wash_llm import MouthWashLLM

logger = logging.getLogger("youkai.mouthwash")


# ── Cog ───────────────────────────────────────────────────────────────────────

class MouthWashCog(commands.Cog, name="MouthWash"):
    """Lavado de boca: borra mensajes y los reenvía reescritos vía webhook."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._tasks: set[asyncio.Task] = set()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Inicializa el motor LLM y restaura lavados activos."""
        # Cargar modelos LLM locales (no bloquea si falla)
        try:
            MouthWashLLM.initialize()
        except Exception:
            logger.exception("MouthWashCog: error inicializando MouthWashLLM")

        # Restaurar lavados activos desde DB
        await self._restore_washes()

    def cog_unload(self) -> None:
        """Cancela tareas pendientes y limpia."""
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info("MouthWashCog descargado")

    # ── Restauración de lavados ───────────────────────────────────────────

    async def _restore_washes(self) -> None:
        """Carga lavados activos desde DB y reprograma auto-liberación."""
        if not self.bot.db or not self.bot.guilds:
            return
        try:
            active = await self.bot.db.get_active_mouth_washes(
                self.bot.guilds[0].id
            )
        except Exception:
            logger.exception("MouthWashCog: error cargando lavados activos")
            return
        now = datetime.now(timezone.utc)
        for wash in active:
            release_at = datetime.fromisoformat(wash["release_at"])
            remaining = (release_at - now).total_seconds()
            if remaining <= 0:
                # Ya expiró — limpiar
                await self.bot.db.remove_mouth_wash(
                    wash["guild_id"], wash["user_id"]
                )
                continue
            # Reprogramar
            task = asyncio.create_task(
                self._auto_unwash(wash["guild_id"], wash["user_id"], remaining)
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            logger.info(
                "Lavado restaurado: user %d en guild %d (expira en %.0fs)",
                wash["user_id"], wash["guild_id"], remaining,
            )

    async def _auto_unwash(
        self, guild_id: int, user_id: int, delay: float
    ) -> None:
        """Libera automáticamente tras <delay> segundos."""
        await asyncio.sleep(delay)
        try:
            await self.bot.db.remove_mouth_wash(guild_id, user_id)
            logger.info("Lavado expirado: user %d en guild %d", user_id, guild_id)
        except Exception:
            logger.exception("Error en auto-liberación de lavado de boca")

    # ── on_message interceptor ────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Intercepta mensajes de usuarios con lavado de boca."""
        if not message.guild or message.author.bot:
            return
        if not self.bot.db:
            return

        # Verificar si el autor está lavado
        wash = await self.bot.db.get_mouth_wash(
            message.guild.id, message.author.id
        )
        if not wash:
            return

        # Verificar que el lavado no haya expirado
        release_at = datetime.fromisoformat(wash["release_at"])
        if datetime.now(timezone.utc) >= release_at:
            await self.bot.db.remove_mouth_wash(
                message.guild.id, message.author.id
            )
            return

        # Obtener el miembro (para nombre y avatar)
        member = message.guild.get_member(message.author.id)
        if not member:
            return

        # ── 1. Borrar mensaje original ─────────────────────────────────
        try:
            await message.delete()
        except discord.Forbidden:
            return  # Sin permiso para borrar
        except discord.NotFound:
            return  # Ya fue borrado
        except discord.HTTPException as e:
            logger.warning("Error borrando mensaje lavado: %s", e)
            return

        # ── 2. Reescribir vía LLM local ────────────────────────────────
        rewritten, elapsed_ms, model_used = await MouthWashLLM.rewrite(
            message.content
        )
        if not rewritten or not rewritten.strip():
            rewritten = message.content

        # ── 3. Enviar webhook ──────────────────────────────────────────
        avatar_url = (
            str(member.display_avatar.url)
            if member.display_avatar
            else ""
        )
        await CurseWebhookManager.send_cursed(
            channel=message.channel,
            content=rewritten,
            username=member.display_name,
            avatar_url=avatar_url,
            bot_user=self.bot.user,
        )

        logger.info(
            "Lavado: msg de %s reescrito (%s, %.0fms) en #%s",
            member.display_name, model_used, elapsed_ms, message.channel.name,
        )

        # Registrar en DB
        if self.bot.db:
            await self.bot.db.log_action(
                message.guild.id, "mouth_wash_message",
                target_id=message.author.id,
                details={
                    "original": message.content[:100],
                    "rewritten": rewritten[:100],
                    "model": model_used,
                    "elapsed_ms": round(elapsed_ms, 1),
                    "channel_id": message.channel.id,
                },
            )


async def setup(bot):
    """Carga el cog de lavado de boca como extensión de discord.py."""
    await bot.add_cog(MouthWashCog(bot))

"""Gestor de webhooks para impersonación de usuarios maldecidos.

Arquitectura:
  - Un webhook por canal, creado bajo demanda.
  - El webhook se cachea en memoria (dict) y se limpia al descargar el cog.
  - Envía mensajes con el nombre y avatar exactos del usuario original.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import discord
from loguru import logger

# Discord limita username a 80 caracteres
_MAX_USERNAME_LEN = 80

class CurseWebhookManager:
    """Gestiona webhooks para la Maldición — uno por canal."""

    _webhooks: dict[int, discord.Webhook] = {}  # channel_id -> webhook

    @classmethod
    async def get_or_create(
        cls,
        channel: discord.TextChannel,
        bot_user: discord.ClientUser,
    ) -> Optional[discord.Webhook]:
        """Obtiene o crea un webhook en el canal para el bot.

        Args:
            channel: Canal de texto donde se enviará el mensaje.
            bot_user: El ClientUser del bot (para buscar webhooks propios).

        Returns:
            El webhook, o None si no se pudo crear (falta permiso).
        """
        # Cache hit
        if channel.id in cls._webhooks:
            wh = cls._webhooks[channel.id]
            # Verificar que el webhook sigue siendo válido
            try:
                # Forzar refresh ligero
                return wh
            except Exception:
                del cls._webhooks[channel.id]

        # Buscar webhook existente del bot
        try:
            webhooks = await channel.webhooks()
            for wh in webhooks:
                if wh.user and wh.user.id == bot_user.id:
                    cls._webhooks[channel.id] = wh
                    return wh
        except discord.Forbidden:
            logger.warning("Sin permiso para listar webhooks en #%s", channel.name)
            return None
        except discord.HTTPException as e:
            logger.error("Error listando webhooks en #%s: %s", channel.name, e)
            return None

        # Crear nuevo webhook
        try:
            webhook = await channel.create_webhook(
                name="Curse-Impersonator",
                reason="Maldición: impersonación de usuario",
            )
            cls._webhooks[channel.id] = webhook
            logger.info("Webhook creado en #%s para la Maldición", channel.name)
            return webhook
        except discord.Forbidden:
            logger.warning(
                "Falta permiso MANAGE_WEBHOOKS para crear webhook en #%s. "
                "La Maldición no puede impersonar en este canal.",
                channel.name,
            )
            return None
        except discord.HTTPException as e:
            logger.error("Error creando webhook en #%s: %s", channel.name, e)
            return None

    @classmethod
    async def send_cursed(
        cls,
        channel: discord.TextChannel,
        content: str,
        username: str,
        avatar_url: str,
        bot_user: discord.ClientUser,
    ) -> Optional[discord.WebhookMessage]:
        """Envía un mensaje via webhook con la identidad del usuario maldecido.

        Args:
            channel: Canal donde enviar.
            content: Contenido del mensaje (traducido).
            username: Nombre a mostrar (display_name del usuario original).
            avatar_url: URL del avatar del usuario original.
            bot_user: ClientUser del bot.

        Returns:
            El mensaje enviado, o None si falló.
        """
        webhook = await cls.get_or_create(channel, bot_user)
        if webhook is None:
            return None

        safe_username = username[:_MAX_USERNAME_LEN] if username else "Usuario Maldecido"

        try:
            msg = await webhook.send(
                content=content,
                username=safe_username,
                avatar_url=avatar_url or "",
                wait=True,
            )
            return msg
        except discord.HTTPException as e:
            # Si falla por rate limit, no reintentamos — el mensaje se pierde
            logger.warning("Error enviando webhook en #%s: %s", channel.name, e)
            return None

    @classmethod
    def clear_cache(cls) -> None:
        """Limpia el cache de webhooks (llamar al descargar el cog)."""
        cls._webhooks.clear()

"""
Cog: Actions — Acciones de rol interactivo (hug, kiss, pat, heal) con GIFs de anime y botones de correspondencia.
"""
from __future__ import annotations

import logging
import random
from typing import Optional, Tuple

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("djinn.actions")

HEAL_GIFS = [
    "https://media.giphy.com/media/Vz58J8shFW6BvqnYTm/giphy.gif",      # Tsunade curación ninjutsu
    "https://media.giphy.com/media/74MLruEFGOjqGMBhzG/giphy.gif",      # Bardock tanque de curación DBZ
    "https://media.giphy.com/media/mdsDQcD6U2pVokVWy2/giphy.gif",      # Hechizo de curación anime
    "https://media.giphy.com/media/mGHLnuyg063HSIZ1uR/giphy.gif",      # Recuperación mágica anime
    "https://media.giphy.com/media/iGYJsm4Lw2sDGZTME3/giphy.gif",      # Chica mágica conjuro curativo (HIDIVE)
]

# Colores premium personalizados para cada acción
ACTION_COLORS = {
    "hug": 0xFFB6C1,   # Rosa pastel suave
    "kiss": 0xFF1493,  # Rosa profundo brillante (Deep Pink)
    "pat": 0x87CEFA,   # Azul cielo vibrante
    "heal": 0x00FF7F,  # Verde curación mágico (Spring Green)
}


def action_emoji(action: str) -> str:
    """Retorna el emoji correspondiente a la acción."""
    emojis = {
        "hug": "🫂",
        "kiss": "💋",
        "pat": "👋",
        "heal": "💖",
    }
    return emojis.get(action, "✨")


def action_title_es(action: str) -> str:
    """Retorna el título en español para el embed."""
    titles = {
        "hug": "Abrazo",
        "kiss": "Beso",
        "pat": "Caricia",
        "heal": "Curación",
    }
    return titles.get(action, "Interacción")


async def fetch_nekos_best_gif(action: str) -> Tuple[Optional[str], Optional[str]]:
    """Consulta la API de nekos.best para obtener un GIF aleatorio y el nombre del anime."""
    url = f"https://nekos.best/api/v2/{action}"
    headers = {"User-Agent": "YoukaiBot/1.0 (https://github.com/los-nitos-hermanos/youkai)"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=5.0) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and "results" in data and len(data["results"]) > 0:
                        item = data["results"][0]
                        return item.get("url"), item.get("anime_name")
    except Exception as exc:
        logger.error("Actions: Error consultando nekos.best para %s: %s", action, exc)
    return None, None


class ActionButtonView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        sender: discord.Member,
        recipient: discord.Member,
        action: str,
        timeout: float = 120.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.bot = bot
        self.sender = sender
        self.recipient = recipient
        self.action = action
        self.message: Optional[discord.Message] = None

        # Configurar etiquetas y emojis del botón
        button_configs = {
            "hug": ("Abrazar de vuelta 🫂", discord.ButtonStyle.success),
            "kiss": ("Besar de vuelta 💋", discord.ButtonStyle.danger),
            "pat": ("Acariciar de vuelta 👋", discord.ButtonStyle.primary),
            "heal": ("Curar de vuelta 💖", discord.ButtonStyle.success),
        }
        label, style = button_configs.get(action, ("Corresponder", discord.ButtonStyle.secondary))
        self.correspond_button.label = label
        self.correspond_button.style = style

    async def on_timeout(self) -> None:
        """Desactiva los botones cuando el tiempo de espera expira."""
        if self.message:
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button()
    async def correspond_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.recipient.id:
            # Respuestas sarcásticas típicas de Youkai para los intrusos
            sarcastic_replies = [
                f"¡Oye! Este {self.action_name_es()} no era para ti, no seas metiche.",
                f"¿Qué haces metiéndote aquí? ¡El {self.action_name_es()} no es para ti!",
                f"Intento fallido de robar un {self.action_name_es()}. Búscate a alguien más.",
                f"Alto ahí. Este {self.action_name_es()} tiene dueño, y definitivamente no eres tú.",
            ]
            await interaction.response.send_message(random.choice(sarcastic_replies), ephemeral=True)
            return

        # Desactivar botón tras interactuar
        button.disabled = True
        await interaction.response.edit_message(view=self)

        # Obtener GIF para la respuesta
        gif_url = None
        anime_name = None
        if self.action in ("hug", "kiss", "pat"):
            gif_url, anime_name = await fetch_nekos_best_gif(self.action)
        else:
            gif_url = random.choice(HEAL_GIFS)

        if not gif_url:
            gif_url = "https://media.giphy.com/media/Vz58J8shFW6BvqnYTm/giphy.gif"

        # Incrementar el contador en la DB para el remitente original (quien recibe la correspondencia)
        count = 1
        try:
            count = await self.bot.db.increment_action_count(
                guild_id=interaction.guild_id,
                user_id=self.sender.id,
                action_type=self.action,
            )
        except Exception as exc:
            logger.error("Actions: Error incrementando contador en correspondencia: %s", exc)

        # Mensajes descriptivos al corresponder
        action_phrases = {
            "hug": "¡{} correspondió al abrazo de {}! 🫂💖",
            "kiss": "¡{} correspondió al beso de {}! 💋🔥",
            "pat": "¡{} correspondió a la caricia de {}! 👋✨",
            "heal": "¡{} le devolvió el hechizo de curación a {}! 💖🌟",
        }
        
        phrase = action_phrases.get(self.action, "¡{} correspondió a {}!").format(
            self.recipient.mention,
            self.sender.mention,
        )

        emoji = action_emoji(self.action)
        title = action_title_es(self.action)
        plural_name = self.action_plural_es()

        embed = discord.Embed(
            description=f"### {emoji} {title} Correspondido\n{phrase}",
            color=ACTION_COLORS.get(self.action, 0x2F3136),
        )
        embed.set_image(url=gif_url)
        
        footer_parts = [f"¡{self.sender.display_name} ya acumula {count} {plural_name}!"]
        if anime_name:
            footer_parts.append(f"Anime: {anime_name}")
        embed.set_footer(text=" • ".join(footer_parts))

        # Enviar respuesta interactiva
        reply_msg = await interaction.followup.send(embed=embed)

        # Registrar el mensaje enviado como inerte
        self._register_inert(reply_msg.id)

    def action_name_es(self) -> str:
        names = {
            "hug": "abrazo",
            "kiss": "beso",
            "pat": "cariño",
            "heal": "hechizo de curación",
        }
        return names.get(self.action, "hecho")

    def action_plural_es(self) -> str:
        plurals = {
            "hug": "abrazos",
            "kiss": "besos",
            "pat": "caricias",
            "heal": "curaciones",
        }
        return plurals.get(self.action, "acciones")

    def _register_inert(self, msg_id: int) -> None:
        if not hasattr(self.bot, "inert_message_ids"):
            self.bot.inert_message_ids = set()
        self.bot.inert_message_ids.add(msg_id)
        # Limitar tamaño de la caché en memoria
        if len(self.bot.inert_message_ids) > 1000:
            self.bot.inert_message_ids.pop()


class ActionsCog(commands.Cog, name="Actions"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _handle_action(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
        action: str,
        phrase_template: str,
    ) -> None:
        if usuario.id == interaction.user.id:
            await interaction.response.send_message(
                f"¿Quieres darte un {self._action_name_es(action)} a ti mismo? Qué triste...",
                ephemeral=True,
            )
            return

        if usuario.bot:
            await interaction.response.send_message(
                "Los bots no tienen sentimientos (excepto yo), no puedes hacer eso.",
                ephemeral=True,
            )
            return

        # Cargar de forma inmediata la respuesta interactiva para evitar que expire la interacción (timeout de 3s)
        await interaction.response.defer()

        # Obtener el GIF
        gif_url = None
        anime_name = None
        if action in ("hug", "kiss", "pat"):
            gif_url, anime_name = await fetch_nekos_best_gif(action)
        else:
            gif_url = random.choice(HEAL_GIFS)

        if not gif_url:
            gif_url = "https://media.giphy.com/media/Vz58J8shFW6BvqnYTm/giphy.gif"

        # Incrementar contador en la DB para el destinatario de la acción inicial
        count = 1
        try:
            count = await self.bot.db.increment_action_count(
                guild_id=interaction.guild_id,
                user_id=usuario.id,
                action_type=action,
            )
        except Exception as exc:
            logger.error("Actions: Error incrementando contador en acción inicial: %s", exc)

        plural_name = self._action_plural_es(action)
        phrase = phrase_template.format(interaction.user.mention, usuario.mention)

        emoji = action_emoji(action)
        title = action_title_es(action)

        embed = discord.Embed(
            description=f"### {emoji} {title}\n{phrase}",
            color=ACTION_COLORS.get(action, 0x2F3136),
        )
        embed.set_image(url=gif_url)
        
        footer_parts = [f"¡{usuario.display_name} ya acumula {count} {plural_name}!"]
        if anime_name:
            footer_parts.append(f"Anime: {anime_name}")
        embed.set_footer(text=" • ".join(footer_parts))

        # Generar vista interactiva de botones
        view = ActionButtonView(self.bot, interaction.user, usuario, action)
        msg = await interaction.followup.send(embed=embed, view=view)
        view.message = msg

        # Registrar el mensaje de Youkai como inerte
        if not hasattr(self.bot, "inert_message_ids"):
            self.bot.inert_message_ids = set()
        self.bot.inert_message_ids.add(msg.id)
        if len(self.bot.inert_message_ids) > 1000:
            self.bot.inert_message_ids.pop()

    def _action_name_es(self, action: str) -> str:
        names = {
            "hug": "abrazo",
            "kiss": "beso",
            "pat": "cariño",
            "heal": "hechizo de curación",
        }
        return names.get(action, "hecho")

    def _action_plural_es(self, action: str) -> str:
        plurals = {
            "hug": "abrazos",
            "kiss": "besos",
            "pat": "caricias",
            "heal": "curaciones",
        }
        return plurals.get(action, "acciones")

    @app_commands.command(name="hug", description="Le da un cálido abrazo a un usuario")
    @app_commands.describe(usuario="El usuario al que quieres abrazar")
    async def hug(self, interaction: discord.Interaction, usuario: discord.Member) -> None:
        await self._handle_action(
            interaction,
            usuario,
            "hug",
            "{} le dio un fuerte abrazo a {} 🫂💖",
        )

    @app_commands.command(name="kiss", description="Le da un dulce beso a un usuario")
    @app_commands.describe(usuario="El usuario al que quieres besar")
    async def kiss(self, interaction: discord.Interaction, usuario: discord.Member) -> None:
        await self._handle_action(
            interaction,
            usuario,
            "kiss",
            "{} le dio un apasionado beso a {} 💋🔥",
        )

    @app_commands.command(name="pat", description="Le da unas caricias en la cabeza a un usuario")
    @app_commands.describe(usuario="El usuario al que quieres acariciar")
    async def pat(self, interaction: discord.Interaction, usuario: discord.Member) -> None:
        await self._handle_action(
            interaction,
            usuario,
            "pat",
            "{} acarició suavemente la cabeza de {} 👋✨",
        )

    @app_commands.command(name="heal", description="Utiliza magia de curación sobre un usuario")
    @app_commands.describe(usuario="El usuario al que quieres curar")
    async def heal(self, interaction: discord.Interaction, usuario: discord.Member) -> None:
        await self._handle_action(
            interaction,
            usuario,
            "heal",
            "{} conjuró un hechizo de curación sobre {} 💖🌟",
        )

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ) -> None:
        """Manejador local de errores para los comandos de este Cog."""
        if isinstance(error, app_commands.TransformerError):
            logger.warning(
                "Actions: Falló la conversión de '%s' a Member para el comando '%s' por parte de %s",
                error.value,
                interaction.command.name if interaction.command else "desconocido",
                interaction.user,
            )
            msg = "¡Oye! No pude encontrar al usuario que mencionaste. Asegúrate de seleccionarlo de la lista o mencionarlo correctamente (@Usuario)."
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(msg, ephemeral=True)
                else:
                    await interaction.followup.send(msg, ephemeral=True)
            except Exception as exc:
                logger.error("Actions: Error al enviar respuesta de error: %s", exc)
            return

        # Dejar que otros errores se propaguen o loguearlos
        logger.error("Actions: Error no manejado en comando %s: %s", interaction.command.name if interaction.command else "desconocido", error)



async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ActionsCog(bot))

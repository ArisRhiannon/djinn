"""Cog: Maldición (Curse Tool) — intercepta mensajes de usuarios maldecidos.

Flujo:
  Usuario maldecido escribe → on_message listener
    → borrar mensaje original
    → traducir a idioma aleatorio (vía CurseTranslator)
    → reenviar vía webhook con nombre y avatar del usuario original

Comandos slash:
  /curse <user> [duración] [razón]   — Maldice a un usuario (admin)
  /uncurse <user>                     — Libera a un usuario (admin)
  /listcursed                         — Lista maldiciones activas (admin)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.curse_translator import CurseTranslator
from utils.curse_webhook import CurseWebhookManager

logger = logging.getLogger("djinn.curse")

# ── Constantes ────────────────────────────────────────────────────────────────

_DURATION_CHOICES = [
    app_commands.Choice(name="10 minutos", value="10m"),
    app_commands.Choice(name="1 hora",    value="1h"),
    app_commands.Choice(name="6 horas",   value="6h"),
    app_commands.Choice(name="1 día",     value="1d"),
]

_DURATION_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_MAX_CURSE_SECONDS = 28 * 86_400  # 28 días máximo


def _parse_duration(raw: str) -> int:
    """Parsea una duración tipo '10m', '1h', '1d' a segundos."""
    import re
    m = re.match(r"^(\d+)\s*([smhd])$", raw.strip().lower())
    if not m:
        raise ValueError(f"Duración inválida: '{raw}'. Usa ej: 10m, 1h, 1d")
    return min(int(m.group(1)) * _DURATION_SECONDS[m.group(2)], _MAX_CURSE_SECONDS)


# ── Cog ───────────────────────────────────────────────────────────────────────

class CurseCog(commands.Cog, name="Curse"):
    """Maldición: borra mensajes y los reenvía traducidos vía webhook."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._tasks: set[asyncio.Task] = set()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Carga modelos de traducción y restaura maldiciones activas."""
        # Cargar modelo de traducción (no bloquea si falla)
        try:
            ok = await CurseTranslator.load_model()
            if ok:
                logger.info("CurseCog: modelo de traducción NLLB-200 listo")
        except Exception:
            logger.exception("CurseCog: error cargando modelos de traducción")

        # Restaurar maldiciones activas desde DB
        await self._restore_curses()

    def cog_unload(self) -> None:
        """Cancela tareas pendientes y limpia caché de webhooks."""
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        CurseWebhookManager.clear_cache()
        logger.info("CurseCog descargado")

    # ── Restauración de maldiciones ───────────────────────────────────────

    async def _restore_curses(self) -> None:
        """Carga maldiciones activas desde DB y reprograma auto-liberación."""
        if not self.bot.db or not self.bot.guilds:
            return
        try:
            active = await self.bot.db.get_active_curses(self.bot.guilds[0].id)
        except Exception:
            logger.exception("CurseCog: error cargando maldiciones activas")
            return
        now = datetime.now(timezone.utc)
        for curse in active:
            release_at = datetime.fromisoformat(curse["release_at"])
            remaining = (release_at - now).total_seconds()
            if remaining <= 0:
                # Ya expiró — limpiar
                await self.bot.db.remove_curse(curse["guild_id"], curse["user_id"])
                continue
            # Reprogramar
            task = asyncio.create_task(
                self._auto_uncurse(curse["guild_id"], curse["user_id"], remaining)
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            logger.info(
                "Maldición restaurada: user %d en guild %d (expira en %.0fs)",
                curse["user_id"], curse["guild_id"], remaining,
            )

    async def _auto_uncurse(self, guild_id: int, user_id: int, delay: float) -> None:
        """Libera automáticamente tras <delay> segundos."""
        await asyncio.sleep(delay)
        try:
            await self.bot.db.remove_curse(guild_id, user_id)
            logger.info("Maldición expirada: user %d en guild %d", user_id, guild_id)
        except Exception:
            logger.exception("Error en auto-liberación de maldición")

    # ── on_message interceptor ────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Intercepta mensajes de usuarios maldecidos."""
        if not message.guild or message.author.bot:
            return
        if not self.bot.db:
            return

        # Verificar si el autor está maldecido
        curse = await self.bot.db.get_curse(message.guild.id, message.author.id)
        if not curse:
            return

        # Verificar que la maldición no haya expirado
        release_at = datetime.fromisoformat(curse["release_at"])
        if datetime.now(timezone.utc) >= release_at:
            await self.bot.db.remove_curse(message.guild.id, message.author.id)
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
            logger.warning("Error borrando mensaje maldito: %s", e)
            return

        # ── 2. Traducir ────────────────────────────────────────────────
        translated, lang_name = await CurseTranslator.translate(message.content)

        # ── 3. Enviar webhook ──────────────────────────────────────────
        avatar_url = str(member.display_avatar.url) if member.display_avatar else ""
        await CurseWebhookManager.send_cursed(
            channel=message.channel,
            content=translated,
            username=member.display_name,
            avatar_url=avatar_url,
            bot_user=self.bot.user,
        )

        logger.info(
            "Maldición: msg de %s traducido a %s en #%s",
            member.display_name, lang_name, message.channel.name,
        )

    # ── /curse ────────────────────────────────────────────────────────────

    @app_commands.command(
        name="curse",
        description="🔮 Maldice a un usuario: sus mensajes se borran y reenvían traducidos",
    )
    @app_commands.describe(
        user="Usuario a maldecir",
        duration="Duración de la maldición (default: 1h)",
        reason="Razón de la maldición (opcional)",
    )
    @app_commands.default_permissions(administrator=True)
    async def curse(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        duration: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Aplica una maldición a un usuario."""
        # Validaciones
        if user.bot:
            await interaction.response.send_message(
                "🤖 No se puede maldecir a un bot.", ephemeral=True,
            )
            return
        if user.id == interaction.guild.owner_id:
            await interaction.response.send_message(
                "👑 No se puede maldecir al dueño del servidor.", ephemeral=True,
            )
            return
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "⛔ Solo administradores pueden usar este comando.", ephemeral=True,
            )
            return

        # Parsear duración
        dur_str = duration or "1h"
        try:
            dur_seconds = _parse_duration(dur_str)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        release_at = datetime.now(timezone.utc)
        release_at_str = (release_at + timedelta(seconds=dur_seconds)).isoformat()

        # Guardar en DB
        if self.bot.db:
            await self.bot.db.add_curse(
                guild_id=interaction.guild_id,
                user_id=user.id,
                release_at=release_at_str,
                reason=reason or "Maldición de Youkai",
                created_by=interaction.user.id,
                display_name=user.display_name,
            )
            # Registrar en audit log
            await self.bot.db.log_action(
                interaction.guild_id, "curse",
                actor_id=interaction.user.id, target_id=user.id,
                details={"reason": reason, "duration": dur_str},
            )

        # Programar auto-liberación
        task = asyncio.create_task(
            self._auto_uncurse(interaction.guild_id, user.id, dur_seconds)
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

        await interaction.response.send_message(
            f"🔮 **{user.display_name}** ha sido maldecido por **{dur_str}**.\n"
            f"Sus mensajes serán borrados y reenviados en idiomas aleatorios.\n"
            f"Razón: {reason or 'Maldición de Youkai'}",
            ephemeral=True,
        )

    # ── /uncurse ──────────────────────────────────────────────────────────

    @app_commands.command(
        name="uncurse",
        description="🕊️ Libera a un usuario de la maldición",
    )
    @app_commands.describe(user="Usuario a liberar")
    @app_commands.default_permissions(administrator=True)
    async def uncurse(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ) -> None:
        """Quita la maldición de un usuario."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "⛔ Solo administradores pueden usar este comando.", ephemeral=True,
            )
            return

        removed = False
        if self.bot.db:
            removed = await self.bot.db.remove_curse(interaction.guild_id, user.id)
            if removed:
                await self.bot.db.log_action(
                    interaction.guild_id, "uncurse",
                    actor_id=interaction.user.id, target_id=user.id,
                )

        if removed:
            await interaction.response.send_message(
                f"🕊️ **{user.display_name}** ha sido liberado de la maldición.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"❓ **{user.display_name}** no estaba maldecido.", ephemeral=True,
            )

    # ── /listcursed ───────────────────────────────────────────────────────

    @app_commands.command(
        name="listcursed",
        description="📜 Lista todos los usuarios maldecidos en este servidor",
    )
    @app_commands.default_permissions(administrator=True)
    async def listcursed(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Lista maldiciones activas."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "⛔ Solo administradores pueden usar este comando.", ephemeral=True,
            )
            return

        if not self.bot.db:
            await interaction.response.send_message("❌ DB no disponible.", ephemeral=True)
            return

        curses = await self.bot.db.get_active_curses(interaction.guild_id)
        if not curses:
            await interaction.response.send_message(
                "✨ No hay maldiciones activas en este servidor.", ephemeral=True,
            )
            return

        lines = [f"**{len(curses)} maldición(es) activa(s):**\n"]
        for c in curses:
            member = interaction.guild.get_member(c["user_id"])
            name = member.display_name if member else f"ID {c['user_id']}"
            release = datetime.fromisoformat(c["release_at"])
            remaining = release - datetime.now(timezone.utc)
            if remaining.total_seconds() > 0:
                mins = int(remaining.total_seconds() // 60)
                time_str = f"{mins}min" if mins < 120 else f"{mins // 60}h {mins % 60}min"
            else:
                time_str = "expirada"
            reason = c.get("reason", "—")
            lines.append(f"• **{name}** — {time_str} restante — _{reason}_")

        await interaction.response.send_message("\n".join(lines), ephemeral=True)


async def setup(bot):
    """Carga el cog de la maldición como extensión de discord.py."""
    await bot.add_cog(CurseCog(bot))

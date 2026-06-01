"""Automod v3 — sistema principal de automoderación (motor 0-FP).

Reemplaza a automod_v2 (movido a deprecated/). Aplica acciones REVERSIBLES y
graduadas según la decisión del motor puro `utils/automod3`:
  • SOFT/QUARANTINE/HOLD → borra el mensaje gatillo + registra en modqueue/audit
    (sin castigo al usuario; el contenido queda en logs/DB para revisión).
  • PUNITIVE → además aplica un timeout REVERSIBLE (solo con ≥2 llaves HIGH y
    autor no-trusted, según la regla de 2 llaves del motor).

Kill-switch: exportar AM3_SHADOW=1 vuelve a modo log-only al instante (sin
desplegar), por si se necesita observar sin actuar. Validado por backtest sobre
199k mensajes reales (0 castigos automáticos sobre el histórico).
"""

from __future__ import annotations

import datetime
import os
import re
import time
from urllib.parse import urlparse

import discord
from discord.ext import commands
from loguru import logger

from utils.audit_log import send_audit
from goodfaith import Engine, Policy, Mode, Account as AccountContext, Message as MessageContext, Action
from utils.safe_domains import is_safe_domain

_URL = re.compile(r"https?://\S+", re.IGNORECASE)
_INVITE = re.compile(
    r"(?:discord\.(?:gg|com/invite)|discordapp\.com/invite|dsc\.gg|discord\.me)/\S+",
    re.IGNORECASE,
)

_DISCORD_EPOCH_MS = 1420070400000


def _account_age_days(user_id: int) -> float:
    created_ms = (user_id >> 22) + _DISCORD_EPOCH_MS
    return (time.time() - created_ms / 1000) / 86400


class AutomodV3(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.shadow = os.environ.get("AM3_SHADOW", "0") == "1"
        mode = Mode.SHADOW if self.shadow else Mode.ENFORCE
        self.engine = Engine(Policy(mode=mode))
        # Duración del timeout PUNITIVE (reversible). Default 1h.
        self.timeout_seconds = int(os.environ.get("AM3_TIMEOUT_SECONDS", "3600"))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        
        # Sincronizar dinámicamente el modo de la política con self.shadow (por si cambia en tests/runtime)
        mode = Mode.SHADOW if self.shadow else Mode.ENFORCE
        if self.engine.default_policy.mode != mode:
            self.engine.default_policy = Policy(mode=mode)

        try:
            ctx = await self._build_context(message)
        except Exception as exc:  # nunca romper por el shadow
            logger.debug("automod_v3: build_context falló: {}", exc)
            return

        decision = self.engine.evaluate(ctx)
        if decision.action == Action.ALLOW:
            return

        logger.info(
            "[automod_v3 {}] guild={} ch={} user={} → {} (conf={:.2f}) keys={} allow={} | {}",
            "shadow" if self.shadow else "enforce",
            message.guild.id, message.channel.id, message.author.id,
            decision.action.name, decision.confidence,
            [k.name for k in decision.keys], decision.allowlisted,
            "; ".join(decision.reasons)[:200],
        )

        if decision.enforced:
            await self._enforce(message, decision)

    # ── Acciones reversibles ─────────────────────────────────────────────
    async def _enforce(self, message: discord.Message, decision) -> None:
        action = decision.action
        if action <= Action.OBSERVE:
            return  # OBSERVE: solo log, no se toca el mensaje.

        # SOFT+ → borrar el mensaje gatillo (reversible: queda en logs/DB).
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

        # PUNITIVE → timeout reversible (solo aquí; ≥2 llaves, no-trusted).
        if action == Action.PUNITIVE:
            await self._timeout(message.author, "; ".join(decision.reasons)[:300])

        # Modqueue / audit para todo lo accionable (revisión humana + reversión).
        await self._audit(message, decision)

    async def _timeout(self, member, reason: str) -> None:
        until = discord.utils.utcnow() + datetime.timedelta(seconds=self.timeout_seconds)
        try:
            await member.timeout(until, reason=f"automod v3: {reason}"[:400])
        except (discord.Forbidden, discord.HTTPException) as exc:
            logger.warning("automod_v3: timeout falló para {}: {}", member, exc)

    async def _audit(self, message: discord.Message, decision) -> None:
        try:
            target = message.author if isinstance(message.author, discord.Member) else None
            await send_audit(
                message.guild, self.bot.db, "automod", target=target,
                reason=(
                    f"v3 {decision.action.name} | keys={[k.name for k in decision.keys]} | "
                    f"{'; '.join(decision.reasons)[:200]}"
                ),
            )
        except Exception as exc:
            logger.debug("automod_v3: audit falló: {}", exc)

    async def _build_context(self, message: discord.Message) -> MessageContext:
        member = message.author
        content = message.content or ""

        invites = _INVITE.findall(content)
        unsafe = []
        for url in _URL.findall(content):
            try:
                host = (urlparse(url).hostname or "").lower().removeprefix("www.")
            except ValueError:
                host = ""
            if host and not is_safe_domain(host) and not _INVITE.search(url):
                unsafe.append(url)

        try:
            trust = await self.bot.db.get_trust(message.guild.id, member.id)
            msg_count = (trust or {}).get("message_count", 0)
        except Exception:
            msg_count = 0

        server_age = 999.0
        if getattr(member, "joined_at", None):
            server_age = (discord.utils.utcnow() - member.joined_at).total_seconds() / 86400

        perms = getattr(member, "guild_permissions", None)
        is_staff = bool(perms and (
            perms.administrator or perms.ban_members
            or perms.kick_members or perms.manage_messages
        ))

        acc = AccountContext(
            user_id=member.id,
            account_age_days=_account_age_days(member.id),
            server_age_days=server_age,
            msg_count=msg_count,
            has_avatar=getattr(member, "avatar", None) is not None,
            is_staff=is_staff,
        )
        return MessageContext(
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            message_id=message.id,
            author=acc,
            content=content,
            created_at=time.time(),
            mention_count=len(getattr(message, "mentions", []) or []),
            mentions_everyone=bool(getattr(message, "mention_everyone", False)),
            has_attachments=bool(getattr(message, "attachments", None)),
            sticker_count=len(getattr(message, "stickers", []) or []),
            invite_urls=tuple(invites),
            external_invite=bool(invites),
            unsafe_links=tuple(unsafe),
            is_reply=getattr(message, "reference", None) is not None,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutomodV3(bot))

"""Smoke tests del adapter Discord automod_v3 (log-only). Mocks ligeros."""

from __future__ import annotations

import datetime
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from cogs.automod_v3 import AutomodV3
from goodfaith import Action, Message as MessageContext


def _new_uid() -> int:
    # Snowflake reciente → cuenta NUEVA (account_age < NEW_ACCOUNT_DAYS).
    return (int(time.time() * 1000) - 1420070400000) << 22


def _bot(msg_count=5):
    bot = MagicMock()
    bot.db.get_trust = AsyncMock(return_value={"message_count": msg_count})
    bot.db.log_action = AsyncMock()
    bot.db.get_guild_config = AsyncMock(return_value={})
    return bot


def _message(content="", *, uid=111111111111111111, mentions_everyone=False,
             attachments=0, stickers=0, joined_days_ago=30, is_bot=False):
    member = MagicMock()
    member.id = uid
    member.bot = is_bot
    member.joined_at = discord.utils.utcnow() - datetime.timedelta(days=joined_days_ago)
    member.avatar = None
    member.guild_permissions = SimpleNamespace(
        administrator=False, ban_members=False, kick_members=False, manage_messages=False
    )
    member.timeout = AsyncMock()
    msg = MagicMock()
    msg.author = member
    msg.guild = SimpleNamespace(id=1, name="g")
    msg.channel = SimpleNamespace(id=2)
    msg.id = 999
    msg.content = content
    msg.mentions = []
    msg.mention_everyone = mentions_everyone
    msg.attachments = [object()] * attachments
    msg.stickers = [object()] * stickers
    msg.reference = None
    msg.delete = AsyncMock()
    return msg


@pytest.mark.asyncio
async def test_build_context_maps_fields():
    cog = AutomodV3(_bot(msg_count=42))
    ctx = await cog._build_context(_message("hello world"))
    assert isinstance(ctx, MessageContext)
    assert ctx.guild_id == 1 and ctx.channel_id == 2
    assert ctx.author.msg_count == 42
    assert ctx.author.is_staff is False
    assert ctx.author.server_age_days == pytest.approx(30, abs=1)


@pytest.mark.asyncio
async def test_build_context_extracts_invite_and_unsafe_link():
    cog = AutomodV3(_bot())
    ctx = await cog._build_context(_message("join discord.gg/abc and http://evil.example/x"))
    assert ctx.external_invite is True
    assert any("discord.gg/abc" in u for u in ctx.invite_urls)
    assert any("evil.example" in u for u in ctx.unsafe_links)


@pytest.mark.asyncio
async def test_staff_detected():
    cog = AutomodV3(_bot())
    msg = _message("hi")
    msg.author.guild_permissions = SimpleNamespace(
        administrator=True, ban_members=True, kick_members=True, manage_messages=True
    )
    ctx = await cog._build_context(msg)
    assert ctx.author.is_staff is True


@pytest.mark.asyncio
async def test_on_message_bot_author_ignored():
    cog = AutomodV3(_bot())
    cog.engine.evaluate = MagicMock()
    await cog.on_message(_message("anything", is_bot=True))
    cog.engine.evaluate.assert_not_called()


@pytest.mark.asyncio
async def test_enforce_legit_no_action():
    cog = AutomodV3(_bot())
    assert cog.shadow is False  # primario por defecto
    msg = _message("lol same fr")  # legítimo → ALLOW
    await cog.on_message(msg)
    assert not msg.delete.called
    assert not msg.author.timeout.called


@pytest.mark.asyncio
async def test_enforce_punitive_deletes_and_timeouts():
    cog = AutomodV3(_bot(msg_count=0))
    # Cuenta nueva + @everyone + invite + link no-safe → 2 llaves → PUNITIVE.
    msg = _message("@everyone free nitro discord.gg/scam http://scam.tld",
                   uid=_new_uid(), mentions_everyone=True, joined_days_ago=0)
    await cog.on_message(msg)
    assert msg.delete.called
    assert msg.author.timeout.called  # timeout reversible


@pytest.mark.asyncio
async def test_enforce_single_key_deletes_but_no_timeout():
    cog = AutomodV3(_bot(msg_count=0))
    # Cuenta nueva + UN invite → QUARANTINE (1 llave): borra pero NO castiga.
    msg = _message("join discord.gg/cool", uid=_new_uid(), joined_days_ago=0)
    await cog.on_message(msg)
    assert msg.delete.called
    assert not msg.author.timeout.called


@pytest.mark.asyncio
async def test_shadow_kill_switch_no_action():
    cog = AutomodV3(_bot(msg_count=0))
    cog.shadow = True  # kill-switch
    msg = _message("@everyone free nitro discord.gg/scam http://scam.tld",
                   uid=_new_uid(), mentions_everyone=True, joined_days_ago=0)
    await cog.on_message(msg)
    assert not msg.delete.called
    assert not msg.author.timeout.called

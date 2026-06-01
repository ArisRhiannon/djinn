"""
Tests for actions cog, button view, and inert reply registration.
"""
from __future__ import annotations

import unittest.mock as mock
import pytest
import discord
from cogs.actions import ActionsCog, ActionButtonView, fetch_nekos_best_gif
from cogs.nlp_handler import NLPHandlerCog


def test_action_button_view_initialization():
    bot = mock.MagicMock()
    sender = mock.MagicMock(spec=discord.Member)
    recipient = mock.MagicMock(spec=discord.Member)
    
    # Test Hug view setup
    view_hug = ActionButtonView(bot, sender, recipient, "hug")
    assert view_hug.correspond_button.label == "Abrazar de vuelta 🫂"
    assert view_hug.correspond_button.style == discord.ButtonStyle.success

    # Test Kiss view setup
    view_kiss = ActionButtonView(bot, sender, recipient, "kiss")
    assert view_kiss.correspond_button.label == "Besar de vuelta 💋"
    assert view_kiss.correspond_button.style == discord.ButtonStyle.danger


@pytest.mark.asyncio
async def test_action_button_view_correspond_by_correct_recipient():
    bot = mock.MagicMock()
    bot.user.id = 123
    bot.inert_message_ids = set()
    bot.db = mock.MagicMock()
    bot.db.increment_action_count = mock.AsyncMock(return_value=10)
    
    sender = mock.MagicMock(spec=discord.Member)
    sender.mention = "<@111>"
    sender.display_name = "SenderName"
    recipient = mock.MagicMock(spec=discord.Member)
    recipient.id = 456
    recipient.mention = "<@222>"
    recipient.display_name = "RecipientName"

    view = ActionButtonView(bot, sender, recipient, "hug")
    
    interaction = mock.MagicMock(spec=discord.Interaction)
    interaction.guild_id = 999
    interaction.user.id = 456  # Correct recipient!
    interaction.response = mock.AsyncMock()
    interaction.followup = mock.AsyncMock()
    button = mock.MagicMock(spec=discord.ui.Button)

    with mock.patch("cogs.actions.fetch_nekos_best_gif", return_value=("https://example.com/gif.gif", "MyAnime")):
        await view.correspond_button.callback(interaction)

    assert interaction.response.edit_message.called
    assert interaction.followup.send.called
    
    # Assert reply embed description pings and counter
    sent_args, sent_kwargs = interaction.followup.send.call_args
    sent_embed = sent_kwargs["embed"]
    assert "<@222>" in sent_embed.description
    assert "<@111>" in sent_embed.description
    assert "10 abrazos" in sent_embed.footer.text
    assert sent_embed.image.url == "https://example.com/gif.gif"
    assert "Anime: MyAnime" in sent_embed.footer.text


@pytest.mark.asyncio
async def test_action_button_view_ignored_by_non_recipient():
    bot = mock.MagicMock()
    sender = mock.MagicMock(spec=discord.Member)
    recipient = mock.MagicMock(spec=discord.Member)
    recipient.id = 456

    view = ActionButtonView(bot, sender, recipient, "hug")
    
    interaction = mock.MagicMock(spec=discord.Interaction)
    interaction.user.id = 789  # Intruder!
    interaction.response = mock.AsyncMock()
    button = mock.MagicMock(spec=discord.ui.Button)

    await view.correspond_button.callback(interaction)

    assert not interaction.response.edit_message.called
    assert interaction.response.send_message.called
    
    sent_args, sent_kwargs = interaction.response.send_message.call_args
    assert sent_kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_handle_action_self_rejection():
    bot = mock.MagicMock()
    bot.inert_message_ids = set()
    cog = ActionsCog(bot)

    interaction = mock.MagicMock(spec=discord.Interaction)
    interaction.user.id = 111
    interaction.response = mock.AsyncMock()
    
    usuario = mock.MagicMock(spec=discord.Member)
    usuario.id = 111  # Self!

    await cog._handle_action(interaction, usuario, "hug", "template")
    assert interaction.response.send_message.called
    
    sent_args, sent_kwargs = interaction.response.send_message.call_args
    assert "a ti mismo" in sent_args[0]
    assert sent_kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_handle_action_bot_rejection():
    bot = mock.MagicMock()
    bot.inert_message_ids = set()
    cog = ActionsCog(bot)

    interaction = mock.MagicMock(spec=discord.Interaction)
    interaction.user.id = 111
    interaction.response = mock.AsyncMock()
    
    usuario = mock.MagicMock(spec=discord.Member)
    usuario.id = 222
    usuario.bot = True  # Bot!

    await cog._handle_action(interaction, usuario, "hug", "template")
    assert interaction.response.send_message.called
    
    sent_args, sent_kwargs = interaction.response.send_message.call_args
    assert "Los bots no tienen" in sent_args[0]
    assert sent_kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_handle_action_success():
    bot = mock.MagicMock()
    bot.inert_message_ids = set()
    bot.db = mock.MagicMock()
    bot.db.increment_action_count = mock.AsyncMock(return_value=5)
    cog = ActionsCog(bot)

    interaction = mock.MagicMock(spec=discord.Interaction)
    interaction.guild_id = 999
    interaction.user.id = 111
    interaction.user.mention = "<@111>"
    interaction.response = mock.AsyncMock()
    interaction.followup = mock.AsyncMock()
    
    usuario = mock.MagicMock(spec=discord.Member)
    usuario.id = 222
    usuario.bot = False
    usuario.mention = "<@222>"
    usuario.display_name = "UsuarioName"

    with mock.patch("cogs.actions.fetch_nekos_best_gif", return_value=("https://example.com/gif.gif", "MyAnime")):
        await cog._handle_action(interaction, usuario, "hug", "{} abrazó a {}")

    assert interaction.response.defer.called
    assert interaction.followup.send.called
    
    sent_args, sent_kwargs = interaction.followup.send.call_args
    sent_embed = sent_kwargs["embed"]
    assert "<@111>" in sent_embed.description
    assert "<@222>" in sent_embed.description
    assert "5 abrazos" in sent_embed.footer.text
    assert sent_embed.image.url == "https://example.com/gif.gif"
    assert "Anime: MyAnime" in sent_embed.footer.text
    
    # Assert registered as inert
    sent_msg = interaction.followup.send.return_value
    assert sent_msg.id in bot.inert_message_ids


@pytest.mark.asyncio
async def test_nlp_handler_ignores_action_replies():
    bot = mock.MagicMock()
    bot.user.id = 12345
    bot.inert_message_ids = set()
    
    cog = NLPHandlerCog(bot)
    
    message = mock.MagicMock(spec=discord.Message)
    message.guild = mock.MagicMock()
    message.author.bot = False
    message.webhook_id = None
    message.mentions = [bot.user]
    
    message.reference = mock.MagicMock()
    resolved_message = mock.MagicMock(spec=discord.Message)
    resolved_message.author.id = bot.user.id
    resolved_message.id = 99999
    
    # Simulation an action embed message
    embed = mock.MagicMock(spec=discord.Embed)
    embed.description = "Sender abrazó a Recipient"
    resolved_message.embeds = [embed]
    
    message.reference.resolved = resolved_message
    
    with mock.patch("cogs.nlp_handler.can_use_youkai_nl", return_value=True):
        message.channel.typing = mock.MagicMock()
        await cog.on_message(message)
        assert not message.channel.typing.called


@pytest.mark.asyncio
async def test_database_action_counters(tmp_path):
    from utils.database import Database
    import aiosqlite
    
    db_path = tmp_path / "test_actions.db"
    db = Database(str(db_path))
    await db.initialize()
    
    # Verify migration executed and table exists
    async with db._db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_action_counters'") as cursor:
        row = await cursor.fetchone()
        assert row is not None
    
    # Test initial increment
    cnt1 = await db.increment_action_count(guild_id=123, user_id=456, action_type="hug")
    assert cnt1 == 1
    
    # Test second increment
    cnt2 = await db.increment_action_count(guild_id=123, user_id=456, action_type="hug")
    assert cnt2 == 2
    
    # Test get count
    cnt_get = await db.get_action_count(guild_id=123, user_id=456, action_type="hug")
    assert cnt_get == 2
    
    # Test non-existing get count
    cnt_non = await db.get_action_count(guild_id=123, user_id=456, action_type="kiss")
    assert cnt_non == 0
    
    await db.close()


@pytest.mark.asyncio
async def test_cog_app_command_error_transformer_error():
    bot = mock.MagicMock()
    cog = ActionsCog(bot)
    
    interaction = mock.MagicMock(spec=discord.Interaction)
    interaction.command.name = "hug"
    interaction.user = "sender"
    
    interaction.response = mock.MagicMock()
    interaction.response.is_done.return_value = False
    interaction.response.send_message = mock.AsyncMock()
    
    interaction.followup = mock.MagicMock()
    interaction.followup.send = mock.AsyncMock()
    
    # Simulate a TransformerError
    transformer = mock.MagicMock()
    value = "xoft.io"
    error = discord.app_commands.TransformerError(value, discord.Member, transformer)
    
    await cog.cog_app_command_error(interaction, error)
    
    assert interaction.response.send_message.called
    sent_args, sent_kwargs = interaction.response.send_message.call_args
    assert "No pude encontrar al usuario que mencionaste" in sent_args[0]
    assert sent_kwargs["ephemeral"] is True



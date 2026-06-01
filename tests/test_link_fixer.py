"""
Tests for link fixer replacement logic.
"""
from __future__ import annotations

import unittest.mock as mock
import pytest
from cogs.link_fixer import fix_links, LinkFixerCog


def test_fix_links_twitter_and_x():
    # Standard Twitter and X links
    assert fix_links("https://x.com/google/status/12345")[0] == "https://fxtwitter.com/google/status/12345"
    assert fix_links("https://twitter.com/google/status/12345")[0] == "https://fxtwitter.com/google/status/12345"
    assert fix_links("https://mobile.twitter.com/google/status/12345")[0] == "https://fxtwitter.com/google/status/12345"
    assert fix_links("https://www.x.com/google/status/12345")[0] == "https://fxtwitter.com/google/status/12345"

    # Query parameters preserved
    assert fix_links("https://x.com/user/status/123?s=20&t=abc")[0] == "https://fxtwitter.com/user/status/123?s=20&t=abc"


def test_fix_links_tiktok():
    # TikTok standard and mobile links
    assert fix_links("https://tiktok.com/@user/video/12345")[0] == "https://tnktok.com/@user/video/12345"
    assert fix_links("https://www.tiktok.com/@user/video/12345")[0] == "https://tnktok.com/@user/video/12345"
    assert fix_links("https://vm.tiktok.com/ZMYxX/")[0] == "https://vm.tnktok.com/ZMYxX/"
    assert fix_links("https://vt.tiktok.com/ZMYxX/")[0] == "https://vt.tnktok.com/ZMYxX/"


def test_fix_links_instagram_posts_and_reels():
    # Instagram posts, reels, tv and share links should be fixed to the default eeinstagram.com
    assert fix_links("https://instagram.com/p/CoX/")[0] == "https://eeinstagram.com/p/CoX/"
    assert fix_links("https://www.instagram.com/reel/CoX/")[0] == "https://eeinstagram.com/reel/CoX/"
    assert fix_links("https://instagram.com/reels/CoX/")[0] == "https://eeinstagram.com/reel/CoX/"
    assert fix_links("https://instagram.com/tv/CoX/")[0] == "https://eeinstagram.com/tv/CoX/"
    assert fix_links("https://instagram.com/share/p/CoX/")[0] == "https://eeinstagram.com/share/p/CoX/"

    # Verify custom proxy can be passed
    assert fix_links("https://instagram.com/p/CoX/", instagram_proxy="vxinstagram.com")[0] == "https://vxinstagram.com/p/CoX/"


def test_fix_links_instagram_profiles_preserved():
    # Instagram profile/static links should remain unchanged
    assert fix_links("https://instagram.com/username")[0] == "https://instagram.com/username"
    assert fix_links("https://www.instagram.com/about/us")[0] == "https://www.instagram.com/about/us"
    assert fix_links("https://instagram.com/developer/")[0] == "https://instagram.com/developer/"


def test_fix_links_unsupported_domains():
    # Other domains should remain unchanged
    assert fix_links("https://google.com")[0] == "https://google.com"
    assert fix_links("https://github.com/google/gemma")[0] == "https://github.com/google/gemma"
    assert fix_links("https://youtube.com/watch?v=123")[0] == "https://youtube.com/watch?v=123"


def test_fix_links_facebook():
    assert fix_links("https://facebook.com/post/123")[0] == "https://fixfacebook.com/post/123"
    assert fix_links("https://www.facebook.com/post/123")[0] == "https://fixfacebook.com/post/123"
    assert fix_links("https://m.facebook.com/video.php?v=123")[0] == "https://fixfacebook.com/video.php?v=123"
    assert fix_links("https://fb.watch/xyz/")[0] == "https://fixfacebook.com/xyz/"


def test_fix_links_reddit():
    assert fix_links("https://reddit.com/r/pics/comments/123/")[0] == "https://rxddit.com/r/pics/comments/123/"
    assert fix_links("https://www.reddit.com/r/pics/comments/123/")[0] == "https://rxddit.com/r/pics/comments/123/"
    assert fix_links("https://old.reddit.com/r/pics/comments/123/")[0] == "https://rxddit.com/r/pics/comments/123/"


def test_fix_links_content_wrapping():
    # Multiple links, punctuation and text wrapping
    text = "Mira esto: https://x.com/user/status/123 y luego esto: https://vm.tiktok.com/ZMYxX/. ¿Qué opinas?"
    expected = "Mira esto: https://fxtwitter.com/user/status/123 y luego esto: https://vm.tnktok.com/ZMYxX/. ¿Qué opinas?"
    
    res_text, replaced = fix_links(text)
    assert replaced is True
    assert res_text == expected

    # Mixed links containing safe instagram links, facebook, and reddit
    text_mixed = "Enlace corregible: https://instagram.com/p/CoX/ y fb: https://fb.watch/xyz/ y reddit: https://reddit.com/r/pics/comments/123/ y no corregible: https://instagram.com/my_profile"
    expected_mixed = "Enlace corregible: https://eeinstagram.com/p/CoX/ y fb: https://fixfacebook.com/xyz/ y reddit: https://rxddit.com/r/pics/comments/123/ y no corregible: https://instagram.com/my_profile"
    
    res_mixed, replaced_mixed = fix_links(text_mixed)
    assert replaced_mixed is True
    assert res_mixed == expected_mixed


def test_fix_links_code_blocks_ignored():
    # URLs inside code blocks (backticks) should be ignored
    text = "Corrección: https://x.com/status/1, pero no corrijas `https://x.com/status/2` ni:\n```python\n# code block\nurl = 'https://instagram.com/p/123/'\n```"
    expected = "Corrección: https://fxtwitter.com/status/1, pero no corrijas `https://x.com/status/2` ni:\n```python\n# code block\nurl = 'https://instagram.com/p/123/'\n```"
    
    res_text, replaced = fix_links(text)
    assert replaced is True
    assert res_text == expected

    # Entire message is code block
    text_all_code = "```\nhttps://x.com/status/1\n```"
    res_all_code, replaced_all_code = fix_links(text_all_code)
    assert replaced_all_code is False
    assert res_all_code == text_all_code


@pytest.mark.asyncio
async def test_link_fixer_cog_check_proxies_task():
    bot = mock.MagicMock()
    with mock.patch("discord.ext.tasks.Loop.start") as mock_start:
        cog = LinkFixerCog(bot)
        assert mock_start.called
        
    mock_resp = mock.MagicMock()
    mock_resp.status = 200
    
    mock_resp_ctx = mock.AsyncMock()
    mock_resp_ctx.__aenter__.return_value = mock_resp
    
    mock_session = mock.MagicMock()
    mock_session.get.return_value = mock_resp_ctx
    
    mock_session_ctx = mock.AsyncMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    
    with mock.patch("aiohttp.ClientSession", return_value=mock_session_ctx):
        await cog.check_proxies_task()
        
    assert cog.instagram_proxy == "eeinstagram.com"


@pytest.mark.asyncio
async def test_link_fixer_cog_check_proxies_task_fallback():
    bot = mock.MagicMock()
    with mock.patch("discord.ext.tasks.Loop.start"):
        cog = LinkFixerCog(bot)
        
    def mock_get(url, **kwargs):
        if url == "https://eeinstagram.com/":
            raise Exception("Connection timed out")
        mock_resp = mock.MagicMock()
        mock_resp.status = 200
        mock_resp_ctx = mock.AsyncMock()
        mock_resp_ctx.__aenter__.return_value = mock_resp
        return mock_resp_ctx
        
    mock_session = mock.MagicMock()
    mock_session.get.side_effect = mock_get
    
    mock_session_ctx = mock.AsyncMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    
    with mock.patch("aiohttp.ClientSession", return_value=mock_session_ctx):
        await cog.check_proxies_task()
        
    assert cog.instagram_proxy == "ddinstagram.com"


@pytest.mark.asyncio
async def test_nlp_handler_ignores_inert_replies():
    from cogs.nlp_handler import NLPHandlerCog
    import discord
    
    bot = mock.MagicMock()
    bot.user.id = 12345
    bot.inert_message_ids = {55555}
    
    cog = NLPHandlerCog(bot)
    
    message = mock.MagicMock(spec=discord.Message)
    message.guild = mock.MagicMock()
    message.author.bot = False
    message.webhook_id = None
    message.mentions = [bot.user]
    
    message.reference = mock.MagicMock()
    resolved_message = mock.MagicMock(spec=discord.Message)
    resolved_message.author.id = bot.user.id
    resolved_message.id = 55555
    message.reference.resolved = resolved_message
    
    with mock.patch("cogs.nlp_handler.can_use_youkai_nl", return_value=True):
        message.channel.typing = mock.MagicMock()
        await cog.on_message(message)
        assert not message.channel.typing.called


@pytest.mark.asyncio
async def test_nlp_handler_ignores_inert_replies_fallback():
    from cogs.nlp_handler import NLPHandlerCog
    import discord
    
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
    resolved_message.content = "https://fxtwitter.com/status/123 https://vxinstagram.com/reel/abc"
    message.reference.resolved = resolved_message
    
    with mock.patch("cogs.nlp_handler.can_use_youkai_nl", return_value=True):
        message.channel.typing = mock.MagicMock()
        await cog.on_message(message)
        assert not message.channel.typing.called


@pytest.mark.asyncio
async def test_nlp_handler_processes_normal_replies():
    from cogs.nlp_handler import NLPHandlerCog
    import discord
    
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
    resolved_message.content = "Hola Youkai, como estas?"
    message.reference.resolved = resolved_message
    
    typing_ctx = mock.AsyncMock()
    message.channel.typing.return_value = typing_ctx
    
    with mock.patch("cogs.nlp_handler.can_use_youkai_nl", return_value=True):
        try:
            await cog.on_message(message)
        except Exception:
            pass
            
        assert message.channel.typing.called


@pytest.mark.asyncio
async def test_link_fixer_cog_on_message_only_fixed_links():
    import discord
    bot = mock.MagicMock()
    bot.inert_message_ids = set()

    with mock.patch("discord.ext.tasks.Loop.start"):
        cog = LinkFixerCog(bot)

    message = mock.MagicMock(spec=discord.Message)
    message.guild = mock.MagicMock()
    message.guild.me = mock.MagicMock()
    message.author.bot = False
    message.content = "Mira esto: https://x.com/google/status/12345 y esta mención a @Karu"

    # Mock permissions to check message.channel.permissions_for(me)
    perms = mock.MagicMock()
    perms.manage_messages = True
    message.channel.permissions_for.return_value = perms

    # Mock message.edit and message.reply
    message.edit = mock.AsyncMock()
    
    reply_msg = mock.MagicMock(spec=discord.Message)
    reply_msg.id = 77777
    message.reply = mock.AsyncMock(return_value=reply_msg)

    await cog.on_message(message)

    # Assert it suppressed the original message embeds
    message.edit.assert_called_once_with(suppress=True)

    # Assert it replied with only the corrected URL
    expected_msg = "[Tweet](<https://x.com/google/status/12345>) • [@google](<https://x.com/google>) • [FxTwitter](https://fxtwitter.com/google/status/12345)"
    message.reply.assert_called_once_with(expected_msg, mention_author=False)
    assert 77777 in bot.inert_message_ids


@pytest.mark.asyncio
async def test_link_fixer_cog_on_message_multiple_links_and_duplicates():
    import discord
    bot = mock.MagicMock()
    bot.inert_message_ids = set()

    with mock.patch("discord.ext.tasks.Loop.start"):
        cog = LinkFixerCog(bot)

    message = mock.MagicMock(spec=discord.Message)
    message.guild = mock.MagicMock()
    message.guild.me = mock.MagicMock()
    message.author.bot = False
    # Multiple and duplicate URLs to fix
    message.content = (
        "Check these: https://x.com/user/status/1\n"
        "https://x.com/user/status/1 (duplicate)\n"
        "https://vm.tiktok.com/ZMYxX/ (tiktok)"
    )

    perms = mock.MagicMock()
    perms.manage_messages = False  # No permission to edit
    message.channel.permissions_for.return_value = perms

    message.edit = mock.AsyncMock()
    reply_msg = mock.MagicMock(spec=discord.Message)
    reply_msg.id = 88888
    message.reply = mock.AsyncMock(return_value=reply_msg)

    await cog.on_message(message)

    # Should not call edit because manage_messages is False
    assert not message.edit.called

    # Expected: only unique fixed URLs separated by newlines in new format
    expected_msg = (
        "[Tweet](<https://x.com/user/status/1>) • [@user](<https://x.com/user>) • [FxTwitter](https://fxtwitter.com/user/status/1)\n"
        "[TikTok](<https://vm.tiktok.com/ZMYxX/>) • [tnkTok](https://vm.tnktok.com/ZMYxX/)"
    )
    message.reply.assert_called_once_with(expected_msg, mention_author=False)
    assert 88888 in bot.inert_message_ids


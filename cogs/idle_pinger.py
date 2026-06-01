"""
Idle Pinger — posts a configured GIF to a channel after N hours of inactivity.

After triggering, requires at least 60 NEW messages in the channel before
re-arming, to prevent spam. State is in-memory (resets on bot restart, which
naturally re-arms the trigger).
"""
from __future__ import annotations

import logging
import time

import discord
from discord.ext import commands, tasks

logger = logging.getLogger("djinn.idle_pinger")

# ── Configuration ────────────────────────────────────────────────────────────

GUILD_ID = 1269877200488763472
CHANNEL_ID = 1269877200988016640
GIF_URL = "https://tenor.com/view/mischacrossing-twitch-hollow-knight-bench-rain-gif-17361834"
IDLE_SECONDS = 60 * 60        # 1 hour of no activity
RECHARGE_MESSAGES = 60        # need 60 new messages after a post to re-arm
CHECK_INTERVAL = 60           # background check runs every 60s


class IdlePinger(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # State (in-memory, per channel)
        self._last_activity: float = time.time()
        self._messages_since_last_post: int = RECHARGE_MESSAGES  # start armed
        self._armed: bool = True
        self._idle_check.start()

    def cog_unload(self) -> None:
        self._idle_check.cancel()

    # ── Listener ─────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None or message.guild.id != GUILD_ID:
            return
        if message.channel.id != CHANNEL_ID:
            return
        # Ignore the bot's own messages — including the gif post itself
        if message.author.bot:
            return

        self._last_activity = time.time()

        # If we're not armed yet, count messages towards re-arming
        if not self._armed:
            self._messages_since_last_post += 1
            if self._messages_since_last_post >= RECHARGE_MESSAGES:
                self._armed = True
                logger.info(
                    "idle_pinger: re-armed after %d messages",
                    self._messages_since_last_post,
                )

    # ── Background task ──────────────────────────────────────────────────────

    @tasks.loop(seconds=CHECK_INTERVAL)
    async def _idle_check(self) -> None:
        if not self._armed:
            return
        idle = time.time() - self._last_activity
        if idle < IDLE_SECONDS:
            return

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            return
        channel = guild.get_channel(CHANNEL_ID)
        if channel is None or not isinstance(channel, discord.TextChannel):
            return

        try:
            await channel.send(GIF_URL)
            logger.info("idle_pinger: posted gif after %.0fs of inactivity", idle)
        except Exception as e:
            logger.warning("idle_pinger: failed to send: %s", e)
            return

        # Disarm and reset counter
        self._armed = False
        self._messages_since_last_post = 0

    @_idle_check.before_loop
    async def _before(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(IdlePinger(bot))

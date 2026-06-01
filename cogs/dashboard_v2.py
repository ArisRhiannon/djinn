"""Cog: Dashboard v2 — HUD determinista de Youkai (sin AI).

/dashboard genera un embed rico con métricas en tiempo real del servidor.
Todo es computado directamente desde la DB y discord.py, sin LLM.
"""

from __future__ import annotations

import math
import time
import logging
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("youkai.dashboard_v2")

_COLOR = 0xE63946  # Youkai red


class DashboardV2(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="dashboard", description="HUD de Youkai — métricas del servidor en tiempo real")
    @app_commands.guild_only()
    async def dashboard(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        embed = await self._build(interaction.guild)
        await interaction.followup.send(embed=embed)

    async def _build(self, guild: discord.Guild) -> discord.Embed:
        db = self.bot.db
        gid = guild.id
        now_epoch = int(time.time())
        one_hour_ago = now_epoch - 3600
        today_start = int(datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).timestamp())

        # ── Queries ──────────────────────────────────────────────────────
        # Messages last hour
        msgs_1h = await db.fetchone(
            "SELECT COUNT(*) as c FROM messages WHERE guild_id=? AND timestamp>?",
            (gid, one_hour_ago),
        )
        total_1h = msgs_1h["c"] if msgs_1h else 0
        msgs_per_min = total_1h / 60.0

        # Active users last hour
        active_row = await db.fetchone(
            "SELECT COUNT(DISTINCT user_id) as c FROM messages WHERE guild_id=? AND timestamp>?",
            (gid, one_hour_ago),
        )
        active_users = active_row["c"] if active_row else 0

        # Voice users
        voice_users = sum(len(vc.members) for vc in guild.voice_channels)

        # Top 5 users last hour
        top5 = await db.fetch(
            "SELECT user_id, COUNT(*) as c FROM messages WHERE guild_id=? AND timestamp>? "
            "GROUP BY user_id ORDER BY c DESC LIMIT 5",
            (gid, one_hour_ago),
        )

        # Channel distribution (entropy)
        ch_dist = await db.fetch(
            "SELECT channel_id, COUNT(*) as c FROM messages WHERE guild_id=? AND timestamp>? "
            "GROUP BY channel_id",
            (gid, one_hour_ago),
        )

        # Warnings active
        warns_row = await db.fetchone(
            "SELECT COUNT(*) as c FROM warnings WHERE guild_id=?", (gid,)
        )
        total_warns = warns_row["c"] if warns_row else 0

        # Sealed users
        sealed_row = await db.fetchone(
            "SELECT COUNT(*) as c FROM user_seals WHERE guild_id=?", (gid,)
        )
        sealed_count = sealed_row["c"] if sealed_row else 0

        # Active listeners
        listeners_row = await db.fetchone(
            "SELECT COUNT(*) as c FROM guild_listeners WHERE guild_id=? AND enabled=1", (gid,)
        )
        listeners_count = listeners_row["c"] if listeners_row else 0

        # Economy
        econ_total = await db.fetchone(
            "SELECT SUM(balance) as s FROM user_credits WHERE guild_id=?", (gid,)
        )
        total_credits = econ_total["s"] if econ_total and econ_total["s"] else 0

        top_holder = await db.fetchone(
            "SELECT user_id, balance FROM user_credits WHERE guild_id=? ORDER BY balance DESC LIMIT 1",
            (gid,),
        )

        # Peak hour (all time)
        peak = await db.fetchone(
            "SELECT CAST(((timestamp % 86400) / 3600) AS INTEGER) as hour, COUNT(*) as c "
            "FROM messages WHERE guild_id=? GROUP BY hour ORDER BY c DESC LIMIT 1",
            (gid,),
        )

        # Messages today
        msgs_today_row = await db.fetchone(
            "SELECT COUNT(*) as c FROM messages WHERE guild_id=? AND timestamp>?",
            (gid, today_start),
        )
        msgs_today = msgs_today_row["c"] if msgs_today_row else 0

        # ── Computations ─────────────────────────────────────────────────
        # Entropy
        entropy, max_entropy, entropy_norm = 0.0, 0.0, 0.0
        if ch_dist:
            counts = [r["c"] for r in ch_dist]
            total = sum(counts)
            if total > 0:
                probs = [c / total for c in counts]
                entropy = -sum(p * math.log2(p) for p in probs if p > 0)
                max_entropy = math.log2(len(counts)) if len(counts) > 1 else 1.0
                entropy_norm = entropy / max_entropy if max_entropy > 0 else 0.0

        entropy_label = "CONCENTRADA" if entropy_norm < 0.3 else ("MODERADA" if entropy_norm < 0.7 else "DIVERSA")
        entropy_bar = int(entropy_norm * 10)
        entropy_visual = "▓" * entropy_bar + "░" * (10 - entropy_bar)

        # Hottest channel
        hottest_ch = max(ch_dist, key=lambda r: r["c"]) if ch_dist else None
        hottest_name = "—"
        if hottest_ch:
            ch_obj = guild.get_channel(hottest_ch["channel_id"])
            hottest_name = f"#{ch_obj.name}" if ch_obj else f"#{hottest_ch['channel_id']}"
            hottest_count = hottest_ch["c"]
        else:
            hottest_count = 0

        # Top 5 formatted
        top5_lines = []
        for i, row in enumerate(top5):
            member = guild.get_member(row["user_id"])
            name = member.display_name if member else str(row["user_id"])
            top5_lines.append(f"`{i+1}.` **{name}** — {row['c']}")
        top5_text = "\n".join(top5_lines) if top5_lines else "`sin actividad`"

        # Top credit holder
        if top_holder and top_holder["balance"] > 0:
            holder_member = guild.get_member(top_holder["user_id"])
            holder_name = holder_member.display_name if holder_member else str(top_holder["user_id"])
            econ_text = f"💰 **{total_credits:,}** en circulación\n👑 {holder_name} — {top_holder['balance']:,}"
        else:
            econ_text = f"💰 **{total_credits:,}** en circulación"

        # Peak hour — show as Discord timestamp so each user sees their local time
        if peak:
            today = datetime.now(timezone.utc).replace(hour=peak["hour"], minute=0, second=0, microsecond=0)
            peak_text = f"<t:{int(today.timestamp())}:t>"
        else:
            peak_text = "—"

        # Uptime
        uptime_secs = int(time.time() - getattr(self.bot, '_start_time', time.time()))
        days, rem = divmod(uptime_secs, 86400)
        hours, rem = divmod(rem, 3600)
        mins, _ = divmod(rem, 60)
        uptime_str = f"{days}d {hours}h {mins}m"

        # ── Build Embed ──────────────────────────────────────────────────
        embed = discord.Embed(color=_COLOR)
        embed.set_author(
            name="Y O U K A I",
            icon_url=self.bot.user.display_avatar.url,
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)

        # Server Pulse
        embed.add_field(
            name="⌁ SERVER PULSE",
            value=f"**{msgs_per_min:.1f}** msg/min · **{active_users}** activos · **{voice_users}** en voz",
            inline=False,
        )

        # Top 5
        embed.add_field(name="⌁ TOP 5 (1h)", value=top5_text, inline=True)

        # Entropy
        embed.add_field(
            name="⌁ ENTROPÍA",
            value=f"`{entropy_visual}` {entropy_norm:.2f}\n{entropy_label}",
            inline=True,
        )

        # Channel Heat
        embed.add_field(
            name="⌁ CANAL HOT",
            value=f"🔥 {hottest_name} — **{hottest_count}** msgs/h",
            inline=True,
        )

        # Moderation
        embed.add_field(
            name="⌁ MODERACIÓN",
            value=f"⚠ {total_warns} warns · 🔒 {sealed_count} sellados · 👁 {listeners_count} reglas",
            inline=False,
        )

        # Economy
        embed.add_field(name="⌁ ECONOMÍA", value=econ_text, inline=True)

        # Peak Hour
        embed.add_field(name="⌁ PEAK HOUR", value=f"🕐 {peak_text}", inline=True)

        # Today
        embed.add_field(name="⌁ HOY", value=f"📨 **{msgs_today:,}** mensajes", inline=True)

        # Footer
        embed.set_footer(
            text=f"Uptime: {uptime_str} · {guild.member_count} miembros · Refreshed",
            icon_url=self.bot.user.display_avatar.url,
        )
        embed.timestamp = datetime.now(timezone.utc)

        return embed


async def setup(bot) -> None:
    await bot.add_cog(DashboardV2(bot))

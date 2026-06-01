"""Cog: Override API — HTTP server for Aris's remote control panel.

Serves guild/channel/message data + tool execution via REST.
Protected by bearer token. Runs on port 7700 (internal only).
"""

from __future__ import annotations

import logging
import datetime
import os

import aiohttp.web as web
import discord
from discord.ext import commands

logger = logging.getLogger("djinn.override_api")

_PORT = int(os.environ.get("FAIRY_OVERRIDE_API_PORT") or 7700)
_TOKEN = os.environ.get("OVERRIDE_API_TOKEN") or "yk-override-Kx9$mR2vL7nQ4wZp8jF1bT6cY0hA3dE5"


def _auth(request: web.Request) -> bool:
    auth = request.headers.get("Authorization", "")
    return auth == f"Bearer {_TOKEN}"


class OverrideAPI(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None

    async def cog_load(self) -> None:
        self._app = web.Application()
        self._app.router.add_get("/api/guilds", self._h_guilds)
        self._app.router.add_get("/api/channels/{guild_id}", self._h_channels)
        self._app.router.add_get("/api/messages/{guild_id}/{channel_id}", self._h_messages)
        self._app.router.add_get("/api/members/{guild_id}", self._h_members)
        self._app.router.add_post("/api/send/{guild_id}/{channel_id}", self._h_send)
        self._app.router.add_post("/api/trigger_daily_report", self._h_trigger_daily_report)
        self._app.router.add_post("/api/mute", self._h_mute)
        self._app.router.add_post("/api/seal", self._h_seal)
        self._app.router.add_post("/api/send_dm", self._h_send_dm)
        self._app.router.add_get("/api/health", self._h_health)
        self._runner = web.AppRunner(self._app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", _PORT)
        await site.start()
        logger.info(f"Override API running on port {_PORT}")

    async def cog_unload(self) -> None:
        if self._runner:
            await self._runner.cleanup()

    # ── Handlers ──────────────────────────────────────────────────────────

    async def _h_health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "guilds": len(self.bot.guilds)})

    async def _h_guilds(self, request: web.Request) -> web.Response:
        if not _auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        guilds = []
        for g in self.bot.guilds:
            guilds.append({
                "id": str(g.id), "name": g.name,
                "icon": str(g.icon.url) if g.icon else None,
                "members": g.member_count,
            })
        return web.json_response(guilds)

    async def _h_channels(self, request: web.Request) -> web.Response:
        if not _auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        gid = int(request.match_info["guild_id"])
        guild = self.bot.get_guild(gid)
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)
        channels = []
        for ch in sorted(guild.channels, key=lambda c: (c.position, c.name)):
            if isinstance(ch, (discord.CategoryChannel, discord.VoiceChannel, discord.StageChannel)):
                continue
            perms = ch.permissions_for(guild.me)
            if not perms.read_messages:
                continue
            channels.append({
                "id": str(ch.id), "name": ch.name,
                "type": str(ch.type),
                "category": ch.category.name if ch.category else None,
            })
        return web.json_response(channels)

    async def _h_messages(self, request: web.Request) -> web.Response:
        if not _auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        gid = int(request.match_info["guild_id"])
        cid = int(request.match_info["channel_id"])
        guild = self.bot.get_guild(gid)
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)
        ch = guild.get_channel(cid)
        if not ch or not hasattr(ch, "history"):
            return web.json_response({"error": "channel not found"}, status=404)

        limit = min(int(request.query.get("limit", "50")), 100)
        before = request.query.get("before")

        kwargs = {"limit": limit}
        if before:
            kwargs["before"] = discord.Object(id=int(before))

        messages = []
        try:
            async for msg in ch.history(**kwargs):
                m = {
                    "id": str(msg.id), "content": msg.content,
                    "author": {"id": str(msg.author.id), "name": msg.author.display_name,
                               "avatar": str(msg.author.display_avatar.url)},
                    "timestamp": msg.created_at.isoformat(),
                    "attachments": [{"url": a.url, "filename": a.filename,
                                     "content_type": a.content_type} for a in msg.attachments],
                    "embeds": len(msg.embeds),
                }
                messages.append(m)
        except discord.Forbidden:
            return web.json_response({"error": "no access to this channel"}, status=403)
        return web.json_response(messages)

    async def _h_members(self, request: web.Request) -> web.Response:
        if not _auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        gid = int(request.match_info["guild_id"])
        guild = self.bot.get_guild(gid)
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)
        members = []
        for m in guild.members[:200]:
            members.append({
                "id": str(m.id), "name": m.display_name,
                "avatar": str(m.display_avatar.url),
                "status": str(m.status) if hasattr(m, "status") else "unknown",
                "top_role": m.top_role.name if m.top_role else None,
            })
        return web.json_response(members)

    async def _h_send(self, request: web.Request) -> web.Response:
        if not _auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        gid = int(request.match_info["guild_id"])
        cid = int(request.match_info["channel_id"])
        guild = self.bot.get_guild(gid)
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)
        ch = guild.get_channel(cid)
        if not ch:
            return web.json_response({"error": "channel not found"}, status=404)
        body = await request.json()
        content = body.get("content", "")
        if not content:
            return web.json_response({"error": "no content"}, status=400)
        msg = await ch.send(content)
        return web.json_response({"success": True, "message_id": str(msg.id)})

    async def _h_trigger_daily_report(self, request: web.Request) -> web.Response:
        if not _auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        
        conscious_cog = self.bot.get_cog("ConsciousMode")
        if not conscious_cog:
            return web.json_response({"error": "ConsciousMode cog not found"}, status=404)
        
        from zoneinfo import ZoneInfo
        from collections import Counter
        import asyncio
        
        CDMX_TZ = ZoneInfo("America/Mexico_City")
        now_cdmx = datetime.datetime.now(CDMX_TZ)
        start_ts = int(datetime.datetime(now_cdmx.year, now_cdmx.month, now_cdmx.day, 0, 0, 0, tzinfo=CDMX_TZ).timestamp())
        end_ts = int(datetime.datetime(now_cdmx.year, now_cdmx.month, now_cdmx.day, 8, 0, 0, tzinfo=CDMX_TZ).timestamp())
        
        results = []
        for guild in self.bot.guilds:
            gid = guild.id
            config = await self.bot.db.get_guild_config(gid)
            mod_ch_id = config.get("mod_channel")
            if not mod_ch_id:
                results.append({"guild_id": str(gid), "name": guild.name, "status": "skipped (no mod channel)"})
                continue
            
            mod_channel = guild.get_channel(mod_ch_id)
            if not mod_channel:
                results.append({"guild_id": str(gid), "name": guild.name, "status": "skipped (mod channel not found)"})
                continue
            
            rows = await self.bot.db.fetch(
                "SELECT username, channel_id, timestamp FROM messages "
                "WHERE guild_id = ? AND timestamp >= ? AND timestamp <= ? "
                "ORDER BY timestamp ASC",
                (gid, start_ts, end_ts)
            )
            
            # Reset or initialize notes for this guild
            conscious_cog._notes[gid] = []
            
            if rows:
                by_hour = {}
                for r in rows:
                    dt = datetime.datetime.fromtimestamp(r["timestamp"], tz=CDMX_TZ)
                    by_hour.setdefault(dt.hour, []).append(r)
                
                for h in sorted(by_hour.keys()):
                    msgs = by_hour[h]
                    unique_channels = len(set(m["channel_id"] for m in msgs))
                    
                    # Count users
                    user_counts = Counter(m["username"] for m in msgs)
                    active_users = [u for u, _ in user_counts.most_common(4)]
                    users_str = ", ".join(active_users)
                    
                    time_str = f"{h:02d}:00"
                    note = f"[{time_str}] CLEAR — {len(msgs)} msgs en {unique_channels} canales. Activos: {users_str}"
                    conscious_cog._add_note(gid, note)
            else:
                conscious_cog._add_note(gid, "Sin mensajes en las últimas rondas de vigilancia.")
            
            # Send the daily report
            asyncio.create_task(conscious_cog._send_daily_report(guild, mod_channel))
            results.append({
                "guild_id": str(gid),
                "name": guild.name,
                "status": "triggered",
                "notes_count": len(conscious_cog._notes.get(gid, []))
            })
            
        return web.json_response({"success": True, "results": results})

    async def _h_mute(self, request: web.Request) -> web.Response:
        if not _auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        
        body = await request.json()
        gid = int(body.get("guild_id"))
        uid = int(body.get("user_id"))
        duration = int(body.get("duration", 60))
        reason = body.get("reason", "Mute manual via API")
        
        guild = self.bot.get_guild(gid)
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)
            
        try:
            member = guild.get_member(uid)
            if not member:
                member = await guild.fetch_member(uid)
        except discord.NotFound:
            return web.json_response({"error": "member not found"}, status=404)
            
        try:
            until = discord.utils.utcnow() + datetime.timedelta(seconds=duration)
            await member.timeout(until, reason=reason)
            return web.json_response({"success": True, "muted_until": until.isoformat()})
        except Exception as e:
            logger.error(f"Failed to mute user {uid} in guild {gid}: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _h_seal(self, request: web.Request) -> web.Response:
        if not _auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        
        body = await request.json()
        gid = int(body.get("guild_id"))
        uid = int(body.get("user_id"))
        duration = body.get("duration", "5m")
        reason = body.get("reason", "Sellado manual via API")
        
        guild = self.bot.get_guild(gid)
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)
            
        try:
            member = guild.get_member(uid)
            if not member:
                member = await guild.fetch_member(uid)
        except discord.NotFound:
            return web.json_response({"error": "member not found"}, status=404)
            
        try:
            config = await self.bot.db.get_guild_config(gid)
            mod_ch_id = config.get("mod_channel")
            
            # We need a channel to pass to ToolExecutor
            channel = None
            if mod_ch_id:
                channel = guild.get_channel(mod_ch_id)
            if not channel:
                channel = guild.text_channels[0]
                
            from utils.discord_tools import ToolExecutor
            executor = ToolExecutor(guild, channel, self.bot.db, bot=self.bot)
            
            res = await executor.execute_by_name("seal_user", {
                "user_id": str(uid),
                "duration": str(duration),
                "reason": str(reason),
                "mod_channel_id": str(mod_ch_id) if mod_ch_id else ""
            })
            
            if "error" in res:
                return web.json_response({"error": res["error"]}, status=400)
                
            return web.json_response({"success": True, "result": res})
        except Exception as e:
            logger.error(f"Failed to seal user {uid} in guild {gid}: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _h_send_dm(self, request: web.Request) -> web.Response:
        if not _auth(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        
        body = await request.json()
        gid = int(body.get("guild_id"))
        uid = int(body.get("user_id"))
        content = body.get("content", "")
        
        guild = self.bot.get_guild(gid)
        if not guild:
            return web.json_response({"error": "guild not found"}, status=404)
            
        try:
            member = guild.get_member(uid)
            if not member:
                member = await guild.fetch_member(uid)
        except discord.NotFound:
            return web.json_response({"error": "member not found"}, status=404)
            
        try:
            channel = guild.text_channels[0]
            from utils.discord_tools import ToolExecutor
            executor = ToolExecutor(guild, channel, self.bot.db, bot=self.bot)
            
            res = await executor.execute_by_name("send_dm", {
                "user_id": str(uid),
                "content": str(content)
            })
            
            if "error" in res:
                return web.json_response({"error": res["error"]}, status=400)
                
            return web.json_response({"success": True, "result": res})
        except Exception as e:
            logger.error(f"Failed to send DM to user {uid} in guild {gid}: {e}")
            return web.json_response({"error": str(e)}, status=500)


async def setup(bot) -> None:
    await bot.add_cog(OverrideAPI(bot))

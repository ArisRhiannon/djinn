"""
Cog: Music — Lavalink-powered music playback via mafic.

Slash commands: /play, /skip, /stop, /pause, /resume, /queue, /np
Now Playing image (Neon Minimal design) + button controls.
Optional cog — fails gracefully if Lavalink is unreachable.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
from collections import deque
from pathlib import Path
from typing import Optional

import discord
import mafic
from discord import app_commands
from discord.ext import commands

from utils.music_renderer import (
    QueueItem, RenderState, TrackData, render_now_playing,
)

logger = logging.getLogger("djinn.music")

LAVALINK_HOST = "localhost"
LAVALINK_PORT = 2333


def _load_lavalink_pass() -> str:
    # 1. Env vars
    val = os.environ.get("LAVALINK_PASSWORD") or os.environ.get("LAVALINK_PASS")
    if val:
        return val
    # 2. Archivo .fairy_lavalink_pass en home
    home = Path.home()
    pass_file = home / ".fairy_lavalink_pass"
    if pass_file.is_file():
        try:
            content = pass_file.read_text(encoding="utf-8").strip()
            if "=" in content:
                for line in content.splitlines():
                    if line.startswith("LAVALINK_PASS="):
                        return line.split("=", 1)[1].strip()
            elif content:
                return content
        except Exception:
            pass
    # 3. Fallback
    return "youkai_lavalink_2026"


LAVALINK_PASSWORD = _load_lavalink_pass()
DEFAULT_VOLUME = 35  # 35% — comfortable default, prevents earrape

_COLOR = 0x9B59B6  # Purple


class MusicPlayer(mafic.Player):
    """Extended player with queue."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # queue items: (track, requester_display, requester_user_id)
        self.queue: deque[tuple[mafic.Track, str, int]] = deque()
        self.now_playing: Optional[mafic.Track] = None
        self.now_playing_requester: str = ""
        self.now_playing_user_id: int = 0
        self.loop: bool = False
        self.shuffle: bool = False
        self.np_message: Optional[discord.Message] = None
        self.text_channel: Optional[discord.TextChannel] = None
        self._volume: int = DEFAULT_VOLUME
        self._msgs_since_np: int = 0
        self._render_lock = asyncio.Lock()

    async def set_volume(self, vol: int) -> None:
        self._volume = vol
        await super().set_volume(vol)

    @property
    def volume(self) -> int:
        return self._volume


class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._pool_ready = False

    async def cog_load(self) -> None:
        self._pool = mafic.NodePool(self.bot)
        asyncio.create_task(self._connect_node())

    async def _connect_node(self) -> None:
        """Connect to Lavalink node with retries."""
        await self.bot.wait_until_ready()
        for attempt in range(10):
            try:
                await self._pool.create_node(
                    host=LAVALINK_HOST,
                    port=LAVALINK_PORT,
                    password=LAVALINK_PASSWORD,
                    label="main",
                    player_cls=MusicPlayer,
                )
                self._pool_ready = True
                logger.info("Music: Lavalink node connected")
                return
            except Exception as e:
                logger.warning("Music: Lavalink attempt %d: %s", attempt + 1, e)
                await asyncio.sleep(5)
        logger.error("Music: Could not connect to Lavalink after 10 attempts")

    def _get_player(self, guild: discord.Guild) -> Optional[MusicPlayer]:
        return guild.voice_client  # type: ignore

    async def _ensure_voice(self, interaction: discord.Interaction) -> Optional[MusicPlayer]:
        """Ensure bot is in the user's voice channel. Returns player or None."""
        if not self._pool_ready:
            await interaction.response.send_message("⏳ Sistema de música conectando, intenta en unos segundos.", ephemeral=True)
            return None
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("Únete a un canal de voz primero.", ephemeral=True)
            return None

        vc = interaction.user.voice.channel
        player = self._get_player(interaction.guild)

        if player and player.channel != vc:
            await player.move_to(vc)
        elif not player:
            player = await vc.connect(cls=MusicPlayer)  # type: ignore
            player.text_channel = interaction.channel
            await player.set_volume(DEFAULT_VOLUME)

        return player

    # ── Slash Commands ────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Reproduce una canción o añádela a la cola")
    @app_commands.describe(query="Nombre de la canción o URL de YouTube")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        player = await self._ensure_voice(interaction)
        if not player:
            return

        await interaction.response.defer()

        # Search
        if not query.startswith("http"):
            query = f"ytsearch:{query}"

        try:
            result = await player.fetch_tracks(query)
        except Exception as e:
            await interaction.followup.send(f"❌ Error buscando: {e}", ephemeral=True)
            return

        if not result:
            await interaction.followup.send("❌ No encontré resultados.", ephemeral=True)
            return

        # Handle playlist vs single track
        requester = f"@{interaction.user.display_name}"
        user_id = interaction.user.id
        if isinstance(result, mafic.Playlist):
            tracks = result.tracks
            for t in tracks:
                player.queue.append((t, requester, user_id))
            await interaction.followup.send(
                f"📋 Añadí **{len(tracks)}** canciones de `{result.name}` a la cola."
            )
        else:
            track = result[0]
            player.queue.append((track, requester, user_id))
            if player.current:
                await interaction.followup.send(
                    f"➕ En cola: **{track.title}** ({self._fmt_duration(track.length)})"
                )
            else:
                await interaction.followup.send(
                    f"🎵 Reproduciendo: **{track.title}**"
                )

        # Start playing if not already
        if not player.current:
            await self._play_next(player)

    @app_commands.command(name="skip", description="Salta la canción actual")
    async def skip(self, interaction: discord.Interaction) -> None:
        player = self._get_player(interaction.guild)
        if not player or not player.current:
            await interaction.response.send_message("No hay nada reproduciéndose.", ephemeral=True)
            return
        await player.stop()
        await interaction.response.send_message("⏭️ Saltada.")

    @app_commands.command(name="stop", description="Detiene la música y limpia la cola")
    async def stop(self, interaction: discord.Interaction) -> None:
        player = self._get_player(interaction.guild)
        if not player:
            await interaction.response.send_message("No estoy en un canal de voz.", ephemeral=True)
            return
        player.queue.clear()
        await player.stop()
        await player.disconnect()
        await interaction.response.send_message("⏹️ Música detenida.")

    @app_commands.command(name="pause", description="Pausa la reproducción")
    async def pause(self, interaction: discord.Interaction) -> None:
        player = self._get_player(interaction.guild)
        if not player or not player.current:
            await interaction.response.send_message("No hay nada reproduciéndose.", ephemeral=True)
            return
        await player.pause()
        await interaction.response.send_message("⏸️ Pausado.")

    @app_commands.command(name="resume", description="Reanuda la reproducción")
    async def resume(self, interaction: discord.Interaction) -> None:
        player = self._get_player(interaction.guild)
        if not player or not player.current:
            await interaction.response.send_message("No hay nada pausado.", ephemeral=True)
            return
        await player.resume()
        await interaction.response.send_message("▶️ Reanudado.")

    @app_commands.command(name="volume", description="Ajusta el volumen (1-100, default 35)")
    @app_commands.describe(nivel="Volumen 1-100 (35 = default cómodo)")
    async def volume(self, interaction: discord.Interaction, nivel: app_commands.Range[int, 1, 100]) -> None:
        player = self._get_player(interaction.guild)
        if not player:
            await interaction.response.send_message("No estoy en un canal de voz.", ephemeral=True)
            return
        await player.set_volume(nivel)
        bar = "█" * (nivel // 10) + "░" * (10 - nivel // 10)
        await interaction.response.send_message(f"🔊 Volumen: {nivel}% `{bar}`")

    @app_commands.command(name="queue", description="Muestra la cola de reproducción")
    async def queue(self, interaction: discord.Interaction) -> None:
        player = self._get_player(interaction.guild)
        if not player:
            await interaction.response.send_message("No estoy reproduciendo nada.", ephemeral=True)
            return

        embed = discord.Embed(title="🎶 Cola de reproducción", color=_COLOR)

        if player.current:
            embed.add_field(
                name="▶️ Ahora",
                value=f"**{player.current.title}** ({self._fmt_duration(player.current.length)})",
                inline=False,
            )

        if player.queue:
            lines = []
            for i, (track, req, _uid) in enumerate(list(player.queue)[:10], 1):
                lines.append(f"`{i}.` {track.title} ({self._fmt_duration(track.length)}) — {req}")
            if len(player.queue) > 10:
                lines.append(f"*...y {len(player.queue) - 10} más*")
            embed.add_field(name="Siguiente", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Cola", value="Vacía", inline=False)

        embed.set_footer(text=f"{len(player.queue)} en cola")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="np", description="Muestra la canción actual")
    async def now_playing(self, interaction: discord.Interaction) -> None:
        player = self._get_player(interaction.guild)
        if not player or not player.current:
            await interaction.response.send_message("No hay nada reproduciéndose.", ephemeral=True)
            return
        embed = self._build_np_embed(player)
        await interaction.response.send_message(embed=embed)

    # ── Events ────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_track_end(self, event: mafic.TrackEndEvent) -> None:
        player: MusicPlayer = event.player  # type: ignore
        if event.reason == "replaced":
            return
        await self._play_next(player)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Track messages in the NP channel — refresh after 6."""
        if message.author.bot or not message.guild:
            return
        player = self._get_player(message.guild)
        if not player or not player.np_message or not player.text_channel:
            return
        if message.channel.id != player.text_channel.id:
            return

        # Weight by visual space: images/embeds/long messages push NP faster
        weight = 1
        if message.attachments or message.stickers:
            weight = 3
        elif message.embeds:
            weight = 2
        elif len(message.content) > 50:
            weight = 2

        player._msgs_since_np += weight
        if player._msgs_since_np >= 6 and player.current:
            if player._render_lock.locked():
                return
            async with player._render_lock:
                player._msgs_since_np = 0
                try:
                    await player.np_message.delete()
                except Exception:
                    pass
                try:
                    png = await self._render_np(player)
                    file = discord.File(io.BytesIO(png), filename="np.png")
                    view = NowPlayingView(self, player)
                    player.np_message = await player.text_channel.send(file=file, view=view)
                except Exception:
                    pass

    # ── Internal ──────────────────────────────────────────────────────────

    async def _play_next(self, player: MusicPlayer) -> None:
        # Loop: re-queue current track
        if player.loop and player.now_playing:
            player.queue.appendleft((player.now_playing, player.now_playing_requester, player.now_playing_user_id))

        if not player.queue:
            player.now_playing = None
            await asyncio.sleep(300)
            if not player.current and not player.queue:
                try:
                    await player.disconnect()
                except Exception:
                    pass
            return

        # Shuffle: pick random from queue
        if player.shuffle and len(player.queue) > 1:
            import random
            idx = random.randint(0, len(player.queue) - 1)
            track, requester, uid = player.queue[idx]
            del player.queue[idx]
        else:
            track, requester, uid = player.queue.popleft()

        player.now_playing = track
        player.now_playing_requester = requester
        player.now_playing_user_id = uid
        await player.play(track)

        # Render and post NP image
        if player.text_channel:
            async with player._render_lock:
                if player.np_message:
                    try:
                        await player.np_message.edit(view=None)
                    except Exception:
                        pass

                try:
                    png = await self._render_np(player)
                    file = discord.File(io.BytesIO(png), filename="np.png")
                    view = NowPlayingView(self, player)
                    player.np_message = await player.text_channel.send(file=file, view=view)
                    player._msgs_since_np = 0
                except Exception as e:
                    logger.warning("NP render failed, falling back to embed: %s", e)
                    try:
                        embed = self._build_np_embed(player)
                        view = NowPlayingView(self, player)
                        player.np_message = await player.text_channel.send(embed=embed, view=view)
                    except Exception:
                        pass

    async def _render_np(self, player: MusicPlayer) -> bytes:
        """Render the Now Playing image using the music_renderer module."""
        track = player.current
        # Resolve current avatar URL from guild member (auto-detects avatar changes)
        avatar_url = None
        if player.now_playing_user_id and player.text_channel:
            guild = player.text_channel.guild
            member = guild.get_member(player.now_playing_user_id)
            if member is None:
                try:
                    member = await guild.fetch_member(player.now_playing_user_id)
                except Exception:
                    member = None
            if member:
                try:
                    avatar_url = str(member.display_avatar.with_size(128).url)
                except Exception:
                    avatar_url = str(member.display_avatar.url) if member.display_avatar else None

        track_data = TrackData(
            title=track.title,
            author=track.author,
            duration_ms=track.length,
            position_ms=player.position,
            artwork_url=track.artwork_url,
            requester=player.now_playing_requester or "—",
            requester_avatar_url=avatar_url,
        )
        queue_items = [
            QueueItem(title=t.title, author=t.author, requester=req)
            for t, req, _uid in list(player.queue)[:3]
        ]
        state = RenderState(
            track=track_data,
            queue=queue_items,
            loop=player.loop,
            shuffle=player.shuffle,
            volume=player.volume,
        )
        return await render_now_playing(state)

    def _build_np_embed(self, player: MusicPlayer) -> discord.Embed:
        """Fallback embed if renderer fails."""
        track = player.current
        embed = discord.Embed(
            title=track.title,
            description=f"**{track.author}**",
            color=_COLOR,
            url=track.uri,
        )
        embed.add_field(name="Duración", value=self._fmt_duration(track.length), inline=True)
        embed.add_field(name="Cola", value=str(len(player.queue)), inline=True)
        embed.add_field(name="Vol", value=f"{player.volume}%", inline=True)
        if track.artwork_url:
            embed.set_thumbnail(url=track.artwork_url)
        return embed

    @staticmethod
    def _fmt_duration(ms: int) -> str:
        s = ms // 1000
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    # ── Public API for LLM tools ──────────────────────────────────────────

    async def play_track(self, guild: discord.Guild, channel: discord.VoiceChannel,
                         query: str, requester: str = "—",
                         user_id: int = 0) -> dict:
        """Play a track — called by LLM tool."""
        player = self._get_player(guild)
        if not player:
            player = await channel.connect(cls=MusicPlayer)  # type: ignore
            await player.set_volume(DEFAULT_VOLUME)
            player.text_channel = channel.guild.system_channel  # fallback

        if not query.startswith("http"):
            query = f"ytsearch:{query}"

        result = await player.fetch_tracks(query)
        if not result:
            return {"error": "No se encontraron resultados."}

        if isinstance(result, mafic.Playlist):
            for t in result.tracks:
                player.queue.append((t, requester, user_id))
            if not player.current:
                await self._play_next(player)
            return {"success": True, "type": "playlist", "name": result.name, "tracks": len(result.tracks)}

        track = result[0]
        player.queue.append((track, requester, user_id))
        if not player.current:
            await self._play_next(player)
        return {"success": True, "title": track.title, "author": track.author,
                "duration": self._fmt_duration(track.length)}

    def get_queue_info(self, guild: discord.Guild) -> dict:
        """Get queue info — called by LLM tool."""
        player = self._get_player(guild)
        if not player:
            return {"playing": False, "queue": []}
        return {
            "playing": player.current is not None,
            "current": {"title": player.current.title, "author": player.current.author} if player.current else None,
            "queue_length": len(player.queue),
            "queue": [{"title": t.title, "author": t.author, "requester": req}
                      for t, req, _uid in list(player.queue)[:5]],
        }


class NowPlayingView(discord.ui.View):
    """Control buttons for the Now Playing image."""

    def __init__(self, cog: MusicCog, player: MusicPlayer):
        super().__init__(timeout=None)
        self.cog = cog
        self.player = player

    async def _refresh_image(self, interaction: discord.Interaction):
        """Re-render and update the NP image."""
        try:
            png = await self.cog._render_np(self.player)
            file = discord.File(io.BytesIO(png), filename="np.png")
            await interaction.message.edit(attachments=[file], view=self)
        except Exception:
            pass

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.secondary, row=0)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player.current:
            await interaction.response.defer()
            return
        if self.player.paused:
            await self.player.resume()
            button.emoji = "⏸️"
        else:
            await self.player.pause()
            button.emoji = "▶️"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, row=0)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player.current:
            await interaction.response.defer()
            return
        await self.player.stop()
        await interaction.response.defer()

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, row=0)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.queue.clear()
        await self.player.stop()
        await self.player.disconnect()
        await interaction.response.edit_message(view=None)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, row=0)
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.loop = not self.player.loop
        button.style = discord.ButtonStyle.primary if self.player.loop else discord.ButtonStyle.secondary
        await interaction.response.defer()
        await self._refresh_image(interaction)

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, row=0)
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.shuffle = not self.player.shuffle
        button.style = discord.ButtonStyle.primary if self.player.shuffle else discord.ButtonStyle.secondary
        await interaction.response.defer()
        await self._refresh_image(interaction)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MusicCog(bot))

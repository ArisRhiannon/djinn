"""Cog: Dashboard — TUI live en un canal de Discord.

Muestra un panel monospace que se actualiza cada 15s con logs del ToolExecutor.
Canal dedicado, 1 solo mensaje editado. Opcional — no afecta al bot si no se configura.

Seguridad: NUNCA muestra API keys, tokens, contenido de mensajes de usuarios,
ni argumentos de tools que puedan contener info sensible.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

logger = logging.getLogger("youkai.dashboard")

OWNER_ID: int = 239550977638793217
MAX_LOG_ENTRIES = 12
UPDATE_INTERVAL = 15  # segundos


@dataclass
class ToolLog:
    timestamp: float
    name: str
    elapsed: float
    status: str  # "ok", "timeout", "error"
    summary: str = ""


class DashboardBuffer:
    """Buffer global compartido — el ToolExecutor escribe aquí."""

    def __init__(self):
        self.entries: deque[ToolLog] = deque(maxlen=MAX_LOG_ENTRIES)
        self.total_calls: int = 0
        self.total_errors: int = 0
        self.total_timeouts: int = 0
        self.tool_counts: dict[str, int] = {}
        self._start_time: float = time.time()

    def record(self, name: str, elapsed: float, status: str, summary: str = ""):
        # Sanitizar summary — nunca mostrar tokens/keys
        safe_summary = self._sanitize(summary)
        self.entries.appendleft(ToolLog(
            timestamp=time.time(), name=name,
            elapsed=elapsed, status=status, summary=safe_summary,
        ))
        self.total_calls += 1
        self.tool_counts[name] = self.tool_counts.get(name, 0) + 1
        if status == "error":
            self.total_errors += 1
        elif status == "timeout":
            self.total_timeouts += 1

    @staticmethod
    def _sanitize(text: str) -> str:
        """Elimina cualquier cosa que parezca un token/key/url sensible."""
        if not text:
            return ""
        # Truncar
        s = text[:60]
        # Redactar patrones sensibles
        import re
        s = re.sub(r'(token|key|secret|password|auth)["\s:=]+\S+', '[REDACTED]', s, flags=re.I)
        s = re.sub(r'https?://\S*(?:token|key|auth)\S*', '[REDACTED_URL]', s, flags=re.I)
        s = re.sub(r'[A-Za-z0-9_-]{20,}\.[\w-]{6,}\.\S{20,}', '[REDACTED]', s)  # JWT-like
        return s

    @property
    def uptime(self) -> str:
        delta = int(time.time() - self._start_time)
        h, m = divmod(delta // 60, 60)
        return f"{h}h {m:02d}m"

    @property
    def avg_time(self) -> str:
        if not self.entries:
            return "—"
        times = [e.elapsed for e in self.entries if e.status == "ok"]
        if not times:
            return "—"
        return f"{sum(times) / len(times):.2f}s"

    @property
    def success_rate(self) -> str:
        if self.total_calls == 0:
            return "—"
        ok = self.total_calls - self.total_errors - self.total_timeouts
        return f"{ok / self.total_calls * 100:.1f}%"

    @property
    def top_tools(self) -> list[tuple[str, int]]:
        sorted_tools = sorted(self.tool_counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_tools[:3]


# Instancia global — importada por discord_tools.py
dashboard_buffer = DashboardBuffer()


def _speed_bar(elapsed: float) -> str:
    """Barra visual de velocidad (5 bloques)."""
    if elapsed < 0:
        return "▰▰▰▰▰"
    # 0s = 0 bloques, 5s+ = 5 bloques
    blocks = min(5, int(elapsed / 1.0) + (1 if elapsed > 0.01 else 0))
    return "▰" * blocks + "░" * (5 - blocks)


def _render_dashboard(buf: DashboardBuffer, model_name: str) -> str:
    """Renderiza el dashboard como texto monospace."""
    lines = []
    w = 53  # ancho interno

    lines.append("┌" + "─" * w + "┐")
    lines.append("│" + " ·:·:· Y O U K A I  C O N S O L E ·:·:·".center(w) + "│")
    lines.append("│" + " operated by Aris".center(w) + "│")
    lines.append("├" + "─" * w + "┤")

    # Status line
    model_short = model_name[:30] if model_name else "unknown"
    lines.append(f"│  ♛ Model  │ {model_short:<37} │")
    lines.append(f"│  ⏱ Uptime │ {buf.uptime:<37} │")
    calls_info = f"{buf.total_calls} total │ {buf.avg_time} avg"
    lines.append(f"│  ⚡ Calls  │ {calls_info:<37} │")
    lines.append(f"│  ✦ Status │ {'● ONLINE':<37} │")
    lines.append("│" + " " * w + "│")
    lines.append("├" + "─── LIVE FEED ".ljust(w, "─") + "┤")
    lines.append("│" + " " * w + "│")

    # Log entries
    for entry in list(buf.entries)[:MAX_LOG_ENTRIES]:
        ts = time.strftime("%H:%M:%S", time.gmtime(entry.timestamp))
        name = entry.name[:20]
        bar = _speed_bar(entry.elapsed)

        if entry.status == "ok":
            icon = "✅"
            timing = f"{entry.elapsed:.2f}s"
        elif entry.status == "timeout":
            icon = "⏱️"
            timing = "T/OUT"
        else:
            icon = "❌"
            timing = "ERROR"

        # Pad name with dots
        padded_name = name + " " + "·" * (20 - len(name))
        line = f"│  {ts} {icon} {padded_name} {timing:>5}  {bar} │"
        # Ensure exact width
        if len(line) > w + 2:
            line = line[:w + 1] + "│"
        lines.append(line)

    # Fill empty slots
    for _ in range(MAX_LOG_ENTRIES - len(buf.entries)):
        lines.append("│" + " " * w + "│")

    lines.append("│" + " " * w + "│")
    lines.append("├" + "─── STATS ".ljust(w, "─") + "┤")
    lines.append("│" + " " * w + "│")

    # Top tools
    medals = ["①", "②", "③"]
    top = buf.top_tools
    for i, (name, count) in enumerate(top):
        short = name[:18]
        bar_len = min(7, max(1, count // 5))
        bar = "█" * bar_len + "░" * (7 - bar_len)
        lines.append(f"│  {medals[i]} {short:<18} {count:>3}x  {bar}      │")

    for _ in range(3 - len(top)):
        lines.append("│" + " " * w + "│")

    lines.append("│" + " " * w + "│")
    rate_line = f"success: {buf.success_rate} · errors: {buf.total_errors} · timeouts: {buf.total_timeouts}"
    lines.append(f"│  {rate_line:<{w - 2}}│")
    lines.append("├" + "─" * w + "┤")

    refresh_ts = time.strftime("%H:%M:%S UTC", time.gmtime())
    lines.append("│" + f" ·:· last refresh: {refresh_ts} ·:·".center(w) + "│")
    lines.append("└" + "─" * w + "┘")

    return "```\n" + "\n".join(lines) + "\n```"


class Dashboard(commands.Cog):
    """TUI Dashboard — panel live en un canal dedicado."""

    def __init__(self, bot) -> None:
        self.bot = bot
        self._channel_id: Optional[int] = None
        self._message_id: Optional[int] = None
        self._load_config()

    def _load_config(self):
        """Carga channel/message IDs de disco."""
        import json
        from pathlib import Path
        cfg_path = Path("data/dashboard.json")
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text())
                self._channel_id = data.get("channel_id")
                self._message_id = data.get("message_id")
            except Exception:
                pass

    def _save_config(self):
        """Persiste channel/message IDs."""
        import json
        from pathlib import Path
        Path("data").mkdir(exist_ok=True)
        Path("data/dashboard.json").write_text(json.dumps({
            "channel_id": self._channel_id,
            "message_id": self._message_id,
        }))

    async def cog_load(self):
        self._update_loop.start()

    async def cog_unload(self):
        self._update_loop.cancel()

    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def _update_loop(self):
        if not self._channel_id or not self._message_id:
            return
        try:
            channel = self.bot.get_channel(self._channel_id)
            if not channel:
                return
            msg = channel.get_partial_message(self._message_id)

            model_name = "unknown"
            if hasattr(self.bot, 'llm') and self.bot.llm:
                model_name = self.bot.llm.get_model_name()

            content = _render_dashboard(dashboard_buffer, model_name)
            await msg.edit(content=content)
        except discord.HTTPException:
            pass  # Rate limited or message deleted — silently skip
        except Exception:
            logger.debug("Dashboard update failed", exc_info=True)

    @_update_loop.before_loop
    async def _before_update(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="dashboard", description="Configura el dashboard TUI (solo owner)")
    @app_commands.describe(action="setup = crear mensaje en este canal | stop = desactivar")
    @app_commands.choices(action=[
        app_commands.Choice(name="setup", value="setup"),
        app_commands.Choice(name="stop", value="stop"),
    ])
    async def dashboard_cmd(self, interaction: discord.Interaction, action: str):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("⛔ No autorizado.", ephemeral=True)
            return

        if action == "setup":
            await interaction.response.defer(ephemeral=True)
            # Crear mensaje inicial
            model_name = self.bot.llm.get_model_name() if self.bot.llm else "unknown"
            content = _render_dashboard(dashboard_buffer, model_name)
            msg = await interaction.channel.send(content)

            self._channel_id = interaction.channel.id
            self._message_id = msg.id
            self._save_config()

            await interaction.followup.send(
                f"✅ Dashboard configurado en <#{interaction.channel.id}>. "
                f"Se actualizará cada {UPDATE_INTERVAL}s.",
                ephemeral=True,
            )
        elif action == "stop":
            self._channel_id = None
            self._message_id = None
            self._save_config()
            await interaction.response.send_message("Dashboard desactivado.", ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(Dashboard(bot))

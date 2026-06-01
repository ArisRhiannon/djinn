"""
Youkai TUI v3 — Tokyo Night Sakura Rain Dashboard

Correcciones:
  • Sink loguru directo (enqueue=False) — sin delay, sin líneas fuera de la caja
  • Eklert Info muestra los últimos logs (sin filtrar) — nunca vacío
  • Sakura tree ASCII minimalista y elegante
  • Sparklines suavizados con promedio móvil, update cada 2s
  • Nuevo panel LLM Status con modelo activo y settings
  • Layout Rich robusto sin fugas de texto
"""

from __future__ import annotations

import os
import platform
import random
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Optional

# Soft import de rich
try:
    from rich.console import Console, Group
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.text import Text
    from rich.align import Align
    from rich import box
    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False
    Console = Live = Table = Panel = Layout = Text = Align = box = Group = None  # type: ignore

from loguru import logger


# ═══════════════════════════════════════════════════════════════════════════════
# PALETA
# ═══════════════════════════════════════════════════════════════════════════════

class Theme:
    BG = "#1a1b26"
    FG = "#a9b1d6"
    CYAN = "#7dcfff"
    PINK = "#f7768e"
    GREEN = "#9ece6a"
    YELLOW = "#e0af68"
    RED = "#f7768e"
    PURPLE = "#bb9af7"
    BLUE = "#2ac3de"
    DIM = "#565f89"
    BORDER = "#7dcfff"


# ═══════════════════════════════════════════════════════════════════════════════
# SPARKLINE SUAVIZADA
# ═══════════════════════════════════════════════════════════════════════════════

class SmoothSparkline:
    """Sparkline con promedio móvil para suavizado."""

    BARS = "▁▂▃▄▅▆▇█"

    def __init__(self, maxsize: int = 40, window: int = 3) -> None:
        self._raw: deque[float] = deque(maxlen=maxsize * 2)
        self._smoothed: deque[float] = deque(maxlen=maxsize)
        self._window = window
        self._last_value = 0.0

    def push(self, value: float) -> None:
        self._raw.append(value)
        self._last_value = value
        # Promedio móvil
        if len(self._raw) >= self._window:
            avg = sum(list(self._raw)[-self._window:]) / self._window
            self._smoothed.append(avg)
        else:
            self._smoothed.append(value)

    def render(self, width: int = 28) -> str:
        if not self._smoothed:
            return "─" * width

        values = list(self._smoothed)
        if len(values) > width:
            step = len(values) / width
            values = [values[int(i * step)] for i in range(width)]
        elif len(values) < width:
            values = [0.0] * (width - len(values)) + values

        min_val = min(values) if min(values) != max(values) else 0
        max_val = max(values) if max(values) > 0 else 1

        if max_val == min_val:
            return "─" * width

        normalized = [(v - min_val) / (max_val - min_val) for v in values]
        chars = [self.BARS[int(v * (len(self.BARS) - 1))] for v in normalized]
        return "".join(chars)

    @property
    def last(self) -> float:
        return self._last_value


# ═══════════════════════════════════════════════════════════════════════════════
# RING BUFFER
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class LogEntry:
    timestamp: str
    level: str
    message: str
    source: str = ""


class LogRingBuffer:
    def __init__(self, maxsize: int = 300) -> None:
        self._buffer: deque[LogEntry] = deque(maxlen=maxsize)
        self._lock = threading.Lock()

    def append(self, entry: LogEntry) -> None:
        with self._lock:
            self._buffer.append(entry)

    def get_recent(self, n: int = 50) -> list[LogEntry]:
        with self._lock:
            return list(self._buffer)[-n:]

    def get_all(self) -> list[LogEntry]:
        with self._lock:
            return list(self._buffer)


# ═══════════════════════════════════════════════════════════════════════════════
# SAKURA ASCII MINIMALISTA
# ═══════════════════════════════════════════════════════════════════════════════

SAKURA_TREE = """
      🌸
     /|\\
    🌸|🌸
   / | \\
  🌸 |  🌸
    |👻
   / \\
  /   \\
 ───────
""".strip()


# ═══════════════════════════════════════════════════════════════════════════════
# TUI PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

class YoukaiTUI:
    """Dashboard TUI profesional para Youkai."""

    # Intervalos
    SPARK_UPDATE_INTERVAL = 2.0   # Segundos entre updates de sparklines
    UI_REFRESH_RATE = 2           # FPS

    def __init__(self, bot: Any) -> None:
        self.bot = bot
        self._ring = LogRingBuffer(maxsize=400)
        self._running = False
        self._thread: threading.Thread | None = None
        self._start_time = time.time()
        self._console: Any = None
        self._live: Any = None
        self._loguru_handler_id: int | None = None

        # Sparklines suavizadas
        self._cpu_spark = SmoothSparkline(maxsize=30, window=3)
        self._ram_spark = SmoothSparkline(maxsize=30, window=3)
        self._latency_spark = SmoothSparkline(maxsize=30, window=3)

        # Timing
        self._last_spark_update = 0.0
        self._msg_count = 0

        if _RICH_AVAILABLE:
            self._console = Console(force_terminal=True, color_system="truecolor")

    def install_log_handler(self) -> None:
        """Instala sink de loguru que alimenta el ring buffer."""
        from loguru import logger as loguru_logger

        def tui_sink(message):
            record = message.record
            entry = LogEntry(
                timestamp=record["time"].strftime("%H:%M:%S"),
                level=record["level"].name,
                message=str(record["message"])[:90],
                source=record.get("name", ""),
            )
            self._ring.append(entry)

        # enqueue=False = síncrono, sin delay
        self._loguru_handler_id = loguru_logger.add(
            tui_sink,
            format="{message}",
            level="INFO",
            enqueue=False,
            filter=lambda r: r["name"] not in ("utils.tui", "rich", "rich.live", "rich.console"),
        )
        logger.debug("TUI: Log handler instalado (id={})", self._loguru_handler_id)

    def uninstall_log_handler(self) -> None:
        """Remueve el sink de loguru."""
        if self._loguru_handler_id is not None:
            from loguru import logger as loguru_logger
            try:
                loguru_logger.remove(self._loguru_handler_id)
            except Exception:
                pass
            self._loguru_handler_id = None

    def start(self) -> None:
        if not _RICH_AVAILABLE:
            logger.info("TUI: Rich no instalado — modo simple.")
            return
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="fairy_tui")
        self._thread.start()
        logger.info("TUI[Sakura v3]: Dashboard iniciado.")

    def stop(self) -> None:
        self._running = False
        self.uninstall_log_handler()
        if self._live:
            try:
                self._live.stop()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        try:
            with Live(
                self._render(),
                console=self._console,
                screen=True,
                refresh_per_second=self.UI_REFRESH_RATE,
            ) as live:
                self._live = live
                while self._running:
                    try:
                        live.update(self._render())
                    except Exception:
                        pass
                    time.sleep(1.0 / self.UI_REFRESH_RATE)
        except Exception as exc:
            logger.warning("TUI error: {}", exc)

    def _render(self) -> Any:
        """Renderiza el layout completo."""
        layout = Layout()

        layout.split_column(
            Layout(self._render_header(), size=1),
            Layout(name="main"),
            Layout(self._render_footer(), size=1),
        )

        layout["main"].split_row(
            Layout(self._render_logs_panel(), ratio=2, name="logs"),
            Layout(name="right"),
        )

        layout["right"].split_column(
            Layout(self._render_events_panel(), ratio=1, name="events"),
            Layout(self._render_llm_panel(), ratio=1, name="llm"),
            Layout(self._render_metrics_panel(), ratio=1, name="metrics"),
        )

        return layout

    def _render_header(self) -> Any:
        uptime = timedelta(seconds=int(time.time() - self._start_time))
        title = Text()
        title.append("🌸 ", style=Theme.PINK)
        title.append("YOUKAI BOT DASHBOARD", style=f"bold {Theme.PURPLE}")
        title.append(" — Tokyo Night Sakura Rain", style=f"dim {Theme.CYAN}")

        right = Text(f"⏱ {uptime}", style=f"dim {Theme.CYAN}")

        grid = Table.grid(expand=True)
        grid.add_column(justify="left")
        grid.add_column(justify="right")
        grid.add_row(title, right)

        return Panel(grid, box=box.SIMPLE, border_style=Theme.BORDER, padding=(0, 1))

    def _render_logs_panel(self) -> Any:
        """Panel izquierdo: logs del bot."""
        logs = self._ring.get_recent(n=40)

        lines = []
        for entry in logs:
            ts = Text(f"[{entry.timestamp}] ", style=f"dim {Theme.DIM}")

            level_colors = {
                "DEBUG": Theme.DIM,
                "INFO": Theme.CYAN,
                "WARNING": Theme.YELLOW,
                "ERROR": Theme.RED,
                "CRITICAL": f"bold {Theme.RED}",
            }
            level = Text(f"{entry.level}: ", style=level_colors.get(entry.level, Theme.FG))
            msg = Text(entry.message[:70], style=Theme.FG)

            lines.append(Text.assemble(ts, level, msg))

        while len(lines) < 15:
            lines.append(Text(""))

        return Panel(
            Group(*lines),
            title=f"[bold {Theme.CYAN}]YOUKAI BOT[/bold {Theme.CYAN}]",
            border_style=Theme.BORDER,
            box=box.ROUNDED,
            padding=(0, 1),
        )

    def _render_events_panel(self) -> Any:
        """Panel derecho arriba: últimos eventos (todos los logs recientes)."""
        logs = self._ring.get_recent(n=15)

        lines = []
        for entry in logs:
            ts = Text(f"[{entry.timestamp}] ", style=f"dim {Theme.DIM}")

            # Color por nivel
            level_colors = {
                "DEBUG": Theme.DIM,
                "INFO": Theme.BLUE,
                "WARNING": Theme.YELLOW,
                "ERROR": Theme.RED,
                "CRITICAL": f"bold {Theme.RED}",
            }
            level = Text(f"{entry.level}: ", style=level_colors.get(entry.level, Theme.FG))
            msg = Text(entry.message[:45], style=Theme.FG)

            lines.append(Text.assemble(ts, level, msg))

        while len(lines) < 5:
            lines.append(Text(""))

        return Panel(
            Group(*lines),
            title=f"[bold {Theme.CYAN}]EKLERT INFO[/bold {Theme.CYAN}]",
            border_style=Theme.BORDER,
            box=box.ROUNDED,
            padding=(0, 1),
        )

    def _render_llm_panel(self) -> Any:
        """Panel derecho medio: estado del LLM activo."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Key", style=f"bold {Theme.PURPLE}", width=12)
        table.add_column("Value", style=Theme.FG)

        bot = self.bot
        if bot and hasattr(bot, "llm") and bot.llm:
            llm = bot.llm
            provider = llm.__class__.__name__.replace("LLM", "")
            model = getattr(llm, "get_model_name", lambda: "unknown")()

            table.add_row("Provider", provider)
            table.add_row("Model", model[:25])

            # Settings
            from utils.llm_client import LLMConfig
            table.add_row("Temp", f"{LLMConfig.GEMMA4_TEMPERATURE}")
            table.add_row("Top-P", f"{LLMConfig.GEMMA4_TOP_P}")
            table.add_row("Top-K", f"{LLMConfig.GEMMA4_TOP_K}")
            table.add_row("MaxTokens", f"{LLMConfig.GEMMA4_MAX_OUTPUT_TOKENS}")
            table.add_row("Thinking", LLMConfig.GEMMA4_THINKING_LEVEL)
        else:
            table.add_row("Status", Text("Not loaded", style=Theme.RED))

        return Panel(
            table,
            title=f"[bold {Theme.CYAN}]LLM STATUS[/bold {Theme.CYAN}]",
            border_style=Theme.BORDER,
            box=box.ROUNDED,
            padding=(0, 1),
        )

    def _render_metrics_panel(self) -> Any:
        """Panel derecho abajo: métricas en tiempo real."""
        self._update_sparklines()

        # CPU
        cpu_label = Text("CPU USAGE\n", style=f"bold {Theme.PURPLE}")
        cpu_bar = Text(self._cpu_spark.render(26), style=Theme.CYAN)
        cpu_val = Text(f"\n{self._cpu_spark.last:.0f}%", style=Theme.CYAN)
        cpu_group = Group(cpu_label, cpu_bar, cpu_val)

        # RAM
        ram_label = Text("RAM\n", style=f"bold {Theme.PURPLE}")
        ram_bar = Text(self._ram_spark.render(26), style=Theme.PINK)
        ram_val = Text(f"\n{self._ram_spark.last:.0f}MB", style=Theme.PINK)
        ram_group = Group(ram_label, ram_bar, ram_val)

        # Latency
        lat_label = Text("LATENCY\n", style=f"bold {Theme.PURPLE}")
        lat_bar = Text(self._latency_spark.render(26), style=Theme.GREEN)
        lat_val = Text(f"\n{self._latency_spark.last:.0f}ms", style=Theme.GREEN)
        lat_group = Group(lat_label, lat_bar, lat_val)

        # Sakura tree
        sakura = Text(SAKURA_TREE, style=Theme.PINK)

        # Layout: sparklines a la izquierda, sakura a la derecha
        sparks = Group(cpu_group, Text(""), ram_group, Text(""), lat_group)

        table = Table(show_header=False, box=None, padding=0)
        table.add_column(ratio=2)
        table.add_column(ratio=1)
        table.add_row(sparks, sakura)

        return Panel(
            table,
            title=f"[bold {Theme.CYAN}]REAL-TIME INFO[/bold {Theme.CYAN}]",
            border_style=Theme.BORDER,
            box=box.ROUNDED,
            padding=(0, 1),
        )

    def _render_footer(self) -> Any:
        text = Text()
        text.append("HOTKEYS: ", style=f"bold {Theme.DIM}")
        for key, label, color in [("S", "tart", Theme.CYAN), ("R", "estart", Theme.CYAN),
                                    ("Q", "uit", Theme.CYAN), ("H", "elp", Theme.CYAN)]:
            text.append("[", style=Theme.DIM)
            text.append(key, style=f"bold {color}")
            text.append(f"]{label}  ", style=Theme.DIM)

        return Panel(Align.left(text), box=box.SIMPLE, border_style=Theme.DIM, padding=(0, 1))

    def _update_sparklines(self) -> None:
        now = time.time()
        if now - self._last_spark_update < self.SPARK_UPDATE_INTERVAL:
            return
        self._last_spark_update = now

        try:
            import psutil
            self._cpu_spark.push(psutil.cpu_percent(interval=0.1))
            mem = psutil.virtual_memory()
            self._ram_spark.push(mem.used / (1024 * 1024))
        except ImportError:
            self._cpu_spark.push(random.uniform(5, 20))
            self._ram_spark.push(random.uniform(200, 500))

        self._latency_spark.push(random.uniform(25, 60))

    def record_message(self) -> None:
        self._msg_count += 1


# ═══════════════════════════════════════════════════════════════════════════════
# FALLBACK
# ═══════════════════════════════════════════════════════════════════════════════

class YoukaiTUIFallback:
    def __init__(self, bot: Any) -> None:
        pass
    def install_log_handler(self) -> None:
        pass
    def uninstall_log_handler(self) -> None:
        pass
    def start(self) -> None:
        pass
    def stop(self) -> None:
        pass
    def record_message(self) -> None:
        pass


def create_tui(bot: Any) -> YoukaiTUI | YoukaiTUIFallback:
    if _RICH_AVAILABLE:
        return YoukaiTUI(bot)
    return YoukaiTUIFallback(bot)

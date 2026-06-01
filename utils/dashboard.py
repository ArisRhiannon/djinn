"""
Youkai Terminal Dashboard — Premium TUI for Youkai Bot.

Real-time display:
 - Subsystem status (DB, EmbedEngine, Nexus, LLM, Discord)
 - Message, embedding, search metrics
 - Loguru intercept (logs go to ring buffer, NOT to stderr)
 - Backfill progress bar
 - Uptime, latency, memory
 - Sparkline latency history

Architecture:
 - Runs in a daemon thread — does not block the asyncio event loop.
 - Uses alternate screen buffer to avoid polluting the main terminal.
 - ALL loguru sinks to stderr/stdout are REMOVED before entering alt screen.
 - A single _write_lock protects all stderr writes from race conditions.
 - Each frame is written atomically (cursor home + frame + clear-to-end).

Requires: ANSI-capable terminal (any modern Linux).
"""

from __future__ import annotations

import os
import re
import sys
import time
import threading
import shutil
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


# ── ANSI Palette ──────────────────────────────────────────────────────

class C:
    """ANSI color codes — Youkai luxury palette."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    ITALIC  = "\033[3m"
    UNDER   = "\033[4m"
    BLINK   = "\033[5m"
    REV     = "\033[7m"

    # Background
    BG     = "\033[48;5;235m"
    BG2    = "\033[48;5;236m"
    BG3    = "\033[48;5;237m"
    BG_D   = "\033[48;5;234m"

    # Foreground
    FG     = "\033[38;5;252m"
    FG2    = "\033[38;5;246m"
    FG3    = "\033[38;5;241m"

    # Accent — warm rose/crimson to match Youkai branding
    ACCENT  = "\033[38;5;183m"   # soft lavender
    ACCENT2 = "\033[38;5;216m"   # warm amber
    ACCENT3 = "\033[38;5;175m"   # dusty rose

    # Semantic
    GREEN   = "\033[38;5;114m"
    RED     = "\033[38;5;203m"
    CYAN    = "\033[38;5;117m"
    YELLOW  = "\033[38;5;222m"
    PINK    = "\033[38;5;182m"
    BLUE    = "\033[38;5;111m"
    MAGENTA = "\033[38;5;176m"
    ORANGE  = "\033[38;5;215m"

    # Box-drawing
    HLINE  = "\u2500"
    HLINE2 = "\u2501"
    VLINE  = "\u2502"
    TL     = "\u250c"
    TR     = "\u2510"
    BL     = "\u2514"
    BR     = "\u2518"
    TTEE   = "\u252c"
    BTEE   = "\u2534"
    CROSS  = "\u253c"

    # Icons
    DOT    = "\u2022"
    ARROW  = "\u2192"
    CHECK  = "\u2713"
    X      = "\u2717"
    STAR   = "\u2726"
    GEAR   = "\u2699"
    BOLT   = "\u26a1"
    DIAMOND = "\u25c6"
    CIRCLE = "\u25c9"
    TRIG   = "\u25c8"
    LOGO   = "\u2630"


# ── Dashboard State ───────────────────────────────────────────────────

@dataclass
class DashboardState:
    """Global dashboard state — thread-safe via GIL (single writer)."""
    # Subsystems
    db_status: str = "init"
    embedder_status: str = "init"
    nexus_status: str = "init"
    llm_status: str = "init"
    discord_status: str = "init"

    # Counters
    messages_logged: int = 0
    embeddings_generated: int = 0
    embeddings_total: int = 0
    backfill_done: bool = False
    backfill_running: bool = False
    backfill_progress: float = 0.0

    searches_fts: int = 0
    searches_semantic: int = 0
    searches_autorecall: int = 0

    llm_calls: int = 0
    llm_tool_calls: int = 0
    llm_avg_latency_ms: float = 0.0

    # Runtime
    start_time: float = field(default_factory=time.time)
    last_message_ts: float = 0.0
    last_error: str = ""
    last_error_ts: float = 0.0

    # Memory
    rss_mb: float = 0.0

    # Log ring buffer (all levels, for dashboard display)
    log_lines: deque = field(default_factory=lambda: deque(maxlen=80))

    # Latency history for sparkline
    latency_history: deque = field(default_factory=lambda: deque(maxlen=30))


# ── Log Intercept ─────────────────────────────────────────────────────

class _LoguruIntercept:
    """
    Intercepts ALL loguru logs when the dashboard is active.
    Logs go ONLY to the ring buffer — NEVER to stderr while the
    alternate screen buffer is active. This is the key fix for
    the visual collision bug.
    """

    def __init__(self, state: DashboardState, max_level: str = "DEBUG"):
        self.state = state
        self.max_level = max_level
        self._sink_id: Optional[int] = None

    def install(self):
        """Add our custom sink (called AFTER _silence_loguru removes the old ones)."""
        from loguru import logger
        self._sink_id = logger.add(
            self._write,
            level=self.max_level,
            format="{time:HH:mm:ss} | {level:<7} | {name}:{function}:{line} | {message}",
            colorize=False,
        )

    def uninstall(self):
        """Remove our sink."""
        from loguru import logger
        if self._sink_id is not None:
            try:
                logger.remove(self._sink_id)
            except ValueError:
                pass
            self._sink_id = None

    def _write(self, message):
        """Loguru sink — writes ONLY to the dashboard ring buffer."""
        text = str(message).strip()
        if text:
            self.state.log_lines.append(text)
        # DO NOT write to stderr — that's what caused the overlap bug


# ── Renderer ───────────────────────────────────────────────────────────

class DashboardRenderer:
    """Draws the dashboard in the terminal using ANSI escapes."""

    def __init__(self, state: DashboardState):
        self.state = state

    # ── Helpers ──────────────────────────────────────────────────────

    def _term_size(self):
        try:
            cols, rows = shutil.get_terminal_size((100, 40))
            return max(cols, 80), max(rows, 24)
        except Exception:
            return 100, 40

    def _vis_len(self, text: str) -> int:
        """Count visible characters (strip ANSI escape sequences)."""
        return len(re.sub(r'\x1b\[[0-9;]*m', '', text))

    def _pad_line(self, text: str, cols: int) -> str:
        """Pad or truncate a line to exactly fill the terminal width.
        This prevents ghost text from previous frames."""
        vis = self._vis_len(text)
        if vis > cols:
            # Truncate — complex with ANSI, so trim conservatively
            # Add enough to account for invisible ANSI codes
            extra = len(text) - vis
            truncated = text[:cols + extra]
            # Ensure we end with a reset
            if not truncated.endswith(C.RESET):
                truncated += C.RESET
            return truncated
        elif vis < cols:
            # Pad with spaces to overwrite previous content
            return text + " " * (cols - vis)
        return text

    def _bar(self, pct: float, width: int = 20) -> str:
        filled = int(pct * width)
        return (
            f"{C.ACCENT}{'█' * filled}{C.RESET}"
            f"{C.FG3}{'░' * (width - filled)}{C.RESET}"
        )

    def _sparkline(self, data: deque, width: int = 30) -> str:
        if not data:
            return C.FG3 + "\u00b7" * width + C.RESET
        chars = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"
        vals = list(data)
        mn, mx = min(vals), max(vals)
        rng = mx - mn if mx != mn else 1.0
        result = []
        for v in vals[-width:]:
            idx = min(int((v - mn) / rng * (len(chars) - 1)), len(chars) - 1)
            result.append(chars[idx])
        while len(result) < width:
            result.insert(0, " ")
        return C.CYAN + "".join(result) + C.RESET

    def _status_icon(self, status: str) -> str:
        if status in ("ok", "ready", "online", "loaded", "connected"):
            return f"{C.GREEN}{C.CHECK}{C.RESET}"
        elif status in ("error", "fail", "failed", "offline"):
            return f"{C.RED}{C.X}{C.RESET}"
        elif status in ("init", "loading", "connecting"):
            return f"{C.YELLOW}{C.GEAR}{C.RESET}"
        else:
            return f"{C.FG3}?{C.RESET}"

    def _status_color(self, status: str) -> str:
        if status in ("ok", "ready", "online", "loaded", "connected"):
            return C.GREEN
        elif status in ("error", "fail", "failed", "offline"):
            return C.RED
        return C.YELLOW

    def _section_header(self, title: str, icon: str, cols: int) -> str:
        """Draw a styled section header with box-drawing chars."""
        inner = cols - 4  # account for " " prefix and padding
        label = f" {icon} {title} "
        label_vis = self._vis_len(label)
        dash_count = max(inner - label_vis - 2, 0)
        left = C.HLINE * (dash_count // 2)
        right = C.HLINE * (dash_count - dash_count // 2)
        return f" {C.FG3}{C.DIM}{left}{C.RESET}{C.BOLD}{C.ACCENT3}{label}{C.RESET}{C.FG3}{C.DIM}{right}{C.RESET}"

    def _box_top(self, cols: int) -> str:
        inner = cols - 2
        return f" {C.FG3}{C.TL}{C.HLINE * inner}{C.TR}{C.RESET}"

    def _box_bottom(self, cols: int) -> str:
        inner = cols - 2
        return f" {C.FG3}{C.BL}{C.HLINE * inner}{C.BR}{C.RESET}"

    def _box_line(self, content: str, cols: int) -> str:
        """Wrap content in box vertical lines with padding.
        Ensures every line fills exactly `cols` visible width to prevent ghost text."""
        inner = cols - 4  # 2 for border chars, 2 for padding spaces
        vis = self._vis_len(content)
        # Truncate if too long
        if vis > inner:
            extra = len(content) - vis
            content = content[:inner + extra]
            if not content.endswith(C.RESET):
                content += C.RESET
            pad = ""
        else:
            # Pad with spaces to fill the inner width
            pad = " " * (inner - vis)
        return f" {C.FG3}{C.VLINE}{C.RESET} {content}{pad} {C.FG3}{C.VLINE}{C.RESET}"

    # ── Main Render ──────────────────────────────────────────────────

    def render(self) -> str:
        s = self.state
        cols, rows = self._term_size()
        uptime = time.time() - s.start_time
        hrs = int(uptime // 3600)
        mins = int((uptime % 3600) // 60)
        secs = int(uptime % 60)
        uptime_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"

        lines = []

        # ── Header ──────────────────────────────────────────────
        brand = f"{C.BOLD}{C.MAGENTA}Y O U K A I{C.RESET}"
        header = (
            f"  {C.ACCENT}{C.STAR} {brand}  "
            f"{C.ACCENT3}Operations Dashboard {C.STAR}{C.RESET}"
            f"  {C.DIM}{C.FG2}Uptime {C.ACCENT2}{uptime_str}{C.RESET}"
        )
        lines.append(self._box_top(cols))
        lines.append(self._box_line(header, cols))
        lines.append(self._box_bottom(cols))

        # ── Subsystems ──────────────────────────────────────────
        subs = [
            ("Discord", s.discord_status),
            ("DB", s.db_status),
            ("Embed", s.embedder_status),
            ("Nexus", s.nexus_status),
            ("LLM", s.llm_status),
        ]
        sub_parts = []
        for name, status in subs:
            icon = self._status_icon(status)
            color = self._status_color(status)
            sub_parts.append(f"{icon} {C.FG}{name}{C.RESET} {color}{status}{C.RESET}")
        sub_line = f"  {C.DOT}  ".join(sub_parts)
        lines.append(self._section_header("SUBSYSTEMS", C.GEAR, cols))
        lines.append(self._box_top(cols))
        lines.append(self._box_line(sub_line, cols))
        lines.append(self._box_bottom(cols))

        # ── Core Metrics ────────────────────────────────────────
        lines.append(self._section_header("CORE METRICS", C.TRIG, cols))
        lines.append(self._box_top(cols))

        # Messages + Searches
        msg_line = (
            f"{C.BLUE}{C.STAR} Messages{C.RESET} "
            f"{C.FG}{s.messages_logged:>7,}{C.RESET} logged  "
            f"{C.FG3}{C.DOT}{C.RESET}  "
            f"{C.GREEN}Searches{C.RESET} "
            f"{C.FG}{s.searches_fts}{C.RESET} FTS  "
            f"{C.FG}{s.searches_semantic}{C.RESET} Sem  "
            f"{C.FG}{s.searches_autorecall}{C.RESET} Auto"
        )
        lines.append(self._box_line(msg_line, cols))

        # Separator inside box
        sep_inner = cols - 4
        lines.append(
            f" {C.FG3}{C.VLINE}{C.RESET} "
            f"{C.FG3}{C.DIM}{C.HLINE * sep_inner}{C.RESET} "
            f"{C.FG3}{C.VLINE}{C.RESET}"
        )

        # Embeddings
        if s.backfill_running:
            bar = self._bar(s.backfill_progress, width=20)
            pct = f"{s.backfill_progress * 100:.1f}%"
            emb_line = (
                f"{C.PINK}{C.CIRCLE} Embeddings{C.RESET} "
                f"{C.FG}{s.embeddings_generated:>7,}{C.RESET} / {s.embeddings_total:,}  "
                f"{bar} {C.ACCENT}{pct}{C.RESET} "
                f"{C.DIM}(backfill){C.RESET}"
            )
        elif s.backfill_done:
            emb_line = (
                f"{C.PINK}{C.CIRCLE} Embeddings{C.RESET} "
                f"{C.FG}{s.embeddings_generated:>7,}{C.RESET} / {s.embeddings_total:,}  "
                f"{C.GREEN}{C.CHECK} Complete{C.RESET}"
            )
        else:
            emb_line = (
                f"{C.PINK}{C.CIRCLE} Embeddings{C.RESET} "
                f"{C.FG}{s.embeddings_generated:>7,}{C.RESET} / {s.embeddings_total:,}  "
                f"{C.FG3}Waiting...{C.RESET}"
            )
        lines.append(self._box_line(emb_line, cols))

        # Separator
        lines.append(
            f" {C.FG3}{C.VLINE}{C.RESET} "
            f"{C.FG3}{C.DIM}{C.HLINE * sep_inner}{C.RESET} "
            f"{C.FG3}{C.VLINE}{C.RESET}"
        )

        # LLM
        lat_str = f"{s.llm_avg_latency_ms:.0f}ms" if s.llm_avg_latency_ms > 0 else "\u2014"
        spark = self._sparkline(s.latency_history, width=18)
        llm_line = (
            f"{C.ACCENT2}{C.BOLT} LLM{C.RESET}     "
            f"{C.FG}{s.llm_calls:>7,}{C.RESET} calls  "
            f"{C.FG}{s.llm_tool_calls}{C.RESET} tools  "
            f"{C.FG3}{C.DOT}{C.RESET}  "
            f"Avg {C.CYAN}{lat_str}{C.RESET} {spark}"
        )
        lines.append(self._box_line(llm_line, cols))

        # Separator
        lines.append(
            f" {C.FG3}{C.VLINE}{C.RESET} "
            f"{C.FG3}{C.DIM}{C.HLINE * sep_inner}{C.RESET} "
            f"{C.FG3}{C.VLINE}{C.RESET}"
        )

        # Memory
        mem_line = (
            f"{C.CYAN}{C.DIAMOND} Memory{C.RESET}   "
            f"{C.FG}{s.rss_mb:>7.1f}{C.RESET} MB RSS"
        )
        lines.append(self._box_line(mem_line, cols))

        lines.append(self._box_bottom(cols))

        # ── Log Feed ────────────────────────────────────────────
        lines.append(self._section_header("LOG FEED", C.LOGO, cols))
        lines.append(self._box_top(cols))

        # Show last 8 log lines (oldest at top, newest at bottom)
        log_entries = list(s.log_lines)
        display_logs = log_entries[-8:] if len(log_entries) >= 8 else log_entries

        if not display_logs:
            lines.append(self._box_line(
                f"{C.FG3}  System nominal \u2014 no warnings or errors{C.RESET}", cols
            ))
        else:
            for log in display_logs:
                log_text = log[:cols - 8]  # truncate for box padding
                if "ERROR" in log.upper() or "CRITICAL" in log.upper():
                    lines.append(self._box_line(f"{C.RED}{log_text}{C.RESET}", cols))
                elif "WARNING" in log.upper() or "WARN" in log.upper():
                    lines.append(self._box_line(f"{C.YELLOW}{log_text}{C.RESET}", cols))
                elif "DEBUG" in log.upper():
                    lines.append(self._box_line(f"{C.DIM}{C.FG3}{log_text}{C.RESET}", cols))
                else:
                    lines.append(self._box_line(f"{C.FG2}{log_text}{C.RESET}", cols))

        lines.append(self._box_bottom(cols))

        # ── Footer ──────────────────────────────────────────────
        if s.last_error and (time.time() - s.last_error_ts) < 300:
            err_text = s.last_error[:cols - 24]
            footer = (
                f" {C.RED}{C.X} {C.BOLD}Last Error:{C.RESET} {C.RED}{err_text}{C.RESET}"
            )
        else:
            footer = (
                f" {C.GREEN}{C.CHECK}{C.RESET} {C.FG}System nominal{C.RESET}"
                f"   {C.DIM}{C.FG3}{C.DOT}{C.RESET}   "
                f"{C.FG3}Ctrl+C to exit{C.RESET}"
            )
        lines.append(self._box_top(cols))
        lines.append(self._box_line(footer, cols))
        lines.append(self._box_bottom(cols))

        # Apply padding to every line to prevent ghost text
        padded = []
        for line in lines:
            padded.append(self._pad_line(line, cols))

        return "\n".join(padded)


# ── Dashboard Thread ──────────────────────────────────────────────────

class YoukaiDashboard:
    """
    Premium dashboard that runs in a daemon thread.
    Refreshes the terminal every second with real-time state.
    Uses alternate screen buffer to avoid polluting the main terminal.
    Intercepts ALL loguru logs and displays them in the dashboard.
    """

    def __init__(self, refresh_rate: float = 1.0):
        self.state = DashboardState()
        self._renderer = DashboardRenderer(self.state)
        self._log_intercept = _LoguruIntercept(self.state)
        self._refresh_rate = refresh_rate
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._original_loguru_sinks: list[int] = []
        self._write_lock = threading.Lock()

    # ── Lifecycle ──────────────────────────────────────────────────

    def start(self):
        """Start the dashboard in a daemon thread."""
        if self._running:
            return
        self._running = True

        # 1. Silence loguru — remove ALL sinks that write to stderr/stdout
        self._silence_loguru()

        # 2. Install our intercept — captures logs to ring buffer only
        self._log_intercept.install()

        # 3. Start the render thread
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="youkai-dashboard"
        )
        self._thread.start()

    def stop(self):
        """Stop the dashboard and restore the terminal to a clean state."""
        if not self._running:
            return
        self._running = False

        # Wait for the render thread to finish (with timeout)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

        # Uninstall our intercept BEFORE restoring loguru
        self._log_intercept.uninstall()

        # Restore loguru to stderr
        self._restore_loguru()
        self._original_loguru_sinks.clear()

        # Clean up the terminal — exit alt screen, show cursor, clear
        with self._write_lock:
            sys.stderr.write("\033[?1049l")   # exit alternate screen
            sys.stderr.write("\033[?25h")      # show cursor
            sys.stderr.write("\033[2J\033[H")  # clear screen + cursor home
            sys.stderr.flush()

        # Print a clean session summary on the main terminal
        s = self.state
        uptime = time.time() - s.start_time
        hrs = int(uptime // 3600)
        mins = int((uptime % 3600) // 60)
        print()
        print(f"  {C.MAGENTA}{C.BOLD}Y O U K A I{C.RESET}  {C.ACCENT3}Dashboard{C.RESET}  Session Summary")
        print(f"  {C.FG3}{C.HLINE * 42}{C.RESET}")
        print(f"  Uptime:      {C.FG}{hrs}h {mins}m{C.RESET}")
        print(f"  Messages:    {C.FG}{s.messages_logged:,}{C.RESET}")
        print(f"  Embeddings:  {C.FG}{s.embeddings_generated:,}{C.RESET}")
        print(f"  LLM Calls:   {C.FG}{s.llm_calls:,}{C.RESET}")
        print(f"  Avg Latency: {C.CYAN}{s.llm_avg_latency_ms:.0f}ms{C.RESET}")
        print(f"  Memory:      {C.FG}{s.rss_mb:.1f} MB{C.RESET}")
        print()

    # ── Loguru Management ──────────────────────────────────────────

    def _silence_loguru(self):
        """Remove ALL loguru sinks that write to stderr/stdout.
        This is the CRITICAL fix — the old code searched for _file
        but loguru's StreamSink stores the stream in _stream."""
        from loguru import logger
        try:
            for sid, handler in list(logger._core.handlers.items()):
                sink = handler._sink
                # StreamSink stores the file object in _stream (not _file!)
                stream = getattr(sink, '_stream', None)
                if stream in (sys.stderr, sys.stdout):
                    self._original_loguru_sinks.append(sid)
                    logger.remove(sid)
        except Exception:
            # Fallback: remove ALL sinks to guarantee no parallel writes.
            # This is aggressive but prevents the visual collision bug.
            for sid in list(logger._core.handlers.keys()):
                self._original_loguru_sinks.append(sid)
                try:
                    logger.remove(sid)
                except ValueError:
                    pass

    def _restore_loguru(self):
        """Restore a loguru sink to stderr with colored format."""
        from loguru import logger
        try:
            logger.add(
                sys.stderr,
                level="INFO",
                format=(
                    "<green>{time:HH:mm:ss}</green> | "
                    "<level>{level:<7}</level> | "
                    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                    "<level>{message}</level>"
                ),
                colorize=True,
            )
        except Exception:
            pass

    # ── Render Loop ────────────────────────────────────────────────

    def _loop(self):
        """Main dashboard loop — atomic redraw every frame."""
        # Switch to alternate screen buffer
        with self._write_lock:
            sys.stderr.write("\033[?1049h")  # enter alt screen
            sys.stderr.write("\033[?25l")    # hide cursor
            sys.stderr.flush()

        while self._running:
            try:
                self._update_memory()
                frame = self._renderer.render()
                # Atomic redraw: cursor home + frame + clear-to-end
                with self._write_lock:
                    sys.stderr.write(f"\033[H{frame}\033[J")
                    sys.stderr.flush()
            except Exception:
                pass  # never crash the bot
            time.sleep(self._refresh_rate)

        # Exit alternate screen and restore
        with self._write_lock:
            sys.stderr.write("\033[?1049l\033[?25h\033[2J\033[H")
            sys.stderr.flush()

    def _update_memory(self):
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        self.state.rss_mb = int(line.split()[1]) / 1024.0
                        break
        except Exception:
            pass

    # ── Convenience API for other modules ─────────────────────────

    def record_message(self):
        self.state.messages_logged += 1
        self.state.last_message_ts = time.time()

    def record_embedding(self, count: int = 1):
        self.state.embeddings_generated += count

    def set_embedding_total(self, total: int):
        self.state.embeddings_total = total

    def set_backfill(self, running: bool, progress: float = 0.0, done: bool = False):
        self.state.backfill_running = running
        self.state.backfill_progress = progress
        self.state.backfill_done = done

    def record_search(self, search_type: str = "fts"):
        if search_type == "semantic":
            self.state.searches_semantic += 1
        elif search_type == "autorecall":
            self.state.searches_autorecall += 1
        else:
            self.state.searches_fts += 1

    def record_llm_call(self, latency_ms: float = 0.0, tool_call: bool = False):
        self.state.llm_calls += 1
        if tool_call:
            self.state.llm_tool_calls += 1
        if latency_ms > 0:
            alpha = 0.3
            self.state.llm_avg_latency_ms = (
                alpha * latency_ms + (1 - alpha) * self.state.llm_avg_latency_ms
            )
            self.state.latency_history.append(latency_ms)

    def set_subsystem(self, name: str, status: str):
        mapping = {
            "db": "db_status",
            "embedder": "embedder_status",
            "nexus": "nexus_status",
            "llm": "llm_status",
            "discord": "discord_status",
        }
        attr = mapping.get(name)
        if attr:
            setattr(self.state, attr, status)

    def record_error(self, msg: str):
        self.state.last_error = msg[:100]
        self.state.last_error_ts = time.time()


# ── Singleton ──────────────────────────────────────────────────────────

_global_dashboard: Optional[YoukaiDashboard] = None


def get_dashboard() -> YoukaiDashboard:
    """Return the global dashboard instance (lazy init)."""
    global _global_dashboard
    if _global_dashboard is None:
        _global_dashboard = YoukaiDashboard()
    return _global_dashboard

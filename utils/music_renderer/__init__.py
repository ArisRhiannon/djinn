"""Music NP image renderer — Neon Minimal design via Playwright."""
from __future__ import annotations

import asyncio
import base64
import html as html_mod
import io
import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp
from playwright.async_api import async_playwright

from .cropper import smart_square_crop

logger = logging.getLogger("djinn.music_renderer")

_TEMPLATE = """<!DOCTYPE html><html><head><style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@500;700;900&display=swap');
* { margin: 0; padding: 0; box-sizing: border-box; }
html { background: transparent; }
body {
  font-family: 'Inter', sans-serif;
  width: 500px; height: 280px;
  color: white;
  position: relative; overflow: hidden;
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: 0 0 0 1px rgba(180,124,235,0.15), 0 20px 60px rgba(0,0,0,0.5);
}
.bg {
  position: absolute; inset: -20px;
  background-image: url('data:image/png;base64,__THUMB_B64__');
  background-size: cover; background-position: center;
  filter: blur(50px) brightness(0.35) saturate(1.6);
  transform: scale(1.3);
}
.bokeh {
  position: absolute; inset: 0;
  background:
    radial-gradient(circle 80px at 15% 25%, rgba(180,124,235,0.4), transparent),
    radial-gradient(circle 60px at 75% 70%, rgba(246,135,179,0.35), transparent),
    radial-gradient(circle 40px at 50% 10%, rgba(255,255,255,0.08), transparent),
    radial-gradient(circle 50px at 85% 20%, rgba(180,124,235,0.2), transparent),
    radial-gradient(circle 35px at 30% 80%, rgba(246,135,179,0.2), transparent);
}
.overlay {
  position: absolute; inset: 0;
  background: linear-gradient(135deg, rgba(0,0,0,0.3) 0%, rgba(10,5,20,0.5) 100%);
}
.inner-glow {
  position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(180,124,235,0.4) 30%, rgba(246,135,179,0.3) 70%, transparent);
  z-index: 2;
}
.container { position: relative; z-index: 1; display: flex; gap: 18px; height: 100%; padding: 22px; }
.left { display: flex; flex-direction: column; align-items: center; gap: 10px; }
.thumb {
  width: 114px; height: 114px;
  border-radius: 12px;
  background-image: url('data:image/png;base64,__THUMB_B64__');
  background-size: cover; background-position: center;
  border: 1px solid rgba(255,255,255,0.15);
  flex-shrink: 0;
  box-shadow: 0 10px 40px rgba(0,0,0,0.5);
}
.vol {
  font-family: 'JetBrains Mono', monospace; font-size: 11px;
  color: rgba(255,255,255,0.7); font-weight: 700;
}
.vol b { color: white; }
.right { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.brand {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px; font-weight: 700; letter-spacing: 4px; color: #d4a5ff;
  margin-bottom: 6px;
}
.title {
  font-size: 20px; font-weight: 900; line-height: 1.25;
  margin-bottom: 4px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  text-shadow: 0 2px 8px rgba(0,0,0,0.5);
}
.author { font-size: 13px; color: rgba(255,255,255,0.7); margin-bottom: 6px; font-weight: 500; }
.requester { font-size: 12px; color: rgba(255,255,255,0.6); margin-bottom: 10px; }
.requester b { color: white; font-weight: 700; }
.progress-row { display: flex; align-items: center; gap: 10px; }
.progress-bar { flex: 1; height: 4px; background: rgba(255,255,255,0.15); border-radius: 3px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #b794f4, #f687b3); border-radius: 3px; }
.time { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: rgba(255,255,255,0.8); font-weight: 700; }
.queue-section {
  margin-top: 14px; padding-top: 12px;
  border-top: 1px solid rgba(255,255,255,0.1);
}
.queue-label { font-family: 'JetBrains Mono', monospace; font-size: 9px; letter-spacing: 3px; color: rgba(255,255,255,0.5); margin-bottom: 6px; font-weight: 700; }
.q-item { font-size: 13px; padding: 3px 0; display: flex; gap: 8px; align-items: baseline; }
.q-num { color: rgba(255,255,255,0.4); font-weight: 700; min-width: 16px; font-family: 'JetBrains Mono', monospace; font-size: 11px; }
.q-name { color: rgba(255,255,255,0.9); flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500; text-shadow: 0 1px 4px rgba(0,0,0,0.3); }
.q-who { color: #f687b3; font-size: 11px; font-weight: 700; flex-shrink: 0; }
.empty-q { color: rgba(255,255,255,0.3); font-size: 12px; font-style: italic; padding: 4px 0; }
.pfp-card {
  margin-top: 12px;
  padding: 6px 6px 12px 6px;
  background: rgba(255,255,255,0.95);
  border-radius: 4px;
  transform: rotate(-4deg);
  box-shadow: 0 4px 20px rgba(0,0,0,0.5);
  width: 82px;
  display: __PFP_DISPLAY__;
  flex-direction: column;
}
.pfp {
  width: 70px; height: 70px;
  background-image: url('__PFP_URL__');
  background-size: cover; background-position: center;
}
.pfp-name {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #1a1a1a;
  text-align: center; margin-top: 4px;
  letter-spacing: 0.5px;
  line-height: 1.15;
}
.pfp-name.short { font-size: 10px; }
.pfp-name.medium { font-size: 9px; }
.pfp-name.long { font-size: 8px; }
.pfp-name.xlong { font-size: 7px; letter-spacing: 0; }
.vol-floating {
  position: absolute; bottom: 18px; right: 22px;
  font-family: 'JetBrains Mono', monospace; font-size: 11px;
  color: rgba(255,255,255,0.7); font-weight: 700;
  z-index: 3;
}
.vol-floating b { color: white; }
</style></head><body>
<div class="bg"></div>
<div class="bokeh"></div>
<div class="overlay"></div>
<div class="inner-glow"></div>
<div class="vol-floating">🔊 <b>__VOL__%</b></div>
<div class="container">
  <div class="left">
    <div class="thumb"></div>
    <div class="pfp-card">
      <div class="pfp"></div>
      <div class="pfp-name __NAME_SIZE__">@__REQ_HANDLE_HTML__</div>
    </div>
  </div>
  <div class="right">
    <div class="brand">━ NOW PLAYING</div>
    <div class="title">__TITLE__</div>
    <div class="author">__AUTHOR__ · __DUR__</div>
    <div class="requester">Pedida por <b>__REQUESTER__</b></div>
    <div class="progress-row">
      <span class="time">__POS__</span>
      <div class="progress-bar"><div class="progress-fill" style="width:__PROGRESS_PCT__%"></div></div>
      <span class="time">__DUR__</span>
    </div>
    <div class="queue-section">
      <div class="queue-label">EN COLA · __QUEUE_COUNT__</div>
      __QUEUE_HTML__
    </div>
  </div>
</div>
</body></html>
"""


@dataclass
class TrackData:
    title: str
    author: str
    duration_ms: int
    position_ms: int
    artwork_url: Optional[str]
    requester: str
    requester_avatar_url: Optional[str] = None


@dataclass
class QueueItem:
    title: str
    author: str
    requester: str


@dataclass
class RenderState:
    track: TrackData
    queue: list[QueueItem]
    loop: bool
    shuffle: bool
    volume: int


def _fmt_duration(ms: int) -> str:
    s = max(0, ms // 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"


async def _download_thumbnail(url: str) -> bytes:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            return await resp.read()


_browser_lock = asyncio.Lock()
_browser = None
_playwright = None
_page = None  # Reused page
_thumb_cache: dict[str, str] = {}  # url -> b64
_avatar_cache: dict[str, str] = {}  # url -> b64


async def _get_page():
    global _browser, _playwright, _page
    async with _browser_lock:
        if _browser is None:
            _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(args=["--no-sandbox"])
        if _page is None or _page.is_closed():
            ctx = await _browser.new_context(viewport={"width": 504, "height": 284}, device_scale_factor=1)
            _page = await ctx.new_page()
        return _page


async def render_now_playing(state: RenderState) -> bytes:
    """Render the Now Playing image and return PNG bytes."""
    thumb_b64 = ""
    if state.track.artwork_url:
        # Cache cropped thumbnails
        if state.track.artwork_url in _thumb_cache:
            thumb_b64 = _thumb_cache[state.track.artwork_url]
        else:
            try:
                raw = await _download_thumbnail(state.track.artwork_url)
                cropped = await asyncio.get_event_loop().run_in_executor(
                    None, smart_square_crop, raw, 228
                )
                thumb_b64 = base64.b64encode(cropped).decode()
                _thumb_cache[state.track.artwork_url] = thumb_b64
                # Keep cache small
                if len(_thumb_cache) > 20:
                    _thumb_cache.pop(next(iter(_thumb_cache)))
            except Exception as e:
                logger.warning("Thumbnail download/crop failed: %s", e)

    # Cache avatar as base64 to avoid network race
    avatar_b64 = ""
    if state.track.requester_avatar_url:
        url = state.track.requester_avatar_url
        if url in _avatar_cache:
            avatar_b64 = _avatar_cache[url]
        else:
            try:
                raw = await _download_thumbnail(url)
                avatar_b64 = base64.b64encode(raw).decode()
                _avatar_cache[url] = avatar_b64
                if len(_avatar_cache) > 30:
                    _avatar_cache.pop(next(iter(_avatar_cache)))
            except Exception as e:
                logger.warning("Avatar download failed for %s: %s", url, e)

    # Build queue HTML
    queue_html_parts = []
    for i, q in enumerate(state.queue[:3], start=1):
        title = html_mod.escape(_truncate(q.title, 45))
        who = html_mod.escape(q.requester)
        queue_html_parts.append(
            f'<div class="q-item"><span class="q-num">{i}</span>'
            f'<span class="q-name">{title}</span>'
            f'<span class="q-who">{who}</span></div>'
        )
    queue_html = "\n".join(queue_html_parts) if queue_html_parts else '<div class="empty-q">Vacía</div>'

    progress_pct = 0
    if state.track.duration_ms > 0:
        progress_pct = min(100, int(100 * state.track.position_ms / state.track.duration_ms))

    html = _TEMPLATE
    html = html.replace("__THUMB_B64__", thumb_b64)
    html = html.replace("__TITLE__", html_mod.escape(_truncate(state.track.title, 60)))
    html = html.replace("__AUTHOR__", html_mod.escape(_truncate(state.track.author, 40)))
    html = html.replace("__POS__", _fmt_duration(state.track.position_ms))
    html = html.replace("__DUR__", _fmt_duration(state.track.duration_ms))
    html = html.replace("__PROGRESS_PCT__", str(progress_pct))
    html = html.replace("__REQUESTER__", html_mod.escape(state.track.requester))
    # Smart line-break for polaroid handle: split at natural separator near mid
    raw_handle = state.track.requester.lstrip("@")[:20]
    handle_upper = raw_handle.upper()
    if len(handle_upper) <= 8:
        size_class = "short"
        handle_html = handle_upper
    else:
        # Find best break point (closest to middle, prefer space > _ > - > . > camelCase)
        mid = len(raw_handle) // 2
        seps = [" ", "_", "-", "."]
        best = -1
        best_dist = 999
        for i, ch in enumerate(raw_handle):
            if ch in seps:
                d = abs(i - mid)
                if d < best_dist:
                    best = i
                    best_dist = d
        # If no separator found, try camelCase (lowercase→uppercase boundary)
        if best == -1:
            for i in range(1, len(raw_handle)):
                if raw_handle[i-1].islower() and raw_handle[i].isupper():
                    d = abs(i - mid)
                    if d < best_dist:
                        best = i - 1  # break BEFORE the uppercase, so user gets to keep right-side
                        best_dist = d

        if best >= 0:
            # Split into two lines (skip the separator if it's space/underscore/etc)
            sep_char = raw_handle[best]
            if sep_char in (" ", "_"):
                line1 = raw_handle[:best].upper()
                line2 = raw_handle[best+1:].upper()
            else:
                # Keep separator on left line
                line1 = raw_handle[:best+1].upper()
                line2 = raw_handle[best+1:].upper()
            longest = max(len(line1), len(line2))
            if longest <= 7:
                size_class = "short"
            elif longest <= 10:
                size_class = "medium"
            else:
                size_class = "long"
            handle_html = f"{html_mod.escape(line1)}<br>{html_mod.escape(line2)}"
        else:
            # No good break — single line, shrink font
            if len(handle_upper) <= 12:
                size_class = "medium"
            elif len(handle_upper) <= 16:
                size_class = "long"
            else:
                size_class = "xlong"
            handle_html = html_mod.escape(handle_upper)

    html = html.replace("__REQ_HANDLE_HTML__", handle_html)
    html = html.replace("__NAME_SIZE__", size_class)
    if avatar_b64:
        html = html.replace("__PFP_URL__", f"data:image/png;base64,{avatar_b64}")
        html = html.replace("__PFP_DISPLAY__", "flex")
    else:
        html = html.replace("__PFP_URL__", "")
        html = html.replace("__PFP_DISPLAY__", "none")
    html = html.replace("__QUEUE_COUNT__", str(len(state.queue)))
    html = html.replace("__QUEUE_HTML__", queue_html)
    html = html.replace("__VOL__", str(state.volume))

    page = await _get_page()
    await page.set_content(html, wait_until="domcontentloaded")
    await page.wait_for_timeout(400)
    png = await page.screenshot(
        type="png",
        clip={"x": 0, "y": 0, "width": 500, "height": 280},
        omit_background=True,
    )

    # Optimize PNG size without destroying gradients
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(png)).convert("RGBA")
        out = io.BytesIO()
        img.save(out, format="PNG", optimize=True)
        return out.getvalue()
    except Exception:
        return png


async def shutdown():
    """Cleanup browser on bot shutdown."""
    global _browser, _playwright, _page
    if _page and not _page.is_closed():
        await _page.close()
        _page = None
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright:
        await _playwright.stop()
        _playwright = None

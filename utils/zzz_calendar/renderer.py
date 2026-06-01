"""
ZZZ Calendar — HTML renderer (editorial infographic style).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Optional

from utils.zzz_calendar.assets import prefetch_calendar_assets
from utils.zzz_calendar.data import Banner, CalendarData, Event

logger = logging.getLogger("djinn.zzz_calendar.renderer")

TEMPLATE_PATH = Path(__file__).parent / "template.html"
W = 1100


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _d(dt: datetime) -> str:
    return dt.strftime("%d.%m")


def _pct(dt: datetime, cal: CalendarData) -> float:
    dt = _utc(dt)
    total = (cal.end - cal.start).total_seconds()
    if total <= 0:
        return 0.0
    return max(0.0, min(100.0, ((dt - cal.start).total_seconds() / total) * 100.0))


def _layers(items, gs, ge):
    rows = []
    for it in items:
        s, e = gs(it), ge(it)
        if not (s and e):
            continue
        placed = False
        for row in rows:
            if all(not (s < ge(x) and e > gs(x)) for x in row):
                row.append(it)
                placed = True
                break
        if not placed:
            rows.append([it])
    return rows


# ── Builders ──────────────────────────────────────────────────────────────

def _header(cal, urls):
    # Use v2.8 splash as background
    bg = urls.get("ui:splash_v28", "")
    logo = urls.get("ui:zzz_logo", "")
    bg_style = f'background-image:url(\'{bg}\');' if bg else ""
    logo_html = f'<img class="header-logo" src="{logo}">' if logo else ""

    return f"""
<div class="header">
  <div class="header-art" style="{bg_style}"></div>
  <div class="header-content">
    <div class="header-top">
      {logo_html}
      <span class="header-version">Zenless Zone Zero V{escape(cal.version)}</span>
    </div>
    <div class="header-bottom">
      <div class="header-title">Calendario de Eventos y Canales</div>
      <div class="header-sub">Versión {escape(cal.version)} | {cal.start.strftime('%d %B').lower()} — {cal.end.strftime('%d %B').lower()}</div>
    </div>
  </div>
  <div class="header-credits">Hecho por<strong>YOUKAI</strong></div>
</div>"""


def _weeks(cal):
    cols = []
    cur = cal.start
    i = 0
    while cur < cal.end and i < 8:
        end = min(cur + timedelta(days=6), cal.end)
        n = ["1ra", "2da", "3ra", "4ta", "5ta", "6ta", "7ma", "8va"][i]
        cols.append(f'<div class="week-col"><div class="wc-num">{n} semana</div><div class="wc-range">{_d(cur)} - {_d(end)}</div></div>')
        cur += timedelta(days=7)
        cur = cur.replace(hour=0, minute=0, second=0)
        i += 1

    return f"""
<div class="weeks-bar">
  <div class="weeks-label"><div class="wl-title">Semanas</div><div class="wl-sub">formato: dd.mm</div></div>
  <div class="weeks-cols" style="--wc:{len(cols)};">{''.join(cols)}</div>
</div>"""


def _agent_fig(name, urls, is_main, rank=""):
    """Free-flowing agent — no rectangle, only constrained by card bottom."""
    url = urls.get(f"agent:{name}", "")
    label = name if len(name) <= 13 else name[:12] + "…"
    main_cls = " main" if is_main else ""

    if url:
        img = f'<img src="{url}">'
    else:
        img = f'<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#666;font-weight:900;font-size:24px;">{escape(name[:2].upper())}</div>'

    rank_html = f'<div class="rank-badge {rank}">{rank}</div>' if rank else ""
    return f'<div class="b-agent{main_cls}">{img}<div class="b-agent-overlay"></div>{rank_html}<div class="b-agent-name">{escape(label)}</div></div>'


def _wengine_fig(name, urls, is_main):
    url = urls.get(f"wengine:{name}", "")
    label = name if len(name) <= 14 else name[:13] + "…"
    main_cls = " main" if is_main else ""
    if url:
        img = f'<img src="{url}">'
    else:
        img = f'<div style="width:80px;height:80px;display:flex;align-items:center;justify-content:center;color:#666;font-weight:900;font-size:20px;">{escape(name[:2].upper())}</div>'
    return f'<div class="b-we{main_cls}">{img}<div class="b-we-name">{escape(label)}</div></div>'


def _banner_card(b, cal, urls, meta, is_we):
    """Build single banner card."""
    bg_url = urls.get(f"splash:{b.main}", "")
    bg_html = f'<div class="b-card-bg" style="background-image:url(\'{bg_url}\');"></div>' if bg_url else ""

    if is_we:
        # W-engine showcase: main weapon big with backplate, side smaller
        figs = [_wengine_fig(b.main, urls, True)]
        if b.side:
            figs.append('<div class="b-we-divider"></div>')
            for s in b.side[:2]:
                figs.append(_wengine_fig(s, urls, False))
        body = f'<div class="b-wengines">{"".join(figs)}</div>'
    else:
        # Free-flowing agent silhouettes
        agents = [_agent_fig(b.main, urls, True, b.rarity or "S")]
        for s in b.side[:2]:
            agents.append(_agent_fig(s, urls, False, "A"))
        body = f'<div class="b-agents">{"".join(agents)}</div>'

    return f"""<div class="b-card">
  {bg_html}
  <div class="b-card-overlay"></div>
  <div class="b-card-header">
    <div class="b-card-name">{escape(b.name)}</div>
    <div class="b-card-dates">{_d(b.start)} - {_d(b.end)}</div>
  </div>
  {body}
</div>"""


def _banner_section(title, banners, cal, urls, meta, is_we):
    if not banners:
        return ""
    # Group banners into rows: pair Phase 1 and Phase 2 side by side
    # Use temporal layering (banners with overlapping dates go in same row)
    rows = _layers(banners, lambda b: b.start, lambda b: b.end)
    rows_html = ""
    for row in rows:
        cards = "".join(_banner_card(b, cal, urls, meta, is_we) for b in row)
        rows_html += f'<div class="banner-row">{cards}</div>'

    return f"""
<div class="panel">
  <div class="panel-label"><div class="pl-title">{escape(title)}</div></div>
  <div class="panel-content"><div class="banner-grid">{rows_html}</div></div>
</div>"""


def _ev_bar(ev, cal, kind):
    start = ev.start or cal.start
    end = ev.end or cal.end
    if ev.permanent:
        end = cal.end
    left = _pct(start, cal)
    width = max(8.0, _pct(end, cal) - left - 0.3)
    dates = f"{_d(start)} - disponible indefinidamente" if ev.permanent else f"{_d(start)} - {_d(end)}"
    new = '<span class="new-badge">NEW!</span>' if ev.new else ""
    return f"""<div class="ev-bar {kind}" style="left:{left}%;width:{width}%;">
  <div class="ev-info"><div class="ev-name">{escape(ev.name)}</div><div class="ev-dates">📅 {dates}</div></div>{new}
</div>"""


def _events_section(title, events, cal, kind, wc):
    if not events:
        return ""
    rows = _layers(events, lambda e: e.start or cal.start,
                   lambda e: cal.end if e.permanent else (e.end or cal.end))
    rows_html = ""
    for row in rows:
        bars = "".join(_ev_bar(ev, cal, kind) for ev in row)
        rows_html += f'<div class="ev-row">{bars}</div>'

    # TODAY indicator
    now = datetime.now(timezone.utc)
    today_html = ""
    if cal.start <= now <= cal.end:
        today_pct = _pct(now, cal)
        today_html = f'<div class="today-line" style="left:{today_pct}%;"></div>'

    return f"""
<div class="panel">
  <div class="panel-label"><div class="pl-title">{escape(title)}</div></div>
  <div class="panel-content"><div class="events-area" style="--wc:{wc};">{today_html}{rows_html}</div></div>
</div>"""


def _build_html(cal, urls, meta):
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    wc = cal.num_weeks
    parts = [
        '<div class="cal">',
        _header(cal, urls),
        _weeks(cal),
        _banner_section("Canales Exclusivos", cal.exclusive_channels, cal, urls, meta, False),
        _banner_section("Canales W-Engine", cal.wengine_channels, cal, urls, meta, True),
        _events_section("Eventos de Login", cal.login_events, cal, "login", wc),
        _events_section("Eventos Permanentes", cal.permanent_events, cal, "permanent", wc),
    ]
    if cal.battle_pass:
        parts.append(_events_section("Pase de Batalla", [cal.battle_pass], cal, "bp", wc))
    parts.append(_events_section("Otros Eventos", cal.other_events, cal, "other", wc))
    parts.append('<div class="footer">© HOYOVERSE · TODOS LOS DERECHOS RESERVADOS · HOYOVERSE Y ZENLESS ZONE ZERO SON MARCAS REGISTRADAS DE HOYOVERSE</div>')
    parts.append('</div>')
    return template.replace("{{ body }}", "\n".join(parts))


async def render_calendar(cal: CalendarData, output_path=None) -> bytes:
    urls, meta = await prefetch_calendar_assets(cal)
    html = _build_html(cal, urls, meta)
    Path("/tmp/zzz_calendar_debug.html").write_text(html, encoding="utf-8")

    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--no-sandbox"])
        try:
            ctx = await browser.new_context(viewport={"width": W, "height": 800}, device_scale_factor=2)
            page = await ctx.new_page()
            await page.set_content(html, wait_until="networkidle", timeout=30000)
            el = await page.query_selector(".cal")
            png = await el.screenshot(type="png")
        finally:
            await browser.close()

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(png)
    return png


__all__ = ["render_calendar"]

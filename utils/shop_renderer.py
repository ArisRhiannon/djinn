"""
Shop renderer — paginated PNG for /recompensas.

Roles GM are grouped into a single "Roles Grandmaster" entry. All other
items are listed individually with their description. 10 items per page.
"""
from __future__ import annotations

import asyncio
import base64
import html as html_mod
import io
import logging
import math
from dataclasses import dataclass

from playwright.async_api import async_playwright

logger = logging.getLogger("djinn.shop_renderer")

ITEMS_PER_PAGE = 10


@dataclass
class ShopEntry:
    name: str
    description: str
    price: int
    stock: str
    icon_key: str


# ── SVG Icons ────────────────────────────────────────────────────────────────

_ICON_SVGS = {
    "roles_gm": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none">
      <defs><linearGradient id="g1" x1="0" y1="0" x2="32" y2="32"><stop offset="0%" stop-color="#b794f4"/><stop offset="100%" stop-color="#805ad5"/></linearGradient></defs>
      <rect width="32" height="32" rx="7" fill="#1a1025"/>
      <path d="M7 21l3.5-9 5.5 4.5 5.5-4.5 3.5 9z" fill="url(#g1)" opacity="0.9"/>
      <circle cx="10.5" cy="12" r="1.6" fill="#d4a5ff"/>
      <circle cx="16" cy="8" r="2" fill="#f687b3"/>
      <circle cx="21.5" cy="12" r="1.6" fill="#d4a5ff"/>
      <rect x="8" y="22" width="16" height="2.5" rx="1.25" fill="url(#g1)" opacity="0.6"/>
    </svg>''',
    "coupon": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none">
      <defs><linearGradient id="g2" x1="0" y1="0" x2="32" y2="32"><stop offset="0%" stop-color="#f687b3"/><stop offset="100%" stop-color="#d53f8c"/></linearGradient></defs>
      <rect width="32" height="32" rx="7" fill="#1a1025"/>
      <rect x="5" y="10" width="22" height="12" rx="2.5" fill="url(#g2)" opacity="0.85"/>
      <line x1="12.5" y1="10" x2="12.5" y2="22" stroke="#1a1025" stroke-width="1.4" stroke-dasharray="2 2"/>
      <circle cx="20" cy="16" r="2.6" fill="none" stroke="#fff" stroke-width="1.4" opacity="0.85"/>
      <path d="M18.7 16l1 1 2-2" stroke="#fff" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>''',
    "rule": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none">
      <defs><linearGradient id="g3" x1="0" y1="0" x2="32" y2="32"><stop offset="0%" stop-color="#78c8ff"/><stop offset="100%" stop-color="#3182ce"/></linearGradient></defs>
      <rect width="32" height="32" rx="7" fill="#1a1025"/>
      <rect x="9" y="6" width="14" height="20" rx="1.8" fill="url(#g3)" opacity="0.8"/>
      <line x1="11.5" y1="13" x2="20.5" y2="13" stroke="#fff" stroke-width="1.1" opacity="0.6" stroke-linecap="round"/>
      <line x1="11.5" y1="16" x2="18.5" y2="16" stroke="#fff" stroke-width="1.1" opacity="0.5" stroke-linecap="round"/>
      <line x1="11.5" y1="19" x2="17" y2="19" stroke="#fff" stroke-width="1.1" opacity="0.4" stroke-linecap="round"/>
      <path d="M21 23l2.5-10 1.3 0.3-2.5 10z" fill="#f6e05e" opacity="0.75"/>
    </svg>''',
    "generic": '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none">
      <rect width="32" height="32" rx="7" fill="#1a1025"/>
      <circle cx="16" cy="16" r="7" fill="none" stroke="#b794f4" stroke-width="1.4" opacity="0.7"/>
      <circle cx="16" cy="16" r="2.5" fill="#b794f4" opacity="0.55"/>
    </svg>''',
}

_ICON_URIS: dict[str, str] = {}


def _icon(key: str) -> str:
    if key not in _ICON_URIS:
        svg = _ICON_SVGS.get(key, _ICON_SVGS["generic"])
        b64 = base64.b64encode(svg.strip().encode()).decode()
        _ICON_URIS[key] = f"data:image/svg+xml;base64,{b64}"
    return _ICON_URIS[key]


# ── Template ─────────────────────────────────────────────────────────────────

_TEMPLATE = '''<!DOCTYPE html><html><head><style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700;800&display=swap');
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { background: transparent; font-family: 'Inter', sans-serif; color: white; }
body { padding: 8px; }

.card {
  width: 472px;
  background: #0c0814;
  border-radius: 14px;
  overflow: hidden;
  position: relative;
  border: 1px solid rgba(255,255,255,0.06);
}
.card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, #b794f4, #f687b3, #78c8ff, #b794f4);
  opacity: 0.8;
}
.ambient {
  position: absolute; inset: 0; pointer-events: none;
  background:
    radial-gradient(ellipse 200px 120px at 0% 0%, rgba(183,148,244,0.06), transparent),
    radial-gradient(ellipse 160px 100px at 100% 100%, rgba(246,135,179,0.05), transparent);
}
.inner { position: relative; z-index: 1; padding: 14px 16px 14px; }
.header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px;
}
.brand {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px; font-weight: 700; letter-spacing: 2.5px;
  color: rgba(255,255,255,0.7);
}
.page-info {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9.5px; font-weight: 500; letter-spacing: 1px;
  color: rgba(255,255,255,0.35);
}
.sep {
  height: 1px; margin-bottom: 10px;
  background: linear-gradient(90deg, rgba(183,148,244,0.3), rgba(246,135,179,0.2) 50%, transparent);
}
.items { display: flex; flex-direction: column; gap: 3px; }
.item {
  display: flex; align-items: center; gap: 9px;
  padding: 6px 10px 6px 0;
  border-radius: 7px;
  position: relative;
}
.item.even { background: rgba(255,255,255,0.015); }
.item.odd { background: rgba(255,255,255,0.03); }
.accent-bar {
  width: 3px; align-self: stretch;
  border-radius: 2px;
  background: var(--accent);
  opacity: 0.7;
  box-shadow: 0 0 8px var(--accent);
  margin-right: 2px;
  flex-shrink: 0;
}
.icon { width: 22px; height: 22px; flex-shrink: 0; border-radius: 5px; }
.info { flex: 1; min-width: 0; }
.name {
  font-size: 11.5px; font-weight: 700;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  line-height: 1.35;
}
.desc {
  font-size: 9px; font-weight: 400;
  color: rgba(255,255,255,0.38);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  line-height: 1.3;
}
.right { text-align: right; flex-shrink: 0; padding-left: 8px; }
.price-pill {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px; font-weight: 700;
  color: #f6e05e;
  background: rgba(246,224,94,0.08);
  border: 1px solid rgba(246,224,94,0.15);
  border-radius: 10px;
  padding: 2px 7px;
  line-height: 1.3;
  display: inline-block;
}
.stock {
  font-family: 'JetBrains Mono', monospace;
  font-size: 8px; font-weight: 500;
  color: rgba(255,255,255,0.3);
  margin-top: 2px;
}
</style></head><body>
<div class="card">
  <div class="ambient"></div>
  <div class="inner">
    <div class="header">
      <div class="brand">YOUKAI SHOP</div>
      __PAGE_INFO__
    </div>
    <div class="sep"></div>
    <div class="items">
      __ITEMS_HTML__
    </div>
  </div>
</div>
</body></html>'''


# ── Renderer ─────────────────────────────────────────────────────────────────

_browser = None
_playwright_inst = None
_lock = asyncio.Lock()


async def _get_browser():
    global _browser, _playwright_inst
    async with _lock:
        if _browser is None:
            _playwright_inst = await async_playwright().start()
            _browser = await _playwright_inst.chromium.launch(args=["--no-sandbox"])
    return _browser


def build_entries(items: list[dict]) -> list[ShopEntry]:
    """Convert raw DB rows into ShopEntry list, grouping GM roles."""
    gm_roles = [i for i in items if i.get("category") == "Roles GM"]
    others = [i for i in items if i.get("category") != "Roles GM"]

    entries: list[ShopEntry] = []
    if gm_roles:
        entries.append(ShopEntry(
            name="Roles Grandmaster",
            description=f"{len(gm_roles)} roles exclusivos de personaje",
            price=gm_roles[0]["price"],
            stock=str(len(gm_roles)),
            icon_key="roles_gm",
        ))

    for item in others:
        t = item.get("type", "")
        cat = item.get("category", "")
        if t == "coupon" or "cupón" in cat.lower() or "cupon" in cat.lower():
            icon = "coupon"
        elif "regla" in item["name"].lower() or "listener" in (item.get("description", "")).lower():
            icon = "rule"
        else:
            icon = "generic"

        stock_val = item.get("stock", -1)
        stock_str = "∞" if stock_val == -1 else str(stock_val)

        entries.append(ShopEntry(
            name=item["name"],
            description=item.get("description", "")[:65],
            price=item["price"],
            stock=stock_str,
            icon_key=icon,
        ))
    return entries


def total_pages(entries: list[ShopEntry]) -> int:
    return max(1, math.ceil(len(entries) / ITEMS_PER_PAGE))


async def render_shop_page(entries: list[ShopEntry], page: int = 0) -> bytes:
    """Render a single page of the shop as PNG."""
    pages = total_pages(entries)
    page = max(0, min(page, pages - 1))
    page_items = entries[page * ITEMS_PER_PAGE:(page + 1) * ITEMS_PER_PAGE]

    parts = []
    for i, entry in enumerate(page_items):
        color = {"roles_gm": "#b794f4", "coupon": "#f687b3", "rule": "#78c8ff"}.get(entry.icon_key, "#a0aec0")
        even_odd = "even" if i % 2 == 0 else "odd"
        stock_label = f"{entry.stock} disp." if entry.stock != "∞" else "∞ disp."
        parts.append(
            f'<div class="item {even_odd}" style="--accent: {color}">'
            f'<div class="accent-bar"></div>'
            f'<img class="icon" src="{_icon(entry.icon_key)}"/>'
            f'<div class="info">'
            f'<div class="name">{html_mod.escape(entry.name)}</div>'
            f'<div class="desc">{html_mod.escape(entry.description) if entry.description else ""}</div>'
            f'</div>'
            f'<div class="right">'
            f'<div class="price-pill">{entry.price:,}</div>'
            f'<div class="stock">{stock_label}</div>'
            f'</div></div>'
        )
    page_info_html = (
        f'<div class="page-info">PÁG {page + 1}/{pages}</div>'
        if pages > 1 else ''
    )
    html = _TEMPLATE.replace("__ITEMS_HTML__", "\n".join(parts)).replace("__PAGE_INFO__", page_info_html)

    browser = await _get_browser()
    ctx = await browser.new_context(viewport={"width": 500, "height": 900}, device_scale_factor=2)
    pg = await ctx.new_page()
    await pg.set_content(html, wait_until="networkidle")
    await pg.wait_for_timeout(250)
    # Measure the .card element's bounding box for exact clip
    box = await pg.evaluate("""() => {
      const el = document.querySelector('.card');
      const r = el.getBoundingClientRect();
      return {x: r.x, y: r.y, w: r.width, h: r.height};
    }""")
    # Add 1px margin so the bottom rounded corner isn't clipped by AA
    png = await pg.screenshot(
        type="png",
        clip={"x": max(0, box["x"] - 2), "y": max(0, box["y"] - 2),
              "width": box["w"] + 4, "height": box["h"] + 4},
        omit_background=True,
    )
    await ctx.close()

    try:
        from PIL import Image
        img = Image.open(io.BytesIO(png)).convert("RGBA")
        out = io.BytesIO()
        img.save(out, format="PNG", optimize=True)
        return out.getvalue()
    except Exception:
        return png


async def shutdown():
    global _browser, _playwright_inst
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright_inst:
        await _playwright_inst.stop()
        _playwright_inst = None

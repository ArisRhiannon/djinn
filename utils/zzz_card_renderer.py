"""ZZZ Build Card Renderer v2.1 — layout horizontal con fixes."""
from __future__ import annotations

import colorsys
import io
import urllib.parse
from typing import Optional

import aiohttp
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

API_BASE = "http://140.84.187.50:8000"

# ── Design tokens ─────────────────────────────────────────────────────────
BG_DARK = (10, 12, 18)
BG_CARD = (22, 25, 36)
BG_SOFT = (32, 36, 52)
BG_TAG = (30, 34, 50)
BORDER = (45, 50, 70)
BORDER_SOFT = (38, 42, 60)

TEXT_W = (248, 250, 255)
TEXT_G = (170, 178, 198)
TEXT_D = (105, 115, 135)
TEXT_DIM = (72, 80, 100)

GOLD = (255, 199, 56)
GREEN = (80, 220, 100)
RED = (255, 90, 90)
ORANGE = (255, 140, 60)

# ── Rarity colors (trending: Genshin/ZZZ/TCG standard) ───────────────
# Orden de rareza: C < B < A < S < SS
RARITY_COLORS = {
    "SS": (255, 215, 90),    # Dorado brillante (legendary)
    "S":  (205, 125, 255),   # Púrpura vibrante (epic)
    "A":  (90, 180, 255),    # Azul cyan (rare)
    "B":  (110, 210, 130),   # Verde (uncommon)
    "C":  (155, 165, 180),   # Gris plateado (common)
}
# Intensity del glow por rareza (mayor rareza = más efecto)
RARITY_GLOW = {
    "SS": (14, 200),  # radius, intensity
    "S":  (10, 170),
    "A":  (6, 120),
    "B":  (3, 70),
    "C":  (0, 0),     # sin glow
}
# Rank del agente colors
AGENT_RANK_COLORS = {
    "S": (255, 200, 80),   # dorado para S-rank agents
    "A": (205, 125, 255),  # púrpura para A-rank agents
}

# Colores por elemento (menos saturados para no abrumar)
ELEM_COLORS = {
    "FIRE":        (255, 110, 75),
    "FIRE_FROST":  (180, 210, 255),
    "ICE":         (110, 200, 255),
    "ELECTRIC":    (195, 130, 255),
    "ETHER":       (220, 130, 230),
    "PHYSICAL":    (255, 180, 80),
    "ZHEN_ASSAULT":(255, 100, 100),
}
DEFAULT_ACCENT = (0, 200, 255)

SPEC_COLORS = {
    "ATTACK":  (255, 110, 110),
    "STUN":    (255, 200, 90),
    "ANOMALY": (190, 115, 240),
    "SUPPORT": (110, 220, 170),
    "DEFENSE": (110, 185, 255),
    "RUPTURE": (220, 110, 220),
}
SPEC_LABELS = {
    "ATTACK": "ATTACK", "STUN": "STUN", "ANOMALY": "ANOMALY",
    "SUPPORT": "SUPPORT", "DEFENSE": "DEFENSE", "RUPTURE": "RUPTURE",
}

GOOD_STATS = {"CRIT Rate", "CRIT DMG", "Percent ATK", "PEN Ratio", "Anomaly Proficiency"}
CRIT_STATS = {"CRIT Rate", "CRIT DMG"}

# ── ZZZ substat roll increments (valor por roll fijo) ──────────────────
SUBSTAT_INCREMENTS = {
    "HP": 112,                    # HP flat
    "ATK": 19,                    # ATK flat
    "DEF": 15,                    # DEF flat
    "Percent HP": 3.0,
    "Percent ATK": 3.0,
    "Percent DEF": 4.8,
    "CRIT Rate": 2.4,
    "CRIT DMG": 4.8,
    "Anomaly Proficiency": 9,
    "PEN Ratio": 2.4,
    "PEN": 9,
}


def _parse_stat_value(value_str):
    """'3.0%' → 3.0, '112' → 112, '2,200' → 2200"""
    s = str(value_str).replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _count_rolls(stat_name, value_str):
    """Cuántos rolls tiene este substat (1-5)."""
    inc = SUBSTAT_INCREMENTS.get(stat_name, 0)
    if inc <= 0:
        return 0
    val = _parse_stat_value(value_str)
    if val <= 0:
        return 0
    rolls = round(val / inc)
    return max(1, min(5, rolls))


def _disc_liner_type(disc):
    """Detecta 3-liner vs 4-liner por total de rolls.
    3-liner: 8 rolls totales (3 iniciales + 1 nuevo sub + 4 upgrades)
    4-liner: 9 rolls totales (4 iniciales + 5 upgrades) — RARO/VALIOSO
    """
    total = sum(_count_rolls(s["name"], s["value"])
                for s in disc.get("sub_stats", []))
    if total >= 9:
        return "4L"  # 4-liner (nació con 4)
    return "3L"      # 3-liner (nació con 3)

# ── ZZZ substat roll increments (valor por roll) ──────────────────────
SUBSTAT_INCREMENTS = {
    "HP": 112,           # flat HP
    "ATK": 19,           # flat ATK
    "DEF": 15,           # flat DEF
    "Percent HP": 3.0,
    "Percent ATK": 3.0,
    "Percent DEF": 4.8,
    "CRIT Rate": 2.4,
    "CRIT DMG": 4.8,
    "Anomaly Proficiency": 9,
    "PEN Ratio": 2.4,
    "PEN": 9,
}


def _parse_stat_value(value_str: str) -> float:
    """'3.0%' → 3.0, '112' → 112, '2,200' → 2200"""
    s = value_str.replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _count_rolls(stat_name: str, value_str: str) -> int:
    """Cuántos rolls tiene este substat (1-5)."""
    inc = SUBSTAT_INCREMENTS.get(stat_name, 0)
    if inc <= 0:
        return 0
    val = _parse_stat_value(value_str)
    rolls = round(val / inc)
    return max(1, min(5, rolls))

FONT_PATHS = {
    "thin":   "/usr/share/fonts/opentype/inter/Inter-Thin.otf",
    "light":  "/usr/share/fonts/opentype/inter/Inter-Light.otf",
    "medium": "/usr/share/fonts/opentype/inter/Inter-Medium.otf",
    "bold":   "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
    "black":  "/usr/share/fonts/opentype/inter/Inter-Black.otf",
}

def _font(weight: str, size: int):
    try:
        return ImageFont.truetype(FONT_PATHS[weight], size)
    except Exception:
        return ImageFont.truetype(FONT_PATHS["medium"], size)


# ── Premium fonts (Orbitron for display, Manrope for numbers/labels) ────
_PREMIUM = "/home/ubuntu/.local/share/fonts/premium"
_PREMIUM_FONT_PATHS = {
    "orbitron_black":  f"{_PREMIUM}/Orbitron-Black.ttf",
    "manrope_bold":    "/usr/share/fonts/truetype/manrope/Manrope-Bold.ttf",
    "manrope_semi":    "/usr/share/fonts/truetype/manrope/Manrope-SemiBold.ttf",
    "manrope_med":     "/usr/share/fonts/truetype/manrope/Manrope-Medium.ttf",
    "inter_med":       "/usr/share/fonts/opentype/inter/Inter-Medium.otf",
    "inter_semi":      "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
}

def _f(key: str, size: int):
    """Premium font loader with fallback to Inter black."""
    path = _PREMIUM_FONT_PATHS.get(key)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return _font("black", size)


# ── Pastel cool palette for rolls breakdown (harmonic HSL) ──────────────
def _hsl(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h / 360.0, l, s)
    return (int(r * 255), int(g * 255), int(b * 255))

P_PASTEL_COOL = {
    "ideal":  _hsl(165, 0.38, 0.70),   # mint
    "ok":     _hsl(35, 0.50, 0.70),    # peach
    "waste":  _hsl(345, 0.42, 0.70),   # pink
    "dot":    _hsl(215, 0.10, 0.50),   # neutral
}


# ══════════════════════════════════════════════════════════════════════════
# PREMIUM RENDER PRIMITIVES — glass, conic bg, dithering, gradient text
# ══════════════════════════════════════════════════════════════════════════

def _dither_rgb(img, amplitude=0.8, seed=42):
    """Per-pixel noise to break 8-bit banding. Amplitude 0.8 is imperceptible."""
    np.random.seed(seed)
    arr = np.array(img.convert("RGB")).astype(np.float32)
    noise = np.random.uniform(-amplitude, amplitude, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB").convert("RGBA")


def _rounded_mask_aa(w, h, radius, supersample=3):
    """High-quality AA rounded-rect mask via supersampling."""
    sw, sh = w * supersample, h * supersample
    m = Image.new("L", (sw, sh), 0)
    ImageDraw.Draw(m).rounded_rectangle(
        (0, 0, sw - 1, sh - 1),
        radius=radius * supersample, fill=255)
    return m.resize((w, h), Image.LANCZOS)


def _bg_conic(w, h, c1, c2, c3, cx_frac=-0.2, cy_frac=-0.3):
    """Smooth conic gradient (C¹-continuous) con centro off-frame."""
    cx, cy = int(cx_frac * w), int(cy_frac * h)
    y, x = np.ogrid[:h, :w]
    angle = np.arctan2(y - cy, x - cx)
    t = (angle + np.pi) / (2 * np.pi)

    arr = np.zeros((h, w, 3), dtype=np.float32)
    colors = [c1, c2, c3, c1]
    for i in range(3):
        chan = np.zeros((h, w), dtype=np.float32)
        for k in range(3):
            t0 = k / 3
            t1 = (k + 1) / 3
            mask = (t >= t0) & (t <= t1)
            lt = (t - t0) / (t1 - t0)
            lt_s = lt * lt * (3.0 - 2.0 * lt)  # smoothstep
            chan_val = colors[k][i] * (1 - lt_s) + colors[k + 1][i] * lt_s
            chan = np.where(mask, chan_val, chan)
        arr[:, :, i] = chan
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, "RGB").convert("RGBA")
    return _dither_rgb(img, amplitude=0.8, seed=42)


def _drop_shadow(img, box, radius, alpha=55, offset=3, blur=12):
    """Soft outer shadow biased downward — call BEFORE painting the card."""
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    pad = blur * 2 + offset + 4
    sw, sh = w + pad * 2, h + pad * 2
    shadow = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    inset = max(2, w // 60)
    ImageDraw.Draw(shadow).rounded_rectangle(
        (pad + inset, pad + offset,
         pad + w - 1 - inset, pad + offset + h - 1),
        radius=radius, fill=(0, 0, 0, alpha))
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(shadow, (x1 - pad, y1 - pad))


def _glass_clean_line(img, box, radius=12):
    """Clean-line glass card: heavy blur, minimal tint, thin border,
    1px top-inner highlight, soft drop shadow. NO broad shine gradient
    (avoids Vista/Frutiger look).
    Design: iOS 26 / Linear / Vercel."""
    _drop_shadow(img, box, radius, alpha=55, offset=3, blur=12)

    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    rmask = _rounded_mask_aa(w, h, radius)

    # 1. Backdrop blur
    region = img.crop((x1, y1, x2, y2)).convert("RGBA")
    blurred = region.filter(ImageFilter.GaussianBlur(18))
    img.paste(blurred, (x1, y1), rmask)

    # 2. Very subtle dark tint
    tint_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    tf = Image.new("RGBA", (w, h), (10, 12, 20, 78))
    tint_layer.paste(tf, (0, 0), rmask)
    img.alpha_composite(tint_layer, (x1, y1))

    # 3. 1-PIXEL top inner highlight (not a ramp)
    hl_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(hl_layer).rounded_rectangle(
        (0, 0, w - 1, h - 1), radius=radius,
        outline=(255, 255, 255, 32), width=1)
    top_band = Image.new("L", (w, h), 0)
    ImageDraw.Draw(top_band).rectangle((0, 0, w, 2), fill=255)
    hl_masked = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hl_masked.paste(hl_layer, (0, 0), top_band)
    img.alpha_composite(hl_masked, (x1, y1))

    # 4. Hairline border (outline, subtle)
    bl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(bl).rounded_rectangle(
        (0, 0, w - 1, h - 1), radius=radius,
        outline=(255, 255, 255, 44), width=1)
    img.alpha_composite(bl, (x1, y1))


def _clean_gradient_text(img, pos, text, font, color_top, color_bottom,
                         glow_color=None, glow_radius=0, glow_intensity=80):
    """Render text with vertical gradient + optional glow. Used for grade+score
    so they share the same positioning pipeline → identical alignment."""
    tmp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = tmp_draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad = max(glow_radius * 3, 8)
    cw, ch = tw + pad * 2, th + pad * 2
    mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(mask).text((pad - bbox[0], pad - bbox[1]), text,
                               font=font, fill=255)
    gradient = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gradient)
    top_y, bot_y = pad, pad + th
    for y in range(ch):
        if y < top_y:
            t = 0.0
        elif y > bot_y:
            t = 1.0
        else:
            t = (y - top_y) / max(bot_y - top_y, 1)
        r = int(color_top[0] * (1 - t) + color_bottom[0] * t)
        g = int(color_top[1] * (1 - t) + color_bottom[1] * t)
        b = int(color_top[2] * (1 - t) + color_bottom[2] * t)
        gd.line([(0, y), (cw, y)], fill=(r, g, b, 255))
    gradient.putalpha(mask)
    if glow_color and glow_radius > 0:
        blurred_mask = mask.filter(ImageFilter.GaussianBlur(glow_radius))
        glow_layer = Image.new("RGBA", (cw, ch), (*glow_color, glow_intensity))
        glow_layer.putalpha(blurred_mask)
        img.alpha_composite(glow_layer, (pos[0] - pad, pos[1] - pad))
    img.alpha_composite(gradient, (pos[0] - pad, pos[1] - pad))


def _draw_rolls_inline(img, draw, right_x, y_anchor, eval_data, palette):
    """Inline rolls breakdown: 13 IDEAL · 15 OK · 20 WASTE / 48.
    Labels centered vertically with numbers (anchor='lm'/'rm'/'mm').
    Returns leftmost x (for ROLLS BREAKDOWN label alignment)."""
    num_f = _f("manrope_bold", 20)
    label_f = _f("manrope_semi", 10)
    sep_f = _f("manrope_med", 16)
    total = eval_data.get("rolls_total", 0)
    decent = eval_data.get("rolls_decent", 0)
    ideal = eval_data.get("rolls_ideal", 0)
    waste = total - decent - ideal

    tmp = draw.textbbox((0, 0), "0", font=num_f)
    num_h = tmp[3] - tmp[1]
    center_y = y_anchor + num_h // 2

    x = right_x
    total_txt = f"/ {total}"
    draw.text((x, center_y), total_txt, font=num_f, fill=palette["dot"], anchor="rm")
    tw = draw.textbbox((0, 0), total_txt, font=num_f)[2]
    x -= tw + 14

    for label, val, color in [
        ("WASTE", waste, palette["waste"]),
        ("OK", decent, palette["ok"]),
        ("IDEAL", ideal, palette["ideal"]),
    ]:
        lw = draw.textbbox((0, 0), label, font=label_f)[2]
        x -= lw
        draw.text((x, center_y), label, font=label_f, fill=palette["dot"], anchor="lm")
        x -= 6
        nw = draw.textbbox((0, 0), str(val), font=num_f)[2]
        x -= nw
        draw.text((x, center_y), str(val), font=num_f, fill=color, anchor="lm")
        if label != "IDEAL":
            x -= 12
            draw.text((x, center_y), "·", font=sep_f, fill=palette["dot"], anchor="mm")
            x -= 10
    return x





# ── Utility ──────────────────────────────────────────────────────────────

def _text(draw, xy, text, font, fill, shadow=False):
    if shadow:
        draw.text((xy[0]+1, xy[1]+1), text, font=font, fill=(0, 0, 0, 180))
    draw.text(xy, text, font=font, fill=fill)

def _text_right(draw, right_x, y, text, font, fill, shadow=False):
    w = draw.textbbox((0, 0), text, font=font)[2]
    _text(draw, (right_x - w, y), text, font, fill, shadow)

def _text_center(draw, cx, y, text, font, fill, shadow=False):
    w = draw.textbbox((0, 0), text, font=font)[2]
    _text(draw, (cx - w // 2, y), text, font, fill, shadow)

def _rounded_rect(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)

def _composite_rect(img, box, radius, fill_rgba, outline=None, width=1):
    """Pega un rectángulo semi-transparente usando alpha compositing real."""
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle((0, 0, w-1, h-1), radius=radius, fill=fill_rgba,
                         outline=outline, width=width)
    img.alpha_composite(layer, (x1, y1))

def _glow_text_contained(img, pos, text, font, color, glow_color, radius=8):
    """Glow que no se sale del canvas."""
    base = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(base).text(pos, text, font=font, fill=(*glow_color, 100))
    glow = base.filter(ImageFilter.GaussianBlur(radius))
    img.alpha_composite(glow)
    ImageDraw.Draw(img).text(pos, text, font=font, fill=color)


def _rate_disc(disc):
    good = sum(1 for s in disc.get("sub_stats", [])
               if s["name"] in GOOD_STATS or "CRIT" in s["name"])
    if good >= 4: return "SS", RARITY_COLORS["SS"]
    if good >= 3: return "S", RARITY_COLORS["S"]
    if good >= 2: return "A", RARITY_COLORS["A"]
    if good >= 1: return "B", RARITY_COLORS["B"]
    return "C", RARITY_COLORS["C"]


def _grade_from_score(score):
    if score >= 95: return "SS", RARITY_COLORS["SS"]
    if score >= 90: return "S", RARITY_COLORS["S"]
    if score >= 80: return "A", RARITY_COLORS["A"]
    if score >= 70: return "B", RARITY_COLORS["B"]
    return "C", RARITY_COLORS["C"]


def _count_set_bonuses(discs):
    counts = {}
    for d in discs:
        name = d.get("set_name") or f"Set {d.get('set_id', '?')}"
        counts[name] = counts.get(name, 0) + 1
    return sorted(counts.items(), key=lambda x: -x[1])


def _radial_gradient(w, h, center_color, edge_color):
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    cx, cy = w // 2, h // 2
    max_d = np.sqrt(cx**2 + cy**2)
    y, x = np.ogrid[:h, :w]
    d = np.clip(np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / max_d, 0, 1)
    for i in range(3):
        arr[:, :, i] = (center_color[i] * (1 - d) + edge_color[i] * d).astype(np.uint8)
    arr[:, :, 3] = 255
    return Image.fromarray(arr, "RGBA")


def _draw_mindscape_dots(draw, x, y, count, accent, max_count=6):
    size = 9
    gap = 15
    for i in range(max_count):
        cx = x + i * gap
        cy = y + size // 2
        pts = [(cx, cy - size//2), (cx + size//2, cy),
               (cx, cy + size//2), (cx - size//2, cy)]
        if i < count:
            draw.polygon(pts, fill=accent)
        else:
            draw.polygon(pts, outline=(70, 76, 96), width=1)


def _format_stat_name(name: str) -> str:
    repl = {
        "Percent ": "", "Anomaly Proficiency": "Anom Prof",
        "Anomaly Mastery": "Anom Mast", "CRIT Rate": "CR", "CRIT DMG": "CD",
    }
    for k, v in repl.items():
        name = name.replace(k, v)
    return name


def _stat_color(name: str) -> tuple:
    if "CRIT" in name or "Crit" in name:
        return (120, 220, 255)
    if "Percent" in name or name in ("PEN Ratio",):
        return GOLD
    if "Anomaly Proficiency" in name:
        return (195, 130, 240)
    return TEXT_G


# ═══════════════════════════════════════════════════════════════════════════

async def render_build_card(uid: int, agent_name: str) -> Optional[bytes]:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}/uid/{uid}/agente/{agent_name}",
                               timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status != 200:
                return None
            data = await r.json()

        # Rank del agente (S/A)
        agent_rank = None
        try:
            async with session.get(f"{API_BASE}/api/agentes/{urllib.parse.quote(agent_name)}/detalle",
                                   timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    detalle = await r.json()
                    agent_rank = detalle.get("rango")
        except Exception:
            pass

        set_names = {}
        try:
            async with session.get(f"{API_BASE}/api/uid/{uid}/completo",
                                   timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    completo = await r.json()
                    for ag in completo.get("agentes", []):
                        if ag.get("nombre") == agent_name or ag.get("name") == agent_name:
                            parsed = ag.get("discos_parseados", {})
                            for slot, d in parsed.items():
                                set_names[int(slot)] = d.get("set", "")
                            break
        except Exception:
            pass

        char_art = None
        try:
            async with session.get(f"{API_BASE}/images/builds/{agent_name}.png",
                                   timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    char_art = Image.open(io.BytesIO(await r.read())).convert("RGBA")
        except Exception:
            pass

        wengine_img = None
        try:
            weng_url = f"{API_BASE}/images/wengine/{urllib.parse.quote(data['agente']['weapon']['name'])}.png"
            async with session.get(weng_url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    wengine_img = Image.open(io.BytesIO(await r.read())).convert("RGBA")
        except Exception:
            pass

        disc_imgs = {}
        for slot, sname in set_names.items():
            if not sname:
                continue
            try:
                disc_url = f"{API_BASE}/images/discos/{urllib.parse.quote(sname)}.png"
                async with session.get(disc_url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status == 200:
                        disc_imgs[slot] = Image.open(io.BytesIO(await r.read())).convert("RGBA")
            except Exception:
                pass

    for disc in data["agente"]["discs"]:
        disc["set_name"] = set_names.get(disc["slot"], f"Set {disc['set_id']}")

    return _render(data, char_art, wengine_img, disc_imgs, uid, agent_rank)




# ══════════════════════════════════════════════════════════════════════════
# v10 LV999 HELPERS — adaptive colors, luxury bg, watermark, holo, modules
# ══════════════════════════════════════════════════════════════════════════

PREMIUM_FONT_DIR = "/home/ubuntu/.local/share/fonts/premium"


def _rgb_to_hue(r, g, b):
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    return h * 360, s, l


def _extract_signature_hue(char_art):
    """Extract representative accent hue from character art (HSL-normalized)."""
    if char_art is None:
        return None
    img = char_art.copy()
    img.thumbnail((256, 256), Image.LANCZOS)
    rgba = np.array(img.convert("RGBA"))
    r, g, b, a = rgba[..., 0], rgba[..., 1], rgba[..., 2], rgba[..., 3]
    valid = a > 120
    rf, gf, bf = r.astype(np.float32) / 255, g.astype(np.float32) / 255, b.astype(np.float32) / 255
    mx = np.maximum(np.maximum(rf, gf), bf)
    mn = np.minimum(np.minimum(rf, gf), bf)
    v = mx
    s = np.where(mx > 0, (mx - mn) / (mx + 1e-6), 0)
    valid = valid & (v > 0.12) & (v < 0.92) & (s > 0.20)
    # Compute hue to detect & discard skin tones
    h = np.zeros_like(v)
    mask_r = (mx == rf)
    mask_g = (mx == gf)
    mask_b = (mx == bf)
    delta = mx - mn + 1e-6
    h = np.where(mask_r, ((gf - bf) / delta) % 6, h)
    h = np.where(mask_g, ((bf - rf) / delta) + 2, h)
    h = np.where(mask_b, ((rf - gf) / delta) + 4, h)
    h = h * 60
    h = np.where(h < 0, h + 360, h)
    skin = (h > 10) & (h < 40) & (s > 0.15) & (s < 0.55) & (v > 0.5)
    valid = valid & ~skin

    masked = rgba.copy()
    masked[~valid] = 0
    img_masked = Image.fromarray(masked, "RGBA")
    rgb_img = Image.new("RGB", img_masked.size, (0, 0, 0))
    rgb_img.paste(img_masked, mask=img_masked.split()[3])
    q = rgb_img.quantize(colors=10, method=Image.FASTOCTREE)
    palette = q.getpalette()[:30]
    counts = q.getcolors()
    best_score = -1
    best_hue = None
    for count, idx in counts:
        cr = palette[idx * 3]
        cg = palette[idx * 3 + 1]
        cb = palette[idx * 3 + 2]
        if cr + cg + cb < 30:
            continue
        ph, ps, pl = _rgb_to_hue(cr, cg, cb)
        vibrancy = ps * (1 - abs(pl - 0.55) * 2)
        score = count * max(ps, 0.05) * max(vibrancy, 0.1)
        if score > best_score:
            best_score = score
            best_hue = ph
    return best_hue


def _derive_palette_from_hue(hue, fallback_rgb=None):
    """Build a harmonic palette from a hue (degrees) with hue-specific tweaks."""
    if hue is None:
        if fallback_rgb:
            hue, _, _ = _rgb_to_hue(*fallback_rgb)
        else:
            hue = 270
    s_main = 0.55
    l_main = 0.62
    if 90 <= hue <= 150:
        s_main = 0.42
        l_main = 0.65
    elif 50 <= hue <= 70:
        s_main = 0.55
        l_main = 0.72
    return {
        "accent":       _hsl(hue, s_main, l_main),
        "accent_muted": _hsl(hue, s_main * 0.55, l_main * 0.85),
        "accent_soft":  _hsl(hue, s_main * 0.4, min(l_main * 1.15, 0.95)),
        "accent_deep":  _hsl(hue, s_main * 0.75, l_main * 0.55),
    }


def _bg_luxury(w, h, palette):
    """Layered BG: base gradient + diagonal guilloché + atmospheric light."""
    accent_deep = palette["accent_deep"]
    y, x = np.ogrid[:h, :w]
    tx = (w - x) / w
    ty = 1 - ((h - y) / h)
    t = (tx * 0.6 + ty * 0.4)
    t = np.clip(t, 0, 1)
    c_bright = tuple(int(c * 0.18 + 16) for c in accent_deep)
    c_dark = (8, 10, 18)
    arr = np.zeros((h, w, 3), dtype=np.float32)
    for i in range(3):
        arr[..., i] = c_bright[i] * t + c_dark[i] * (1 - t)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    base = Image.fromarray(arr, "RGB").convert("RGBA")
    base = _dither_rgb(base, amplitude=0.8, seed=7)

    lines = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines)
    spacing = 11
    line_color = (*palette["accent_soft"], 10)
    for d in range(-h, w, spacing):
        ld.line([(d, 0), (d + h, h)], fill=line_color, width=1)
    base = Image.alpha_composite(base, lines)

    atmo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ad = ImageDraw.Draw(atmo)
    col_w = int(w * 0.35)
    col_x = (w - col_w) // 2 + int(w * 0.25)
    for dy in range(int(h * 0.75)):
        t_a = 1 - (dy / (h * 0.75))
        alpha = int(18 * t_a)
        ad.line([(col_x, dy), (col_x + col_w, dy)],
                fill=(*palette["accent"], alpha))
    atmo = atmo.filter(ImageFilter.GaussianBlur(30))
    base = Image.alpha_composite(base, atmo)

    base_rgb = base.convert("RGB").filter(ImageFilter.GaussianBlur(0.5))
    return base_rgb.convert("RGBA")


def _hero_watermark(img, name, palette, hero_w=480, H=900):
    """Giant agent name rotated, behind char art, clipped to hero area."""
    font_size = 280
    try:
        font = ImageFont.truetype(f"{PREMIUM_FONT_DIR}/Orbitron-Black.ttf", font_size)
    except Exception:
        font = _font("black", font_size)
    text_upper = name.upper()
    tmp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = tmp_draw.textbbox((0, 0), text_upper, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    canvas = Image.new("RGBA", (tw + 80, th + 80), (0, 0, 0, 0))
    cd = ImageDraw.Draw(canvas)
    cd.text((40 - bbox[0], 40 - bbox[1]), text_upper,
            font=font, fill=(*palette["accent_soft"], 40))
    rotated = canvas.rotate(8, resample=Image.BICUBIC, expand=True)
    rw, rh = rotated.size
    pos_x = -int(rw * 0.1)
    pos_y = 180
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    layer.paste(rotated, (pos_x, pos_y), rotated)
    clip_mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(clip_mask).rectangle((0, 0, hero_w, H), fill=255)
    final = Image.new("RGBA", img.size, (0, 0, 0, 0))
    final.paste(layer, (0, 0), clip_mask)
    img.alpha_composite(final)


from functools import lru_cache


@lru_cache(maxsize=16)
def _holo_gradient(w, h):
    """Opalescent holographic gradient with specular highlights."""
    colors = [
        (195, 205, 228),
        (174, 185, 232),
        (210, 195, 228),
        (235, 235, 244),
        (180, 215, 226),
        (198, 208, 230),
    ]
    stops = [0.0, 0.22, 0.42, 0.52, 0.74, 1.0]
    arr = np.zeros((h, w, 3), dtype=np.float32)
    for x in range(w):
        t = x / max(w - 1, 1)
        for i in range(len(stops) - 1):
            if stops[i] <= t <= stops[i + 1]:
                lt = (t - stops[i]) / (stops[i + 1] - stops[i])
                lt = lt * lt * (3.0 - 2.0 * lt)
                c1, c2 = colors[i], colors[i + 1]
                for k in range(3):
                    arr[:, x, k] = c1[k] * (1 - lt) + c2[k] * lt
                break
    for sx, inten, width in [(0.48, 0.45, 3), (0.56, 0.35, 4), (0.68, 0.22, 3)]:
        line_x = int(sx * w)
        for dx in range(-width, width + 1):
            xl = line_x + dx
            if 0 <= xl < w:
                falloff = (1 - abs(dx) / (width + 1)) * inten
                arr[:, xl] = arr[:, xl] * (1 - falloff) + 255 * falloff
    for y in range(h):
        ty = abs(y - h / 2) / (h / 2 + 1)
        arr[y] *= (1.0 - ty * 0.08)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB").convert("RGBA")


def _holo_text(img, pos, text, font, holo_img,
               glow_color=None, glow_radius=0, glow_intensity=80):
    """Render text filled with holographic gradient."""
    tmp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = tmp_draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = max(glow_radius * 3, 8)
    cw, ch = tw + pad * 2, th + pad * 2
    mask = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(mask).text((pad - bbox[0], pad - bbox[1]), text,
                               font=font, fill=255)
    holo_resized = holo_img.resize((cw, ch), Image.LANCZOS).convert("RGBA")
    holo_resized.putalpha(mask)
    if glow_color and glow_radius > 0:
        blurred = mask.filter(ImageFilter.GaussianBlur(glow_radius))
        glow_layer = Image.new("RGBA", (cw, ch), (*glow_color, glow_intensity))
        glow_layer.putalpha(blurred)
        img.alpha_composite(glow_layer, (pos[0] - pad, pos[1] - pad))
    img.alpha_composite(holo_resized, (pos[0] - pad, pos[1] - pad))


def _draw_rarity_strip(img, x1, y1, x2, y2, rc, is_4l):
    w = x2 - x1
    h = y2 - y1
    strip = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(strip)
    top_color = rc
    gold = RARITY_COLORS["SS"]
    bot_color = tuple(int(rc[i] * 0.4 + gold[i] * 0.6) for i in range(3)) if is_4l else rc
    for dy in range(h):
        t = dy / max(h - 1, 1)
        r = int(top_color[0] * (1 - t) + bot_color[0] * t)
        g = int(top_color[1] * (1 - t) + bot_color[1] * t)
        b = int(top_color[2] * (1 - t) + bot_color[2] * t)
        sd.line([(0, dy), (w, dy)], fill=(r, g, b, 255))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=2, fill=255)
    strip.putalpha(mask)
    img.alpha_composite(strip, (x1, y1))


def _draw_bq_module(img, box, grade, grade_color, score, palette):
    """204×180 centered BQ module. score>=95 → SOVEREIGN with holo."""
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2

    is_sovereign = score >= 95
    draw = ImageDraw.Draw(img)
    score_txt = f"{score:.1f}%"

    if is_sovereign:
        grade_label = "SOVEREIGN"
        sv_size = 34
        sv_f = _f("orbitron_black", sv_size)
        while sv_size > 22:
            sv_f = _f("orbitron_black", sv_size)
            sv_w = draw.textbbox((0, 0), grade_label, font=sv_f)[2]
            if sv_w <= w - 24:
                break
            sv_size -= 2
        sv_bbox = draw.textbbox((0, 0), grade_label, font=sv_f)
        sv_w = sv_bbox[2] - sv_bbox[0]
        sv_h = sv_bbox[3] - sv_bbox[1]

        score_f = _f("orbitron_black", 44)
        sc_bbox = draw.textbbox((0, 0), score_txt, font=score_f)
        sc_w = sc_bbox[2] - sc_bbox[0]
        sc_h = sc_bbox[3] - sc_bbox[1]

        line_h = 2
        gap1 = 8
        gap2 = 16
        total_h = sv_h + gap1 + sc_h + gap2 + line_h
        start_y = cy - total_h // 2

        holo = _holo_gradient(200, 80)
        _holo_text(img, (cx - sv_w // 2, start_y), grade_label, sv_f, holo,
                    glow_color=(230, 230, 250), glow_radius=6, glow_intensity=70)
        draw = ImageDraw.Draw(img)

        sc_y = start_y + sv_h + gap1
        _clean_gradient_text(img, (cx - sc_w // 2, sc_y), score_txt, score_f,
                              color_top=TEXT_W, color_bottom=TEXT_W)
        draw = ImageDraw.Draw(img)

        line_y = sc_y + sc_h + gap2
        line_w_px = 60
        line_layer = Image.new("RGBA", (line_w_px, line_h), (195, 205, 230, 180))
        img.alpha_composite(line_layer, (cx - line_w_px // 2, line_y))
    else:
        grade_f = _f("orbitron_black", 64)
        gb = draw.textbbox((0, 0), grade, font=grade_f)
        gw = gb[2] - gb[0]
        gh = gb[3] - gb[1]

        score_f = _f("orbitron_black", 26)
        sb = draw.textbbox((0, 0), score_txt, font=score_f)
        sw = sb[2] - sb[0]
        sh = sb[3] - sb[1]

        line_h = 2
        gap1 = 10
        gap2 = 16
        total_h = gh + gap1 + sh + gap2 + line_h
        start_y = cy - total_h // 2

        _clean_gradient_text(img, (cx - gw // 2, start_y), grade, grade_f,
                              color_top=(255, 255, 255),
                              color_bottom=grade_color,
                              glow_color=grade_color, glow_radius=8,
                              glow_intensity=65)
        draw = ImageDraw.Draw(img)

        sc_y = start_y + gh + gap1
        _clean_gradient_text(img, (cx - sw // 2, sc_y), score_txt, score_f,
                              color_top=TEXT_W, color_bottom=TEXT_W)
        draw = ImageDraw.Draw(img)

        line_y = sc_y + sh + gap2
        line_w_px = 50
        line_layer = Image.new("RGBA", (line_w_px, line_h), (*palette["accent"], 160))
        img.alpha_composite(line_layer, (cx - line_w_px // 2, line_y))


def _draw_disc_module(img, box, disc, disc_img, palette):
    """LV999 disc card with rarity strip + icon upper-right + substats."""
    x1, y1, x2, y2 = box
    disc_w = x2 - x1
    disc_h = y2 - y1

    _glass_clean_line(img, box, radius=12)
    draw = ImageDraw.Draw(img)

    rating, rc = _rate_disc(disc)
    liner = _disc_liner_type(disc)
    is_4l = liner == "4L"

    _draw_rarity_strip(img, x1 + 4, y1 + 12, x1 + 8, y2 - 12, rc, is_4l)
    draw = ImageDraw.Draw(img)

    _text(draw, (x1 + 16, y1 + 10), f"DISC {disc['slot']}",
          _f("manrope_med", 10), TEXT_D)
    _text_right(draw, x2 - 14, y1 + 10,
                f"+{disc['level']}", _f("manrope_med", 10), TEXT_DIM)

    rl_font = _f("orbitron_black", 28)
    rl_bbox = draw.textbbox((0, 0), rating, font=rl_font)
    rl_w = rl_bbox[2] - rl_bbox[0]
    rl_x = x2 - 14 - rl_w
    rl_y = y1 + 26
    if rating in ("S", "SS"):
        holo = _holo_gradient(max(rl_w + 20, 60), 50)
        _holo_text(img, (rl_x, rl_y), rating, rl_font, holo,
                    glow_color=(220, 220, 245), glow_radius=5, glow_intensity=70)
    else:
        _clean_gradient_text(img, (rl_x, rl_y), rating, rl_font,
                              color_top=(255, 255, 255), color_bottom=rc,
                              glow_color=rc, glow_radius=4, glow_intensity=50)
    draw = ImageDraw.Draw(img)

    if disc_img is not None:
        icon_size = 22
        si = disc_img.resize((icon_size, icon_size), Image.LANCZOS)
        img.paste(si, (x2 - 14 - icon_size, y1 + 56), si)
        draw = ImageDraw.Draw(img)

    main = disc["main_stat"]
    main_name = _format_stat_name(main["name"])
    _text(draw, (x1 + 16, y1 + 32), main_name.upper(),
          _font("medium", 10), TEXT_D)
    _text(draw, (x1 + 16, y1 + 48), main["value"],
          _font("black", 26), TEXT_W)

    sep_y = y1 + 82
    draw.line([(x1 + 14, sep_y), (x2 - 14, sep_y)],
              fill=(*palette["accent_muted"], 40), width=1)

    subs = disc.get("sub_stats", [])[:4]
    for j, sub in enumerate(subs):
        sub_y = y1 + 90 + j * 22
        sub_name = _format_stat_name(sub["name"])
        is_good = (sub["name"] in GOOD_STATS or "CRIT" in sub["name"])
        color = _stat_color(sub["name"]) if is_good else TEXT_G
        rolls = _count_rolls(sub["name"], sub["value"])
        name_x = x1 + 26
        if is_good:
            draw.ellipse([x1 + 16, sub_y + 5, x1 + 20, sub_y + 9], fill=color)
        _text(draw, (name_x, sub_y), sub_name,
              _font("medium" if is_good else "light", 12), color)
        _text_right(draw, x2 - 14, sub_y,
                    sub["value"], _font("bold", 12),
                    color if is_good else TEXT_G)
        if rolls > 0:
            br_x = name_x
            br_y = sub_y + 15
            seg_w = 9
            seg_gap = 2
            seg_h = 3
            for k in range(5):
                seg_x = br_x + k * (seg_w + seg_gap)
                if k < rolls:
                    fill = (color if is_good else TEXT_D)
                else:
                    fill = (38, 42, 56, 130)
                if isinstance(fill, tuple) and len(fill) == 3:
                    fill = (*fill, 255)
                tmp_l = Image.new("RGBA", (seg_w + 1, seg_h + 1), (0, 0, 0, 0))
                ImageDraw.Draw(tmp_l).rounded_rectangle(
                    [0, 0, seg_w, seg_h], radius=1, fill=fill)
                img.alpha_composite(tmp_l, (seg_x, br_y))
            draw = ImageDraw.Draw(img)


# ══════════════════════════════════════════════════════════════════════════
# v10 LV999 RENDER — full luxury redesign
# ══════════════════════════════════════════════════════════════════════════

def _render(data, char_art, wengine_img, disc_imgs, uid, agent_rank=None):
    """LV999 build card render — v10.
    Features:
      - Adaptive color extracted from char art (HSL-normalized)
      - Layered luxury bg: diagonal gradient + guilloché + atmospheric light
      - Giant rotated agent-name watermark behind hero
      - Condensed 4×2 stats + BQ side module (Sovereign if score>=95)
      - Disc lv999: rarity gradient strip, icon upper-right, holo S rating
      - Holographic gradient on S/SS rating letters and SOVEREIGN text
    """
    agent = data["agente"]
    eval_data = data["evaluacion"]
    nick = data["nick"]

    element = agent.get("element", "")
    spec = agent.get("specialty", "")
    spec_color = SPEC_COLORS.get(spec, DEFAULT_ACCENT)

    hue = _extract_signature_hue(char_art)
    palette = _derive_palette_from_hue(hue, fallback_rgb=ELEM_COLORS.get(element, DEFAULT_ACCENT))
    accent = palette["accent"]

    W, H = 1400, 900
    img = Image.new("RGBA", (W, H), BG_DARK)

    tinted = tuple(int(c * 0.08 + BG_DARK[i] * 0.92) for i, c in enumerate(accent))
    bg_left = _radial_gradient(W, H, tinted, BG_DARK)
    img = Image.alpha_composite(img, bg_left)

    right_x0 = 480
    right_w = W - right_x0
    right_bg = _bg_luxury(right_w, H, palette)
    img.paste(right_bg, (right_x0, 0), right_bg)

    _hero_watermark(img, agent["name"], palette, hero_w=480, H=H)

    hero_w = 480
    if char_art:
        ratio = max(hero_w / char_art.width, H / char_art.height)
        new_w = int(char_art.width * ratio)
        new_h = int(char_art.height * ratio)
        art = char_art.resize((new_w, new_h), Image.LANCZOS)
        off_x = (hero_w - new_w) // 2
        off_y = (H - new_h) // 2
        hero_layer = Image.new("RGBA", (hero_w, H), (0, 0, 0, 0))
        hero_layer.paste(art, (off_x, off_y), art)
        img.paste(hero_layer, (0, 0), hero_layer)

    overlay = Image.new("RGBA", (hero_w, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for y in range(H):
        t = y / H
        alpha = int(20 + 200 * (t ** 2.2))
        od.line([(0, y), (hero_w, y)], fill=(BG_DARK[0], BG_DARK[1], BG_DARK[2], alpha))
    img = Image.alpha_composite(img, _extend(overlay, W, H, offset=(0, 0)))

    edge_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ed = ImageDraw.Draw(edge_layer)
    ed.rectangle([hero_w, 0, hero_w + 1, H], fill=(*accent, 140))
    edge_layer = edge_layer.filter(ImageFilter.GaussianBlur(2))
    img = Image.alpha_composite(img, edge_layer)

    draw = ImageDraw.Draw(img)

    _composite_rect(img, (24, 24, 134, 56), 6, (*accent, 220))
    draw = ImageDraw.Draw(img)
    _text_center(draw, 79, 31, element.replace("_", " ").title(),
                 _font("black", 13), (10, 10, 15))
    if spec:
        _composite_rect(img, (144, 24, 254, 56), 6, (*spec_color, 50),
                        outline=spec_color, width=2)
        draw = ImageDraw.Draw(img)
        _text_center(draw, 199, 31, SPEC_LABELS.get(spec, spec),
                     _font("black", 13), spec_color)

    name_text = agent["name"].upper()
    max_name_w = hero_w - 48
    name_size = 72
    while name_size > 36:
        f = _font("black", name_size)
        if ImageDraw.Draw(img).textbbox((0, 0), name_text, font=f)[2] <= max_name_w:
            break
        name_size -= 4
    _glow_text_contained(img, (24, 620), name_text,
                          _font("black", name_size), TEXT_W, accent, radius=12)
    draw = ImageDraw.Draw(img)

    _text(draw, (24, 702), f"LV. {agent['level']}", _font("bold", 22), TEXT_G)
    _draw_mindscape_dots(draw, 144, 712, agent.get("mindscape", 0), accent)

    _text(draw, (24, 748), nick, _font("bold", 18), accent)
    nick_w = draw.textbbox((0, 0), nick, font=_font("bold", 18))[2]
    _text(draw, (32 + nick_w, 752), f"· UID {uid}", _font("medium", 14), TEXT_D)
    _text(draw, (24, 776), "Z E N L E S S   Z O N E   Z E R O",
          _font("medium", 10), TEXT_DIM)

    # ═══ RIGHT CONTENT ═════════════════════════════════════════════════
    content_x = hero_w + 30
    content_w = W - content_x - 30

    _text(draw, (content_x, 32), "BUILD SHOWCASE", _font("black", 20), TEXT_W)
    _text(draw, (content_x, 58), f"Analysis • {nick}", _font("medium", 13), TEXT_D)
    amark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(amark).rounded_rectangle(
        (content_x, 80, content_x + 42, 82), radius=1, fill=(*accent, 200))
    img.alpha_composite(amark)
    draw = ImageDraw.Draw(img)

    # ═══ STATS PANEL + BQ SIDE MODULE ══════════════════════════════════
    STATS_W = 640
    BQ_W = 204
    GAP_RIGHT = content_w - STATS_W - BQ_W

    stats_y = 100
    stats_h = 180
    stats_box = (content_x, stats_y, content_x + STATS_W, stats_y + stats_h)
    _glass_clean_line(img, stats_box, radius=12)
    draw = ImageDraw.Draw(img)

    ELEM_DMG_KEY = {
        "FIRE": "Fire DMG\xa0Bonus",
        "ICE": "Ice DMG\xa0Bonus",
        "FIRE_FROST": "Ice DMG\xa0Bonus",
        "ELECTRIC": "Electric DMG\xa0Bonus",
        "ETHER": "Ether DMG Bonus",
        "PHYSICAL": "Physical DMG Bonus",
    }
    elem_dmg = ELEM_DMG_KEY.get(element)

    def _v(k):
        return agent["stats"].get(k, {}).get("value", 0)

    if spec == "ANOMALY":
        key_stats = ["HP", "ATK", "DEF", "Impact",
                     "CRIT Rate", "CRIT DMG", "Anomaly Proficiency", "Anomaly Mastery"]
    elif spec == "ATTACK":
        key_stats = ["HP", "ATK", "DEF", "Impact",
                     "CRIT Rate", "CRIT DMG", "PEN Ratio", elem_dmg or "PEN"]
    elif spec == "STUN":
        key_stats = ["HP", "ATK", "DEF", "Impact",
                     "CRIT Rate", "CRIT DMG", "Energy Regen", "Anomaly Proficiency"]
    elif spec == "SUPPORT":
        key_stats = ["HP", "ATK", "DEF", "Impact",
                     "CRIT Rate", "CRIT DMG", "Energy Regen", "PEN Ratio"]
    elif spec == "DEFENSE":
        key_stats = ["HP", "ATK", "DEF", "Impact",
                     "CRIT Rate", "CRIT DMG", "Energy Regen", "PEN Ratio"]
    elif spec == "RUPTURE":
        key_stats = ["HP", "ATK", "DEF", "Impact",
                     "CRIT Rate", "CRIT DMG", "Sheer Force", "Sheer DMG Bonus"]
    else:
        key_stats = ["HP", "ATK", "DEF", "Impact",
                     "CRIT Rate", "CRIT DMG", "PEN Ratio", "Anomaly Proficiency"]

    STAT_DISPLAY = {
        "Anomaly Proficiency": "ANOM PROF",
        "Anomaly Mastery": "ANOM MAST",
        "Energy Regen": "ENERGY REGEN",
        "CRIT Rate": "CRIT RATE",
        "CRIT DMG": "CRIT DMG",
        "PEN Ratio": "PEN RATIO",
        "PEN": "PEN",
        "Fire DMG\xa0Bonus": "FIRE DMG",
        "Ice DMG\xa0Bonus": "ICE DMG",
        "Electric DMG\xa0Bonus": "ELEC DMG",
        "Ether DMG Bonus": "ETHER DMG",
        "Physical DMG Bonus": "PHYS DMG",
        "Sheer DMG Bonus": "SHEER DMG",
        "Sheer Force": "SHEER FORCE",
        "Impact": "IMPACT",
    }

    COLS = 4
    ROWS = 2
    stat_w_cell = STATS_W // COLS
    stat_cell_h = stats_h // ROWS
    for i, skey in enumerate(key_stats[:COLS * ROWS]):
        col, row = i % COLS, i // COLS
        sx = content_x + col * stat_w_cell
        sy = stats_y + row * stat_cell_h
        stat = agent["stats"].get(skey, {})
        value = stat.get("formatted", "—")
        stat_color = TEXT_W
        if skey == "CRIT Rate":
            cr = _v("CRIT Rate") / 100
            cd = _v("CRIT DMG") / 100
            if 0 < cr and 0 < cd and 1.8 <= (cd / cr) <= 2.3:
                stat_color = GOLD
        if value in ("0", "0.0%", "0.0", "—", 0):
            stat_color = TEXT_DIM
        label = STAT_DISPLAY.get(skey, skey.upper())
        _text(draw, (sx + 16, sy + 18), label,
              _font("medium", 9), TEXT_D)
        _text(draw, (sx + 16, sy + 34), value,
              _font("black", 22), stat_color)
        if col < COLS - 1:
            draw.line([(sx + stat_w_cell - 1, sy + 14),
                       (sx + stat_w_cell - 1, sy + stat_cell_h - 14)],
                      fill=(90, 95, 115, 50), width=1)
        if row == 0:
            draw.line([(content_x + 16, stats_y + stat_cell_h),
                       (content_x + STATS_W - 16, stats_y + stat_cell_h)],
                      fill=(90, 95, 115, 50), width=1)

    bq_x = content_x + STATS_W + GAP_RIGHT
    bq_box = (bq_x, stats_y, bq_x + BQ_W, stats_y + stats_h)
    _glass_clean_line(img, bq_box, radius=12)
    draw = ImageDraw.Draw(img)
    score = eval_data["calidad_pct"]
    grade, grade_color = _grade_from_score(score)
    _draw_bq_module(img, bq_box, grade, grade_color, score, palette)
    draw = ImageDraw.Draw(img)

    # ═══ WEAPON CARD ═══════════════════════════════════════════════════
    weap_y = stats_y + stats_h + 15
    weap_h = 90
    weap_box = (content_x, weap_y, content_x + content_w, weap_y + weap_h)
    _glass_clean_line(img, weap_box, radius=12)
    draw = ImageDraw.Draw(img)

    if wengine_img:
        ws = wengine_img.resize((70, 70), Image.LANCZOS)
        img.paste(ws, (content_x + 12, weap_y + 10), ws)
        draw = ImageDraw.Draw(img)

    rarity = agent["weapon"].get("rarity", 4)
    rarity_color = GOLD if rarity >= 5 else (180, 110, 220) if rarity >= 4 else (110, 180, 255)
    draw.rounded_rectangle([content_x + 5, weap_y + 14,
                             content_x + 8, weap_y + 76],
                            radius=2, fill=rarity_color)

    _text(draw, (content_x + 95, weap_y + 12), "W-ENGINE",
          _f("manrope_med", 10), TEXT_D)
    _text(draw, (content_x + 95, weap_y + 26), agent["weapon"]["name"],
          _font("bold", 19), TEXT_W)
    refi = f"R{agent['weapon']['refinement']}"
    lvl = f"Lv.{agent['weapon']['level']}"
    _text(draw, (content_x + 95, weap_y + 56), refi, _font("black", 14), GOLD)
    _text(draw, (content_x + 125, weap_y + 56), "•",
          _font("medium", 14), TEXT_D)
    _text(draw, (content_x + 140, weap_y + 56), lvl,
          _font("medium", 14), TEXT_G)

    ms = agent["weapon"]["main_stat"]
    _text_right(draw, content_x + content_w - 20, weap_y + 18,
                ms["name"].upper(), _f("manrope_med", 10), TEXT_D)
    _text_right(draw, content_x + content_w - 20, weap_y + 34,
                ms["value"], _font("black", 28), TEXT_W)

    # ═══ DISC GRID ═════════════════════════════════════════════════════
    disc_start_y = weap_y + weap_h + 15
    footer_reserved = 90
    disc_grid_h = H - disc_start_y - footer_reserved - 15
    gap = 10
    disc_w = (content_w - gap * 2) // 3
    disc_h = (disc_grid_h - gap) // 2

    for i, disc in enumerate(agent.get("discs", [])[:6]):
        col, row = i % 3, i // 3
        dx = content_x + col * (disc_w + gap)
        dy = disc_start_y + row * (disc_h + gap)
        _draw_disc_module(img, (dx, dy, dx + disc_w, dy + disc_h),
                           disc, disc_imgs.get(disc.get("slot")), palette)

    draw = ImageDraw.Draw(img)

    # ═══ FOOTER ═══════════════════════════════════════════════════════
    footer_y = disc_start_y + disc_grid_h + 10
    footer_h = H - footer_y - 15
    footer_box = (content_x, footer_y, content_x + content_w, footer_y + footer_h)
    _glass_clean_line(img, footer_box, radius=12)
    draw = ImageDraw.Draw(img)

    _text(draw, (content_x + 16, footer_y + 12), "SET BONUSES",
          _f("manrope_med", 10), TEXT_D)

    bonuses = _count_set_bonuses(agent.get("discs", []))
    bx = content_x + 16
    by = footer_y + 32
    for sname, count in bonuses:
        if count < 2:
            continue
        tier = 4 if count >= 4 else 2
        tag_color = RARITY_COLORS["SS"] if tier == 4 else RARITY_COLORS["A"]
        tag_text = f"{tier}pc · {sname}"
        tf = _font("bold", 14)
        tw = draw.textbbox((0, 0), tag_text, font=tf)[2] + 28
        fill_bg = tuple(int(c * 0.15 + BG_DARK[i] * 0.85) for i, c in enumerate(tag_color))
        _rounded_rect(draw, (bx, by, bx + tw, by + 32), 8,
                      fill=fill_bg, outline=tag_color, width=1)
        prefix = f"{tier}pc"
        prefix_f = _font("black", 14)
        prefix_w = draw.textbbox((0, 0), prefix, font=prefix_f)[2]
        _text(draw, (bx + 14, by + 8), prefix, prefix_f, tag_color)
        _text(draw, (bx + 14 + prefix_w + 8, by + 8),
              sname, _font("bold", 14), TEXT_W)
        bx += tw + 10

    rolls_right = content_x + content_w - 16
    rolls_num_y = footer_y + 32
    leftmost_x = _draw_rolls_inline(img, draw, rolls_right, rolls_num_y,
                                      eval_data, P_PASTEL_COOL)
    _text(draw, (leftmost_x, footer_y + 12), "ROLLS BREAKDOWN",
          _f("manrope_med", 10), TEXT_D)

    # Accent bars top/bottom with lateral fade
    def _paint_accent_bar(y_start, y_end):
        bar = Image.new("RGBA", (W, y_end - y_start), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bar)
        fade = 60
        for x in range(W):
            if x < fade:
                a = int(255 * (x / fade))
            elif x > W - fade:
                a = int(255 * ((W - x) / fade))
            else:
                a = 255
            bd.line([(x, 0), (x, y_end - y_start)], fill=(*accent, a))
        img.alpha_composite(bar, (0, y_start))
    _paint_accent_bar(0, 2)
    _paint_accent_bar(H - 2, H)

    # Rounded canvas corners
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1],
                                             radius=24, fill=255)
    img.putalpha(mask)

    buf = io.BytesIO()
    img.save(buf, "PNG", compress_level=1)
    return buf.getvalue()


def _extend(layer, W, H, offset=(0, 0)):
    """Extender layer al tamaño W x H con offset."""
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    base.paste(layer, offset, layer)
    return base

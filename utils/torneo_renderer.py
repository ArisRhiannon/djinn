"""
TorneoRenderer v4 — Motor visual premium para el TorneoCog.

Solo PIL (Pillow 9+). Sin dependencias extra.
Gradientes • Sombras • Glow • Tipografía jerárquica • Composición sólida.

Genera UNA imagen vertical por fase: header atmosférico, eventos con
barras de acento, PFPs con sombra, burbujas de diálogo alternadas,
y recuento de vivos/caídos con presentación dramática.

API pública: renderizar_fase_completa(nombre_fase, escenario, eventos, recuento, pfp_cache) -> bytes
"""

from __future__ import annotations

import io
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES DE DISEÑO — Premium Dark Solid
# ══════════════════════════════════════════════════════════════════════════════

CANVAS_WIDTH = 1200

# Superficies (jerarquía de elevación)
BG_DEEP      = (8,  9,  16)    # fondo canvas
BG_SURFACE   = (16, 18, 28)   # superficie base (header, eventos)
BG_ELEVATED  = (22, 24, 38)   # superficie elevada (burbujas, cards)
BG_HIGHLIGHT = (28, 30, 46)   # hover / detalle

# Acentos
GOLD         = (240, 192, 64)  # más cálido y rico
GOLD_DIM     = (160, 128, 40)
RED          = (231, 76, 60)   # más saturado
RED_DIM      = (160, 40, 30)
GREEN        = (46, 204, 113)  # vibrante
GREEN_DIM    = (25, 120, 60)
BLUE         = (52, 152, 219)
BLUE_DIM     = (30, 90, 140)

# Texto
TEXT_PRIMARY   = (235, 238, 248)
TEXT_SECONDARY = (150, 156, 180)
TEXT_MUTED     = (90, 96, 115)

# Bordes
BORDER_SUBTLE  = (38, 40, 56)
BORDER_MEDIUM  = (55, 58, 78)

# Sombras
SHADOW_COLOR   = (0, 0, 0)
SHADOW_STRONG  = 120   # alpha para shadow fuerte
SHADOW_SOFT    = 60    # alpha para shadow suave
GLOW_ALPHA     = 80    # alpha para glows

# Layout
PADDING         = 28
EVENT_SPACING   = 32
HEADER_HEIGHT   = 148
GRID_COLS       = 6

# PFP sizes
EVENT_PFP_SIZE  = 64
DIALOG_PFP_SIZE = 28
RECAP_PFP_SIZE  = 56

# Board
BOARD_PFP_SIZE  = 22
BOARD_COLS      = 4
BOARD_CELL_H    = 62
BOARD_CELL_PAD  = 10
BOARD_GAP       = 6

# Event accent bar
ACCENT_BAR_W    = 5
ACCENT_BAR_GAP  = 14

# Derived
EVT_CONTENT_X   = PADDING + ACCENT_BAR_W + ACCENT_BAR_GAP

# Burbujas
BUBBLE_MAX_FRAC = 0.68
BUBBLE_RADIUS   = 10

# Badge
BADGE_RADIUS    = 13


# ── Fuentes ───────────────────────────────────────────────────────────────────
_BOLD_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
_REGULAR_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]

_FONT_CACHE: Dict[Tuple[int, bool], ImageFont.FreeTypeFont] = {}


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Busca fuente con cache. Fallback tipografico inteligente."""
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    primary = _BOLD_PATHS if bold else _REGULAR_PATHS
    secondary = _REGULAR_PATHS if bold else _BOLD_PATHS
    for path in primary + secondary:
        try:
            font = ImageFont.truetype(path, size)
            _FONT_CACHE[key] = font
            return font
        except (OSError, IOError):
            pass
    font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


# ══════════════════════════════════════════════════════════════════════════════
# PRIMITIVAS VISUALES
# ══════════════════════════════════════════════════════════════════════════════

def _linear_gradient(w: int, h: int, top: Tuple[int, int, int],
                     bottom: Tuple[int, int, int]) -> Image.Image:
    """Gradiente vertical suave (numpy, rapido)."""
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    tr, tg, tb = top
    br, bg, bb = bottom
    for y in range(h):
        t = y / max(h - 1, 1)
        arr[y, :, 0] = int(tr + (br - tr) * t)
        arr[y, :, 1] = int(tg + (bg - tg) * t)
        arr[y, :, 2] = int(tb + (bb - tb) * t)
        arr[y, :, 3] = 255
    return Image.fromarray(arr, 'RGBA')


def _radial_glow(diameter: int, color: Tuple[int, int, int],
                 center_alpha: int = 120, edge_alpha: int = 0) -> Image.Image:
    """Glow radial circular centrado."""
    arr = np.zeros((diameter, diameter, 4), dtype=np.uint8)
    cx = cy = diameter / 2.0
    max_dist = diameter / 2.0
    for y in range(diameter):
        for x in range(diameter):
            dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2) / max_dist
            alpha = center_alpha + (edge_alpha - center_alpha) * dist
            alpha = max(0, min(255, int(alpha)))
            arr[y, x] = [*color, alpha]
    return Image.fromarray(arr, 'RGBA')


def _drop_shadow_rect(w: int, h: int, radius: int = 10,
                      offset: Tuple[int, int] = (3, 5),
                      alpha: int = 80, blur: int = 6) -> Image.Image:
    """Sombra para rectangulo redondeado."""
    pad = blur * 3
    total_w = w + pad * 2
    total_h = h + pad * 2
    shadow = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle(
        [pad + offset[0], pad + offset[1],
         pad + offset[0] + w, pad + offset[1] + h],
        radius=radius, fill=(0, 0, 0, alpha),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    result = Image.new("RGBA", (w + abs(offset[0]) + blur * 2,
                                 h + abs(offset[1]) + blur * 2), (0, 0, 0, 0))
    result.paste(shadow, (-blur, -blur), shadow)
    return result


def _drop_shadow_circle(size: int, alpha: int = 80, blur: int = 5,
                        offset: Tuple[int, int] = (2, 4)) -> Image.Image:
    """Sombra circular suave para PFPs."""
    pad = blur * 2 + 4
    total = size + pad * 2
    shadow = Image.new("RGBA", (total, total), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    cx = pad + size // 2 + offset[0]
    cy = pad + size // 2 + offset[1]
    r = size // 2
    sdraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, alpha))
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    return shadow


def _ring_glow(size: int, color: Tuple[int, int, int],
               inner_alpha: int = 120, thickness: int = 4) -> Image.Image:
    """Anillo de glow alrededor de PFP."""
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    cx = cy = size / 2.0
    outer_r = size / 2.0
    inner_r = outer_r - thickness
    for y in range(size):
        for x in range(size):
            dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            if inner_r <= dist <= outer_r:
                t = (dist - inner_r) / max(thickness, 1)
                alpha = int(inner_alpha * (1.0 - abs(t - 0.5) * 2))
                alpha = max(0, min(255, alpha))
                arr[y, x] = [*color, alpha]
    return Image.fromarray(arr, 'RGBA')


# ── Text helpers ──────────────────────────────────────────────────────────────

def _wrap(text: Any, font: ImageFont.FreeTypeFont, max_w: int,
          draw: ImageDraw.Draw) -> List[str]:
    if text is None:
        return []
    if not isinstance(text, str):
        text = str(text)
    if not text.strip():
        return []
    words = text.split()
    lines, cur = [], words[0]
    for w in words[1:]:
        test = cur + " " + w
        w_px = draw.textbbox((0, 0), test, font=font)[2]
        if w_px <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _text_w(text: str, font: ImageFont.FreeTypeFont, draw: ImageDraw.Draw) -> int:
    return draw.textbbox((0, 0), text, font=font)[2]


def _draw_text(draw: ImageDraw.Draw, pos: Tuple[int, int], text: Any,
               fill: Tuple, font: ImageFont.FreeTypeFont,
               anchor: Optional[str] = None) -> None:
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    try:
        if anchor:
            draw.text(pos, text, fill=fill, font=font, anchor=anchor)
        else:
            draw.text(pos, text, fill=fill, font=font)
    except TypeError:
        draw.text(pos, text, fill=fill, font=font)


def _draw_text_shadow(draw: ImageDraw.Draw, pos: Tuple[int, int], text: str,
                      fill: Tuple, font: ImageFont.FreeTypeFont,
                      shadow_alpha: int = 60,
                      anchor: Optional[str] = None) -> None:
    """Texto con sombra sutil para mejor legibilidad."""
    _draw_text(draw, (pos[0] + 1, pos[1] + 2), text,
               (0, 0, 0, shadow_alpha), font, anchor)
    _draw_text(draw, pos, text, fill, font, anchor)


# ── PFP helpers ───────────────────────────────────────────────────────────────

def _circle_mask(size: int) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size - 1, size - 1), fill=255)
    return m


def _circle_pfp(img: Image.Image, size: int) -> Image.Image:
    img = img.resize((size, size), Image.LANCZOS).convert("RGBA")
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(img, (0, 0), _circle_mask(size))
    return result


def _paste_circle_with_shadow(canvas: Image.Image, pfp: Image.Image,
                               cx: int, cy: int) -> None:
    """Pega PFP circular centrada en (cx, cy) con sombra suave."""
    r = pfp.width // 2
    shadow = _drop_shadow_circle(pfp.width, alpha=SHADOW_SOFT, blur=6)
    spad = shadow.width // 2
    canvas.paste(shadow, (cx - spad, cy - spad), shadow)
    canvas.paste(pfp, (cx - r, cy - r), pfp)


# ── Layout helpers ────────────────────────────────────────────────────────────

def _action_layout(pfp_count: int) -> Tuple[int, int]:
    if pfp_count == 0:
        return EVT_CONTENT_X, CANVAS_WIDTH - EVT_CONTENT_X - PADDING
    elif pfp_count == 1:
        ax = EVT_CONTENT_X + EVENT_PFP_SIZE + 18
        return ax, CANVAS_WIDTH - ax - PADDING
    else:
        ax = EVT_CONTENT_X + EVENT_PFP_SIZE + 18
        return ax, CANVAS_WIDTH - ax - EVENT_PFP_SIZE - 18 - PADDING


# ══════════════════════════════════════════════════════════════════════════════

class TorneoRenderer:
    """Motor de renderizado premium para torneo."""

    def __init__(self) -> None:
        pass

    # ── Carga de PFP ─────────────────────────────────────────────────────────

    def _load_pfp(self, name: str, cache: Dict[str, io.BytesIO],
                  size: int) -> Optional[Image.Image]:
        if name not in cache:
            return None
        try:
            buf = cache[name]
            buf.seek(0)
            return _circle_pfp(Image.open(buf), size)
        except Exception:
            return None

    # ── Medicion de altura de evento ─────────────────────────────────────────

    def _measure_event(self, evt: Dict, draw: ImageDraw.Draw,
                       action_font: ImageFont.FreeTypeFont,
                       dialog_font: ImageFont.FreeTypeFont) -> int:
        nombres  = evt.get("nombres_protagonistas", [])
        accion   = evt.get("accion", "")
        dialogos = evt.get("dialogos", {})

        line_h = draw.textbbox((0, 0), "Tg", font=action_font)[3] + 3
        dl_line_h = draw.textbbox((0, 0), "Tg", font=dialog_font)[3] + 4

        h = 40  # cabecera (badge + tipo)

        # PFPs + accion
        _, action_max_w = _action_layout(len(nombres))
        action_lines = _wrap(accion, action_font, action_max_w, draw)
        action_h = max(len(action_lines) * line_h + 10, EVENT_PFP_SIZE + 16)
        h += action_h

        # Dialogos
        bubble_max_w = int(CANVAS_WIDTH * BUBBLE_MAX_FRAC) - DIALOG_PFP_SIZE - 32
        for speaker, dialogue in dialogos.items():
            if not dialogue or not dialogue.strip():
                continue
            dl_lines = _wrap(dialogue[:360], dialog_font, bubble_max_w, draw)
            h += 36 + len(dl_lines) * dl_line_h + 14

        h += 20
        return h

    # ── Dibuja evento individual ─────────────────────────────────────────────

    def _draw_event(
        self,
        canvas: Image.Image,
        draw: ImageDraw.Draw,
        evt: Dict,
        idx: int,
        cur_y: int,
        evt_h: int,
        event_pfps: Dict[str, Optional[Image.Image]],
        dialog_pfps: Dict[str, Optional[Image.Image]],
        fonts: Dict[str, ImageFont.FreeTypeFont],
    ) -> int:
        nombres  = evt.get("nombres_protagonistas", [])
        accion   = evt.get("accion", "")
        dialogos = evt.get("dialogos", {})
        tipo     = evt.get("tipo_accion", "")
        d20_roll = evt.get("d20_roll", 0)
        roll_res = evt.get("resultado_roll", "")

        # ── Fondo sutil del evento ──────────────────────────────────────
        evt_bg = Image.new("RGBA", (CANVAS_WIDTH - PADDING, evt_h + 10), (0, 0, 0, 0))
        evt_bg_draw = ImageDraw.Draw(evt_bg)
        evt_bg_draw.rounded_rectangle(
            [0, 5, CANVAS_WIDTH - PADDING, evt_h + 5],
            radius=12, fill=(*BG_SURFACE, 180),
            outline=(*BORDER_SUBTLE, 60), width=1,
        )
        canvas.paste(evt_bg, (PADDING // 2, cur_y - 5), evt_bg)

        # ── Barra de acento con gradiente ────────────────────────────────
        bar_h = evt_h - 20
        accent_grad = _linear_gradient(ACCENT_BAR_W, bar_h, RED, RED_DIM)
        canvas.paste(accent_grad, (PADDING, cur_y + 6), accent_grad)

        # Pequeno glow en la barra
        glow = _radial_glow(ACCENT_BAR_W + 12, RED, 30, 0)
        canvas.paste(glow, (PADDING - 6, cur_y + bar_h // 2 - glow.height // 2), glow)

        # ── Badge numerado ───────────────────────────────────────────────
        badge_cx = EVT_CONTENT_X + BADGE_RADIUS
        badge_cy = cur_y + BADGE_RADIUS + 4

        # Glow del badge
        badge_glow = _radial_glow(BADGE_RADIUS * 2 + 12, RED, 60, 0)
        canvas.paste(badge_glow,
                     (badge_cx - badge_glow.width // 2,
                      badge_cy - badge_glow.height // 2),
                     badge_glow)

        # Badge solido con gradiente
        badge_grad = _linear_gradient(BADGE_RADIUS * 2, BADGE_RADIUS * 2,
                                       (RED[0] + 20, RED[1] + 10, RED[2] + 10), RED_DIM)
        badge_mask = _circle_mask(BADGE_RADIUS * 2)
        badge_final = Image.new("RGBA", (BADGE_RADIUS * 2, BADGE_RADIUS * 2), (0, 0, 0, 0))
        badge_final.paste(badge_grad, (0, 0), badge_mask)
        canvas.paste(badge_final,
                     (badge_cx - BADGE_RADIUS, badge_cy - BADGE_RADIUS),
                     badge_final)

        _draw_text(draw, (badge_cx, badge_cy), str(idx + 1),
                   fill=TEXT_PRIMARY, font=fonts["badge"], anchor="mm")

        # ── Tipo de accion + resultado del roll ─────────────────────────
        tipo_x = badge_cx + BADGE_RADIUS + 10
        _draw_text(draw, (tipo_x, cur_y + 2),
                   tipo.upper()[:40] if tipo else f"EVENTO {idx + 1}",
                   fill=GOLD, font=fonts["evt_type"])
        if d20_roll:
            roll_text = f"🎲 {d20_roll} — {roll_res[:30]}" if roll_res else f"🎲 D20: {d20_roll}"
            rw = _text_w(roll_text, fonts["roll_info"], draw)
            roll_x = CANVAS_WIDTH - PADDING - rw - 4
            _draw_text(draw, (roll_x, cur_y + 3), roll_text,
                       fill=TEXT_SECONDARY, font=fonts["roll_info"])
        cur_y += 40

        # ── PFPs + texto de accion ──────────────────────────────────────
        pfp_count = len(nombres)
        action_x, action_max_w = _action_layout(pfp_count)
        pfp_cy = cur_y + EVENT_PFP_SIZE // 2

        if pfp_count >= 1:
            pfp_l = event_pfps.get(nombres[0])
            pfp_lx = EVT_CONTENT_X + EVENT_PFP_SIZE // 2
            if pfp_l:
                _paste_circle_with_shadow(canvas, pfp_l, pfp_lx, pfp_cy)
                ring = _ring_glow(EVENT_PFP_SIZE + 8, RED, 100, 3)
                canvas.paste(ring, (pfp_lx - ring.width // 2, pfp_cy - ring.height // 2), ring)
            _draw_text(draw, (pfp_lx, cur_y + EVENT_PFP_SIZE + 4),
                       nombres[0][:14], fill=TEXT_SECONDARY,
                       font=fonts["pfp_name"], anchor="mt")

        if pfp_count >= 2:
            pfp_r = event_pfps.get(nombres[1])
            pfp_rx = CANVAS_WIDTH - PADDING - EVENT_PFP_SIZE // 2
            if pfp_r:
                _paste_circle_with_shadow(canvas, pfp_r, pfp_rx, pfp_cy)
                ring = _ring_glow(EVENT_PFP_SIZE + 8, BLUE, 100, 3)
                canvas.paste(ring, (pfp_rx - ring.width // 2, pfp_cy - ring.height // 2), ring)
            _draw_text(draw, (pfp_rx, cur_y + EVENT_PFP_SIZE + 4),
                       nombres[1][:14], fill=TEXT_SECONDARY,
                       font=fonts["pfp_name"], anchor="mt")

            # VS entre PFPs
            vs_cx = (EVT_CONTENT_X + EVENT_PFP_SIZE + PADDING +
                     pfp_rx - EVENT_PFP_SIZE // 2) // 2
            _draw_text(draw, (vs_cx, pfp_cy), "⚔",
                       fill=TEXT_MUTED, font=fonts["vs"], anchor="mm")

        # Texto de accion
        line_h = draw.textbbox((0, 0), "Tg", font=fonts["action"])[3] + 3
        action_lines = _wrap(accion, fonts["action"], action_max_w, draw)
        for i, line in enumerate(action_lines):
            _draw_text(draw, (action_x, cur_y + 6 + i * line_h),
                       line, fill=TEXT_PRIMARY, font=fonts["action"])

        action_h = max(len(action_lines) * line_h + 10, EVENT_PFP_SIZE + 16)
        cur_y += action_h + 8

        # ── Burbujas de dialogo ──────────────────────────────────────────
        bubble_max_w = int(CANVAS_WIDTH * BUBBLE_MAX_FRAC)

        for dlg_idx, (speaker, dialogue) in enumerate(dialogos.items()):
            if not dialogue or not dialogue.strip():
                continue

            is_left = (dlg_idx % 2 == 0)
            dl_text = dialogue[:360]
            inner_w = bubble_max_w - DIALOG_PFP_SIZE - 36
            dl_line_h = draw.textbbox((0, 0), "Tg", font=fonts["dialog"])[3] + 4
            dl_lines = _wrap(dl_text, fonts["dialog"], inner_w, draw)
            bubble_h = 34 + len(dl_lines) * dl_line_h

            max_line_w = max(
                (_text_w(ln, fonts["dialog"], draw) for ln in dl_lines),
                default=80,
            )
            bubble_w = min(DIALOG_PFP_SIZE + 40 + max_line_w + 20, bubble_max_w)

            pfp_small = dialog_pfps.get(speaker)

            if is_left:
                bx = EVT_CONTENT_X + 4
            else:
                bx = CANVAS_WIDTH - PADDING - 4 - bubble_w

            # Sombra de la burbuja
            bubble_shadow = _drop_shadow_rect(
                bubble_w, bubble_h, radius=BUBBLE_RADIUS,
                offset=(3, 4), alpha=SHADOW_STRONG, blur=8,
            )
            shadow_x = bx - 4
            shadow_y = cur_y - 4
            canvas.paste(bubble_shadow, (shadow_x, shadow_y), bubble_shadow)

            # Fondo de burbuja con gradiente sutil
            bubble_grad = _linear_gradient(bubble_w, bubble_h,
                                            (BG_ELEVATED[0] + 6, BG_ELEVATED[1] + 6, BG_ELEVATED[2] + 6),
                                            BG_ELEVATED)
            bubble_final = Image.new("RGBA", (bubble_w, bubble_h), (0, 0, 0, 0))
            bubble_final.paste(bubble_grad, (0, 0))
            canvas.paste(bubble_final, (bx, cur_y), bubble_final)

            # Borde
            draw.rounded_rectangle(
                [bx, cur_y, bx + bubble_w, cur_y + bubble_h],
                radius=BUBBLE_RADIUS,
                outline=(*GOLD_DIM, 80), width=1,
            )

            # Linea de acento lateral
            line_color = (GOLD[0], GOLD[1], GOLD[2], 180) if is_left else (BLUE[0], BLUE[1], BLUE[2], 180)
            if is_left:
                draw.line([(bx + 3, cur_y + 12), (bx + 3, cur_y + bubble_h - 12)],
                          fill=line_color, width=3)
            else:
                draw.line([(bx + bubble_w - 4, cur_y + 12),
                           (bx + bubble_w - 4, cur_y + bubble_h - 12)],
                          fill=line_color, width=3)

            # PFP del hablante
            if pfp_small:
                if is_left:
                    pfp_bx = bx + 14
                else:
                    pfp_bx = bx + bubble_w - DIALOG_PFP_SIZE - 14
                pfp_by = cur_y + 6
                canvas.paste(pfp_small, (pfp_bx, pfp_by), pfp_small)

            # Nombre del hablante
            nm_color = GOLD if is_left else BLUE
            if is_left:
                name_x = bx + DIALOG_PFP_SIZE + 22
                _draw_text(draw, (name_x, cur_y + 8), speaker[:20],
                           fill=nm_color, font=fonts["dlg_name"])
                text_x = name_x
            else:
                name_x = bx + bubble_w - DIALOG_PFP_SIZE - 22
                _draw_text(draw, (name_x, cur_y + 8), speaker[:20],
                           fill=nm_color, font=fonts["dlg_name"], anchor="ra")
                text_x = bx + 14

            # Texto del dialogo
            for i, line in enumerate(dl_lines):
                _draw_text(draw, (text_x, cur_y + 28 + i * dl_line_h),
                           line, fill=TEXT_PRIMARY, font=fonts["dialog"])

            cur_y += bubble_h + 12

        cur_y += 20
        return cur_y

    # ── Metodo principal ──────────────────────────────────────────────────────

    def _draw_board(
        self,
        canvas: Image.Image,
        draw: ImageDraw.Draw,
        cur_y: int,
        board_state: Dict[str, str],
        lugares: List[str],
        board_pfps: Dict[str, Optional[Image.Image]],
        fonts: Dict[str, ImageFont.FreeTypeFont],
    ) -> int:
        """Dibuja un tablero de habitaciones conectadas. Retorna nuevo cur_y."""
        if not board_state or not lugares:
            return cur_y

        cols = min(BOARD_COLS, len(lugares))
        rows = (len(lugares) + cols - 1) // cols
        cell_w = (CANVAS_WIDTH - PADDING * 2 - BOARD_GAP * (cols - 1)) // cols
        board_h = rows * (BOARD_CELL_H + BOARD_GAP) + 42

        # Fondo del tablero
        board_bg = Image.new("RGBA", (CANVAS_WIDTH - PADDING, board_h), (0, 0, 0, 0))
        bg_draw = ImageDraw.Draw(board_bg)
        bg_draw.rounded_rectangle(
            [0, 2, CANVAS_WIDTH - PADDING, board_h - 2],
            radius=10, fill=(*BG_SURFACE, 180),
            outline=(*BORDER_SUBTLE, 80), width=1,
        )
        canvas.paste(board_bg, (PADDING // 2, cur_y), board_bg)

        # Título
        _draw_text(draw, (PADDING + 12, cur_y + 8),
                   "— UBICACIONES —", fill=TEXT_MUTED,
                   font=fonts["board_title"])
        cur_y += 30

        # ── Dibujar cada celda como una "habitación" visual ──
        place_names = {l: [n for n, loc in board_state.items() if loc == l] for l in lugares}

        for i, lugar in enumerate(lugares):
            col = i % cols
            row = i // cols
            cx = PADDING + col * (cell_w + BOARD_GAP)
            cy = cur_y + row * (BOARD_CELL_H + BOARD_GAP)

            names = place_names.get(lugar, [])

            # Fondo de la celda (rectángulo redondeado)
            cell_fill = BG_HIGHLIGHT if names else BG_SURFACE
            draw.rounded_rectangle(
                [cx, cy, cx + cell_w, cy + BOARD_CELL_H],
                radius=6, fill=cell_fill,
                outline=(*BORDER_SUBTLE, 120), width=1,
            )

            # Bullet dorado + nombre del lugar
            draw.ellipse([cx + 8, cy + 8, cx + 16, cy + 16], fill=GOLD)
            _draw_text(draw, (cx + 22, cy + 6), lugar,
                       fill=TEXT_SECONDARY if names else TEXT_MUTED,
                       font=fonts["board_place"])

            # PFPs de los que están aquí
            pfp_y = cy + 28
            max_pfps_per_row = max(1, (cell_w - 22) // (BOARD_PFP_SIZE + BOARD_CELL_PAD))
            for j, name in enumerate(names):
                col_pfp = j % max_pfps_per_row
                row_pfp = j // max_pfps_per_row
                pfp_cx = cx + 16 + col_pfp * (BOARD_PFP_SIZE + BOARD_CELL_PAD) + BOARD_PFP_SIZE // 2
                pfp_cy = pfp_y + row_pfp * 22 + BOARD_PFP_SIZE // 2

                pfp = board_pfps.get(name)
                if pfp:
                    canvas.paste(pfp, (pfp_cx - BOARD_PFP_SIZE // 2,
                                        pfp_cy - BOARD_PFP_SIZE // 2), pfp)
                else:
                    draw.ellipse(
                        [pfp_cx - BOARD_PFP_SIZE // 2, pfp_cy - BOARD_PFP_SIZE // 2,
                         pfp_cx + BOARD_PFP_SIZE // 2, pfp_cy + BOARD_PFP_SIZE // 2],
                        fill=BORDER_SUBTLE,
                    )

        return cur_y + rows * (BOARD_CELL_H + BOARD_GAP) + 20

    def renderizar_fase_completa(
        self,
        nombre_fase: str,
        escenario: str,
        eventos: List[Dict[str, Any]],
        recuento: Dict[str, Any],
        pfp_cache: Dict[str, io.BytesIO],
        board_state: Optional[Dict[str, str]] = None,
        lugares: Optional[List[str]] = None,
    ) -> bytes:
        """Renderiza una fase completa. API estable."""
        # ── Sanitizar entradas (LLM puede devolver listas en vez de strings) ──
        nombre_fase = str(nombre_fase) if not isinstance(nombre_fase, str) else nombre_fase
        escenario = str(escenario) if not isinstance(escenario, str) else escenario
        for evt in eventos:
            if isinstance(evt, dict):
                for key in ("accion", "tipo_accion", "resultado_roll"):
                    if key in evt and not isinstance(evt[key], str):
                        evt[key] = str(evt[key]) if evt[key] is not None else ""
                nombres = evt.get("nombres_protagonistas", [])
                if isinstance(nombres, list):
                    evt["nombres_protagonistas"] = [
                        str(n) if n is not None and not isinstance(n, str) else (n or "")
                        for n in nombres[:10]
                    ]
                elif not isinstance(nombres, list):
                    evt["nombres_protagonistas"] = []
                dialogos = evt.get("dialogos", {})
                if isinstance(dialogos, dict):
                    for k, v in list(dialogos.items()):
                        if not isinstance(v, str):
                            dialogos[k] = str(v) if v is not None else ""
        if isinstance(recuento, dict):
            resumen = recuento.get("resumen_breve", "")
            if not isinstance(resumen, str):
                recuento["resumen_breve"] = str(resumen) if resumen is not None else ""

        # ── Fuentes ──────────────────────────────────────────────────────
        fonts = {
            "header":    _get_font(32, bold=True),
            "subtitle":  _get_font(14),
            "evt_type":  _get_font(14, bold=True),
            "roll_info": _get_font(11),
            "badge":     _get_font(12, bold=True),
            "action":    _get_font(15),
            "pfp_name":  _get_font(11),
            "vs":        _get_font(18),
            "dialog":    _get_font(14),
            "dlg_name":  _get_font(13, bold=True),
            "recap_ttl": _get_font(22, bold=True),
            "recap_sec": _get_font(16, bold=True),
            "recap_nm":  _get_font(11),
            "footer":    _get_font(10),
            "board_title": _get_font(11, bold=True),
            "board_place": _get_font(12, bold=True),
            "board_pfp_name": _get_font(7),
        }

        # ── Canvas temporal para mediciones ──────────────────────────────
        temp = Image.new("RGBA", (CANVAS_WIDTH, 100))
        temp_draw = ImageDraw.Draw(temp)

        # ── Recopilar todos los nombres ──────────────────────────────────
        all_names: set = set()
        for evt in eventos:
            for n in evt.get("nombres_protagonistas", []):
                all_names.add(n)
            for n in evt.get("dialogos", {}).keys():
                all_names.add(n)
        for n in recuento.get("vivos_restantes", []):
            all_names.add(n)
        for n in recuento.get("muertos_en_esta_fase", []):
            all_names.add(n)
        if board_state:
            for n in board_state:
                all_names.add(n)

        # ── Cargar PFPs ──────────────────────────────────────────────────
        event_pfps: Dict[str, Optional[Image.Image]] = {}
        dialog_pfps: Dict[str, Optional[Image.Image]] = {}
        recap_pfps: Dict[str, Optional[Image.Image]] = {}
        board_pfps: Dict[str, Optional[Image.Image]] = {}
        for name in all_names:
            event_pfps[name] = self._load_pfp(name, pfp_cache, EVENT_PFP_SIZE)
            dialog_pfps[name] = self._load_pfp(name, pfp_cache, DIALOG_PFP_SIZE)
            recap_pfps[name] = self._load_pfp(name, pfp_cache, RECAP_PFP_SIZE)
            board_pfps[name] = self._load_pfp(name, pfp_cache, BOARD_PFP_SIZE)

        # ── Pre-calcular alturas ─────────────────────────────────────────
        scenario_max_w = CANVAS_WIDTH - PADDING * 3
        scenario_lines = _wrap(escenario, fonts["subtitle"], scenario_max_w, temp_draw)
        header_h = HEADER_HEIGHT + max(0, len(scenario_lines) - 2) * 18

        event_heights = [
            self._measure_event(evt, temp_draw, fonts["action"], fonts["dialog"])
            for evt in eventos
        ]

        # Altura del tablero
        board_h = 0
        if board_state and lugares:
            cols = min(BOARD_COLS, len(lugares))
            rows = (len(lugares) + cols - 1) // cols
            board_h = rows * (BOARD_CELL_H + BOARD_GAP) + 42

        vivos = recuento.get("vivos_restantes", [])
        muertos_fase = recuento.get("muertos_en_esta_fase", [])
        cell_h = RECAP_PFP_SIZE + 34
        cell_w = RECAP_PFP_SIZE + 28

        recap_rows_v = max(1, (len(vivos) + GRID_COLS - 1) // GRID_COLS)
        recap_rows_m = (len(muertos_fase) + GRID_COLS - 1) // GRID_COLS if muertos_fase else 0

        recap_h = 80
        recap_h += recap_rows_v * cell_h + 50
        resumen_text = recuento.get("resumen_breve", "")
        if resumen_text:
            res_lines = _wrap(resumen_text, fonts["subtitle"],
                              CANVAS_WIDTH - PADDING * 3, temp_draw)
            recap_h += 20 + len(res_lines) * 18
        if muertos_fase:
            recap_h += 50 + recap_rows_m * cell_h + 30
        recap_h += 40

        total_h = (header_h + sum(event_heights)
                   + max(len(eventos) - 1, 0) * EVENT_SPACING
                   + board_h
                   + recap_h + 30)

        # ── Canvas ───────────────────────────────────────────────────────
        canvas = Image.new("RGBA", (CANVAS_WIDTH, total_h))
        bg_grad = _linear_gradient(CANVAS_WIDTH, total_h, BG_DEEP,
                                    (BG_SURFACE[0], BG_SURFACE[1], BG_SURFACE[2]))
        canvas.paste(bg_grad, (0, 0))
        draw = ImageDraw.Draw(canvas)

        # ── Header atmosferico ───────────────────────────────────────────
        header_bg = _linear_gradient(CANVAS_WIDTH, header_h,
                                      (BG_SURFACE[0] + 4, BG_SURFACE[1] + 4, BG_SURFACE[2] + 6),
                                      BG_SURFACE)
        canvas.paste(header_bg, (0, 0))

        # Glow ambiental detras del titulo
        ambient = _radial_glow(500, GOLD_DIM, 30, 0)
        canvas.paste(ambient, (60, 20), ambient)

        # Linea de acento superior
        draw.rectangle([0, 0, CANVAS_WIDTH, 3], fill=GOLD)

        # Titulo
        _draw_text_shadow(draw, (PADDING, 22), f"📍 {nombre_fase}",
                          fill=GOLD, font=fonts["header"], shadow_alpha=80)

        # Escenario
        y = 74
        for line in scenario_lines:
            _draw_text(draw, (PADDING + 4, y), line,
                       fill=TEXT_SECONDARY, font=fonts["subtitle"])
            y += 18

        # Linea separadora inferior del header
        draw.line([(PADDING, header_h - 6), (CANVAS_WIDTH - PADDING, header_h - 6)],
                  fill=(*GOLD_DIM, 80), width=1)

        # ── Eventos ───────────────────────────────────────────────────────
        # ── Tablero (entre header y eventos si hay data) ────────────────
        if board_state and lugares and board_h:
            cur_y = header_h + EVENT_SPACING // 2
            cur_y = self._draw_board(canvas, draw, cur_y, board_state, lugares, board_pfps, fonts)
            cur_y += EVENT_SPACING // 2
        else:
            cur_y = header_h + EVENT_SPACING // 2

        for idx, (evt, evt_h) in enumerate(zip(eventos, event_heights)):
            cur_y = self._draw_event(
                canvas, draw, evt, idx, cur_y, evt_h,
                event_pfps, dialog_pfps, fonts,
            )
            cur_y += EVENT_SPACING

        # ── Recuento ─────────────────────────────────────────────────────
        bar_y = cur_y
        draw.rectangle([PADDING, bar_y, CANVAS_WIDTH - PADDING, bar_y + 2],
                       fill=(*RED, 120))
        bar_glow = _linear_gradient(CANVAS_WIDTH - PADDING * 2, 8,
                                     (RED[0], RED[1], RED[2]),
                                     RED_DIM)
        canvas.paste(bar_glow, (PADDING, bar_y - 3), bar_glow)

        cur_y += 18

        _draw_text_shadow(draw, (PADDING, cur_y), "RECUENTO DE FASE",
                          fill=GOLD, font=fonts["recap_ttl"], shadow_alpha=60)
        cur_y += 40

        # Resumen
        if resumen_text:
            res_lines = _wrap(resumen_text, fonts["subtitle"],
                              CANVAS_WIDTH - PADDING * 3, draw)
            res_bg_h = len(res_lines) * 18 + 28
            draw.rounded_rectangle(
                [PADDING, cur_y, CANVAS_WIDTH - PADDING, cur_y + res_bg_h],
                radius=10, fill=(*BG_SURFACE, 180),
                outline=(*BORDER_SUBTLE, 100), width=1,
            )
            for i, line in enumerate(res_lines):
                _draw_text(draw, (PADDING + 20, cur_y + 12 + i * 18),
                           line, fill=TEXT_SECONDARY, font=fonts["subtitle"])
            cur_y += res_bg_h + 18

        # ── Sobrevivientes ───────────────────────────────────────────────
        _draw_text(draw, (PADDING, cur_y),
                   "  SOBREVIVIENTES", fill=GREEN, font=fonts["recap_sec"])
        cur_y += 30

        for i, name in enumerate(vivos):
            col = i % GRID_COLS
            row = i // GRID_COLS
            cx = PADDING + 30 + col * cell_w + RECAP_PFP_SIZE // 2
            cy = cur_y + row * cell_h

            pfp = recap_pfps.get(name)
            if pfp:
                _paste_circle_with_shadow(canvas, pfp, cx, cy + RECAP_PFP_SIZE // 2)
                ring = _ring_glow(RECAP_PFP_SIZE + 8, GREEN, 80, 2)
                canvas.paste(ring, (cx - ring.width // 2,
                                     cy + RECAP_PFP_SIZE // 2 - ring.height // 2), ring)
            _draw_text(draw, (cx, cy + RECAP_PFP_SIZE + 8),
                       name[:13], fill=TEXT_PRIMARY, font=fonts["recap_nm"], anchor="mt")

        cur_y += recap_rows_v * cell_h + 30

        # ── Caidos ───────────────────────────────────────────────────────
        if muertos_fase:
            draw.line([(PADDING + 40, cur_y), (CANVAS_WIDTH - PADDING - 40, cur_y)],
                      fill=(*RED_DIM, 120), width=1)
            cur_y += 16

            _draw_text(draw, (PADDING, cur_y),
                       "  CAÍDOS EN ESTA FASE", fill=RED, font=fonts["recap_sec"])
            cur_y += 30

            x_font = _get_font(22, bold=True)

            for i, name in enumerate(muertos_fase):
                col = i % GRID_COLS
                row = i // GRID_COLS
                cx = PADDING + 30 + col * cell_w + RECAP_PFP_SIZE // 2
                cy = cur_y + row * cell_h

                pfp = recap_pfps.get(name)
                if pfp:
                    gray = ImageOps.grayscale(pfp.convert("RGBA")).convert("RGBA")
                    vignette = _radial_glow(RECAP_PFP_SIZE, RED_DIM, 120, 0)
                    vignette = vignette.resize((RECAP_PFP_SIZE, RECAP_PFP_SIZE), Image.LANCZOS)
                    gray = Image.alpha_composite(gray, vignette)
                    canvas.paste(gray,
                                 (cx - RECAP_PFP_SIZE // 2,
                                  cy - RECAP_PFP_SIZE // 2 + RECAP_PFP_SIZE // 2),
                                 gray)
                    _draw_text(draw, (cx, cy + RECAP_PFP_SIZE // 2),
                               "✕", fill=RED, font=x_font, anchor="mm")

                _draw_text(draw, (cx, cy + RECAP_PFP_SIZE + 8),
                           name[:13], fill=TEXT_MUTED, font=fonts["recap_nm"], anchor="mt")

            cur_y += recap_rows_m * cell_h + 20

        # ── Footer ───────────────────────────────────────────────────────
        _draw_text(draw, (CANVAS_WIDTH // 2, total_h - 18), "Youkai Torneo · v4",
                   fill=(*TEXT_MUTED, 100), font=fonts["footer"], anchor="mt")

        # ── Output ───────────────────────────────────────────────────────
        output = io.BytesIO()
        canvas.save(output, format="PNG", optimize=True)
        return output.getvalue()
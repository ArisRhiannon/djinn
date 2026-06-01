#!/usr/bin/env python3
"""
Xokram el negrito — pseudo-3D synthwave scene renderer.
Emits /tmp/xokram_frames/NNNN.png; ffmpeg does the GIF encode separately.

Techniques:
  - supersampling 2x with Lanczos downsample
  - vertical gradient sky + ground with sun (sliced synthwave style)
  - perspective grid (scrolling)
  - parallaxed stars with twinkle
  - rising particles (loop-safe)
  - 3D-extruded title by stacking offset copies with shaded side fill
  - bloom (threshold -> gaussian blur -> add)
  - lens flare sweep across the title (once per loop)
  - chromatic aberration (channel split with sub-pixel offsets)
  - subtle scanlines + vignette
All cyclic phenomena complete an integer number of cycles over the loop.
"""
import os, math, sys, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops, ImageEnhance

# ---------- config ----------
W, H      = 640, 360
SS        = 2
FW, FH    = W * SS, H * SS
FPS       = 24
DURATION  = 4.0
N_FRAMES  = int(FPS * DURATION)            # 96

OUT_DIR   = "/tmp/xokram_frames"
FONT_TITLE = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
FONT_SUB   = "/usr/share/fonts/truetype/lato/Lato-BlackItalic.ttf"

# ---------- palette (synthwave outrun) ----------
BG_TOP     = ( 14,   4,  40)
BG_MID     = ( 70,  16,  95)
BG_HORIZON = (255,  95, 150)
GROUND_TOP = (120,  25,  95)
GROUND_BOT = (  4,   2,  14)
SUN_TOP    = (255, 235, 110)
SUN_BOT    = (255,  55, 110)
GRID_COLOR = (255,  70, 200)
GRID_VERT  = (255,  40, 160)
STAR_COLOR = (235, 235, 255)
TEXT_TOP   = (140, 245, 255)
TEXT_BOT   = (255,  85, 200)
TEXT_SIDE  = ( 42,  10,  66)
TEXT_SIDE2 = ( 16,   4,  30)
OUTLINE    = (255, 255, 255)
SUB_COLOR  = (255, 225, 240)

# ---------- utilities ----------
def lerp(a, b, t):
    return a + (b - a) * t

def ease_out_cubic(t):
    return 1 - (1 - t) ** 3

def clamp01(x):
    return max(0.0, min(1.0, x))

def np_to_img(arr, mode='RGB'):
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode)

# ---------- background (sky + ground + sun) ----------
def build_background(t):
    """Return a full-canvas RGB background image."""
    horizon_y = int(FH * 0.60)
    arr = np.zeros((FH, FW, 3), dtype=np.float32)

    # sky (top -> horizon)
    for y in range(horizon_y):
        k = y / max(1, horizon_y - 1)
        if k < 0.55:
            kk = k / 0.55
            c = np.array(BG_TOP) * (1 - kk) + np.array(BG_MID) * kk
        else:
            kk = (k - 0.55) / 0.45
            kk = kk ** 1.4
            c = np.array(BG_MID) * (1 - kk) + np.array(BG_HORIZON) * kk
        arr[y, :, :] = c

    # ground (horizon -> bottom)
    for y in range(horizon_y, FH):
        k = (y - horizon_y) / max(1, FH - horizon_y - 1)
        kk = k ** 0.7
        c = np.array(GROUND_TOP) * (1 - kk) + np.array(GROUND_BOT) * kk
        arr[y, :, :] = c

    img = np_to_img(arr, 'RGB').convert('RGBA')

    # sun
    sun_cx = FW // 2
    sun_cy = int(horizon_y * 0.98)
    sun_r  = int(FH * 0.20)
    sun_size = sun_r * 2 + 4
    sun = Image.new('RGBA', (sun_size, sun_size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sun)
    # vertical gradient
    grad = np.zeros((sun_size, sun_size, 4), dtype=np.float32)
    for yy in range(sun_size):
        k = yy / max(1, sun_size - 1)
        c = np.array(SUN_TOP) * (1 - k) + np.array(SUN_BOT) * k
        grad[yy, :, 0:3] = c
        grad[yy, :, 3]   = 255
    sun = np_to_img(grad, 'RGBA')
    # circle mask
    mask = Image.new('L', (sun_size, sun_size), 0)
    ImageDraw.Draw(mask).ellipse([2, 2, sun_size - 2, sun_size - 2], fill=255)
    sun.putalpha(mask)

    # synthwave slices (darkening bands on lower half), phase scrolls 1 cycle per loop
    sd = ImageDraw.Draw(sun)
    phase = (t) % 1.0   # integer cycles per loop
    n_slices = 6
    spacing = sun_r / (n_slices + 1)
    for i in range(n_slices + 2):
        sy = int(sun_r * 0.75 + (i + phase) * spacing)
        if sy <= sun_r * 0.35 or sy >= sun_size:
            continue
        strip_h = max(2, int(spacing * 0.34 * (0.35 + (i + 1) / (n_slices + 2))))
        sd.rectangle([0, sy, sun_size, sy + strip_h], fill=(0, 0, 0, 0))

    # soft glow around sun
    glow = Image.new('RGBA', (sun_size + 80, sun_size + 80), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for rr, aa in [(sun_r + 40, 24), (sun_r + 24, 40), (sun_r + 12, 70)]:
        gd.ellipse([glow.width // 2 - rr, glow.height // 2 - rr,
                    glow.width // 2 + rr, glow.height // 2 + rr],
                   fill=(255, 120, 170, aa))
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    img.alpha_composite(glow, (sun_cx - glow.width // 2, sun_cy - glow.height // 2))
    img.alpha_composite(sun,  (sun_cx - sun_size // 2,  sun_cy - sun_size // 2))

    return img, horizon_y

# ---------- stars ----------
_star_cache = None
def stars_layer(t):
    global _star_cache
    if _star_cache is None:
        rng = np.random.default_rng(2024)
        n = 140
        _star_cache = dict(
            x = rng.uniform(0, FW, n),
            y = rng.uniform(0, FH * 0.55, n),
            phase = rng.uniform(0, 2 * math.pi, n),
            size  = rng.uniform(0.6, 1.8, n),
            cycles = rng.integers(1, 4, n),  # integer cycles per loop
        )
    s = _star_cache
    img = Image.new('RGBA', (FW, FH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(len(s['x'])):
        # twinkle: integer # cycles per loop
        b = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * s['cycles'][i] * t + s['phase'][i]))
        a = int(255 * b)
        r = max(1, int(SS * s['size'][i] * (0.6 + 0.8 * b)))
        x, y = s['x'][i], s['y'][i]
        d.ellipse([x - r, y - r, x + r, y + r], fill=STAR_COLOR + (a,))
    # tiny bloom on stars
    glow = img.filter(ImageFilter.GaussianBlur(2 * SS))
    glow = ImageChops.multiply(glow, Image.new('RGBA', glow.size, (255, 255, 255, 150)))
    return Image.alpha_composite(glow, img)

# ---------- perspective grid ----------
def grid_layer(t, horizon_y):
    img = Image.new('RGBA', (FW, FH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    vp_x = FW // 2
    vp_y = horizon_y

    # vertical lines: converge to vanishing point. spacing at "ground near bottom"
    n_vert = 14
    spread = FW * 1.6   # larger than FW so lines go past edges
    for i in range(-n_vert, n_vert + 1):
        x_near = vp_x + int(i * spread / (2 * n_vert))
        # fade lines near the middle a touch more
        base_a = 175
        falloff = 1.0 - min(1, abs(i) / (n_vert + 2)) * 0.3
        a = int(base_a * falloff)
        width = max(1, SS)
        d.line([(vp_x, vp_y), (x_near, FH + 10)], fill=GRID_VERT + (a,), width=width)

    # horizontal lines: in z-space, step by 1 unit, scroll at integer rate per loop.
    scroll = (t * 2.0) % 1.0   # 2 full grid steps per loop
    n_h = 28
    ground_h = FH - horizon_y
    for i in range(1, n_h):
        z = i + scroll
        # perspective mapping
        denom = (1 + z * 0.22)
        y = horizon_y + ground_h * (1 - 1 / denom)
        if y >= FH:
            break
        # fade and thickness by distance (near lines brighter/thicker)
        prog = (z - 1) / (n_h - 1)   # 0 near, 1 far
        fade = (1 - prog) ** 1.2
        a = int(230 * max(0.05, fade))
        width = max(1, int(round(SS * (2.0 * (1 - prog) + 0.5))))
        d.line([(0, y), (FW, y)], fill=GRID_COLOR + (a,), width=width)

    # soft bloom on grid
    glow = img.filter(ImageFilter.GaussianBlur(3 * SS))
    bloom = ImageChops.multiply(glow, Image.new('RGBA', glow.size, (255, 255, 255, 110)))
    return Image.alpha_composite(bloom, img)

# ---------- rising particles ----------
_particle_cache = None
def particles_layer(t):
    global _particle_cache
    if _particle_cache is None:
        rng = np.random.default_rng(101)
        n = 46
        _particle_cache = dict(
            x = rng.uniform(0, FW, n),
            y0 = rng.uniform(0, FH, n),
            speed = rng.uniform(0.6, 1.4, n),   # in FH units per loop
            size  = rng.uniform(0.8, 2.2, n),
            color = [np.array([255, 180 + int(60 * v), 220 + int(30 * v)]) for v in rng.uniform(0, 1, n)],
            phase = rng.uniform(0, 2 * math.pi, n),
        )
    p = _particle_cache
    img = Image.new('RGBA', (FW, FH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(len(p['x'])):
        # loop: y wraps. speed such that integer cycles = speed over 1 loop.
        cycles = int(round(p['speed'][i]))
        if cycles < 1:
            cycles = 1
        y = (p['y0'][i] - cycles * FH * t) % FH
        x = p['x'][i] + 3 * math.sin(2 * math.pi * t * cycles + p['phase'][i])
        r = max(1, int(SS * p['size'][i]))
        # fade near top edge of sky (above horizon area)
        base_a = 200
        col = tuple(int(c) for c in p['color'][i])
        d.ellipse([x - r, y - r, x + r, y + r], fill=col + (base_a,))
    # bloom
    glow = img.filter(ImageFilter.GaussianBlur(4 * SS))
    return Image.alpha_composite(glow, img)

# ---------- title: render front face ----------
def render_title_front(text, font_size, pad=10):
    font = ImageFont.truetype(FONT_TITLE, font_size)
    tmp = Image.new('RGBA', (4, 4))
    bbox = ImageDraw.Draw(tmp).textbbox((0, 0), text, font=font, stroke_width=0)
    tw = bbox[2] - bbox[0] + pad * 2
    th = bbox[3] - bbox[1] + pad * 2

    # mask (the text silhouette)
    mask = Image.new('L', (tw, th), 0)
    ImageDraw.Draw(mask).text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=255)

    # vertical gradient (cyan -> magenta) with upper highlight
    grad = np.zeros((th, tw, 3), dtype=np.float32)
    for y in range(th):
        k = y / max(1, th - 1)
        kk = k ** 0.9
        c = np.array(TEXT_TOP) * (1 - kk) + np.array(TEXT_BOT) * kk
        grad[y, :, :] = c
    # top highlight
    for y in range(th):
        k = y / max(1, th - 1)
        if k < 0.18:
            boost = (1 - k / 0.18) * 60
            grad[y, :, :] += boost
    # lower shadow band
    for y in range(th):
        k = y / max(1, th - 1)
        if k > 0.80:
            dark = (k - 0.80) / 0.20
            grad[y, :, :] *= (1 - dark * 0.25)
    front_rgb = np_to_img(grad, 'RGB').convert('RGBA')
    front_rgb.putalpha(mask)

    # outline: dilate mask
    kern_sz = max(3, int(font_size * 0.05))
    if kern_sz % 2 == 0:
        kern_sz += 1
    outline_mask = mask.filter(ImageFilter.MaxFilter(kern_sz))
    outline = Image.new('RGBA', (tw, th), OUTLINE + (255,))
    outline.putalpha(outline_mask)

    # thin dark inner-stroke for punch
    inner_dark = Image.new('RGBA', (tw, th), (20, 0, 35, 255))
    inner_mask = mask.filter(ImageFilter.MaxFilter(max(3, int(font_size * 0.02) | 1)))
    inner_dark.putalpha(inner_mask)

    composed = Image.alpha_composite(outline, inner_dark)
    composed = Image.alpha_composite(composed, front_rgb)
    return composed, mask

def make_extruded_title(text, font_size, depth, dx, dy):
    """Returns RGBA image of the 3D-extruded title."""
    front, mask = render_title_front(text, font_size)
    tw, th = front.size
    cw = tw + abs(dx) * depth
    ch = th + abs(dy) * depth
    canvas = Image.new('RGBA', (cw, ch), (0, 0, 0, 0))

    # side color + slight gradient across extrude depth
    # Paint back-to-front so overlap is correct.
    for i in range(depth, 0, -1):
        # deeper (i==depth) is the darkest; i==1 (closest to front) is the brightest side
        k = (depth - i) / max(1, depth - 1)  # 0 at back -> 1 near front
        col = tuple(int(lerp(TEXT_SIDE2[c], TEXT_SIDE[c], k)) for c in range(3))
        layer = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
        fill  = Image.new('RGBA', (tw, th), col + (255,))
        layer.paste(fill, (0, 0), mask)
        ox = i * dx if dx >= 0 else (abs(dx) * depth + i * dx)
        oy = i * dy if dy >= 0 else (abs(dy) * depth + i * dy)
        canvas.alpha_composite(layer, (ox, oy))

    # front face
    fx = 0 if dx >= 0 else abs(dx) * depth
    fy = 0 if dy >= 0 else abs(dy) * depth
    canvas.alpha_composite(front, (fx, fy))

    # bottom bevel highlight: a thin magenta line along bottom edge of front
    # achieved by using a translated mask difference
    return canvas

# ---------- lens flare ----------
def lens_flare(width, height, x_center, intensity):
    """Horizontal streak that looks like a lens flare."""
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # bright core
    core_h = max(4, int(SS * 3))
    for yy in range(height):
        k = abs(yy - height / 2) / (height / 2)
        if k > 1: continue
        a = int(255 * max(0, 1 - k) ** 3)
        if a < 2: continue
        # horizontal gradient along row centered at x_center
        row = Image.new('RGBA', (width, 1), (0, 0, 0, 0))
        rd = ImageDraw.Draw(row)
        for xx in range(width):
            dx = xx - x_center
            dist = abs(dx) / (width * 0.38)
            if dist > 1: continue
            aa = int(a * (1 - dist) ** 2 * intensity)
            rd.point((xx, 0), fill=(255, 245, 230, aa))
        img.paste(row, (0, yy), row)
    # add a bright blob at center
    blob = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blob)
    rr = int(height * 0.6)
    bd.ellipse([x_center - rr, height // 2 - rr, x_center + rr, height // 2 + rr],
               fill=(255, 240, 220, int(180 * intensity)))
    blob = blob.filter(ImageFilter.GaussianBlur(height * 0.25))
    img = Image.alpha_composite(img, blob)
    img = img.filter(ImageFilter.GaussianBlur(2 * SS))
    return img

# ---------- bloom ----------
def add_bloom(img, threshold=180, blur=20, strength=0.6):
    arr = np.array(img.convert('RGB'), dtype=np.float32)
    lum = (0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2])
    mask = np.clip((lum - threshold) / (255 - threshold), 0, 1) ** 1.5
    bright = arr * mask[:, :, None]
    bright_img = np_to_img(bright, 'RGB').filter(ImageFilter.GaussianBlur(blur))
    bright_arr = np.array(bright_img, dtype=np.float32)
    out = arr + bright_arr * strength
    return np_to_img(out, 'RGB')

# ---------- chromatic aberration ----------
def chromatic_aberration(img, shift_px=1):
    """Shift R channel +x, B channel -x by shift_px."""
    arr = np.array(img.convert('RGB'))
    r = np.roll(arr[:, :, 0], shift_px, axis=1)
    g = arr[:, :, 1]
    b = np.roll(arr[:, :, 2], -shift_px, axis=1)
    out = np.stack([r, g, b], axis=2)
    return Image.fromarray(out)

# ---------- scanlines + vignette ----------
_scanline_cache = None
def apply_scanlines_vignette(img):
    global _scanline_cache
    w, h = img.size
    if _scanline_cache is None or _scanline_cache.size != (w, h):
        sl = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(sl)
        for y in range(0, h, 2 * SS):
            d.line([(0, y), (w, y)], fill=(0, 0, 0, 40))
        # vignette
        vg = Image.new('L', (w, h), 0)
        vd = ImageDraw.Draw(vg)
        vd.ellipse([-w * 0.1, -h * 0.15, w * 1.1, h * 1.15], fill=255)
        vg = vg.filter(ImageFilter.GaussianBlur(min(w, h) * 0.15))
        vg_arr = 255 - np.array(vg)
        vg_img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        va = np.zeros((h, w, 4), dtype=np.uint8)
        va[:, :, 3] = (vg_arr * 0.55).astype(np.uint8)
        va[:, :, 0:3] = 0
        vg_img = Image.fromarray(va, 'RGBA')
        _scanline_cache = Image.alpha_composite(sl, vg_img)
    out = img.convert('RGBA')
    out.alpha_composite(_scanline_cache)
    return out

# ---------- main frame renderer ----------
def render_frame(frame_idx):
    t = frame_idx / N_FRAMES   # normalized time in [0, 1)

    # --- background
    bg, horizon_y = build_background(t)

    # --- grid
    grid = grid_layer(t, horizon_y)

    # --- stars
    st = stars_layer(t)

    # --- particles
    pt = particles_layer(t)

    # compose so far
    canvas = bg
    canvas = Image.alpha_composite(canvas, st)
    canvas = Image.alpha_composite(canvas, grid)
    canvas = Image.alpha_composite(canvas, pt)

    # --- TITLE ---
    title_text = "XOKRAM"
    # font size chosen relative to width
    fs = int(FW * 0.185)
    depth = max(6, int(fs * 0.22))
    title_img = make_extruded_title(title_text, fs, depth=depth, dx=-2, dy=2)

    # Subtle animation:
    # - scale breathing: 1.0 +/- 0.015  (2 cycles per loop)
    # - vertical bob: +/- 3 px          (1 cycle per loop)
    # - horizontal wobble: +/- 2 px     (1 cycle per loop)
    scale = 1.0 + 0.015 * math.sin(2 * math.pi * 2 * t)
    ty = int(round(4 * SS * math.sin(2 * math.pi * 1 * t)))
    tx = int(round(2 * SS * math.sin(2 * math.pi * 1 * t + math.pi / 2)))

    tw0, th0 = title_img.size
    tw = max(1, int(tw0 * scale))
    th = max(1, int(th0 * scale))
    title_scaled = title_img.resize((tw, th), Image.LANCZOS)

    # Soft drop shadow under title
    shadow_mask = title_scaled.split()[3].filter(ImageFilter.GaussianBlur(6 * SS))
    shadow = Image.new('RGBA', title_scaled.size, (0, 0, 0, 0))
    sh_arr = np.zeros((th, tw, 4), dtype=np.uint8)
    sh_arr[:, :, 3] = (np.array(shadow_mask) * 0.7).astype(np.uint8)
    sh_arr[:, :, 0:3] = 0
    shadow = Image.fromarray(sh_arr, 'RGBA')

    title_x = (FW - tw) // 2 + tx
    title_y = int(FH * 0.28) + ty

    canvas.alpha_composite(shadow, (title_x + 4 * SS, title_y + 8 * SS))
    canvas.alpha_composite(title_scaled, (title_x, title_y))

    # --- SUBTITLE: "el negrito"
    sub_font = ImageFont.truetype(FONT_SUB, int(FW * 0.062))
    sub_text = "el negrito"
    tmp = Image.new('RGBA', (4, 4))
    bb = ImageDraw.Draw(tmp).textbbox((0, 0), sub_text, font=sub_font, stroke_width=int(FW * 0.004))
    sw = bb[2] - bb[0]
    sh_ = bb[3] - bb[1]
    sub_img = Image.new('RGBA', (sw + 40, sh_ + 40), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sub_img)
    # outer stroke
    sd.text((20 - bb[0], 20 - bb[1]), sub_text, font=sub_font,
            fill=SUB_COLOR + (255,),
            stroke_width=max(2, int(FW * 0.004)),
            stroke_fill=(60, 10, 80, 255))
    # add a tiny purple glow
    glow = sub_img.filter(ImageFilter.GaussianBlur(3 * SS))
    glow = ImageChops.multiply(glow, Image.new('RGBA', glow.size, (255, 150, 255, 180)))
    sub_compose = Image.alpha_composite(glow, sub_img)
    sx = (FW - sub_compose.width) // 2
    sy = title_y + th - int(FH * 0.01)
    # subtle bob in opposite phase
    sy += int(round(3 * SS * math.sin(2 * math.pi * 1 * t + math.pi)))
    canvas.alpha_composite(sub_compose, (sx, sy))

    # --- LENS FLARE (one pass per loop, centered over title area)
    # moves from -20% to +120% across the canvas
    flare_cx = int(-0.2 * FW + t * 1.4 * FW)
    flare = lens_flare(FW, int(FH * 0.35), flare_cx, intensity=0.9)
    # place vertically centered on the title
    fy_ = title_y + th // 2 - flare.height // 2
    # additive-ish blend via alpha
    canvas.alpha_composite(flare, (0, fy_))

    # --- downsample to output size
    canvas_rgb = canvas.convert('RGB')
    canvas_rgb = canvas_rgb.resize((W, H), Image.LANCZOS)

    # --- bloom (final pass)
    canvas_rgb = add_bloom(canvas_rgb, threshold=165, blur=10, strength=0.42)

    # --- chromatic aberration (subtle)
    canvas_rgb = chromatic_aberration(canvas_rgb, shift_px=1)

    # --- scanlines + vignette
    canvas_rgba = apply_scanlines_vignette(canvas_rgb)
    final = canvas_rgba.convert('RGB')

    return final

def main():
    if os.path.exists(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)

    for i in range(N_FRAMES):
        img = render_frame(i)
        img.save(f"{OUT_DIR}/{i:04d}.png", optimize=True)
        if i % 10 == 0 or i == N_FRAMES - 1:
            print(f"  frame {i+1}/{N_FRAMES}", flush=True)

if __name__ == "__main__":
    main()

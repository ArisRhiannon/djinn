"""
Scene: Cozy Rain — synthwave-quality pipeline.
Night city through rainy glass: realistic drops with refraction, bokeh lights,
city silhouette with depth, falling rain streaks, rising mist.
Full pipeline: 2x SS, multi-stop gradients, parallax, 3D title, lens flare,
bloom, chromatic aberration, scanlines, vignette.
"""
import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

W, H = 640, 360
SS = 2
FW, FH = W * SS, H * SS
FPS = 24
DURATION = 4.0
N_FRAMES = int(FPS * DURATION)

FONT_TITLE = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
FONT_SUB = "/usr/share/fonts/truetype/lato/Lato-BlackItalic.ttf"
if not os.path.exists(FONT_TITLE):
    FONT_TITLE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
if not os.path.exists(FONT_SUB):
    FONT_SUB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"

# Palette — warm night city
BG_TOP = (8, 12, 22)
BG_MID = (18, 25, 45)
BG_HORIZON = (40, 38, 55)
GROUND_TOP = (25, 22, 30)
GROUND_BOT = (8, 6, 10)
BOKEH_COLORS = [(255, 200, 100), (255, 150, 70), (180, 200, 255), (255, 220, 140), (200, 160, 255), (100, 220, 200)]
RAIN_COLOR = (150, 175, 210)
DROP_HIGHLIGHT = (220, 235, 255)
DROP_EDGE = (60, 80, 120)
MIST_COLOR = (140, 150, 180)
TEXT_TOP = (255, 235, 190)
TEXT_BOT = (220, 140, 80)
TEXT_SIDE = (70, 40, 20)
TEXT_SIDE2 = (25, 12, 5)
OUTLINE = (255, 245, 230)
SUB_COLOR = (230, 210, 185)

def lerp(a, b, t): return a + (b - a) * t
def np_to_img(arr, mode='RGB'): return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode)

# ========== BACKGROUND ==========
def build_background(t):
    horizon_y = int(FH * 0.52)
    arr = np.zeros((FH, FW, 3), dtype=np.float32)
    for y in range(horizon_y):
        k = y / max(1, horizon_y - 1)
        if k < 0.6:
            kk = k / 0.6
            c = np.array(BG_TOP) * (1 - kk) + np.array(BG_MID) * kk
        else:
            kk = ((k - 0.6) / 0.4) ** 1.4
            c = np.array(BG_MID) * (1 - kk) + np.array(BG_HORIZON) * kk
        arr[y, :, :] = c
    for y in range(horizon_y, FH):
        k = ((y - horizon_y) / max(1, FH - horizon_y - 1)) ** 0.6
        c = np.array(GROUND_TOP) * (1 - k) + np.array(GROUND_BOT) * k
        arr[y, :, :] = c
    img = np_to_img(arr).convert('RGBA')

    # City skyline silhouette
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(42)
    x = 0
    while x < FW:
        bw = int(rng.uniform(25, 70) * SS)
        bh = int(rng.uniform(20, 100) * SS)
        by = horizon_y - bh
        # Building body (dark)
        d.rectangle([x, by, x + bw, horizon_y + 10], fill=(15, 18, 28, 255))
        # Lit windows
        for wy in range(by + 10, horizon_y - 5, int(14 * SS)):
            for wx in range(x + 6, x + bw - 6, int(10 * SS)):
                if rng.random() > 0.55:
                    warmth = rng.uniform(0.5, 1.0)
                    wc = (int(255 * warmth), int(180 * warmth), int(80 * warmth), int(60 + 80 * warmth))
                    d.rectangle([wx, wy, wx + int(5 * SS), wy + int(5 * SS)], fill=wc)
        x += bw + int(rng.uniform(3, 12) * SS)

    # Warm ambient glow at horizon (city light pollution)
    glow = Image.new('RGBA', (FW, FH), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(int(FH * 0.3), 0, -10):
        a = int(18 * (1 - r / (FH * 0.3)))
        gd.ellipse([FW // 2 - r * 4, horizon_y - r, FW // 2 + r * 4, horizon_y + r * 2],
                   fill=(180, 130, 70, a))
    glow = glow.filter(ImageFilter.GaussianBlur(25))
    img = Image.alpha_composite(img, glow)
    return img, horizon_y

# ========== BOKEH LIGHTS (out-of-focus city lights) ==========
_bokeh_cache = None
def bokeh_layer(t):
    global _bokeh_cache
    if _bokeh_cache is None:
        rng = np.random.default_rng(2025)
        n = 55
        _bokeh_cache = dict(
            x=rng.uniform(0, FW, n),
            y=rng.uniform(FH * 0.15, FH * 0.55, n),
            phase=rng.uniform(0, 2 * math.pi, n),
            size=rng.uniform(4, 14, n),
            cycles=rng.integers(1, 3, n),
            color_idx=rng.integers(0, len(BOKEH_COLORS), n),
        )
    s = _bokeh_cache
    img = Image.new('RGBA', (FW, FH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(len(s['x'])):
        b = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(2 * math.pi * s['cycles'][i] * t + s['phase'][i]))
        r = int(s['size'][i] * SS * (0.8 + 0.4 * b))
        a = int(100 * b)
        c = BOKEH_COLORS[s['color_idx'][i]]
        # Bokeh = soft circle with bright edge (ring bokeh)
        x, y = int(s['x'][i]), int(s['y'][i])
        # Outer ring
        d.ellipse([x - r, y - r, x + r, y + r], fill=c + (a // 2,), outline=c + (a,))
        # Inner bright center
        ir = max(1, r // 3)
        d.ellipse([x - ir, y - ir, x + ir, y + ir], fill=c + (int(a * 1.5),))
    # Heavy blur for out-of-focus look
    img = img.filter(ImageFilter.GaussianBlur(6 * SS))
    return img

# ========== RAIN DROPS ON GLASS (realistic) ==========
_drop_cache = None
def drops_layer(t):
    """Realistic water drops on glass: circular with refraction highlight, some with trails."""
    global _drop_cache
    if _drop_cache is None:
        rng = np.random.default_rng(123)
        n = 45
        _drop_cache = dict(
            x=rng.uniform(FW * 0.05, FW * 0.95, n),
            y=rng.uniform(FH * 0.05, FH * 0.85, n),
            r=rng.uniform(3, 12, n) * SS,
            trail_len=rng.uniform(0, 40, n) * SS,  # some have trails
            phase=rng.uniform(0, 2 * math.pi, n),
            speed=rng.uniform(0.2, 0.8, n),
        )
    dc = _drop_cache
    img = Image.new('RGBA', (FW, FH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(len(dc['x'])):
        x = int(dc['x'][i])
        # Drops slowly slide down
        slide = (dc['speed'][i] * FH * 0.3 * t) % (FH * 0.5)
        y = int((dc['y'][i] + slide) % (FH * 0.9))
        r = int(dc['r'][i])
        # Trail (thin line above drop)
        trail = int(dc['trail_len'][i])
        if trail > 5:
            trail_w = max(1, r // 3)
            for ty in range(0, trail, 3):
                ta = int(40 * (1 - ty / trail))
                d.ellipse([x - trail_w, y - ty - trail_w, x + trail_w, y - ty + trail_w],
                         fill=DROP_EDGE + (ta,))
        # Drop body: dark edge ring
        d.ellipse([x - r, y - r, x + r, y + r], fill=DROP_EDGE + (80,))
        # Inner lighter area (refraction of background light)
        ir = max(1, int(r * 0.7))
        d.ellipse([x - ir, y - ir + 1, x + ir, y + ir + 1], fill=(80, 100, 140, 60))
        # Highlight (top-left, like a lens)
        hr = max(1, int(r * 0.35))
        hx, hy = x - int(r * 0.25), y - int(r * 0.25)
        d.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=DROP_HIGHLIGHT + (140,))
        # Tiny bright specular dot
        d.ellipse([hx - 1, hy - 1, hx + 1, hy + 1], fill=(255, 255, 255, 200))
    # Slight blur for glass feel
    img = img.filter(ImageFilter.GaussianBlur(1.5))
    return img

# ========== FALLING RAIN STREAKS ==========
_rain_cache = None
def rain_layer(t):
    global _rain_cache
    if _rain_cache is None:
        rng = np.random.default_rng(777)
        n = 100
        _rain_cache = dict(
            x=rng.uniform(-FW * 0.1, FW * 1.1, n),
            y0=rng.uniform(0, FH, n),
            speed=rng.uniform(1.0, 2.0, n),
            length=rng.uniform(20, 55, n) * SS,
            alpha=rng.uniform(30, 100, n),
        )
    r = _rain_cache
    img = Image.new('RGBA', (FW, FH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(len(r['x'])):
        cycles = max(1, int(r['speed'][i]))
        y = (r['y0'][i] + cycles * FH * t) % (FH * 1.1)
        x = r['x'][i] - y * 0.05  # slight angle
        if 0 <= x <= FW and 0 <= y <= FH:
            length = r['length'][i]
            a = int(r['alpha'][i])
            d.line([(x, y), (x - length * 0.04, y + length)], fill=RAIN_COLOR + (a,), width=max(1, SS))
    glow = img.filter(ImageFilter.GaussianBlur(1.5 * SS))
    return Image.alpha_composite(glow, img)

# ========== MIST PARTICLES (rising, warm) ==========
_mist_cache = None
def mist_layer(t):
    global _mist_cache
    if _mist_cache is None:
        rng = np.random.default_rng(101)
        n = 30
        _mist_cache = dict(
            x=rng.uniform(0, FW, n),
            y0=rng.uniform(FH * 0.4, FH, n),
            speed=rng.uniform(0.3, 0.8, n),
            size=rng.uniform(2, 5, n),
            phase=rng.uniform(0, 2 * math.pi, n),
        )
    p = _mist_cache
    img = Image.new('RGBA', (FW, FH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(len(p['x'])):
        cycles = max(1, int(p['speed'][i]))
        y = (p['y0'][i] - cycles * FH * t) % FH
        x = p['x'][i] + 5 * math.sin(2 * math.pi * t * cycles + p['phase'][i])
        r = max(1, int(SS * p['size'][i]))
        a = int(80 * (0.5 + 0.5 * math.sin(2 * math.pi * 2 * t + p['phase'][i])))
        d.ellipse([x - r, y - r, x + r, y + r], fill=MIST_COLOR + (a,))
    return img.filter(ImageFilter.GaussianBlur(5 * SS))

# ========== TITLE (3D extruded, same as synthwave) ==========
def render_title_front(text, font_size, pad=10):
    font = ImageFont.truetype(FONT_TITLE, font_size)
    bbox = ImageDraw.Draw(Image.new('RGBA', (4, 4))).textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0] + pad * 2, bbox[3] - bbox[1] + pad * 2
    mask = Image.new('L', (tw, th), 0)
    ImageDraw.Draw(mask).text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=255)
    grad = np.zeros((th, tw, 3), dtype=np.float32)
    for y in range(th):
        k = (y / max(1, th - 1)) ** 0.9
        c = np.array(TEXT_TOP) * (1 - k) + np.array(TEXT_BOT) * k
        grad[y, :, :] = c
        if k < 0.18: grad[y, :, :] += (1 - k / 0.18) * 60
        if k > 0.80: grad[y, :, :] *= 1 - (k - 0.80) / 0.20 * 0.25
    front = np_to_img(grad).convert('RGBA')
    front.putalpha(mask)
    kern = max(3, int(font_size * 0.05)) | 1
    omask = mask.filter(ImageFilter.MaxFilter(kern))
    outline = Image.new('RGBA', (tw, th), OUTLINE + (255,))
    outline.putalpha(omask)
    inner = Image.new('RGBA', (tw, th), (40, 25, 10, 255))
    inner.putalpha(mask.filter(ImageFilter.MaxFilter(max(3, int(font_size * 0.02) | 1))))
    return Image.alpha_composite(Image.alpha_composite(outline, inner), front), mask

def make_extruded_title(text, font_size, depth, dx, dy):
    front, mask = render_title_front(text, font_size)
    tw, th = front.size
    cw, ch = tw + abs(dx) * depth, th + abs(dy) * depth
    canvas = Image.new('RGBA', (cw, ch), (0, 0, 0, 0))
    for i in range(depth, 0, -1):
        k = (depth - i) / max(1, depth - 1)
        col = tuple(int(lerp(TEXT_SIDE2[c], TEXT_SIDE[c], k)) for c in range(3))
        layer = Image.new('RGBA', (tw, th), col + (255,))
        layer.putalpha(mask)
        canvas.alpha_composite(layer, (i * abs(dx), i * dy))
    canvas.alpha_composite(front, (0, 0))
    return canvas

# ========== LENS FLARE (warm) ==========
def lens_flare(width, height, x_center, intensity):
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    for yy in range(0, height, 2):
        k = abs(yy - height / 2) / (height / 2)
        if k > 1: continue
        a = int(255 * max(0, 1 - k) ** 3)
        if a < 3: continue
        row = Image.new('RGBA', (width, 2), (0, 0, 0, 0))
        rd = ImageDraw.Draw(row)
        for xx in range(0, width, 3):
            dist = abs(xx - x_center) / (width * 0.38)
            if dist > 1: continue
            aa = int(a * (1 - dist) ** 2 * intensity)
            rd.rectangle([xx, 0, xx + 2, 1], fill=(255, 210, 140, aa))
        img.paste(row, (0, yy), row)
    blob = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    rr = int(height * 0.5)
    ImageDraw.Draw(blob).ellipse([x_center - rr, height // 2 - rr, x_center + rr, height // 2 + rr],
                                  fill=(255, 200, 120, int(140 * intensity)))
    blob = blob.filter(ImageFilter.GaussianBlur(height * 0.25))
    return Image.alpha_composite(img, blob).filter(ImageFilter.GaussianBlur(2 * SS))

# ========== POST-PROCESSING ==========
def add_bloom(img, threshold=180, blur=20, strength=0.6):
    arr = np.array(img.convert('RGB'), dtype=np.float32)
    lum = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
    m = np.clip((lum - threshold) / (255 - threshold), 0, 1) ** 1.5
    bright = np_to_img(arr * m[:, :, None]).filter(ImageFilter.GaussianBlur(blur))
    return np_to_img(arr + np.array(bright, dtype=np.float32) * strength)

def chromatic_aberration(img, shift_px=1):
    arr = np.array(img.convert('RGB'))
    return Image.fromarray(np.stack([np.roll(arr[:, :, 0], shift_px, 1), arr[:, :, 1], np.roll(arr[:, :, 2], -shift_px, 1)], axis=2))

_scanline_cache = None
def apply_scanlines_vignette(img):
    global _scanline_cache
    w, h = img.size
    if _scanline_cache is None or _scanline_cache.size != (w, h):
        sl = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(sl)
        for y in range(0, h, 2 * SS):
            d.line([(0, y), (w, y)], fill=(0, 0, 0, 30))
        vg = Image.new('L', (w, h), 0)
        ImageDraw.Draw(vg).ellipse([-w * 0.1, -h * 0.15, w * 1.1, h * 1.15], fill=255)
        vg = vg.filter(ImageFilter.GaussianBlur(min(w, h) * 0.15))
        va = np.zeros((h, w, 4), dtype=np.uint8)
        va[:, :, 3] = ((255 - np.array(vg)) * 0.6).astype(np.uint8)
        _scanline_cache = Image.alpha_composite(sl, Image.fromarray(va, 'RGBA'))
    out = img.convert('RGBA')
    out.alpha_composite(_scanline_cache)
    return out

# ========== MAIN RENDER ==========
def render_frame(frame_idx, title_text, sub_text, user_image=None):
    t = frame_idx / N_FRAMES
    bg, horizon_y = build_background(t)
    canvas = bg
    canvas = Image.alpha_composite(canvas, bokeh_layer(t))
    canvas = Image.alpha_composite(canvas, rain_layer(t))
    canvas = Image.alpha_composite(canvas, drops_layer(t))
    canvas = Image.alpha_composite(canvas, mist_layer(t))

    # 3D Title
    fs = int(FW * 0.185)
    if len(title_text) > 6: fs = int(fs * 6 / len(title_text))
    depth = max(6, int(fs * 0.22))
    title_img = make_extruded_title(title_text.upper(), fs, depth, -2, 2)
    scale = 1.0 + 0.015 * math.sin(2 * math.pi * 2 * t)
    ty = int(4 * SS * math.sin(2 * math.pi * t))
    tx = int(2 * SS * math.sin(2 * math.pi * t + math.pi / 2))
    tw0, th0 = title_img.size
    tw, th = max(1, int(tw0 * scale)), max(1, int(th0 * scale))
    title_scaled = title_img.resize((tw, th), Image.LANCZOS)
    sm = title_scaled.split()[3].filter(ImageFilter.GaussianBlur(6 * SS))
    sh_arr = np.zeros((th, tw, 4), dtype=np.uint8)
    sh_arr[:, :, 3] = (np.array(sm) * 0.7).astype(np.uint8)
    title_x = (FW - tw) // 2 + tx
    title_y = int(FH * 0.28) + ty
    canvas.alpha_composite(Image.fromarray(sh_arr, 'RGBA'), (title_x + 4 * SS, title_y + 8 * SS))
    canvas.alpha_composite(title_scaled, (title_x, title_y))

    # Subtitle
    if sub_text:
        sf = ImageFont.truetype(FONT_SUB, int(FW * 0.062))
        if len(sub_text) > 12: sf = ImageFont.truetype(FONT_SUB, int(FW * 0.062 * 12 / len(sub_text)))
        bb = ImageDraw.Draw(Image.new('RGBA', (4, 4))).textbbox((0, 0), sub_text, font=sf, stroke_width=int(FW * 0.004))
        sw, sh_ = bb[2] - bb[0], bb[3] - bb[1]
        si = Image.new('RGBA', (sw + 40, sh_ + 40), (0, 0, 0, 0))
        ImageDraw.Draw(si).text((20 - bb[0], 20 - bb[1]), sub_text, font=sf,
                                 fill=SUB_COLOR + (255,), stroke_width=max(2, int(FW * 0.004)), stroke_fill=(35, 25, 15, 255))
        gl = ImageChops.multiply(si.filter(ImageFilter.GaussianBlur(3 * SS)), Image.new('RGBA', si.size, (255, 200, 140, 180)))
        sc = Image.alpha_composite(gl, si)
        canvas.alpha_composite(sc, ((FW - sc.width) // 2, title_y + th - int(FH * 0.01) + int(3 * SS * math.sin(2 * math.pi * t + math.pi))))

    # User image — rendered AFTER title so it's visible on top
    if user_image:
        ph = int(FW * 0.13)
        photo = user_image.resize((ph, ph), Image.LANCZOS).convert('RGBA')
        frame = Image.new('RGBA', (ph + 16, ph + 16), (0, 0, 0, 0))
        ImageDraw.Draw(frame).rectangle([0, 0, ph + 15, ph + 15], fill=(180, 140, 70, 50))
        frame = frame.filter(ImageFilter.GaussianBlur(5))
        frame.alpha_composite(photo, (8, 8))
        canvas.alpha_composite(frame, (int(FW * 0.82), int(FH * 0.05) + int(3 * math.sin(2 * math.pi * t))))

    # Lens flare
    flare_cx = int(-0.2 * FW + t * 1.4 * FW)
    flare = lens_flare(FW, int(FH * 0.3), flare_cx, intensity=0.6)
    canvas.alpha_composite(flare, (0, title_y + th // 2 - flare.height // 2))

    # === FOREGROUND: large close rain drops (over title for depth) ===
    fg = Image.new('RGBA', (FW, FH), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fg)
    rng_fg = np.random.default_rng(999)
    for i in range(8):
        fx = int(rng_fg.uniform(0, FW))
        fy = int((rng_fg.uniform(0, FH) + FH * 2.5 * t * (1 + i * 0.1)) % (FH * 1.2))
        if fy < FH:
            fr = int(rng_fg.uniform(4, 8) * SS)
            fa = int(60 + 30 * math.sin(t * math.pi * 4 + i))
            fd.ellipse([fx - fr, fy - fr, fx + fr, fy + fr], fill=(100, 130, 170, fa))
            # Streak
            fd.line([(fx, fy), (fx - 2, fy + fr * 4)], fill=(120, 150, 190, fa // 2), width=max(1, SS))
    fg = fg.filter(ImageFilter.GaussianBlur(3))
    canvas = Image.alpha_composite(canvas, fg)

    # Post-processing
    rgb = canvas.convert('RGB').resize((W, H), Image.LANCZOS)
    rgb = add_bloom(rgb, threshold=180, blur=12, strength=0.35)
    rgb = chromatic_aberration(rgb, shift_px=1)
    return apply_scanlines_vignette(rgb).convert('RGB')

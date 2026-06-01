"""
Scene: Dreamland — synthwave-quality pipeline.
Ethereal night sky with aurora borealis, layered clouds with parallax depth,
floating sparkle particles, soft moonlight. Magical, not flat.
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

# Palette — dreamy ethereal
BG_TOP = (10, 8, 35)
BG_MID = (30, 20, 70)
BG_HORIZON = (80, 50, 120)
GROUND_TOP = (40, 30, 80)
GROUND_BOT = (15, 10, 40)
AURORA_COLORS = [(80, 255, 180), (100, 200, 255), (180, 100, 255), (255, 150, 200)]
MOON_COLOR = (240, 235, 255)
STAR_COLOR = (220, 220, 255)
CLOUD_COLOR = (60, 50, 100)
CLOUD_HIGHLIGHT = (120, 100, 180)
SPARKLE_COLORS = [(255, 255, 200), (200, 220, 255), (255, 200, 255), (180, 255, 220)]
TEXT_TOP = (200, 240, 255)
TEXT_BOT = (255, 130, 220)
TEXT_SIDE = (50, 20, 80)
TEXT_SIDE2 = (20, 8, 35)
OUTLINE = (255, 255, 255)
SUB_COLOR = (220, 200, 255)

def lerp(a, b, t): return a + (b - a) * t
def np_to_img(arr, mode='RGB'): return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode)

# ========== BACKGROUND ==========
def build_background(t):
    horizon_y = int(FH * 0.65)
    arr = np.zeros((FH, FW, 3), dtype=np.float32)
    for y in range(horizon_y):
        k = y / max(1, horizon_y - 1)
        if k < 0.5:
            kk = k / 0.5
            c = np.array(BG_TOP) * (1 - kk) + np.array(BG_MID) * kk
        else:
            kk = ((k - 0.5) / 0.5) ** 1.3
            c = np.array(BG_MID) * (1 - kk) + np.array(BG_HORIZON) * kk
        arr[y, :, :] = c
    for y in range(horizon_y, FH):
        k = ((y - horizon_y) / max(1, FH - horizon_y - 1)) ** 0.7
        c = np.array(GROUND_TOP) * (1 - k) + np.array(GROUND_BOT) * k
        arr[y, :, :] = c
    img = np_to_img(arr).convert('RGBA')

    # Moon (upper right)
    moon_cx, moon_cy = int(FW * 0.78), int(FH * 0.18)
    moon_r = int(FH * 0.09)
    moon_size = moon_r * 2 + 4
    moon = Image.new('RGBA', (moon_size, moon_size), (0, 0, 0, 0))
    ImageDraw.Draw(moon).ellipse([2, 2, moon_size - 2, moon_size - 2], fill=MOON_COLOR + (220,))
    # Glow
    glow = Image.new('RGBA', (moon_size + 80, moon_size + 80), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for rr, aa in [(moon_r + 35, 15), (moon_r + 20, 30), (moon_r + 8, 50)]:
        gd.ellipse([glow.width // 2 - rr, glow.height // 2 - rr, glow.width // 2 + rr, glow.height // 2 + rr],
                   fill=(200, 190, 255, aa))
    glow = glow.filter(ImageFilter.GaussianBlur(15))
    img.alpha_composite(glow, (moon_cx - glow.width // 2, moon_cy - glow.height // 2))
    img.alpha_composite(moon, (moon_cx - moon_size // 2, moon_cy - moon_size // 2))

    # Rolling hills silhouette at horizon
    d = ImageDraw.Draw(img)
    hill_pts = [(0, horizon_y + 20)]
    for x in range(0, FW + 40, 40):
        y_off = int(25 * math.sin(x * 0.003) + 15 * math.sin(x * 0.007 + 1.5))
        hill_pts.append((x, horizon_y - y_off))
    hill_pts.append((FW, horizon_y + 20))
    d.polygon(hill_pts, fill=(25, 18, 55, 255))

    return img, horizon_y

# ========== STARS ==========
_star_cache = None
def stars_layer(t):
    global _star_cache
    if _star_cache is None:
        rng = np.random.default_rng(2024)
        n = 120
        _star_cache = dict(
            x=rng.uniform(0, FW, n),
            y=rng.uniform(0, FH * 0.6, n),
            phase=rng.uniform(0, 2 * math.pi, n),
            size=rng.uniform(0.5, 1.6, n),
            cycles=rng.integers(1, 4, n),
        )
    s = _star_cache
    img = Image.new('RGBA', (FW, FH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(len(s['x'])):
        b = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(2 * math.pi * s['cycles'][i] * t + s['phase'][i]))
        a = int(220 * b)
        r = max(1, int(SS * s['size'][i] * (0.5 + 0.7 * b)))
        d.ellipse([s['x'][i] - r, s['y'][i] - r, s['x'][i] + r, s['y'][i] + r], fill=STAR_COLOR + (a,))
    glow = img.filter(ImageFilter.GaussianBlur(2 * SS))
    glow = ImageChops.multiply(glow, Image.new('RGBA', glow.size, (255, 255, 255, 130)))
    return Image.alpha_composite(glow, img)

# ========== AURORA BOREALIS (wavy colored bands) ==========
def aurora_layer(t):
    img = Image.new('RGBA', (FW, FH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    n_bands = 4
    for band in range(n_bands):
        color = AURORA_COLORS[band]
        base_y = int(FH * (0.15 + band * 0.08))
        pts = []
        for x in range(0, FW + 20, 20):
            # Multiple sine waves for organic movement
            y = base_y + int(20 * math.sin(x * 0.004 + t * 2 * math.pi * (1 + band * 0.3) + band * 1.5))
            y += int(10 * math.sin(x * 0.008 + t * 2 * math.pi * 0.7 + band))
            pts.append((x, y))
        # Draw as thick semi-transparent band
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            a = int(50 + 30 * math.sin(t * 2 * math.pi + i * 0.1 + band))
            for dy in range(-8, 9, 2):
                aa = int(a * max(0, 1 - abs(dy) / 8))
                d.line([(x1, y1 + dy), (x2, y2 + dy)], fill=color + (aa,), width=2)
    img = img.filter(ImageFilter.GaussianBlur(4 * SS))
    return img

# ========== CLOUDS (parallax layers) ==========
_cloud_cache = None
def clouds_layer(t):
    global _cloud_cache
    if _cloud_cache is None:
        rng = np.random.default_rng(555)
        n = 8
        _cloud_cache = dict(
            x=rng.uniform(-FW * 0.2, FW * 1.2, n),
            y=rng.uniform(FH * 0.35, FH * 0.6, n),
            w=rng.uniform(80, 200, n) * SS,
            h=rng.uniform(20, 50, n) * SS,
            speed=rng.uniform(0.2, 0.6, n),
        )
    c = _cloud_cache
    img = Image.new('RGBA', (FW, FH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(len(c['x'])):
        x = (c['x'][i] + c['speed'][i] * FW * t) % (FW * 1.4) - FW * 0.2
        y = c['y'][i]
        w, h = int(c['w'][i]), int(c['h'][i])
        # Cloud = overlapping ellipses with highlight on top
        d.ellipse([x, y, x + w, y + h], fill=CLOUD_COLOR + (80,))
        d.ellipse([x + w * 0.1, y - h * 0.2, x + w * 0.7, y + h * 0.5], fill=CLOUD_COLOR + (60,))
        d.ellipse([x + w * 0.3, y - h * 0.1, x + w * 0.9, y + h * 0.6], fill=CLOUD_COLOR + (70,))
        # Top highlight (moonlit)
        d.ellipse([x + w * 0.2, y - h * 0.15, x + w * 0.6, y + h * 0.3], fill=CLOUD_HIGHLIGHT + (40,))
    img = img.filter(ImageFilter.GaussianBlur(6 * SS))
    return img

# ========== SPARKLE PARTICLES ==========
_sparkle_cache = None
def sparkles_layer(t):
    global _sparkle_cache
    if _sparkle_cache is None:
        rng = np.random.default_rng(999)
        n = 40
        _sparkle_cache = dict(
            x=rng.uniform(0, FW, n),
            y0=rng.uniform(0, FH, n),
            speed=rng.uniform(0.3, 1.0, n),
            size=rng.uniform(0.8, 2.5, n),
            phase=rng.uniform(0, 2 * math.pi, n),
            color_idx=rng.integers(0, len(SPARKLE_COLORS), n),
        )
    p = _sparkle_cache
    img = Image.new('RGBA', (FW, FH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(len(p['x'])):
        cycles = max(1, int(p['speed'][i]))
        y = (p['y0'][i] - cycles * FH * t) % FH
        x = p['x'][i] + 4 * math.sin(2 * math.pi * t * cycles + p['phase'][i])
        b = 0.5 + 0.5 * math.sin(2 * math.pi * 3 * t + p['phase'][i])
        if b > 0.4:
            r = max(1, int(SS * p['size'][i] * b))
            a = int(200 * b)
            c = SPARKLE_COLORS[p['color_idx'][i]]
            d.ellipse([x - r, y - r, x + r, y + r], fill=c + (a,))
    glow = img.filter(ImageFilter.GaussianBlur(3 * SS))
    return Image.alpha_composite(glow, img)

# ========== TITLE ==========
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
    inner = Image.new('RGBA', (tw, th), (30, 10, 50, 255))
    inner.putalpha(mask.filter(ImageFilter.MaxFilter(max(3, int(font_size * 0.02) | 1))))
    return Image.alpha_composite(Image.alpha_composite(outline, inner), front), mask

def make_extruded_title(text, font_size, depth, dx, dy):
    front, mask = render_title_front(text, font_size)
    tw, th = front.size
    canvas = Image.new('RGBA', (tw + abs(dx) * depth, th + abs(dy) * depth), (0, 0, 0, 0))
    for i in range(depth, 0, -1):
        k = (depth - i) / max(1, depth - 1)
        col = tuple(int(lerp(TEXT_SIDE2[c], TEXT_SIDE[c], k)) for c in range(3))
        layer = Image.new('RGBA', (tw, th), col + (255,))
        layer.putalpha(mask)
        canvas.alpha_composite(layer, (i * abs(dx), i * dy))
    canvas.alpha_composite(front, (0, 0))
    return canvas

# ========== LENS FLARE (cool/magical) ==========
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
            rd.rectangle([xx, 0, xx + 2, 1], fill=(200, 180, 255, aa))
        img.paste(row, (0, yy), row)
    blob = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    rr = int(height * 0.5)
    ImageDraw.Draw(blob).ellipse([x_center - rr, height // 2 - rr, x_center + rr, height // 2 + rr],
                                  fill=(180, 160, 255, int(130 * intensity)))
    blob = blob.filter(ImageFilter.GaussianBlur(height * 0.25))
    return Image.alpha_composite(img, blob).filter(ImageFilter.GaussianBlur(2 * SS))

# ========== POST-PROCESSING ==========
def add_bloom(img, threshold=160, blur=18, strength=0.5):
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
        va[:, :, 3] = ((255 - np.array(vg)) * 0.5).astype(np.uint8)
        _scanline_cache = Image.alpha_composite(sl, Image.fromarray(va, 'RGBA'))
    out = img.convert('RGBA')
    out.alpha_composite(_scanline_cache)
    return out

# ========== MAIN RENDER ==========
def render_frame(frame_idx, title_text, sub_text, user_image=None):
    t = frame_idx / N_FRAMES
    bg, horizon_y = build_background(t)
    canvas = bg
    canvas = Image.alpha_composite(canvas, stars_layer(t))
    canvas = Image.alpha_composite(canvas, aurora_layer(t))
    canvas = Image.alpha_composite(canvas, clouds_layer(t))
    canvas = Image.alpha_composite(canvas, sparkles_layer(t))

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
                                 fill=SUB_COLOR + (255,), stroke_width=max(2, int(FW * 0.004)), stroke_fill=(30, 15, 60, 255))
        gl = ImageChops.multiply(si.filter(ImageFilter.GaussianBlur(3 * SS)), Image.new('RGBA', si.size, (200, 150, 255, 180)))
        sc = Image.alpha_composite(gl, si)
        canvas.alpha_composite(sc, ((FW - sc.width) // 2, title_y + th - int(FH * 0.01) + int(3 * SS * math.sin(2 * math.pi * t + math.pi))))

    # User image — rendered AFTER title so it's visible
    if user_image:
        ph = int(FW * 0.12)
        photo = user_image.resize((ph, ph), Image.LANCZOS).convert('RGBA')
        frame = Image.new('RGBA', (ph + 16, ph + 16), (0, 0, 0, 0))
        ImageDraw.Draw(frame).ellipse([0, 0, ph + 15, ph + 15], fill=(150, 100, 255, 40))
        frame = frame.filter(ImageFilter.GaussianBlur(6))
        frame.alpha_composite(photo, (8, 8))
        bob = int(6 * math.sin(2 * math.pi * t))
        canvas.alpha_composite(frame, (int(FW * 0.82), int(FH * 0.05) + bob))

    # Lens flare (magical purple)
    flare_cx = int(-0.2 * FW + t * 1.4 * FW)
    flare = lens_flare(FW, int(FH * 0.3), flare_cx, intensity=0.7)
    canvas.alpha_composite(flare, (0, title_y + th // 2 - flare.height // 2))

    # === FOREGROUND: large close sparkles drifting (over title for depth) ===
    fg = Image.new('RGBA', (FW, FH), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fg)
    rng_fg = np.random.default_rng(777)
    for i in range(10):
        fx = int((rng_fg.uniform(0, FW) + FW * 0.3 * t * (1 + i * 0.05)) % FW)
        fy = int(rng_fg.uniform(FH * 0.1, FH * 0.8))
        b = 0.5 + 0.5 * math.sin(2 * math.pi * 2 * t + i * 1.3)
        if b > 0.5:
            fr = int(rng_fg.uniform(3, 7) * SS * b)
            fa = int(120 * b)
            c = SPARKLE_COLORS[i % len(SPARKLE_COLORS)]
            fd.ellipse([fx - fr, fy - fr, fx + fr, fy + fr], fill=c + (fa,))
    fg = fg.filter(ImageFilter.GaussianBlur(4 * SS))
    canvas = Image.alpha_composite(canvas, fg)

    # Post-processing
    rgb = canvas.convert('RGB').resize((W, H), Image.LANCZOS)
    rgb = add_bloom(rgb, threshold=160, blur=15, strength=0.45)
    rgb = chromatic_aberration(rgb, shift_px=1)
    return apply_scanlines_vignette(rgb).convert('RGB')

"""Render an animated logo outro as PNG frames.

usage: python3 render.py <W> <H> <outdir>
"""
import sys, os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, OUT = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
os.makedirs(OUT, exist_ok=True)
FPS, DUR = 30, 4.0
LOGO = '/root/.claude/uploads/400bf3a6-24a7-5a24-b4ab-4d5fbb42d185/212d816a-image.png'
FONT = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'
LIME = (204, 255, 0)
BG = (10, 10, 10)

# ---------- split logo into layers ----------
src = Image.open(LOGO).convert('RGBA')
a = np.array(src)
lime = (a[..., 1] > 200) & (a[..., 2] < 80) & (a[..., 0] > 150) & (a[..., 3] > 0)
yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]

def layer(mask):
    out = a.copy(); out[~mask] = 0
    return Image.fromarray(out)

scale = (W * 0.70 if W < H else H * 0.52) / src.width
def up(im):
    return im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)

shield_top = up(layer(~lime & (yy < 100)))
shield_bot = up(layer(~lime & (yy > 345)))
letter_p = up(layer(lime & (xx < 324)))
letter_h = up(layer(lime & (xx >= 324)))
letters = up(layer(lime))
LW, LH = letters.size

# lime glow from letters
glow_src = Image.new('RGBA', (LW + 200, LH + 200), (0, 0, 0, 0))
glow_src.paste(Image.new('RGBA', letters.size, LIME + (255,)), (100, 100), letters)
glow = glow_src.filter(ImageFilter.GaussianBlur(28 * scale))

# logo placement (vertical: a bit above center to leave room for text)
lx = (W - LW) // 2
ly = int(H * 0.40 - LH / 2) if H > W else int(H * 0.42 - LH / 2)

# background radial lime bloom
cy = ly + LH // 2
gy, gx = np.mgrid[0:H, 0:W]
d = np.sqrt((gx - W / 2) ** 2 + ((gy - cy) * 1.1) ** 2) / (max(W, H) * 0.45)
radial = np.clip(1 - d, 0, 1) ** 2  # 0..1

# text
name = 'UPSTATE POWER HOUSE'
fsize = int(min(W, H) * 0.046)
font = ImageFont.truetype(FONT, fsize)
track = int(fsize * 0.22)
widths = [font.getbbox(c)[2] - font.getbbox(c)[0] if c != ' ' else fsize * 0.3 for c in name]
tw = int(sum(widths) + track * (len(name) - 1))
text_img = Image.new('RGBA', (tw + 20, int(fsize * 1.4)), (0, 0, 0, 0))
td = ImageDraw.Draw(text_img)
x = 10
for c, w in zip(name, widths):
    if c != ' ':
        td.text((x - font.getbbox(c)[0], 0), c, font=font, fill=(255, 255, 255, 255))
    x += w + track
ty = ly + LH + int(H * (0.07 if H > W else 0.07))
line_y = ty - int(fsize * 0.55)

# ---------- easing ----------
def clamp(v): return max(0.0, min(1.0, v))
def prog(t, t0, t1): return clamp((t - t0) / (t1 - t0))
def ease_out_cubic(p): return 1 - (1 - p) ** 3
def ease_in_cubic(p): return p ** 3
def ease_out_back(p, s=1.6):
    p -= 1
    return p * p * ((s + 1) * p + s) + 1

def with_alpha(im, k):
    if k >= 1: return im
    im = im.copy()
    al = im.getchannel('A').point(lambda v: int(v * k))
    im.putalpha(al)
    return im

IMPACT = 1.0

def frame(t):
    # background + bloom (spikes at impact, settles)
    bloom = 0.10 * prog(t, 0.0, 0.8)
    if t >= IMPACT:
        bloom += 0.35 * math.exp(-(t - IMPACT) * 4)
    bg = np.empty((H, W, 3), np.float32)
    for i in range(3):
        bg[..., i] = BG[i] + (LIME[i] - BG[i]) * radial * bloom
    canvas = Image.fromarray(bg.clip(0, 255).astype(np.uint8)).convert('RGBA')

    # camera shake after impact
    sx = sy = 0
    if IMPACT <= t < IMPACT + 0.35:
        k = math.exp(-(t - IMPACT) * 12)
        sx = int(14 * k * math.sin(t * 90))
        sy = int(10 * k * math.cos(t * 75))
    ox, oy = lx + sx, ly + sy

    # shield pieces
    p = prog(t, 0.10, 0.60)
    if p > 0:
        dy = int((1 - ease_out_back(p)) * -H * 0.35)
        canvas.alpha_composite(with_alpha(shield_top, clamp(p * 2.5)), (ox, oy + dy))
    p = prog(t, 0.22, 0.72)
    if p > 0:
        dy = int((1 - ease_out_back(p)) * H * 0.35)
        canvas.alpha_composite(with_alpha(shield_bot, clamp(p * 2.5)),
                               (ox, oy + dy))

    # glow (after impact)
    if t >= IMPACT:
        g = 0.55 + 0.9 * math.exp(-(t - IMPACT) * 3.5) + 0.08 * math.sin(t * 5)
        canvas.alpha_composite(with_alpha(glow, clamp(g)), (ox - 100, oy - 100))

    # P and H slam in, with motion-trail ghosts
    p = prog(t, 0.62, IMPACT)
    if p > 0:
        off = (1 - ease_in_cubic(p)) * W * 0.9
        for ghost in (3, 2, 1, 0):
            if ghost and (p >= 1 or p < 0.05):
                continue
            go = off + ghost * W * 0.04 * (1 - p + 0.2)
            k = 1.0 if ghost == 0 else 0.25 / ghost
            canvas.alpha_composite(with_alpha(letter_p, k), (int(ox - go), oy))
            canvas.alpha_composite(with_alpha(letter_h, k), (int(ox + go), oy))

    # light sweep across letters
    p = prog(t, 1.55, 2.15)
    if 0 < p < 1:
        band = Image.new('L', (LW, LH), 0)
        bd = ImageDraw.Draw(band)
        cx = -LW * 0.4 + p * LW * 1.8
        bw = LW * 0.12
        bd.polygon([(cx, 0), (cx + bw, 0), (cx + bw - LH * 0.5, LH), (cx - LH * 0.5, LH)], fill=200)
        band = band.filter(ImageFilter.GaussianBlur(10))
        m = np.minimum(np.array(band), np.array(letters.getchannel('A')))
        shine = Image.new('RGBA', (LW, LH), (255, 255, 255, 0))
        shine.putalpha(Image.fromarray(m))
        canvas.alpha_composite(shine, (ox, oy))

    # accent line grows from center, then name rises in
    p = ease_out_cubic(prog(t, 1.25, 1.75))
    if p > 0:
        half = int(tw * 0.5 * p)
        ld = ImageDraw.Draw(canvas)
        th = max(3, int(W * 0.004))
        ld.rectangle([W // 2 - half, line_y, W // 2 + half, line_y + th], fill=LIME + (255,))
    p = ease_out_cubic(prog(t, 1.45, 2.05))
    if p > 0:
        canvas.alpha_composite(with_alpha(text_img, p),
                               ((W - text_img.width) // 2, int(ty + (1 - p) * fsize * 0.8)))

    # white flash on impact
    if IMPACT <= t < IMPACT + 0.25:
        k = (1 - (t - IMPACT) / 0.25) ** 2 * 0.55
        canvas.alpha_composite(Image.new('RGBA', (W, H), (255, 255, 255, int(255 * k))))

    # subtle slow push-in over the whole clip
    z = 1 + 0.035 * ease_out_cubic(prog(t, IMPACT, DUR))
    img = canvas.convert('RGB')
    if z > 1.0005:
        zw, zh = int(W * z), int(H * z)
        img = img.resize((zw, zh), Image.BICUBIC).crop(((zw - W) // 2, (zh - H) // 2,
                                                         (zw - W) // 2 + W, (zh - H) // 2 + H))
    return img

for i in range(int(FPS * DUR)):
    frame(i / FPS).save(f'{OUT}/f{i:04d}.png')
print('done', OUT)

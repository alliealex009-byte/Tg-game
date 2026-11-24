"""Cartoon DPs for computer players: webapp/avatars/g0..g11.png (girls) and b0..b11.png (boys). Original art."""
import os, random
from PIL import Image, ImageDraw
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webapp", "avatars")
os.makedirs(OUT, exist_ok=True)
S = 4; N = 256 * S
SKIN = ["#f1c9a5", "#e0a97d", "#c68642", "#a8693a", "#8d5524", "#f5d5b8"]
HAIR = ["#1b1210", "#2b1a12", "#3b2416", "#0f0a08", "#4a2c1a"]
BG = [("#ff9a9e", "#fad0c4"), ("#a18cd1", "#fbc2eb"), ("#84fab0", "#8fd3f4"), ("#ffecd2", "#fcb69f"), ("#f6d365", "#fda085"), ("#89f7fe", "#66a6ff"), ("#fbc2eb", "#a6c1ee"), ("#c1dfc4", "#deecdd")]
TOPS_G = ["#e91e63", "#7e57c2", "#26a69a", "#ff7043", "#ffb300", "#5c6bc0"]
TOPS_B = ["#1e88e5", "#43a047", "#ef6c00", "#6d4c41", "#546e7a", "#c62828"]
def hexrgb(h): return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
def make(kind, i):
    r = random.Random(f"{kind}{i}")
    c1, c2 = BG[(i + (3 if kind == "b" else 0)) % len(BG)]
    im = Image.new("RGB", (N, N)); d = ImageDraw.Draw(im)
    for y in range(N):
        t = y / N; a, b = hexrgb(c1), hexrgb(c2); d.line([(0, y), (N, y)], fill=tuple(int(a[k] * (1 - t) + b[k] * t) for k in range(3)))
    skin, hair = SKIN[r.randrange(len(SKIN))], HAIR[r.randrange(len(HAIR))]
    top = (TOPS_G if kind == "g" else TOPS_B)[i % 6]; cx, cy = N // 2, int(N * .46)
    fw, fh = int(N * .21), int(N * .25)
    girl = kind == "g"; style = i % 4
    if girl and style in (0, 1):   # long hair behind
        d.rounded_rectangle([cx - fw - 30 * S, cy - fh - 10 * S, cx + fw + 30 * S, cy + fh + 90 * S], 70 * S, fill=hair)
    if girl and style == 2:        # bun
        d.ellipse([cx - 34 * S, cy - fh - 52 * S, cx + 34 * S, cy - fh + 16 * S], fill=hair)
    d.pieslice([cx - 105 * S, N - 80 * S, cx + 105 * S, N + 90 * S], 180, 360, fill=top)            # shoulders
    if girl: d.arc([cx - 62 * S, N - 80 * S, cx + 62 * S, N - 8 * S], 0, 180, fill="#ffffffaa", width=4 * S)
    d.rectangle([cx - 18 * S, cy + fh - 14 * S, cx + 18 * S, cy + fh + 30 * S], fill=skin)           # neck
    d.ellipse([cx - fw, cy - fh, cx + fw, cy + fh], fill=skin)                                        # face
    d.ellipse([cx - fw - 6 * S, cy - 10 * S, cx - fw + 8 * S, cy + 20 * S], fill=skin); d.ellipse([cx + fw - 8 * S, cy - 10 * S, cx + fw + 6 * S, cy + 20 * S], fill=skin)
    # hair front
    if girl:
        if style == 3:   # bob
            d.chord([cx - fw - 14 * S, cy - fh - 16 * S, cx + fw + 14 * S, cy + 24 * S], 180, 360, fill=hair)
            d.rounded_rectangle([cx - fw - 14 * S, cy - 20 * S, cx - fw + 10 * S, cy + fh - 5 * S], 12 * S, fill=hair); d.rounded_rectangle([cx + fw - 10 * S, cy - 20 * S, cx + fw + 14 * S, cy + fh - 5 * S], 12 * S, fill=hair)
        else:
            d.chord([cx - fw - 8 * S, cy - fh - 14 * S, cx + fw + 8 * S, cy + 10 * S], 180, 360, fill=hair)
            d.polygon([(cx - 4 * S, cy - fh - 6 * S), (cx - fw - 4 * S, cy - 6 * S), (cx - fw + 22 * S, cy - 40 * S)], fill=skin) if False else None
    else:
        if style == 3:   # turban-style
            d.ellipse([cx - fw - 10 * S, cy - fh - 34 * S, cx + fw + 10 * S, cy - 18 * S + 10 * S], fill=["#e53935", "#fb8c00", "#3949ab"][i % 3])
            d.arc([cx - fw - 10 * S, cy - fh - 30 * S, cx + fw + 10 * S, cy - 14 * S], 200, 340, fill="#ffffff66", width=3 * S)
        else:
            d.chord([cx - fw - 6 * S, cy - fh - 18 * S, cx + fw + 6 * S, cy + 0 * S], 180, 360, fill=hair)
    ey = cy - 4 * S
    for sx in (-1, 1):
        ex = cx + sx * 24 * S
        d.ellipse([ex - 9 * S, ey - 8 * S, ex + 9 * S, ey + 8 * S], fill="white"); d.ellipse([ex - 5 * S, ey - 5 * S, ex + 5 * S, ey + 5 * S], fill="#2b1a12"); d.ellipse([ex - 2 * S, ey - 4 * S, ex + 1 * S, ey - 1 * S], fill="white")
        d.arc([ex - 12 * S, ey - 20 * S, ex + 12 * S, ey - 4 * S], 200, 340, fill=hair, width=3 * S)
        if girl: d.arc([ex - 11 * S, ey - 11 * S, ex + 11 * S, ey + 5 * S], 195, 345, fill="#1b1210", width=2 * S)
    d.arc([cx - 24 * S, cy + 8 * S, cx + 24 * S, cy + 44 * S], 20, 160, fill="#7a2e2e" if not girl else "#c2185b", width=4 * S)          # smile
    d.ellipse([cx - 4 * S, cy + 6 * S, cx + 4 * S, cy + 14 * S], fill=hexrgb(skin) and tuple(max(0, v - 25) for v in hexrgb(skin)))
    if girl and i % 2 == 0: d.ellipse([cx - 4 * S, cy - fh + 22 * S, cx + 4 * S, cy - fh + 30 * S], fill="#d50000")   # bindi
    if girl: [d.ellipse([cx + s * (fw + 1 * S) - 5 * S, cy + 24 * S, cx + s * (fw + 1 * S) + 5 * S, cy + 34 * S], fill="#ffd54f") for s in (-1, 1)]   # earrings
    if not girl and i % 3 == 1: d.arc([cx - 30 * S, cy + 20 * S, cx + 30 * S, cy + 58 * S], 200, 340, fill=hair, width=6 * S)       # stubble/moustache
    im = im.resize((256, 256), Image.LANCZOS)
    m = Image.new("L", (256, 256), 0); ImageDraw.Draw(m).ellipse([0, 0, 255, 255], fill=255); out = Image.new("RGBA", (256, 256)); out.paste(im, (0, 0), m)
    out.save(os.path.join(OUT, f"{kind}{i}.png"), optimize=True)
for k in "gb":
    for i in range(12): make(k, i)
print(len(os.listdir(OUT)))

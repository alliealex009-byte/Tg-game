"""Generates one cover image per game (assets/covers/<key>.png). Original art: gradient + shapes + title."""
import colorsys, hashlib, os, sys, random
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ast
ARCADE = next(ast.literal_eval(n.value) for n in ast.parse(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'bot.py')).read()).body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'ARCADE')
from app.games import GAME_INFO
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "covers")
B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W, H = 900, 470
def font(n): return ImageFont.truetype(B, n)
def cols(key):
    h = int(hashlib.md5(key.encode()).hexdigest()[:6], 16) / 0xFFFFFF
    f = lambda hh, s, v: tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hh % 1, s, v))
    return f(h, .75, .95), f(h + .12, .85, .35), f(h + .5, .6, 1)
def make(key, title, tag):
    a, b, c = cols(key); rnd = random.Random(key)
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H; d.line([(0, y), (W, y)], fill=tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3)))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); o = ImageDraw.Draw(ov)
    for _ in range(14):                                   # soft bubbles
        r = rnd.randint(30, 130); x, y = rnd.randint(0, W), rnd.randint(0, H); o.ellipse([x - r, y - r, x + r, y + r], fill=c + (rnd.randint(25, 60),))
    for i in range(0, W, 60): o.line([(i, H), (i + 160, 0)], fill=(255, 255, 255, 18), width=6)
    # big pixel-style emblem: first letters in a rounded badge
    o.rounded_rectangle([60, 90, 300, 330], 48, fill=(255, 255, 255, 40), outline=(255, 255, 255, 140), width=6)
    o.text((180, 210), title[:2].upper(), font=font(110), fill=(255, 255, 255, 235), anchor="mm")
    im = Image.alpha_composite(im.convert("RGBA"), ov); d = ImageDraw.Draw(im)
    sz = 62
    while font(sz).getlength(title) > 540 and sz > 28: sz -= 4
    d.text((330, 190), title, font=font(sz), fill="white", anchor="lm", stroke_width=3, stroke_fill=(0, 0, 0, 120))
    d.text((332, 262), tag, font=font(30), fill=(255, 255, 255, 215), anchor="lm")
    d.rounded_rectangle([0, H - 62, W, H], 0, fill=(0, 0, 0, 110))
    d.text((30, H - 31), "GAMELY  •  by AAKASH  •  Sister bot @Groupingabot", font=font(24), fill="white", anchor="lm")
    im.convert("RGB").save(os.path.join(OUT, key + ".png"), optimize=True)
os.makedirs(OUT, exist_ok=True)
for k, e, t in ARCADE: make(k, t, "Arcade  •  earn coins")
for k, i in GAME_INFO.items(): make(k, i["title"], f"Multiplayer  •  {i['min']}-{i['max']} players" if i["min"] != i["max"] else "Multiplayer  •  2 players")
print(len(os.listdir(OUT)), "covers")

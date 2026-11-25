"""Welcome card generator (Pillow): a 1000x540 PNG with the member's profile photo, full name, @username and Telegram id."""
from __future__ import annotations

import colorsys
import hashlib
import io
import os
import random

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
_FONTS = [  # bundled fonts first (Docker images have none); first font that covers the text wins, unknown glyphs are dropped
    (os.path.join(_ASSETS, "Poppins-Bold.ttf"), 0),            # Latin + Devanagari
    (os.path.join(_ASSETS, "DejaVuSans-Bold.ttf"), 0),         # wide symbol coverage
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
    ("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 0),
    ("/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 0),
]
_cmaps: dict = {}


def _cmap(path: str, idx: int):
    key = (path, idx)
    if key not in _cmaps:
        try:
            from fontTools.ttLib import TTFont
            f = TTFont(path, fontNumber=idx, lazy=True)
            _cmaps[key] = set(f.getBestCmap().keys())
        except Exception:
            _cmaps[key] = None
    return _cmaps[key]


def pick_font(text: str, size: int):
    """Return (font, text) using a font that covers the text, dropping glyphs no font has."""
    avail = [(p, i) for p, i in _FONTS if os.path.exists(p)]
    for p, i in avail:
        cm = _cmap(p, i)
        if cm is not None and all(ord(c) in cm or c.isspace() or not c.isalnum() for c in text):
            return ImageFont.truetype(p, size, index=i), "".join(c for c in text if ord(c) in cm or c.isspace()).strip() or text
    if not avail:
        return ImageFont.load_default(), text
    p, i = avail[0]
    cm = _cmap(p, i) or set()
    clean = "".join(c for c in text if ord(c) in cm or c.isspace()).strip()
    return ImageFont.truetype(p, size, index=i), clean


def _fit(draw, text, max_w, start, min_size=24):
    size = start
    while size > min_size:
        f, t = pick_font(text, size)
        if draw.textlength(t, font=f) <= max_w:
            return f, t
        size -= 3
    f, t = pick_font(text, min_size)
    while t and draw.textlength(t + "…", font=f) > max_w:
        t = t[:-1]
    return f, t + "…"


def _palette(seed: str):
    h = int(hashlib.md5(seed.encode()).hexdigest()[:6], 16) / 0xFFFFFF
    f = lambda hh, s, v: tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hh % 1, s, v))
    return f(h, .7, .55), f(h + .14, .8, .25), f(h + .5, .55, 1)


def _cover(photo, W, H):
    im = Image.open(io.BytesIO(photo)).convert("RGB")
    k = max(W / im.width, H / im.height)
    im = im.resize((max(W, int(im.width * k)), max(H, int(im.height * k))), Image.LANCZOS)
    return im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H))


def _gradient_text(text, font, c1, c2):
    """Text filled with a horizontal gradient, returned as an RGBA layer the size of the text box."""
    box = font.getbbox(text)
    w, h = box[2] + 8, box[3] + 8
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((0, 0), text, font=font, fill=255)
    grad = Image.new("RGB", (w, h))
    gd = ImageDraw.Draw(grad)
    for x in range(w):
        t = x / max(1, w - 1)
        gd.line([(x, 0), (x, h)], fill=tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3)))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    layer.paste(grad, (0, 0), mask)
    return layer, mask


def _glow(base, layer_mask, pos, color, radius, strength=1.0):
    g = Image.new("RGBA", base.size, (0, 0, 0, 0))
    col = Image.new("RGBA", layer_mask.size, color + (int(255 * strength),))
    g.paste(col, pos, layer_mask)
    return Image.alpha_composite(base, g.filter(ImageFilter.GaussianBlur(radius)))


def _track(draw, xy, text, font, fill, spacing):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + spacing
    return x


def render(name: str, username: str | None, uid: int, group: str, photo: bytes | None, member_no: int | None = None,
           owner: str = "AAKASH", sister: str = "@Groupingabot") -> bytes:
    """1000x560 ambient card: the member's own photo, blurred and graded, becomes the background."""
    W, H = 1000, 560
    a, b, acc = _palette(str(uid))
    rnd = random.Random(uid)
    # --- ambient background -------------------------------------------------------------------------------------
    bg = Image.new("RGB", (W, H))
    bd = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / H
        bd.line([(0, y), (W, y)], fill=tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3)))
    ph = None
    if photo:
        try:
            ph = _cover(photo, W, H)
        except Exception:
            ph = None
    if ph is not None:
        amb = ph.filter(ImageFilter.GaussianBlur(38))
        amb = ImageEnhance.Color(amb).enhance(1.5)
        amb = ImageEnhance.Brightness(amb).enhance(0.62)
        bg = Image.blend(bg, amb, 0.82)
    im = bg.convert("RGBA")
    aur = Image.new("RGBA", (W, H), (0, 0, 0, 0))                       # aurora blobs
    ad = ImageDraw.Draw(aur)
    for i in range(5):
        cx, cy = rnd.randint(-50, W + 50), rnd.randint(-30, H + 30)
        r = rnd.randint(140, 260)
        col = acc if i % 2 else tuple(min(255, int(c * 1.6) + 30) for c in a)
        ad.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (70,))
    im = Image.alpha_composite(im, aur.filter(ImageFilter.GaussianBlur(70)))
    bok = Image.new("RGBA", (W, H), (0, 0, 0, 0))                       # bokeh lights
    kd = ImageDraw.Draw(bok)
    for _ in range(26):
        r = rnd.randint(8, 34); x, y = rnd.randint(0, W), rnd.randint(0, H)
        kd.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, rnd.randint(14, 46)), outline=(255, 255, 255, rnd.randint(30, 70)), width=2)
    im = Image.alpha_composite(im, bok.filter(ImageFilter.GaussianBlur(1.5)))
    vig = Image.new("L", (W, H), 0)                                     # vignette
    ImageDraw.Draw(vig).ellipse([-W * .25, -H * .35, W * 1.25, H * 1.35], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(120))
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 150))
    im = Image.composite(im, Image.alpha_composite(im, dark), vig)
    # --- profile photo with glowing double ring ----------------------------------------------------------------------
    S = 270; cx, cy = 195, H // 2 - 6
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([cx - S // 2 - 26, cy - S // 2 - 26, cx + S // 2 + 26, cy + S // 2 + 26], fill=acc + (230,))
    im = Image.alpha_composite(im, glow.filter(ImageFilter.GaussianBlur(26)))
    d = ImageDraw.Draw(im)
    d.ellipse([cx - S // 2 - 20, cy - S // 2 - 20, cx + S // 2 + 20, cy + S // 2 + 20], outline=acc + (255,), width=4)
    d.ellipse([cx - S // 2 - 10, cy - S // 2 - 10, cx + S // 2 + 10, cy + S // 2 + 10], fill=(255, 255, 255, 255))
    if ph is not None:
        m = min(*Image.open(io.BytesIO(photo)).size)
        av = Image.open(io.BytesIO(photo)).convert("RGB")
        av = av.crop(((av.width - m) // 2, (av.height - m) // 2, (av.width + m) // 2, (av.height + m) // 2)).resize((S, S), Image.LANCZOS)
    else:
        av = Image.new("RGB", (S, S), a)
        avd = ImageDraw.Draw(av)
        for y in range(S):
            avd.line([(0, y), (S, y)], fill=tuple(int(acc[i] * (y / S) + a[i] * (1 - y / S)) for i in range(3)))
        f0, t0 = pick_font((name.strip() or "?")[0].upper(), 150)
        avd.text((S // 2, S // 2), t0 or "?", font=f0, fill="white", anchor="mm")
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, S - 1, S - 1], fill=255)
    im.paste(av, (cx - S // 2, cy - S // 2), mask)
    # --- text ---------------------------------------------------------------------------------------------------------
    x0 = 400; maxw = W - x0 - 56
    d = ImageDraw.Draw(im)
    fsm, _ = pick_font("WELCOME TO", 22)
    gtxt = (group or "the group").upper()
    end = _track(d, (x0 + 2, 62), "WELCOME TO", fsm, (255, 255, 255, 200), 5)
    gf, gt = _fit(d, group or "the group", W - 40 - int(end) - 14, 26, 16)
    d.text((end + 14, 60), gt, font=gf, fill=acc + (255,))
    fh, _ = pick_font("WELCOME", 104)
    layer, lmask = _gradient_text("WELCOME", fh, (255, 255, 255), tuple(min(255, c + 60) for c in acc))
    im = _glow(im, lmask, (x0, 84), acc, 14, 0.9)
    im.alpha_composite(layer, (x0, 84))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([x0, 218, x0 + 260, 224], 3, fill=acc + (255,))
    nf, nt = _fit(d, name or "New member", maxw, 66, 28)
    d.text((x0 + 3, 241), nt, font=nf, fill=(0, 0, 0, 140))
    d.text((x0, 238), nt, font=nf, fill="white")
    y = 328
    chips = []
    if username:
        chips.append(("@" + username.lstrip("@"), None))
    chips.append((f"ID  {uid}", None))
    if member_no:
        chips.append((f"Member #{member_no}", None))
    cx0 = x0
    cf, _ = pick_font("x", 28)
    for txt, _ in chips:
        f2, t2 = _fit(d, txt, maxw, 28, 18)
        tw = int(d.textlength(t2, font=f2))
        if cx0 + tw + 44 > W - 40:
            cx0, y = x0, y + 62
        chip = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        cd = ImageDraw.Draw(chip)
        cd.rounded_rectangle([cx0, y, cx0 + tw + 40, y + 50], 25, fill=(255, 255, 255, 46), outline=(255, 255, 255, 120), width=2)
        im = Image.alpha_composite(im, chip)
        d = ImageDraw.Draw(im)
        d.text((cx0 + 20, y + 25), t2, font=f2, fill="white", anchor="lm")
        cx0 += tw + 40 + 14
    # footer ribbon
    rib = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(rib).rectangle([0, H - 54, W, H], fill=(0, 0, 0, 120))
    im = Image.alpha_composite(im, rib)
    d = ImageDraw.Draw(im)
    ff, _ = pick_font("x", 21)
    d.text((W // 2, H - 27), f"Play /play   •   Arcade /arcade   •   Owner {owner}   •   Sister bot {sister}", font=ff, fill=(255, 255, 255, 225), anchor="mm")
    out = io.BytesIO()
    im.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()


QUOTES = [
    ("The best way to predict the future is to create it.", "Peter Drucker"),
    ("Play is the highest form of research.", "Albert Einstein"),
    ("It does not matter how slowly you go as long as you do not stop.", "Confucius"),
    ("Fortune favours the bold.", "Latin proverb"),
    ("You miss 100% of the shots you don't take.", "Wayne Gretzky"),
    ("Great things are done by a series of small things brought together.", "Vincent van Gogh"),
    ("Well played is better than well said.", "Game-night wisdom"),
    ("Winning isn't everything, but wanting to win is.", "Vince Lombardi"),
    ("Every master was once a beginner.", "Robin Sharma"),
    ("The harder you work, the luckier you get.", "Gary Player"),
    ("Do what you can, with what you have, where you are.", "Theodore Roosevelt"),
    ("Life is either a daring adventure or nothing at all.", "Helen Keller"),
    ("Believe you can and you're halfway there.", "Theodore Roosevelt"),
    ("Success is the sum of small efforts, repeated daily.", "R. Collier"),
    ("Dream big. Play bigger.", "GAME HUB"),
    ("A champion is afraid of losing. Everyone else is afraid of winning.", "Billie Jean King"),
    ("Today a reader, tomorrow a leader; today a player, tomorrow a legend.", "GAME HUB"),
    ("Happiness is not by chance, but by choice.", "Jim Rohn"),
    ("Hard work beats talent when talent doesn't work hard.", "Tim Notke"),
    ("In the middle of difficulty lies opportunity.", "Albert Einstein"),
    ("Stars can't shine without darkness.", "D. H. Lawrence"),
    ("Don't watch the clock; do what it does. Keep going.", "Sam Levenson"),
    ("Friends who play together, stay together.", "GAME HUB"),
    ("The only way to do great work is to love what you do.", "Steve Jobs"),
]


def pick_quote(uid: int, day: int) -> tuple[str, str]:
    return QUOTES[(uid * 7 + day) % len(QUOTES)]


def _wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_dm(name: str, username: str | None, uid: int, photo: bytes | None, quote: tuple[str, str],
              coins: int = 0, games: int = 0, owner: str = "AAKASH") -> bytes:
    """1000x640 private-chat welcome: vivid mesh gradient, the user's own photo, a personal greeting and a quote."""
    W, H = 1000, 640
    h0 = int(hashlib.md5(str(uid).encode()).hexdigest()[:6], 16) / 0xFFFFFF
    hsv = lambda hh, s, v: tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hh % 1, s, v))
    c1, c2, c3, acc = hsv(h0, .85, .55), hsv(h0 + .33, .8, .45), hsv(h0 + .66, .85, .5), hsv(h0 + .12, .45, 1)
    im = Image.new("RGB", (W, H))
    px = im.load()
    for y in range(H):                                   # diagonal 3-stop gradient
        for x in range(0, W):
            t = (x / W * .6 + y / H * .4)
            if t < .5:
                u = t / .5; a, b = c1, c2
            else:
                u = (t - .5) / .5; a, b = c2, c3
            px[x, y] = tuple(int(a[i] * (1 - u) + b[i] * u) for i in range(3))
    im = im.convert("RGBA")
    rnd = random.Random(uid)
    blobs = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blobs)
    for i in range(6):
        cx, cy, r = rnd.randint(0, W), rnd.randint(0, H), rnd.randint(120, 240)
        col = hsv(h0 + rnd.random(), .7, 1)
        bd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (80,))
    im = Image.alpha_composite(im, blobs.filter(ImageFilter.GaussianBlur(80)))
    sp = Image.new("RGBA", (W, H), (0, 0, 0, 0))         # sparkles
    sd = ImageDraw.Draw(sp)
    for _ in range(60):
        x, y, r = rnd.randint(0, W), rnd.randint(0, H), rnd.randint(1, 3)
        sd.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, rnd.randint(70, 200)))
    im = Image.alpha_composite(im, sp)
    # glass panel
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle([34, 34, W - 34, H - 34], 40, fill=(255, 255, 255, 30), outline=(255, 255, 255, 110), width=2)
    im = Image.alpha_composite(im, panel)
    # photo
    S = 220; cx, cy = 170, 190
    gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(gl).ellipse([cx - S // 2 - 22, cy - S // 2 - 22, cx + S // 2 + 22, cy + S // 2 + 22], fill=acc + (220,))
    im = Image.alpha_composite(im, gl.filter(ImageFilter.GaussianBlur(24)))
    d = ImageDraw.Draw(im)
    d.ellipse([cx - S // 2 - 14, cy - S // 2 - 14, cx + S // 2 + 14, cy + S // 2 + 14], outline=acc + (255,), width=5)
    av = None
    if photo:
        try:
            a0 = Image.open(io.BytesIO(photo)).convert("RGB"); m0 = min(a0.size)
            av = a0.crop(((a0.width - m0) // 2, (a0.height - m0) // 2, (a0.width + m0) // 2, (a0.height + m0) // 2)).resize((S, S), Image.LANCZOS)
        except Exception:
            av = None
    if av is None:
        av = Image.new("RGB", (S, S), c1)
        ad = ImageDraw.Draw(av)
        for y in range(S):
            ad.line([(0, y), (S, y)], fill=tuple(int(acc[i] * y / S + c1[i] * (1 - y / S)) for i in range(3)))
        f0, t0 = pick_font((name.strip() or "?")[0].upper(), 130)
        ad.text((S // 2, S // 2), t0 or "?", font=f0, fill="white", anchor="mm")
    mk = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mk).ellipse([0, 0, S - 1, S - 1], fill=255)
    im.paste(av, (cx - S // 2, cy - S // 2), mk)
    # greeting
    x0 = 340; maxw = W - x0 - 70
    d = ImageDraw.Draw(im)
    f1, _ = pick_font("HELLO", 26)
    _track(d, (x0, 78), "HELLO & WELCOME", f1, (255, 255, 255, 220), 6)
    first = (name.strip().split(" ")[0] if name.strip() else "Player")
    nf, nt = _fit(d, first, maxw, 96, 40)
    layer, lm = _gradient_text(nt, nf, (255, 255, 255), acc)
    im = _glow(im, lm, (x0, 112), acc, 14, .8)
    im.alpha_composite(layer, (x0, 112))
    d = ImageDraw.Draw(im)
    sub, _ = pick_font("x", 28)
    full = name.strip() or "New player"
    sf, st_ = _fit(d, full + (f"  ·  @{username}" if username else ""), maxw, 28, 18)
    d.text((x0, 232), st_, font=sf, fill=(255, 255, 255, 235))
    d.rounded_rectangle([x0, 280, x0 + 220, 285], 3, fill=acc + (255,))
    # quote
    q, who = quote
    qf, _ = pick_font(q, 38)
    lines = _wrap(d, "“" + q + "”", qf, W - 150)
    while len(lines) > 4 and qf.size > 26:
        qf, _ = pick_font(q, qf.size - 4)
        lines = _wrap(d, "“" + q + "”", qf, W - 150)
    y = 330
    for ln in lines[:4]:
        d.text((80, y), ln, font=qf, fill="white")
        y += int(qf.size * 1.3)
    af, _ = pick_font("x", 24)
    d.text((80, y + 6), "— " + who, font=af, fill=acc + (255,))
    # stat chips
    chips = [f"{coins} coins", f"{games} games", f"ID {uid}"]
    cx0 = 80; cy0 = H - 128
    for t in chips:
        cf, ct = _fit(d, t, 300, 24, 16)
        tw = int(d.textlength(ct, font=cf))
        chip = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(chip).rounded_rectangle([cx0, cy0, cx0 + tw + 36, cy0 + 46], 23, fill=(0, 0, 0, 80), outline=(255, 255, 255, 130), width=2)
        im = Image.alpha_composite(im, chip)
        d = ImageDraw.Draw(im)
        d.text((cx0 + 18, cy0 + 23), ct, font=cf, fill="white", anchor="lm")
        cx0 += tw + 36 + 12
    ff, _ = pick_font("x", 20)
    d.text((W // 2, H - 56), f"Made by {owner}  •  Tap PLAY NOW below", font=ff, fill=(255, 255, 255, 200), anchor="mm")
    out = io.BytesIO()
    im.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()

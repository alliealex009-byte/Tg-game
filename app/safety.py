"""Keeps explicit / drug-related names, usernames, group titles and profile photos out of welcome cards and displayed text.
Text: normalised word-list match (leetspeak, separators, repeated letters). Photos: a conservative skin-tone heuristic
(no ML model is bundled, so this is a best-effort filter, not a guarantee)."""
from __future__ import annotations

import io
import re

# unambiguous terms, matched anywhere in the collapsed text
_SUB = [
    "porn", "pornhub", "xvideo", "xnxx", "xxx", "sex", "nude", "naked", "nsfw", "hentai", "erotic", "fuck", "fck", "cumshot", "blowjob",
    "handjob", "anal", "orgy", "bdsm", "fetish", "milf", "escort", "hooker", "prostitut", "camgirl", "onlyfans", "boobs", "pussy", "dick",
    "cock", "penis", "vagina", "bitch", "slut", "whore", "rape", "pedo", "incest", "lolita", "shemale", "stripper", "horny", "sexy",
    "cocaine", "heroin", "meth", "weed", "ganja", "charas", "marijuana", "cannabis", "opium", "lsd", "mdma", "ecstasy", "drugs", "dealer",
    "smack", "brownsugar", "narcotic", "hashish", "crack", "fentanyl", "420",
    "chut", "lund", "gand", "randi", "bhosd", "madarch", "behench", "chod", "harami", "lauda", "mc", "bc",
]
# short / ambiguous tokens: only as a whole word
_WORD = {"sex", "xxx", "mc", "bc", "anal", "dick", "cock", "weed", "meth", "lsd", "crack", "rape", "420", "gand", "lund", "chut", "smack"}
_SUB = [w for w in _SUB if w not in {"mc", "bc", "anal", "dick", "cock", "weed", "meth", "lsd", "crack", "rape", "420", "gand", "lund", "chut", "smack", "sex", "xxx", "chod", "dealer", "drugs"}] + ["chodu", "chudai", "gandu", "drugdeal"]
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i", "¡": "i", "€": "e", "+": "t"})


def _norm(text: str) -> tuple[str, str]:
    t = (text or "").lower().translate(_LEET)
    words = " ".join(re.findall(r"[a-z]+", t))
    collapsed = re.sub(r"(.)\1+", r"\1", re.sub(r"[^a-z]", "", t))
    return words, collapsed


def is_bad(text: str | None) -> bool:
    if not text:
        return False
    raw = text.lower()
    if any(w in raw.split() for w in ("420", "xxx")):
        return True
    words, collapsed = _norm(text)
    toks = set(words.split())
    if toks & {"sex", "xxx", "mc", "bc", "anal", "dick", "cock", "weed", "meth", "lsd", "crack", "rape", "gand", "lund", "chut", "smack", "chod", "dealer", "drugs", "drug", "cunt", "gaand", "pussy"}:
        return True
    return any(re.sub(r"(.)\1+", r"\1", w.strip()) in collapsed for w in _SUB if len(w.strip()) >= 4)


def safe_name(name: str | None, uid: int | None = None, fallback: str = "Player") -> str:
    n = (name or "").strip()
    if not n or is_bad(n):
        return f"{fallback}{(' ' + str(uid)[-4:]) if uid else ''}"
    return n


def safe_username(username: str | None) -> str | None:
    return None if (not username or is_bad(username)) else username


def skin_heavy(photo: bytes | None, limit: float = .6) -> bool:
    """True when an unusually large share of the image is skin-coloured (typical of explicit photos). Faces alone stay below."""
    if not photo:
        return False
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(photo)).convert("YCbCr").resize((64, 64))
        n = hit = 0
        for y, cb, cr in list(im.tobytes() and zip(*[iter(im.tobytes())] * 3)):
            n += 1
            if 80 <= y <= 235 and 77 <= cb <= 127 and 133 <= cr <= 173:
                hit += 1
        return hit / max(1, n) > limit
    except Exception:
        return False


def photo_ok(photo: bytes | None, *texts: str | None) -> bool:
    """Use the profile photo only when the name/username/bio texts are clean and the image is not skin-dominated."""
    return not (any(is_bad(t) for t in texts) or skin_heavy(photo))

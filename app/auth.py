"""Validation of Telegram Mini App `initData` (HMAC-SHA256, per Telegram docs)."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

MAX_AGE = 2 * 24 * 3600  # accept initData up to 48h old


class AuthError(Exception):
    pass


def _display_name(u: dict) -> str:
    name = " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x).strip()
    return name or u.get("username") or f"user_{u.get('id')}"


def validate_init_data(init_data: str, bot_token: str, max_age: int = MAX_AGE) -> dict:
    """Return the Telegram user dict if the signature is valid, else raise AuthError."""
    if not init_data or not bot_token:
        raise AuthError("Missing credentials")
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop("hash", None)
    if not received:
        raise AuthError("Missing hash")
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise AuthError("Bad signature")
    try:
        if time.time() - int(pairs.get("auth_date", "0")) > max_age:
            raise AuthError("Session expired, reopen the app")
        user = json.loads(pairs["user"])
        int(user["id"])
    except AuthError:
        raise
    except Exception:
        raise AuthError("Malformed user data")
    return user


def user_from_init_data(init_data: str, settings) -> dict:
    """Normalised {id, name, username, photo}. Supports `dev:<id>:<name>` when DEV_MODE is on."""
    if settings.dev_mode and init_data.startswith("dev:"):
        try:
            _, uid, name = init_data.split(":", 2)
            uid = int(uid)
        except ValueError:
            raise AuthError("Bad dev credentials")
        name = name[:32] or f"dev{uid}"
        return {"id": uid, "name": name, "username": f"user_{uid}", "photo": None}
    u = validate_init_data(init_data, settings.bot_token)
    uid = int(u["id"])
    return {
        "id": uid,
        "name": _display_name(u)[:40],
        "username": u.get("username") or f"user_{uid}",
        "photo": u.get("photo_url"),
    }

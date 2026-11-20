"""Settings, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _ints(value: str) -> tuple:
    out = []
    for part in value.replace(" ", "").split(","):
        if part.lstrip("-").isdigit():
            out.append(int(part))
    return tuple(out)


def _bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    bot_token: str = ""
    webapp_url: str = ""          # public https URL of this server, no trailing slash
    app_short_name: str = ""      # BotFather /newapp short name (enables t.me/bot/app?startapp=CODE links)
    admin_ids: tuple = ()
    db_path: str = "data/ludo.db"
    starting_coins: int = 1000
    daily_bonus: int = 200
    rake_percent: int = 10        # % of the pot kept by the house (coin sink)
    turn_seconds: int = 20
    mongo_uri: str = ""
    mongo_db: str = "gamely"
    owner_name: str = "AAKASH"
    owner_username: str = "Advik_prakashh"
    sister_bot: str = "Groupingabot"
    referral_bonus: int = 300
    bot_delay: tuple = (0.9, 1.6)  # seconds a computer player "thinks"
    dev_mode: bool = False        # allows browser testing without Telegram. NEVER enable in production.


def load_settings() -> Settings:
    e = os.environ.get
    return Settings(
        bot_token=e("BOT_TOKEN", "").strip(),
        webapp_url=e("WEBAPP_URL", "").strip().rstrip("/"),
        app_short_name=e("APP_SHORT_NAME", "").strip(),
        admin_ids=_ints(e("ADMIN_IDS", "")),
        db_path=e("DB_PATH", "data/ludo.db"),
        starting_coins=int(e("STARTING_COINS", "1000")),
        daily_bonus=int(e("DAILY_BONUS", "200")),
        rake_percent=max(0, min(50, int(e("RAKE_PERCENT", "10")))),
        turn_seconds=max(8, int(e("TURN_SECONDS", "20"))),
        mongo_uri=e("MONGO_URI", "").strip(),
        mongo_db=e("MONGO_DB", "gamely").strip() or "gamely",
        owner_name=e("OWNER_NAME", "AAKASH").strip(),
        owner_username=e("OWNER_USERNAME", "Advik_prakashh").strip().lstrip("@"),
        sister_bot=e("SISTER_BOT", "Groupingabot").strip().lstrip("@"),
        referral_bonus=int(e("REFERRAL_BONUS", "300")),
        bot_delay=(float(e("BOT_DELAY_MIN", "0.9")), float(e("BOT_DELAY_MAX", "1.6"))),
        dev_mode=_bool(e("DEV_MODE", "0")),
    )

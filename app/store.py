"""Pick the storage backend: MongoDB when MONGO_URI is set, otherwise the local SQLite file."""
from __future__ import annotations

import logging

log = logging.getLogger("store")


def make_db(settings):
    if settings.mongo_uri:
        from .mongo import MongoDB

        db = MongoDB(settings.mongo_uri, settings.mongo_db, settings.starting_coins, settings.daily_bonus)
        log.info("Using MongoDB database '%s'", settings.mongo_db)
        return db
    from .db import DB

    log.info("Using SQLite at %s (set MONGO_URI to use MongoDB)", settings.db_path)
    return DB(settings.db_path, settings.starting_coins, settings.daily_bonus)

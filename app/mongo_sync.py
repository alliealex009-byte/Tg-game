"""MongoDB persistence. SQLite stays the fast working store; this mirrors it into MongoDB so the data
survives hosts with throw-away disks (Railway, Render, Heroku...) and can be inspected with Compass/Atlas.

  * on start-up, if the local SQLite file is empty and MongoDB has data, everything is restored from MongoDB
  * while running, changed rows are written to MongoDB every few seconds (and once more on shutdown)
"""
from __future__ import annotations

import asyncio
import logging

log = logging.getLogger("mongo")

# collection -> (sqlite table, primary key column, append-only?)
TABLES = {
    "users": ("users", "id", False),
    "chats": ("chats", "id", False),
    "kv": ("kv", "k", False),
    "tx": ("tx", "id", True),
    "matches": ("matches", "id", True),
}


class MongoSync:
    def __init__(self, db, mdb):
        """`mdb` is a pymongo Database (or anything with the same collection API)."""
        self.db, self.m = db, mdb
        self.seen: dict = {t: {} for t in TABLES}   # table -> {pk: row tuple} already mirrored
        self.last_id = {"tx": 0, "matches": 0}
        self.primed = False

    # ---------- restore ----------
    def restore(self) -> int:
        if self.db.c.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return 0
        n = 0
        for coll, (table, pk, _) in TABLES.items():
            cols = [r["name"] for r in self.db.c.execute(f"PRAGMA table_info({table})")]
            for doc in self.m[coll].find({}):
                row = {c: doc.get(c) for c in cols if c in doc}
                if pk not in row:
                    continue
                names = ",".join(row)
                self.db.c.execute(f"INSERT OR REPLACE INTO {table}({names}) VALUES({','.join('?' * len(row))})", tuple(row.values()))
                n += 1
        log.info("restored %d rows from MongoDB", n)
        return n

    # ---------- mirror ----------
    def flush(self) -> int:
        """Write rows that changed since the last flush. Returns the number of documents written."""
        written = 0
        if not self.primed:
            self.primed = True
            for coll in self.last_id:  # resume after the newest row Mongo already has
                try:
                    top = self.m[coll].find_one(sort=[("_id", -1)])
                    self.last_id[coll] = int(top["_id"]) if top else 0
                except Exception:
                    pass
        for coll, (table, pk, append_only) in TABLES.items():
            if append_only:
                rows = self.db.c.execute(f"SELECT * FROM {table} WHERE {pk} > ? ORDER BY {pk}", (self.last_id[coll],)).fetchall()
                for r in rows:  # idempotent upserts, so a restart can never create duplicates
                    self.m[coll].replace_one({"_id": r[pk]}, self._doc(r, pk), upsert=True)
                if rows:
                    self.last_id[coll] = rows[-1][pk]
                    written += len(rows)
                continue
            seen = self.seen[coll]
            for r in self.db.c.execute(f"SELECT * FROM {table}").fetchall():
                tup = tuple(r)
                if seen.get(r[pk]) != tup:
                    self.m[coll].replace_one({"_id": r[pk]}, self._doc(r, pk), upsert=True)
                    seen[r[pk]] = tup
                    written += 1
        return written

    @staticmethod
    def _doc(row, pk):
        d = {k: row[k] for k in row.keys()}
        d["_id"] = d[pk]
        return d

    async def run(self, every: float = 8.0):
        while True:
            await asyncio.sleep(every)
            try:
                await asyncio.to_thread(self.flush)
            except Exception:
                log.exception("MongoDB flush failed; will retry")


def connect(uri: str, name: str):
    from pymongo import MongoClient  # imported lazily so the dependency is only needed when used

    client = MongoClient(uri, serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    return client[name]

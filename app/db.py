"""SQLite storage: users, coin ledger, match history. Synchronous and tiny on purpose."""
from __future__ import annotations

import json
import os
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  username TEXT,
  photo TEXT,
  coins INTEGER NOT NULL DEFAULT 0 CHECK(coins >= 0),
  games INTEGER NOT NULL DEFAULT 0,
  wins INTEGER NOT NULL DEFAULT 0,
  last_daily REAL NOT NULL DEFAULT 0,
  created REAL NOT NULL,
  last_seen REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS tx(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  amount INTEGER NOT NULL,
  reason TEXT NOT NULL,
  ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS tx_user ON tx(user_id);
CREATE TABLE IF NOT EXISTS matches(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  game TEXT NOT NULL,
  room TEXT NOT NULL,
  bet INTEGER NOT NULL,
  players TEXT NOT NULL,
  winner INTEGER,
  prize INTEGER NOT NULL,
  ts REAL NOT NULL
);
"""


class DB:
    def __init__(self, path: str, starting_coins: int = 1000, daily_bonus: int = 200):
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.c = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.c.row_factory = sqlite3.Row
        self.c.execute("PRAGMA journal_mode=WAL")
        self.c.execute("PRAGMA synchronous=NORMAL")
        self.c.executescript(SCHEMA)
        self.starting_coins = starting_coins
        self.daily_bonus = daily_bonus

    # ---------- users ----------
    def get_user(self, uid: int):
        row = self.c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        return dict(row) if row else None

    def upsert_user(self, uid: int, name: str, username, photo):
        now = time.time()
        if self.get_user(uid) is None:
            self.c.execute(
                "INSERT INTO users(id,name,username,photo,coins,created,last_seen) VALUES(?,?,?,?,?,?,?)",
                (uid, name, username, photo, self.starting_coins, now, now),
            )
            self._tx(uid, self.starting_coins, "welcome")
        else:
            self.c.execute(
                "UPDATE users SET name=?, username=COALESCE(?,username), photo=COALESCE(?,photo), last_seen=? WHERE id=?",
                (name, username, photo, now, uid),
            )
        return self.get_user(uid)

    def _tx(self, uid, amount, reason):
        self.c.execute(
            "INSERT INTO tx(user_id,amount,reason,ts) VALUES(?,?,?,?)", (uid, amount, reason, time.time())
        )

    # ---------- coins ----------
    def add_coins(self, uid: int, delta: int, reason: str):
        """Add (or subtract) coins. Returns the new balance, or None if it would go negative / user unknown."""
        cur = self.c.execute(
            "UPDATE users SET coins = coins + ? WHERE id = ? AND coins + ? >= 0", (delta, uid, delta)
        )
        if cur.rowcount == 0:
            return None
        self._tx(uid, delta, reason)
        return self.get_user(uid)["coins"]

    def charge_all(self, uids, amount: int, reason: str):
        """Atomically charge every user `amount`. Returns the first uid who can't pay, else None."""
        self.c.execute("BEGIN IMMEDIATE")
        try:
            for u in uids:
                r = self.c.execute("SELECT coins FROM users WHERE id=?", (u,)).fetchone()
                if r is None or r["coins"] < amount:
                    self.c.execute("ROLLBACK")
                    return u
            now = time.time()
            for u in uids:
                self.c.execute("UPDATE users SET coins = coins - ? WHERE id=?", (amount, u))
                self.c.execute(
                    "INSERT INTO tx(user_id,amount,reason,ts) VALUES(?,?,?,?)", (u, -amount, reason, now)
                )
            self.c.execute("COMMIT")
            return None
        except Exception:
            try:
                self.c.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise

    def claim_daily(self, uid: int):
        """Returns (claimed, coins, seconds_until_next)."""
        now = time.time()
        u = self.get_user(uid)
        wait = u["last_daily"] + 86400 - now
        if wait > 0:
            return False, u["coins"], int(wait)
        self.c.execute(
            "UPDATE users SET last_daily=?, coins = coins + ? WHERE id=?", (now, self.daily_bonus, uid)
        )
        self._tx(uid, self.daily_bonus, "daily")
        return True, self.get_user(uid)["coins"], 0

    def daily_wait(self, uid: int) -> int:
        u = self.get_user(uid)
        return max(0, int(u["last_daily"] + 86400 - time.time()))

    # ---------- results ----------
    def record_result(self, game, room, bet, human_uids, winner, prize):
        for u in human_uids:
            self.c.execute("UPDATE users SET games = games + 1 WHERE id=?", (u,))
        if winner is not None and winner > 0:
            self.c.execute("UPDATE users SET wins = wins + 1 WHERE id=?", (winner,))
        self.c.execute(
            "INSERT INTO matches(game,room,bet,players,winner,prize,ts) VALUES(?,?,?,?,?,?,?)",
            (game, room, bet, json.dumps(list(human_uids)), winner, prize, time.time()),
        )

    def leaderboard(self, limit: int = 20):
        rows = self.c.execute(
            "SELECT id,name,username,photo,wins,games,coins FROM users WHERE games>0 "
            "ORDER BY wins DESC, coins DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def stats(self):
        q = lambda s: self.c.execute(s).fetchone()[0]
        return {
            "users": q("SELECT COUNT(*) FROM users"),
            "matches": q("SELECT COUNT(*) FROM matches"),
            "coins_in_circulation": q("SELECT COALESCE(SUM(coins),0) FROM users"),
        }

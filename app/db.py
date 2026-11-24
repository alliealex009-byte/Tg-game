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
        self._migrate()
        self.starting_coins = starting_coins
        self.daily_bonus = daily_bonus

    def _migrate(self):
        cols = {r["name"] for r in self.c.execute("PRAGMA table_info(users)")}
        for name, ddl in (
            ("banned", "INTEGER NOT NULL DEFAULT 0"),
            ("streak", "INTEGER NOT NULL DEFAULT 0"),
            ("referrer", "INTEGER"),
            ("refs", "INTEGER NOT NULL DEFAULT 0"),
            ("verified", "INTEGER NOT NULL DEFAULT 0"),
            ("dm_ok", "INTEGER NOT NULL DEFAULT 1"),
            ("tap_energy", "REAL NOT NULL DEFAULT 300"),
            ("tap_ts", "REAL NOT NULL DEFAULT 0"),
            ("tap_level", "INTEGER NOT NULL DEFAULT 1"),
            ("farm", "TEXT"),
            ("arc_day", "TEXT"),
            ("arc_earned", "INTEGER NOT NULL DEFAULT 0"),
        ):
            if name not in cols:
                self.c.execute(f"ALTER TABLE users ADD COLUMN {name} {ddl}")
        self.c.executescript(
            "CREATE TABLE IF NOT EXISTS chats(id INTEGER PRIMARY KEY, title TEXT, type TEXT, active INTEGER NOT NULL DEFAULT 1, added REAL NOT NULL);"
            "CREATE TABLE IF NOT EXISTS chat_users(chat_id INTEGER NOT NULL, uid INTEGER NOT NULL, PRIMARY KEY(chat_id, uid));"
            "CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);"
            "CREATE TABLE IF NOT EXISTS arc_group(chat_id INTEGER NOT NULL, uid INTEGER NOT NULL, game TEXT NOT NULL, best INTEGER NOT NULL DEFAULT 0, plays INTEGER NOT NULL DEFAULT 0, ts REAL NOT NULL DEFAULT 0, PRIMARY KEY(chat_id, uid, game));"
        )

    # ---------- bot admin helpers ----------
    def kv_get(self, k, default=None):
        r = self.c.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        return r["v"] if r else default

    def kv_set(self, k, v):
        self.c.execute("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, str(v)))

    def set_ban(self, uid: int, banned: bool) -> bool:
        cur = self.c.execute("UPDATE users SET banned=? WHERE id=?", (1 if banned else 0, uid))
        return cur.rowcount > 0

    def is_banned(self, uid: int) -> bool:
        r = self.c.execute("SELECT banned FROM users WHERE id=?", (uid,)).fetchone()
        return bool(r and r["banned"])

    def set_verified(self, uid: int):
        self.c.execute("UPDATE users SET verified=1 WHERE id=?", (uid,))

    def mark_dm(self, uid: int, ok: bool):
        self.c.execute("UPDATE users SET dm_ok=? WHERE id=?", (1 if ok else 0, uid))

    def reset_dm(self):
        self.c.execute("UPDATE users SET dm_ok=1")

    def user_ids(self, only_dm_ok: bool = True):
        q = "SELECT id FROM users WHERE banned=0" + (" AND dm_ok=1" if only_dm_ok else "")
        return [r["id"] for r in self.c.execute(q)]

    def upsert_chat(self, cid: int, title: str, ctype: str, active: bool = True):
        self.c.execute(
            "INSERT INTO chats(id,title,type,active,added) VALUES(?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET title=excluded.title, type=excluded.type, active=excluded.active",
            (cid, title, ctype, 1 if active else 0, time.time()),
        )

    def arc_group_score(self, chat_id: int, uid: int, game: str, score: int):
        """Remember a player's best score for a game inside one group (powers the group arcade board)."""
        self.c.execute(
            "INSERT INTO arc_group(chat_id,uid,game,best,plays,ts) VALUES(?,?,?,?,1,?) "
            "ON CONFLICT(chat_id,uid,game) DO UPDATE SET best=MAX(best,excluded.best), plays=plays+1, ts=excluded.ts",
            (chat_id, uid, game, int(score), time.time()),
        )

    def arc_group_top(self, chat_id: int, limit: int = 10):
        rows = self.c.execute(
            "SELECT g.uid, u.name, SUM(g.best) AS pts, COUNT(*) AS games, SUM(g.plays) AS plays FROM arc_group g "
            "JOIN users u ON u.id=g.uid WHERE g.chat_id=? GROUP BY g.uid ORDER BY pts DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def arc_group_game_top(self, chat_id: int, game: str, limit: int = 3):
        rows = self.c.execute(
            "SELECT u.name, g.best FROM arc_group g JOIN users u ON u.id=g.uid WHERE g.chat_id=? AND g.game=? ORDER BY g.best DESC LIMIT ?",
            (chat_id, game, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def chat_user_add(self, chat_id: int, uid: int):
        self.c.execute("INSERT OR IGNORE INTO chat_users(chat_id,uid) VALUES(?,?)", (chat_id, uid))

    def chat_user_ids(self, chat_id: int):
        return [r["uid"] for r in self.c.execute("SELECT uid FROM chat_users WHERE chat_id=?", (chat_id,))]

    def find_user(self, ref: str):
        """Find a user by numeric id or @username."""
        ref = ref.strip()
        if ref.lstrip("-").isdigit():
            return self.get_user(int(ref))
        row = self.c.execute("SELECT id FROM users WHERE lower(username)=lower(?)", (ref.lstrip("@"),)).fetchone()
        return self.get_user(row["id"]) if row else None

    def chat_ids(self):
        return [r["id"] for r in self.c.execute("SELECT id FROM chats WHERE active=1")]

    def set_chat_active(self, cid: int, active: bool):
        self.c.execute("UPDATE chats SET active=? WHERE id=?", (1 if active else 0, cid))

    def set_referrer(self, uid: int, ref: int, bonus: int) -> bool:
        """Credit a referral once, only for a brand-new user who isn't referring themselves."""
        if uid == ref:
            return False
        u, r = self.get_user(uid), self.get_user(ref)
        if not u or not r or u["referrer"] is not None or u["games"] > 0:
            return False
        self.c.execute("UPDATE users SET referrer=? WHERE id=?", (ref, uid))
        self.c.execute("UPDATE users SET refs=refs+1 WHERE id=?", (ref,))
        reward = min(700, bonus + 50 * r["refs"])  # grows with every friend: 300, 350, ... capped at 700
        self.add_coins(ref, reward, f"referral:{uid}")
        self.add_coins(uid, bonus // 2, f"referred:{ref}")
        self.last_referral = reward
        return True

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
        streak = u["streak"] + 1 if u["last_daily"] and now - u["last_daily"] < 2 * 86400 else 1
        bonus = self.daily_bonus + min(streak - 1, 6) * 50  # +50 per streak day, up to +300
        self.c.execute(
            "UPDATE users SET last_daily=?, streak=?, coins = coins + ? WHERE id=?", (now, streak, bonus, uid)
        )
        self._tx(uid, bonus, "daily")
        self.last_bonus = bonus
        return True, self.get_user(uid)["coins"], 0

    def daily_wait(self, uid: int) -> int:
        u = self.get_user(uid)
        return max(0, int(u["last_daily"] + 86400 - time.time()))

    # ---------- results ----------
    def record_result(self, game, room, bet, human_uids, winner, prize, winners=None):
        for u in human_uids:
            self.c.execute("UPDATE users SET games = games + 1 WHERE id=?", (u,))
        for w in (winners if winners else ([winner] if winner is not None and winner > 0 else [])):
            if w and w > 0:
                self.c.execute("UPDATE users SET wins = wins + 1 WHERE id=?", (w,))
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
            "chats": q("SELECT COUNT(*) FROM chats WHERE active=1"),
            "banned": q("SELECT COUNT(*) FROM users WHERE banned=1"),
            "dm_reachable": q("SELECT COUNT(*) FROM users WHERE banned=0 AND dm_ok=1"),
            "dm_unreachable": q("SELECT COUNT(*) FROM users WHERE banned=0 AND dm_ok=0"),
            "new_today": q("SELECT COUNT(*) FROM users WHERE created > strftime('%s','now') - 86400"),
        }

"""Solo arcade games that pay coins. Everything the client reports is validated and capped here,
so a hacked client can only ever earn the daily cap."""
from __future__ import annotations

import json
import time

DAILY_CAP = 6000          # max coins a player can earn from the arcade per UTC day
MAX_ENERGY = 300
REGEN = 0.5               # energy per second
FARM_PLOTS = 6
SEED_COST, HARVEST, GROW = 20, 50, 60
GAMES = {
    # game: (min seconds, max score per second, coins per score, max coins per run)
    "bricks": (15, 1.5, 2, 160),
    "quickdrop": (28, 3.0, 1, 90),
    "gridpop": (15, 40.0, 0.1, 150),
    "byteblock": (20, 20.0, 0.05, 150),
    "tiledash": (28, 4.0, 1, 90),
    "neonslice": (28, 5.0, 1, 100),
    "minttap": (28, 6.0, 0.5, 90),
    "turbocoin": (10, 9.0, 0.5, 40),
    # batch 4 (90s classics)
    "snake": (8, 2.0, 3, 150),
    "flap": (8, 1.2, 4, 120),
    "galaxy": (10, 4.0, 1, 120),
    "stack": (8, 1.6, 3, 120),
    "roadrush": (8, 40.0, 0.2, 110),
    "mole": (28, 4.5, 1.5, 90),
    "cricketblitz": (10, 4.0, 2, 120),
    "ponyrush": (8, 14.0, 0.4, 120),
    "panipuri": (10, 2.2, 4, 110),
    "memoflip": (12, 7.5, 1.2, 150),
}


class Arcade:
    def __init__(self, db, clock=time.time):
        self.db, self.clock = db, clock
        self.sessions: dict = {}

    # ---- shared helpers
    def _day(self):
        return time.strftime("%Y-%m-%d", time.gmtime(self.clock()))

    def _grant(self, uid: int, coins: int, why: str) -> int:
        """Credit coins, respecting the daily cap. Returns what was actually paid."""
        u = self.db.get_user(uid)
        day = self._day()
        earned = u["arc_earned"] if u["arc_day"] == day else 0
        paid = max(0, min(int(coins), DAILY_CAP - earned))
        self.db.c.execute("UPDATE users SET arc_day=?, arc_earned=? WHERE id=?", (day, earned + paid, uid))
        if paid:
            self.db.add_coins(uid, paid, why)
        return paid

    def left_today(self, uid: int) -> int:
        u = self.db.get_user(uid)
        return DAILY_CAP - (u["arc_earned"] if u["arc_day"] == self._day() else 0)

    # ---- score based games
    def start(self, uid: int, game: str):
        if game not in GAMES:
            raise ValueError("Unknown game")
        self.sessions[uid] = (game, self.clock())

    def claim(self, uid: int, game: str, score) -> dict:
        if game not in GAMES or isinstance(score, bool) or not isinstance(score, (int, float)) or score != score:
            raise ValueError("Bad score")
        sess = self.sessions.pop(uid, None)
        if not sess or sess[0] != game:
            raise ValueError("No active run")
        mins, per_sec, per_score, cap = GAMES[game]
        dt = self.clock() - sess[1]
        if dt < mins:
            raise ValueError("Run too short")
        score = max(0, min(score, per_sec * dt))
        coins = min(int(score * per_score), cap)
        paid = self._grant(uid, coins, f"arcade:{game}")
        return {"coins": paid, "score": int(score), "balance": self.db.get_user(uid)["coins"], "left": self.left_today(uid)}

    # ---- TapVerse (tap to earn)
    def _energy(self, u, now):
        return min(MAX_ENERGY, u["tap_energy"] + max(0.0, now - u["tap_ts"]) * REGEN) if u["tap_ts"] else MAX_ENERGY

    def tap_state(self, uid: int) -> dict:
        u, now = self.db.get_user(uid), self.clock()
        lvl = u["tap_level"]
        return {"energy": int(self._energy(u, now)), "max": MAX_ENERGY, "level": lvl, "upgrade": 150 * lvl * lvl,
                "coins": u["coins"], "left": self.left_today(uid)}

    def tap(self, uid: int, n) -> dict:
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError("Bad taps")
        u, now = self.db.get_user(uid), self.clock()
        energy = self._energy(u, now)
        dt = now - u["tap_ts"] if u["tap_ts"] else 1.0
        n = min(n, 15 * max(dt, 0.4), int(energy))   # at most 15 taps per second
        n = int(n)
        if n < 1:
            return {**self.tap_state(uid), "earned": 0}
        self.db.c.execute("UPDATE users SET tap_energy=?, tap_ts=? WHERE id=?", (energy - n, now, uid))
        paid = self._grant(uid, n * u["tap_level"], "arcade:tap")
        return {**self.tap_state(uid), "earned": paid}

    def tap_upgrade(self, uid: int) -> dict:
        u = self.db.get_user(uid)
        cost = 150 * u["tap_level"] ** 2
        if u["tap_level"] >= 10:
            raise ValueError("Max level")
        if self.db.add_coins(uid, -cost, "arcade:upgrade") is None:
            raise ValueError("Not enough coins")
        self.db.c.execute("UPDATE users SET tap_level=tap_level+1 WHERE id=?", (uid,))
        return self.tap_state(uid)

    # ---- PocketFarm (idle)
    def _plots(self, u):
        try:
            p = json.loads(u["farm"] or "null")
        except ValueError:
            p = None
        return p if isinstance(p, list) and len(p) == FARM_PLOTS else [None] * FARM_PLOTS

    def farm_state(self, uid: int) -> dict:
        u, now = self.db.get_user(uid), self.clock()
        out = []
        for t in self._plots(u):
            out.append(None if t is None else {"left": max(0, int(t + GROW - now)), "ripe": now >= t + GROW})
        return {"plots": out, "coins": u["coins"], "seed": SEED_COST, "harvest": HARVEST, "grow": GROW}

    def farm_act(self, uid: int, idx, action: str) -> dict:
        if isinstance(idx, bool) or not isinstance(idx, int) or not 0 <= idx < FARM_PLOTS:
            raise ValueError("Bad plot")
        u, now = self.db.get_user(uid), self.clock()
        plots = self._plots(u)
        if action == "plant":
            if plots[idx] is not None:
                raise ValueError("Already planted")
            if self.db.add_coins(uid, -SEED_COST, "arcade:seed") is None:
                raise ValueError("Not enough coins")
            plots[idx] = now
        elif action == "harvest":
            if plots[idx] is None or now < plots[idx] + GROW:
                raise ValueError("Not ripe yet")
            plots[idx] = None
            # the seed cost was already paid; only the profit counts toward the daily cap
            profit = self._grant(uid, HARVEST - SEED_COST, "arcade:harvest")
            self.db.add_coins(uid, SEED_COST, "arcade:harvest-seed")
        else:
            raise ValueError("Bad action")
        self.db.c.execute("UPDATE users SET farm=? WHERE id=?", (json.dumps(plots), uid))
        return self.farm_state(uid)

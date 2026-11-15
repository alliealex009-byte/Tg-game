"""Turbo Race: 2-4 drivers race 1000 m. Each round the road condition is known; everyone secretly picks a gear.
Nitro is fast but you only have 2 charges, and the wrong gear on the wrong road means a crash."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

LENGTH = 1000
MAX_ROUNDS = 14
GEARS = ["cruise", "boost", "nitro", "drift"]
CONDS = ["straight", "curve", "rain"]
TABLE = {  # (gain, crash chance, crash gain)
    "straight": {"cruise": (110, 0, 0), "boost": (160, .10, 20), "nitro": (270, .25, 0), "drift": (90, 0, 0)},
    "curve": {"cruise": (100, 0, 0), "boost": (140, .30, 30), "nitro": (260, .65, -30), "drift": (180, .10, 40)},
    "rain": {"cruise": (110, 0, 0), "boost": (140, .35, 20), "nitro": (230, .55, -20), "drift": (130, .35, 20)},
}
DRAFT = 40  # catch-up bonus if you trail the leader by <= 120 m


class RacingGame(BaseGame):
    name = "racing"
    min_players, max_players = 2, 4

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("Racing needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.dist = {u: 0 for u in self.players}
        self.nitro = {u: 2 for u in self.players}
        self.left = set()
        self.picks = {}
        self.conds = [self.rng.choice(CONDS) for _ in range(MAX_ROUNDS)]
        self.round = 0
        self.seq, self.last_round = 0, None
        self.winner, self.finished, self.draw = None, False, False

    def _live(self):
        return [u for u in self.players if u not in self.left]

    def current(self):
        if self.finished:
            return None
        pend = [u for u in self._live() if u not in self.picks]
        humans = [u for u in pend if u > 0]
        return (humans or pend or [None])[0]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The race is over")
        if uid not in self.dist or uid in self.left:
            raise GameError("You are not racing")
        g = msg.get("gear")
        if msg.get("t") != "pick" or g not in GEARS:
            raise GameError("Pick a gear")
        if uid in self.picks:
            raise GameError("Waiting for the other drivers")
        if g == "nitro" and self.nitro[uid] <= 0:
            raise GameError("No nitro charges left")
        self.picks[uid] = g
        self._maybe()

    def _maybe(self):
        if all(u in self.picks for u in self._live()):
            self._resolve()

    def _resolve(self):
        cond = self.conds[self.round]
        lead = max(self.dist.values())
        res = {}
        for u in self._live():
            g = self.picks[u]
            gain, pc, cg = TABLE[cond][g]
            crashed = self.rng.random() < pc
            if crashed:
                gain = cg
            if g == "nitro":
                self.nitro[u] -= 1
            draft = 0
            if 0 < lead - self.dist[u] <= 120 and not crashed:
                draft = DRAFT
            self.dist[u] = max(0, self.dist[u] + gain + draft)
            res[str(u)] = {"gear": g, "gain": gain + draft, "crashed": crashed, "draft": draft}
        self.round += 1
        self.seq += 1
        self.last_round = {"seq": self.seq, "round": self.round, "cond": cond, "results": res, "dist": {str(u): d for u, d in self.dist.items()}}
        self.picks = {}
        far = max(self.dist[u] for u in self._live())
        if far >= LENGTH or self.round >= MAX_ROUNDS:
            self.finished = True
            top = [u for u in self._live() if self.dist[u] == far]
            if len(top) == 1:
                self.winner = top[0]
            else:
                self.draw = True

    def _bot_gear(self, u):
        cond = self.conds[self.round]
        opts = {"straight": ["nitro", "boost", "boost", "cruise"], "curve": ["drift", "drift", "cruise", "boost"], "rain": ["cruise", "cruise", "drift", "boost"]}[cond]
        g = self.rng.choice(opts)
        if g == "nitro" and self.nitro[u] <= 0:
            g = "boost"
        return g

    def auto_play(self):
        if self.finished:
            return
        for u in self._live():
            if u not in self.picks:
                self.picks[u] = self._bot_gear(u) if (u < 0 or True) else "cruise"
        self._resolve()

    def remove_player(self, uid):
        if uid not in self.dist or uid in self.left or self.finished:
            return
        self.left.add(uid)
        self.picks.pop(uid, None)
        act = self._live()
        if len(act) <= 1:
            self.finished, self.winner = True, act[0] if act else None
        else:
            self._maybe()

    def public_state(self):
        return {"kind": "racing", "length": LENGTH, "round": min(self.round + 1, MAX_ROUNDS), "max_rounds": MAX_ROUNDS,
                "cond": self.conds[min(self.round, MAX_ROUNDS - 1)], "upcoming": self.conds[self.round + 1:self.round + 4],
                "players": [{"uid": u, "dist": self.dist[u], "nitro": self.nitro[u], "picked": u in self.picks, "left": u in self.left} for u in self.players],
                "turn": self.current(), "last_round": self.last_round, "mine": None, "winner": self.winner, "draw": self.draw}

    def view(self, uid):
        st = self.public_state()
        st["mine"] = self.picks.get(uid)
        return st

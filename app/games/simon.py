"""Simon Duel: a colour sequence grows by one each round. Everyone repeats it from memory at the same time.
Get it wrong (or run out of time) and you're out. Last player standing wins."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

COLORS = 4
MAX_LEN = 14


class SimonGame(BaseGame):
    name = "simon"
    min_players = 2
    max_players = 6

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 6:
            raise ValueError("Simon Duel needs 2-6 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.alive = list(players)
        self.out = []
        self.seq_colors = []
        self.picks = {}
        self.round = 0
        self.phase_id = 0
        self.seq = 0
        self.last_round = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self._next_round()
        self._bots()

    @property
    def phase_seconds(self):
        return 6 + 1.3 * len(self.seq_colors)

    def _next_round(self):
        self.seq_colors.append(self.rng.randrange(COLORS))
        self.round = len(self.seq_colors)
        self.picks = {}

    def _pending(self):
        return [u for u in self.alive if u not in self.picks]

    def current(self):
        if self.finished:
            return None
        p = self._pending()
        return ([u for u in p if u > 0] or p or [None])[0]

    def _bot_pick(self, u):
        ok = self.rng.random() < max(0.35, 0.97 - 0.045 * self.round)
        s = list(self.seq_colors)
        if not ok:
            i = self.rng.randrange(len(s))
            s[i] = (s[i] + 1) % COLORS
        return s

    def _bots(self):
        while not self.finished:
            for u in self._pending():
                if u < 0:
                    self.picks[u] = self._bot_pick(u)
            if self._pending():
                return
            self._resolve()

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid not in self.alive:
            raise GameError("You are out")
        s = msg.get("seq")
        if msg.get("t") != "repeat" or not isinstance(s, list) or len(s) > MAX_LEN + 1 or not all(isinstance(x, int) and not isinstance(x, bool) and 0 <= x < COLORS for x in s):
            raise GameError("Bad sequence")
        if uid in self.picks:
            raise GameError("Already answered")
        self.picks[uid] = s
        self._bots()

    def auto_play(self):
        if self.finished:
            return
        for u in self._pending():
            self.picks[u] = self._bot_pick(u) if u < 0 else []
        self._resolve()
        self._bots()

    def _resolve(self):
        failed = [u for u in self.alive if self.picks.get(u) != self.seq_colors]
        passed = [u for u in self.alive if u not in failed]
        self.seq += 1
        self.phase_id += 1
        self.last_round = {"seq": self.seq, "round": self.round, "failed": failed, "answer": list(self.seq_colors)}
        if not passed:                       # everybody slipped on the same round: shared draw
            self.finished, self.draw = True, True
            self.winners = None
            return
        for u in failed:
            self.alive.remove(u)
            self.out.append(u)
        if len(self.alive) == 1:
            self.finished, self.winner = True, self.alive[0]
            return
        if self.round >= MAX_LEN:
            self.finished, self.draw = True, True
            return
        self._next_round()

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        if uid in self.alive:
            self.alive.remove(uid)
            self.out.append(uid)
        self.picks.pop(uid, None)
        if len(self.alive) <= 1 or all(u < 0 for u in self.alive):
            self.finished = True
            self.winner = self.alive[0] if self.alive else None
            return
        self._bots()

    def public_state(self):
        return {"kind": "simon", "round": self.round, "colors": COLORS, "show": list(self.seq_colors) if not self.finished else None,
                "players": [{"uid": u, "out": u in self.out} for u in self.players],
                "picked": {u: u in self.picks for u in self.players}, "turn": self.current(),
                "last_round": self.last_round, "winner": self.winner, "draw": self.draw, "secs": self.phase_seconds}

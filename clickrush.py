"""ClickRush: 10-second tap race for 2-6 players. Most taps wins. The server counts taps and caps the rate (anti-cheat)."""
from __future__ import annotations

import random
import time

from .base import BaseGame, GameError

DURATION = 10.0
MAX_RATE = 12.0      # taps per second the server will credit


class ClickRushGame(BaseGame):
    name = "clickrush"
    min_players = 2
    max_players = 6
    phase_seconds = 11

    def __init__(self, players, rng=None, clock=time.monotonic):
        if not 2 <= len(players) <= 6:
            raise ValueError("ClickRush needs 2-6 players")
        self.rng = rng or random.SystemRandom()
        self.clock = clock
        self.players = list(players)
        self.t0 = self.clock()
        self.taps = {u: 0 for u in self.players}
        self._tokens = {u: 3.0 for u in self.players}
        self._last = {u: self.t0 for u in self.players}
        self.rate = {u: self.rng.uniform(3.5, 7.5) for u in self.players if u < 0}
        self.seq = 0
        self.phase_id = 0
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False

    def current(self):
        return None if self.finished else next((u for u in self.players if u > 0), self.players[0])

    def _left(self):
        return max(0.0, DURATION - (self.clock() - self.t0))

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The round is over")
        if uid not in self.players:
            raise GameError("You are not in this round")
        if msg.get("t") != "tap":
            raise GameError("Unknown action")
        now = self.clock()
        if now - self.t0 > DURATION:
            self._finish()
            return
        self._tokens[uid] = min(3.0, self._tokens[uid] + (now - self._last[uid]) * MAX_RATE)
        self._last[uid] = now
        if self._tokens[uid] >= 1:
            self._tokens[uid] -= 1
            self.taps[uid] += 1
            self.seq += 1

    def _finish(self):
        for u in self.players:
            if u < 0:
                self.taps[u] = int(DURATION * self.rate[u])
        self.finished = True
        top = max(self.taps.values())
        w = [u for u in self.players if self.taps[u] == top]
        if len(w) == 1:
            self.winner = w[0]
        else:
            self.draw = True

    def bot_due(self):
        return None if self.finished or not self.rate else 0.8

    def bot_event(self):
        """Nothing to decide; the wake-up lets the room broadcast the bots' growing tap counts."""

    def auto_play(self):
        if not self.finished:
            self._finish()

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.players.remove(uid)
        self.taps.pop(uid, None)
        if len(self.players) < 2 or all(u < 0 for u in self.players):
            self.finished = True
            self.winner = self.players[0] if self.players else None

    def _shown(self, u):
        if u < 0 and not self.finished:
            return int(min(self.clock() - self.t0, DURATION) * self.rate[u])
        return self.taps[u]

    def public_state(self):
        return {"kind": "clickrush", "duration": DURATION, "left": round(self._left(), 1),
                "players": [{"uid": u, "taps": self._shown(u)} for u in self.players],
                "turn": self.current(), "winner": self.winner, "draw": self.draw}

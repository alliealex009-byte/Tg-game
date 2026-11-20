"""Pig: roll or hold. A 1 loses the turn's points. First to 100 wins (2-4 players)."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

TARGET = 100


class PigGame(BaseGame):
    name = "pig"
    min_players = 2
    max_players = 4

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("Pig needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.scores = {u: 0 for u in self.players}
        self.left = set()
        self.turn_idx = 0
        self.turn_total = 0
        self.seq = 0
        self.last_roll = None   # {uid,value,seq,bust}
        self.last_hold = None   # {uid,gained,seq}
        self.winner = None
        self.finished = False
        self.draw = False

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def active(self):
        return [u for u in self.players if u not in self.left]

    def _next(self):
        self.turn_total = 0
        for _ in range(len(self.players)):
            self.turn_idx = (self.turn_idx + 1) % len(self.players)
            if self.players[self.turn_idx] not in self.left:
                return

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        t = msg.get("t")
        if t == "roll":
            self._roll()
        elif t == "hold":
            if self.turn_total <= 0:
                raise GameError("Roll at least once before holding")
            self._hold()
        else:
            raise GameError("Unknown action")

    def _roll(self):
        uid = self.current()
        v = self.rng.randint(1, 6)
        self.seq += 1
        bust = v == 1
        self.last_roll = {"uid": uid, "value": v, "seq": self.seq, "bust": bust}
        if bust:
            self._next()
        else:
            self.turn_total += v
            if self.scores[uid] + self.turn_total >= TARGET:
                self._hold()

    def _hold(self):
        uid = self.current()
        self.scores[uid] += self.turn_total
        self.seq += 1
        self.last_hold = {"uid": uid, "gained": self.turn_total, "seq": self.seq}
        if self.scores[uid] >= TARGET:
            self.winner, self.finished = uid, True
            return
        self._next()

    def auto_play(self):
        if self.finished:
            return
        uid = self.current()
        lead_gap = max(self.scores.values()) - self.scores[uid]
        goal = 20 if lead_gap < 25 else 28
        if self.turn_total >= goal:
            self._hold()
        else:
            self._roll()

    def remove_player(self, uid):
        if uid not in self.scores or uid in self.left or self.finished:
            return
        self.left.add(uid)
        act = self.active()
        if len(act) <= 1:
            self.finished = True
            self.winner = act[0] if act else None
            return
        if self.current() == uid:
            self._next()

    def public_state(self):
        return {
            "kind": "pig", "target": TARGET,
            "players": [{"uid": u, "score": self.scores[u], "left": u in self.left} for u in self.players],
            "turn": self.current(), "turn_total": self.turn_total,
            "last_roll": self.last_roll, "last_hold": self.last_hold,
            "winner": self.winner,
        }

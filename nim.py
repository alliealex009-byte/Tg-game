"""Nim: heaps of 3, 5 and 7. Take any number from one heap; whoever takes the last object wins."""
from __future__ import annotations

import random

from .base import BaseGame, GameError


class NimGame(BaseGame):
    name = "nim"
    min_players = 2
    max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Nim needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.heaps = [3, 5, 7]
        self.turn_idx = 0
        self.seq = 0
        self.last_move = None
        self.winner = None
        self.finished = False
        self.draw = False

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        if msg.get("t") != "take":
            raise GameError("Unknown action")
        h, n = msg.get("heap"), msg.get("n")
        for v in (h, n):
            if isinstance(v, bool) or not isinstance(v, int):
                raise GameError("Bad move")
        if not 0 <= h < len(self.heaps):
            raise GameError("No such heap")
        if not 1 <= n <= self.heaps[h]:
            raise GameError("Take between 1 and %d" % self.heaps[h])
        self._take(h, n)

    def _take(self, h, n):
        uid = self.current()
        self.heaps[h] -= n
        self.seq += 1
        self.last_move = {"uid": uid, "heap": h, "n": n, "seq": self.seq}
        if sum(self.heaps) == 0:
            self.winner, self.finished = uid, True
            return
        self.turn_idx = 1 - self.turn_idx

    def best_move(self):
        x = 0
        for v in self.heaps:
            x ^= v
        if x:
            for i, v in enumerate(self.heaps):
                if v ^ x < v:
                    return i, v - (v ^ x)
        i = max(range(len(self.heaps)), key=lambda k: self.heaps[k])
        return i, 1

    def auto_play(self):
        if not self.finished:
            self._take(*self.best_move())

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        return {
            "kind": "nim", "players": [{"uid": u} for u in self.players], "turn": self.current(),
            "heaps": list(self.heaps), "last_move": self.last_move, "winner": self.winner,
        }

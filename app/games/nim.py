"""Nim with heaps 3-5-7: take any number of stones from one heap; whoever takes the last stone wins."""
from __future__ import annotations

import random

from .base import BaseGame, GameError


class NimGame(BaseGame):
    name = "nim"
    min_players = max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Nim needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.heaps = [3, 5, 7]
        self.turn_idx = 0
        self.seq, self.last_move = 0, None
        self.winner, self.finished, self.draw = None, False, False

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        h, n = msg.get("heap"), msg.get("n")
        if msg.get("t") != "take" or any(isinstance(x, bool) or not isinstance(x, int) for x in (h, n)):
            raise GameError("Bad move")
        if not 0 <= h < 3 or not 1 <= n <= self.heaps[h]:
            raise GameError("You can't take that many")
        self._take(h, n)

    def _take(self, h, n):
        uid = self.current()
        self.heaps[h] -= n
        self.seq += 1
        self.last_move = {"seq": self.seq, "uid": uid, "heap": h, "n": n}
        if not any(self.heaps):
            self.finished, self.winner = True, uid
        else:
            self.turn_idx ^= 1

    def auto_play(self):
        if self.finished:
            return
        x = self.heaps[0] ^ self.heaps[1] ^ self.heaps[2]
        if x and self.rng.random() < 0.85:
            for h, s in enumerate(self.heaps):
                if s ^ x < s:
                    return self._take(h, s - (s ^ x))
        h = self.rng.choice([i for i, s in enumerate(self.heaps) if s])
        self._take(h, self.rng.randint(1, self.heaps[h]))

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished, self.winner = True, next(u for u in self.players if u != uid)

    def public_state(self):
        return {"kind": "nim", "heaps": self.heaps, "players": [{"uid": u} for u in self.players], "turn": self.current(),
                "last_move": self.last_move, "winner": self.winner, "draw": self.draw}

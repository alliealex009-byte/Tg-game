"""Code Breaker (Bulls & Cows): crack a shared secret 4-digit code (no repeated digits). Players alternate guesses."""
from __future__ import annotations

import itertools
import random

from .base import BaseGame, GameError

MAX_GUESSES = 9  # per player


def score(secret, guess):
    bulls = sum(a == b for a, b in zip(secret, guess))
    cows = len(set(secret) & set(guess)) - bulls
    return bulls, cows


class BullsGame(BaseGame):
    name = "bulls"
    min_players, max_players = 2, 4

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("Code Breaker needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.secret = "".join(self.rng.sample("0123456789", 4))
        self.history = []
        self.tries = {u: 0 for u in self.players}
        self.left = set()
        self.turn_idx = 0
        self.seq = 0
        self.winner, self.finished, self.draw = None, False, False

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def _next(self):
        for _ in range(len(self.players)):
            self.turn_idx = (self.turn_idx + 1) % len(self.players)
            u = self.players[self.turn_idx]
            if u not in self.left and self.tries[u] < MAX_GUESSES:
                return True
        return False

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        g = msg.get("digits")
        if msg.get("t") != "guess" or not isinstance(g, str) or len(g) != 4 or not g.isdigit() or len(set(g)) != 4:
            raise GameError("Enter 4 different digits")
        self._guess(uid, g)

    def _guess(self, uid, g):
        b, c = score(self.secret, g)
        self.tries[uid] += 1
        self.seq += 1
        self.history.append({"seq": self.seq, "uid": uid, "guess": g, "bulls": b, "cows": c})
        if b == 4:
            self.finished, self.winner = True, uid
        elif not self._next():
            self.finished = self.draw = True

    def auto_play(self):
        if self.finished:
            return
        pool = ["".join(p) for p in itertools.permutations("0123456789", 4)]
        for h in self.history:
            pool = [p for p in pool if score(p, h["guess"]) == (h["bulls"], h["cows"])]
        self._guess(self.current(), self.rng.choice(pool))

    def remove_player(self, uid):
        if uid not in self.tries or uid in self.left or self.finished:
            return
        was = self.current() == uid
        self.left.add(uid)
        act = [u for u in self.players if u not in self.left]
        if len(act) <= 1:
            self.finished, self.winner = True, act[0] if act else None
        elif was:
            self._next()

    def public_state(self):
        return {"kind": "bulls", "max": MAX_GUESSES, "history": self.history[-24:],
                "players": [{"uid": u, "tries": self.tries[u], "left": u in self.left} for u in self.players],
                "turn": self.current(), "secret": self.secret if self.finished else None, "winner": self.winner, "draw": self.draw}

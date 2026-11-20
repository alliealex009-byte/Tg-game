"""Guess the Number: the bot picks a secret number from 1 to 100. Take turns guessing; you're told higher or lower. Find it to win."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

HI = 100
MAX_GUESSES = 40


class GuessNumberGame(BaseGame):
    name = "guessnum"
    min_players = 2
    max_players = 6

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 6:
            raise ValueError("Guess the Number needs 2-6 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.secret = self.rng.randint(1, HI)
        self.lo, self.hi = 1, HI
        self.turn_idx = 0
        self.history = []
        self.seq = 0
        self.last_move = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        n = msg.get("n")
        if msg.get("t") != "guess" or isinstance(n, bool) or not isinstance(n, int):
            raise GameError("Guess a whole number")
        if not self.lo <= n <= self.hi:
            raise GameError(f"The number is between {self.lo} and {self.hi}")
        self._guess(uid, n)

    def _guess(self, uid, n):
        hint = "correct" if n == self.secret else "higher" if n < self.secret else "lower"
        if hint == "higher":
            self.lo = n + 1
        elif hint == "lower":
            self.hi = n - 1
        self.history.append({"uid": uid, "n": n, "hint": hint})
        self.seq += 1
        self.last_move = {"seq": self.seq, "uid": uid, "n": n, "hint": hint}
        if hint == "correct":
            self.finished, self.winner = True, uid
            return
        if len(self.history) >= MAX_GUESSES:
            self.finished, self.draw = True, True
            return
        self.turn_idx = (self.turn_idx + 1) % len(self.players)

    def auto_play(self):
        if self.finished:
            return
        u = self.current()
        mid = (self.lo + self.hi) // 2
        n = mid if u > 0 else max(self.lo, min(self.hi, mid + self.rng.randint(-max(1, (self.hi - self.lo) // 6), max(1, (self.hi - self.lo) // 6))))
        self._guess(u, n)

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        cur = self.current()
        i = self.players.index(uid)
        self.players.remove(uid)
        if len(self.players) < 2 or all(u < 0 for u in self.players):
            self.finished = True
            self.winner = self.players[0] if self.players else None
            return
        self.turn_idx = self.players.index(cur) if cur in self.players else i % len(self.players)

    def public_state(self):
        return {"kind": "guessnum", "lo": self.lo, "hi": self.hi, "range": HI, "turn": self.current(),
                "history": self.history[-12:], "count": len(self.history), "last_move": self.last_move,
                "players": [{"uid": u} for u in self.players], "secret": self.secret if self.finished else None,
                "winner": self.winner, "draw": self.draw}

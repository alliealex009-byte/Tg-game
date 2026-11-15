"""Higher or Lower with a shared deck. Guess right to score and keep the turn; first to 7 wins."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

TARGET = 7


class HighLowGame(BaseGame):
    name = "highlow"
    min_players, max_players = 2, 4

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("Higher or Lower needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.score = {u: 0 for u in self.players}
        self.left = set()
        self._shuffle()
        self.card = self.deck.pop()
        self.turn_idx = 0
        self.seq, self.last_guess = 0, None
        self.winner, self.finished, self.draw = None, False, False

    def _shuffle(self):
        self.deck = [(v, s) for v in range(2, 15) for s in "SHDC"]
        self.rng.shuffle(self.deck)

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def _next(self):
        for _ in range(len(self.players)):
            self.turn_idx = (self.turn_idx + 1) % len(self.players)
            if self.players[self.turn_idx] not in self.left:
                return

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        g = msg.get("guess")
        if msg.get("t") != "guess" or g not in ("higher", "lower"):
            raise GameError("Pick higher or lower")
        self._guess(uid, g)

    def _guess(self, uid, g):
        if not self.deck:
            self._shuffle()
        nxt = self.deck.pop()
        old = self.card
        if nxt[0] == old[0]:
            res = "push"
        elif (nxt[0] > old[0]) == (g == "higher"):
            res = "right"
        else:
            res = "wrong"
        self.card = nxt
        self.seq += 1
        self.last_guess = {"seq": self.seq, "uid": uid, "guess": g, "old": old, "new": nxt, "result": res}
        if res == "right":
            self.score[uid] += 1
            if self.score[uid] >= TARGET:
                self.finished, self.winner = True, uid
        elif res == "wrong":
            self._next()

    def auto_play(self):
        if self.finished:
            return
        v = self.card[0]
        g = "higher" if v < 8 else "lower" if v > 8 else self.rng.choice(["higher", "lower"])
        self._guess(self.current(), g)

    def remove_player(self, uid):
        if uid not in self.score or uid in self.left or self.finished:
            return
        was = self.current() == uid
        self.left.add(uid)
        act = [u for u in self.players if u not in self.left]
        if len(act) <= 1:
            self.finished, self.winner = True, act[0] if act else None
        elif was:
            self._next()

    def public_state(self):
        return {"kind": "highlow", "target": TARGET, "card": self.card, "deck": len(self.deck),
                "players": [{"uid": u, "score": self.score[u], "left": u in self.left} for u in self.players],
                "turn": self.current(), "last_guess": self.last_guess, "winner": self.winner, "draw": self.draw}

"""Pig: push-your-luck dice. Roll to build your turn total; a 1 loses it. Hold to bank. First to 50 wins."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

TARGET = 50


class PigGame(BaseGame):
    name = "pig"
    min_players, max_players = 2, 4

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("Pig needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.score = {u: 0 for u in self.players}
        self.left = set()
        self.turn_idx, self.run = 0, 0
        self.seq, self.last_roll = 0, None
        self.winner, self.finished, self.draw = None, False, False

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def _next(self):
        for _ in range(len(self.players)):
            self.turn_idx = (self.turn_idx + 1) % len(self.players)
            if self.players[self.turn_idx] not in self.left:
                break
        self.run = 0

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        t = msg.get("t")
        if t == "roll":
            v = self.rng.randint(1, 6)
            self.seq += 1
            busted = v == 1
            lost = self.run if busted else 0
            self.run = 0 if busted else self.run + v
            self.last_roll = {"seq": self.seq, "uid": uid, "value": v, "bust": busted, "lost": lost, "run": self.run}
            if busted:
                self._next()
            elif self.score[uid] + self.run >= TARGET:
                self.score[uid] += self.run
                self.run = 0
                self.finished, self.winner = True, uid
        elif t == "hold":
            if self.run == 0:
                raise GameError("Roll at least once before holding")
            self.score[uid] += self.run
            self.seq += 1
            self.last_roll = {"seq": self.seq, "uid": uid, "value": None, "bust": False, "held": self.run, "run": 0}
            if self.score[uid] >= TARGET:
                self.finished, self.winner = True, uid
            else:
                self._next()
        else:
            raise GameError("Unknown action")

    def auto_play(self):
        if self.finished:
            return
        uid = self.current()
        if self.run >= 18 or (self.run and self.score[uid] + self.run >= TARGET):
            self.handle(uid, {"t": "hold"})
        else:
            self.handle(uid, {"t": "roll"})

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
        return {"kind": "pig", "target": TARGET, "run": self.run, "last_roll": self.last_roll, "turn": self.current(),
                "players": [{"uid": u, "score": self.score[u], "left": u in self.left} for u in self.players],
                "winner": self.winner, "draw": self.draw}

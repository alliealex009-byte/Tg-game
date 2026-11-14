"""Snakes & Ladders (2-4 players). Roll, move, snakes slide you down, ladders lift you up.

Rules: exact roll needed to land on 100 (an overshoot means you stay put). A 6 gives another
roll, but a third 6 in a row loses the move.
"""
from __future__ import annotations

import random

from .base import BaseGame, GameError

SNAKES = {16: 6, 47: 26, 49: 11, 56: 53, 62: 19, 64: 60, 87: 24, 93: 73, 95: 75, 98: 78}
LADDERS = {1: 38, 4: 14, 9: 31, 21: 42, 28: 84, 36: 44, 51: 67, 71: 91, 80: 100}


class SnakesGame(BaseGame):
    name = "snakes"
    min_players = 2
    max_players = 4

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("Snakes & Ladders needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.pos = {u: 0 for u in self.players}
        self.left = set()
        self.turn_idx = 0
        self.sixes = 0
        self.seq = 0
        self.last_roll = None
        self.last_move = None
        self.winner = None
        self.finished = False
        self.draw = False

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def active(self):
        return [u for u in self.players if u not in self.left]

    def _next_turn(self):
        self.sixes = 0
        for _ in range(len(self.players)):
            self.turn_idx = (self.turn_idx + 1) % len(self.players)
            if self.players[self.turn_idx] not in self.left:
                return

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        if msg.get("t") != "roll":
            raise GameError("Unknown action")
        self._roll()

    def _roll(self, forced=None):
        uid = self.current()
        v = forced or self.rng.randint(1, 6)
        self.seq += 1
        self.last_roll = {"uid": uid, "value": v, "seq": self.seq}
        self.sixes = self.sixes + 1 if v == 6 else 0
        frm = self.pos[uid]
        if self.sixes >= 3:  # third six in a row: move is lost
            self.last_move = {"uid": uid, "from": frm, "to": frm, "end": frm, "kind": None, "blocked": True, "seq": self.seq}
            self._next_turn()
            return
        to = frm + v
        if to > 100:  # overshoot: stay
            self.last_move = {"uid": uid, "from": frm, "to": frm, "end": frm, "kind": None, "blocked": True, "seq": self.seq}
        else:
            kind = None
            end = to
            if to in SNAKES:
                end, kind = SNAKES[to], "snake"
            elif to in LADDERS:
                end, kind = LADDERS[to], "ladder"
            self.pos[uid] = end
            self.last_move = {"uid": uid, "from": frm, "to": to, "end": end, "kind": kind, "blocked": False, "seq": self.seq}
            if end == 100:
                self.winner, self.finished = uid, True
                return
        if v == 6:
            return  # roll again
        self._next_turn()

    def auto_play(self):
        if not self.finished:
            self._roll()

    def remove_player(self, uid):
        if uid not in self.pos or uid in self.left or self.finished:
            return
        self.left.add(uid)
        act = self.active()
        if len(act) <= 1:
            self.finished = True
            self.winner = act[0] if act else None
            return
        if self.current() == uid:
            self._next_turn()

    def public_state(self):
        return {
            "kind": "snakes",
            "players": [{"uid": u, "pos": self.pos[u], "left": u in self.left} for u in self.players],
            "turn": self.current(),
            "snakes": SNAKES,
            "ladders": LADDERS,
            "last_roll": self.last_roll,
            "last_move": self.last_move,
            "winner": self.winner,
        }

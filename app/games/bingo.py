"""Bingo (2-6 players). 5x5 cards of numbers 1-75 (free centre). The server calls a number about every 4 seconds
(auto_play is the metronome); tap called numbers on your card, then press BINGO when you hold a full line."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

CALL_SECONDS = 4
PENALTY_CALLS = 3
FREE = 0


def make_card(rng):
    cols = [rng.sample(range(1 + 15 * i, 16 + 15 * i), 5) for i in range(5)]
    card = [[cols[c][r] for c in range(5)] for r in range(5)]  # card[row][col]
    card[2][2] = FREE
    return card


LINES = (
    [[(r, c) for c in range(5)] for r in range(5)]
    + [[(r, c) for r in range(5)] for c in range(5)]
    + [[(i, i) for i in range(5)], [(i, 4 - i) for i in range(5)]]
)


class BingoGame(BaseGame):
    name = "bingo"
    min_players = 2
    max_players = 6
    ticker = True
    phase_seconds = CALL_SECONDS

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 6:
            raise ValueError("Bingo needs 2-6 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.left = set()
        self.cards = {u: make_card(self.rng) for u in self.players}
        self.marks = {u: set() for u in self.players}
        self.penalty = {u: 0 for u in self.players}   # claims blocked until this many numbers were called
        self.bag = list(range(1, 76))
        self.rng.shuffle(self.bag)
        self.called = []
        self.seq = 0
        self.last_call = None
        self.last_claim = None
        self.reveal = None
        self.winner = None
        self.finished = False
        self.draw = False
        self._call()

    @property
    def phase_id(self):
        return len(self.called)

    def current(self):
        if self.finished:
            return None
        act = [u for u in self.players if u not in self.left]
        humans = [u for u in act if u > 0]
        return (humans or act)[0]

    def _line_of(self, u):
        m = self.marks[u]
        for line in LINES:
            if all(self.cards[u][r][c] == FREE or self.cards[u][r][c] in m for r, c in line):
                return line
        return None

    def _call(self):
        # computer players claim with a one-call delay, so humans get a fair chance
        for u in self.players:
            if u < 0 and u not in self.left and not self.finished and self._line_of(u):
                return self._win(u)
        if not self.bag:
            self.finished, self.draw = True, True
            return
        n = self.bag.pop()
        self.called.append(n)
        self.seq += 1
        self.last_call = {"n": n, "seq": self.seq, "count": len(self.called)}
        for u in self.players:
            if u < 0 and any(n == x for row in self.cards[u] for x in row):
                self.marks[u].add(n)

    def _win(self, u):
        line = self._line_of(u)
        self.winner, self.finished = u, True
        self.reveal = {"uid": u, "card": self.cards[u], "marks": sorted(self.marks[u]), "line": [list(p) for p in line] if line else None}

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid not in self.cards or uid in self.left:
            raise GameError("You are not playing")
        t = msg.get("t")
        if t == "mark":
            n = msg.get("n")
            if isinstance(n, bool) or not isinstance(n, int):
                raise GameError("Bad number")
            if n not in self.called:
                raise GameError("That number hasn't been called")
            if not any(n == x for row in self.cards[uid] for x in row):
                raise GameError("That number isn't on your card")
            if n in self.marks[uid]:
                self.marks[uid].discard(n)   # tap again to unmark
            else:
                self.marks[uid].add(n)
        elif t == "bingo":
            if len(self.called) < self.penalty[uid]:
                raise GameError("You're locked out for a few more calls")
            if self._line_of(uid):
                self.seq += 1
                self.last_claim = {"uid": uid, "ok": True, "seq": self.seq}
                self._win(uid)
            else:
                self.seq += 1
                self.penalty[uid] = len(self.called) + PENALTY_CALLS
                self.last_claim = {"uid": uid, "ok": False, "seq": self.seq}
        else:
            raise GameError("Unknown action")

    def auto_play(self):
        if not self.finished:
            self._call()

    def remove_player(self, uid):
        if uid not in self.cards or uid in self.left or self.finished:
            return
        self.left.add(uid)
        act = [u for u in self.players if u not in self.left]
        if len(act) <= 1:
            self.finished = True
            self.winner = act[0] if act else None

    def public_state(self):
        return {
            "kind": "bingo", "call_seconds": CALL_SECONDS,
            "players": [{"uid": u, "left": u in self.left, "marked": len(self.marks[u]), "locked": len(self.called) < self.penalty[u]} for u in self.players],
            "turn": self.current(), "called": list(self.called), "last_call": self.last_call, "last_claim": self.last_claim,
            "winner": self.winner, "draw": self.draw, "reveal": self.reveal,
            "card": None, "marks": [],
        }

    def view(self, uid):
        s = self.public_state()
        if uid in self.cards:
            s["card"] = self.cards[uid]
            s["marks"] = sorted(self.marks[uid])
            s["lock_until"] = self.penalty[uid]
        return s

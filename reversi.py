"""Reversi / Othello 8x8. players[0] is black and moves first. A player with no move is passed automatically."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

DIRS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
W = [100, -20, 10, 5, 5, 10, -20, 100,
     -20, -50, -2, -2, -2, -2, -50, -20,
     10, -2, 1, 1, 1, 1, -2, 10,
     5, -2, 1, 0, 0, 1, -2, 5,
     5, -2, 1, 0, 0, 1, -2, 5,
     10, -2, 1, 1, 1, 1, -2, 10,
     -20, -50, -2, -2, -2, -2, -50, -20,
     100, -20, 10, 5, 5, 10, -20, 100]


def flips(b, cell, me):
    """Cells flipped when `me` (0/1) plays `cell`; empty list if illegal."""
    if b[cell] is not None:
        return []
    r, c = divmod(cell, 8)
    out = []
    for dr, dc in DIRS:
        line = []
        rr, cc = r + dr, c + dc
        while 0 <= rr < 8 and 0 <= cc < 8 and b[rr * 8 + cc] == 1 - me:
            line.append(rr * 8 + cc)
            rr += dr
            cc += dc
        if line and 0 <= rr < 8 and 0 <= cc < 8 and b[rr * 8 + cc] == me:
            out += line
    return out


def valid(b, me):
    return [i for i in range(64) if b[i] is None and flips(b, i, me)]


class ReversiGame(BaseGame):
    name = "reversi"
    min_players = 2
    max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Reversi needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.board = [None] * 64  # 0 = black (players[0]), 1 = white
        self.board[27], self.board[36], self.board[28], self.board[35] = 1, 1, 0, 0
        self.turn_idx = 0
        self.winner = None
        self.finished = False
        self.draw = False
        self.seq = 0
        self.last_move = None

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        if msg.get("t") != "place":
            raise GameError("Unknown action")
        cell = msg.get("cell")
        if isinstance(cell, bool) or not isinstance(cell, int) or not 0 <= cell < 64:
            raise GameError("Bad cell")
        if not flips(self.board, cell, self.turn_idx):
            raise GameError("You must flip at least one disc")
        self._play(cell)

    def _play(self, cell):
        me = self.turn_idx
        fl = flips(self.board, cell, me)
        self.board[cell] = me
        for i in fl:
            self.board[i] = me
        self.seq += 1
        passed = None
        if valid(self.board, 1 - me):
            self.turn_idx = 1 - me
        elif valid(self.board, me):
            passed = self.players[1 - me]  # opponent has no move: same player continues
        else:
            self._end()
        self.last_move = {"uid": self.players[me], "cell": cell, "flips": fl, "passed": passed, "seq": self.seq}

    def _end(self):
        self.finished = True
        a, b = self.board.count(0), self.board.count(1)
        if a == b:
            self.draw = True
        else:
            self.winner = self.players[0 if a > b else 1]

    def auto_play(self):
        if self.finished:
            return
        ms = valid(self.board, self.turn_idx)
        if not ms:
            return
        self._play(max(ms, key=lambda c: W[c] + len(flips(self.board, c, self.turn_idx)) * 0.5 + self.rng.random()))

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        return {
            "kind": "reversi",
            "players": [{"uid": u, "color": c} for u, c in zip(self.players, ("black", "white"))],
            "board": self.board,
            "turn": self.current(),
            "legal": [] if self.finished else valid(self.board, self.turn_idx),
            "counts": [self.board.count(0), self.board.count(1)],
            "last_move": self.last_move,
            "winner": self.winner,
            "draw": self.draw,
        }

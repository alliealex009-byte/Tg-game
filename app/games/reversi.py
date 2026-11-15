"""Reversi / Othello 8x8. Passes happen automatically when a player has no move."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

DIRS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
W = [[100, -20, 10, 5, 5, 10, -20, 100], [-20, -50, -2, -2, -2, -2, -50, -20], [10, -2, 1, 1, 1, 1, -2, 10], [5, -2, 1, 0, 0, 1, -2, 5]]
W = W + W[::-1]


class ReversiGame(BaseGame):
    name = "reversi"
    min_players = max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Reversi needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.mark = {self.players[0]: "B", self.players[1]: "W"}
        self.board = [""] * 64
        self.board[27], self.board[36], self.board[28], self.board[35] = "W", "W", "B", "B"
        self.turn_mark = "B"
        self.seq, self.last_move, self.note = 0, None, ""
        self.winner, self.finished, self.draw = None, False, False

    def _uid(self, m):
        return next(u for u in self.players if self.mark[u] == m)

    def current(self):
        return None if self.finished else self._uid(self.turn_mark)

    def flips(self, sq, m, board=None):
        b = board or self.board
        if b[sq]:
            return []
        r, c = divmod(sq, 8)
        opp = "W" if m == "B" else "B"
        out = []
        for dr, dc in DIRS:
            line, rr, cc = [], r + dr, c + dc
            while 0 <= rr < 8 and 0 <= cc < 8 and b[rr * 8 + cc] == opp:
                line.append(rr * 8 + cc)
                rr, cc = rr + dr, cc + dc
            if line and 0 <= rr < 8 and 0 <= cc < 8 and b[rr * 8 + cc] == m:
                out += line
        return out

    def moves(self, m):
        return {sq: f for sq in range(64) if (f := self.flips(sq, m))}

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        sq = msg.get("cell")
        if msg.get("t") != "place" or isinstance(sq, bool) or not isinstance(sq, int) or not 0 <= sq < 64:
            raise GameError("Bad move")
        if not self.flips(sq, self.turn_mark):
            raise GameError("You must flip at least one disc")
        self._place(sq)

    def _place(self, sq):
        m = self.turn_mark
        fl = self.flips(sq, m)
        self.board[sq] = m
        for f in fl:
            self.board[f] = m
        self.seq += 1
        self.last_move = {"seq": self.seq, "uid": self._uid(m), "cell": sq, "flips": fl}
        self.note = ""
        opp = "W" if m == "B" else "B"
        if self.moves(opp):
            self.turn_mark = opp
        elif self.moves(m):
            self.note = f"{'White' if opp == 'W' else 'Black'} has no move and passes"
        else:
            self.finished = True
            b, w = self.board.count("B"), self.board.count("W")
            if b == w:
                self.draw = True
            else:
                self.winner = self._uid("B" if b > w else "W")

    def auto_play(self):
        if self.finished:
            return
        mv = self.moves(self.turn_mark)
        self._place(max(mv, key=lambda s: W[s // 8][s % 8] + len(mv[s]) * 2 + self.rng.random() * 6))

    def remove_player(self, uid):
        if uid not in self.mark or self.finished:
            return
        self.finished, self.winner = True, next(u for u in self.players if u != uid)

    def public_state(self):
        return {"kind": "reversi", "players": [{"uid": u, "mark": self.mark[u]} for u in self.players],
                "board": self.board, "turn": self.current(),
                "valid": [] if self.finished else sorted(self.moves(self.turn_mark)),
                "counts": {"B": self.board.count("B"), "W": self.board.count("W")},
                "last_move": self.last_move, "note": self.note, "winner": self.winner, "draw": self.draw}

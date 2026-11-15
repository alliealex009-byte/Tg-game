"""Gomoku: first to get five in a row on a 13x13 board."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

N = 13


class GomokuGame(BaseGame):
    name = "gomoku"
    min_players = max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Gomoku needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.mark = {self.players[0]: "X", self.players[1]: "O"}
        self.board = [""] * (N * N)
        self.turn_idx, self.moves = 0, 0
        self.seq, self.last_move, self.line = 0, None, None
        self.winner, self.finished, self.draw = None, False, False

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        c = msg.get("cell")
        if msg.get("t") != "place" or isinstance(c, bool) or not isinstance(c, int) or not 0 <= c < N * N:
            raise GameError("Bad move")
        if self.board[c]:
            raise GameError("That point is taken")
        self._place(c)

    def _run(self, c, m):
        r0, c0 = divmod(c, N)
        for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
            line = [c]
            for sgn in (1, -1):
                r, cc = r0 + sgn * dr, c0 + sgn * dc
                while 0 <= r < N and 0 <= cc < N and self.board[r * N + cc] == m:
                    line.append(r * N + cc)
                    r, cc = r + sgn * dr, cc + sgn * dc
            if len(line) >= 5:
                return line
        return None

    def _place(self, c):
        uid = self.current()
        m = self.mark[uid]
        self.board[c] = m
        self.moves += 1
        self.seq += 1
        self.last_move = {"seq": self.seq, "uid": uid, "cell": c}
        line = self._run(c, m)
        if line:
            self.finished, self.winner, self.line = True, uid, sorted(line)
        elif self.moves == N * N:
            self.finished = self.draw = True
        else:
            self.turn_idx ^= 1

    def _score_pt(self, c, m):
        r0, c0 = divmod(c, N)
        s = 0
        for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
            for who, w in ((m, 1.0), ("O" if m == "X" else "X", 0.9)):
                n = 0
                for sgn in (1, -1):
                    r, cc = r0 + sgn * dr, c0 + sgn * dc
                    while 0 <= r < N and 0 <= cc < N and self.board[r * N + cc] == who:
                        n += 1
                        r, cc = r + sgn * dr, cc + sgn * dc
                s += w * (10 ** n if n < 4 else 100000)
        return s - (abs(r0 - N // 2) + abs(c0 - N // 2)) * 0.3

    def auto_play(self):
        if self.finished:
            return
        m = self.mark[self.current()]
        cand = [i for i in range(N * N) if not self.board[i] and any(
            self.board[j] for j in self._near(i))] or [N * N // 2]
        self._place(max(cand, key=lambda i: self._score_pt(i, m) + self.rng.random()))

    def _near(self, i):
        r, c = divmod(i, N)
        return [rr * N + cc for rr in range(max(0, r - 2), min(N, r + 3)) for cc in range(max(0, c - 2), min(N, c + 3))]

    def remove_player(self, uid):
        if uid not in self.mark or self.finished:
            return
        self.finished, self.winner = True, next(u for u in self.players if u != uid)

    def public_state(self):
        return {"kind": "gomoku", "n": N, "players": [{"uid": u, "mark": self.mark[u]} for u in self.players],
                "board": self.board, "turn": self.current(), "last_move": self.last_move, "line": self.line,
                "winner": self.winner, "draw": self.draw}

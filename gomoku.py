"""Gomoku on a 15x15 board: first to make five (or more) in a row wins. players[0] is black."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

N = 15
DIRS = ((0, 1), (1, 0), (1, 1), (1, -1))


def line_through(b, cell, who):
    """Winning line (>=5) through `cell` for `who`, or None."""
    r, c = divmod(cell, N)
    for dr, dc in DIRS:
        cells = [cell]
        for sgn in (1, -1):
            rr, cc = r + dr * sgn, c + dc * sgn
            while 0 <= rr < N and 0 <= cc < N and b[rr * N + cc] == who:
                cells.append(rr * N + cc)
                rr += dr * sgn
                cc += dc * sgn
        if len(cells) >= 5:
            return sorted(cells)
    return None


def pattern_score(b, cell, who):
    """Heuristic value of `who` playing `cell`: longer, more open lines score more."""
    r, c = divmod(cell, N)
    total = 0
    for dr, dc in DIRS:
        n, open_ends = 1, 0
        for sgn in (1, -1):
            rr, cc = r + dr * sgn, c + dc * sgn
            while 0 <= rr < N and 0 <= cc < N and b[rr * N + cc] == who:
                n += 1
                rr += dr * sgn
                cc += dc * sgn
            if 0 <= rr < N and 0 <= cc < N and b[rr * N + cc] is None:
                open_ends += 1
        if n >= 5:
            total += 100000
        elif n == 4:
            total += 10000 if open_ends == 2 else 1500 if open_ends == 1 else 0
        elif n == 3:
            total += 1000 if open_ends == 2 else 100 if open_ends == 1 else 0
        elif n == 2:
            total += 60 if open_ends == 2 else 8 if open_ends == 1 else 0
        else:
            total += 2 if open_ends else 0
    return total


class GomokuGame(BaseGame):
    name = "gomoku"
    min_players = 2
    max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Gomoku needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.board = [None] * (N * N)   # 0 / 1 = player index
        self.turn_idx = 0
        self.winner = None
        self.finished = False
        self.draw = False
        self.line = None
        self.seq = 0
        self.last_move = None
        self.count = 0

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
        if isinstance(cell, bool) or not isinstance(cell, int) or not 0 <= cell < N * N:
            raise GameError("Bad cell")
        if self.board[cell] is not None:
            raise GameError("That point is taken")
        self._place(cell)

    def _place(self, cell):
        me = self.turn_idx
        self.board[cell] = me
        self.count += 1
        self.seq += 1
        self.last_move = {"uid": self.players[me], "cell": cell, "seq": self.seq}
        line = line_through(self.board, cell, me)
        if line:
            self.winner, self.finished, self.line = self.players[me], True, line
        elif self.count == N * N:
            self.finished, self.draw = True, True
        else:
            self.turn_idx = 1 - me

    def _candidates(self):
        if self.count == 0:
            return [N * 7 + 7]
        out = set()
        for i, v in enumerate(self.board):
            if v is None:
                continue
            r, c = divmod(i, N)
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < N and 0 <= cc < N and self.board[rr * N + cc] is None:
                        out.add(rr * N + cc)
        return list(out) or [i for i, v in enumerate(self.board) if v is None]

    def auto_play(self):
        if self.finished:
            return
        me, opp = self.turn_idx, 1 - self.turn_idx
        best, pick = -1, []
        for cell in self._candidates():
            sc = pattern_score(self.board, cell, me) * 1.05 + pattern_score(self.board, cell, opp)
            r, c = divmod(cell, N)
            sc += 3 - (abs(r - 7) + abs(c - 7)) * 0.1
            if sc > best + 1e-9:
                best, pick = sc, [cell]
            elif abs(sc - best) < 1e-9:
                pick.append(cell)
        self._place(self.rng.choice(pick))

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        return {
            "kind": "gomoku",
            "size": N,
            "players": [{"uid": u, "color": c} for u, c in zip(self.players, ("black", "white"))],
            "board": self.board,
            "turn": self.current(),
            "line": self.line,
            "last_move": self.last_move,
            "winner": self.winner,
            "draw": self.draw,
        }

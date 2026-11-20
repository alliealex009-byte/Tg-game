"""Connect Four: drop discs into a 7x6 grid, first to line up four wins."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

COLS, ROWS = 7, 6


def find_four(board, who):
    """Return the 4 cell indexes (row*7+col) forming a line for `who`, or None. Row 0 is the top."""
    for r in range(ROWS):
        for c in range(COLS):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                cells = []
                for k in range(4):
                    rr, cc = r + dr * k, c + dc * k
                    if not (0 <= rr < ROWS and 0 <= cc < COLS) or board[rr * COLS + cc] != who:
                        break
                    cells.append(rr * COLS + cc)
                else:
                    return cells
    return None


def landing_row(board, col):
    for r in range(ROWS - 1, -1, -1):
        if board[r * COLS + col] is None:
            return r
    return None


class ConnectFourGame(BaseGame):
    name = "connect4"
    min_players = 2
    max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Connect Four needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.board = [None] * (ROWS * COLS)
        self.turn_idx = 0
        self.winner = None
        self.finished = False
        self.draw = False
        self.line = None
        self.seq = 0
        self.last_move = None

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        if msg.get("t") != "drop":
            raise GameError("Unknown action")
        col = msg.get("col")
        if isinstance(col, bool) or not isinstance(col, int) or not 0 <= col < COLS:
            raise GameError("Bad column")
        if landing_row(self.board, col) is None:
            raise GameError("That column is full")
        self._drop(col)

    def _drop(self, col):
        uid = self.current()
        row = landing_row(self.board, col)
        self.board[row * COLS + col] = uid
        self.seq += 1
        self.last_move = {"uid": uid, "col": col, "row": row, "seq": self.seq}
        line = find_four(self.board, uid)
        if line:
            self.winner, self.finished, self.line = uid, True, line
        elif all(v is not None for v in self.board):
            self.finished, self.draw = True, True
        else:
            self.turn_idx = 1 - self.turn_idx

    def auto_play(self):
        if self.finished:
            return
        me = self.current()
        opp = self.players[1 - self.turn_idx]
        valid = [c for c in range(COLS) if landing_row(self.board, c) is not None]

        def would_win(col, who):
            r = landing_row(self.board, col)
            self.board[r * COLS + col] = who
            ok = find_four(self.board, who) is not None
            self.board[r * COLS + col] = None
            return ok

        for who in (me, opp):  # win if possible, otherwise block
            for c in valid:
                if would_win(c, who):
                    return self._drop(c)

        def gives_win(col):  # does playing here let the opponent win right on top?
            r = landing_row(self.board, col)
            if r == 0:
                return False
            self.board[r * COLS + col] = me
            bad = would_win(col, opp)
            self.board[r * COLS + col] = None
            return bad

        safe = [c for c in valid if not gives_win(c)] or valid
        best = min(abs(c - 3) for c in safe)
        self._drop(self.rng.choice([c for c in safe if abs(c - 3) <= best + 1]))

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        return {
            "kind": "connect4",
            "players": [{"uid": u} for u in self.players],
            "board": self.board,
            "turn": self.current(),
            "winner": self.winner,
            "draw": self.draw,
            "line": self.line,
            "last_move": self.last_move,
        }

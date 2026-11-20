"""Tic-Tac-Toe engine. Also the smallest example of how to add a new game."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))


class TicTacToeGame(BaseGame):
    name = "tictactoe"
    min_players = 2
    max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Tic-Tac-Toe needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.marks = {self.players[0]: "X", self.players[1]: "O"}
        self.board = [""] * 9
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
        if msg.get("t") != "place":
            raise GameError("Unknown action")
        cell = msg.get("cell")
        if isinstance(cell, bool) or not isinstance(cell, int) or not 0 <= cell <= 8:
            raise GameError("Bad cell")
        if self.board[cell]:
            raise GameError("That square is taken")
        self._place(cell)

    def _place(self, cell):
        uid = self.current()
        mark = self.marks[uid]
        self.board[cell] = mark
        self.seq += 1
        self.last_move = {"uid": uid, "cell": cell, "seq": self.seq}
        for a, b, c in LINES:
            if self.board[a] == self.board[b] == self.board[c] == mark:
                self.winner, self.finished, self.line = uid, True, [a, b, c]
                return
        if all(self.board):
            self.finished, self.draw = True, True
            return
        self.turn_idx = 1 - self.turn_idx

    def auto_play(self):
        if self.finished:
            return
        mark = self.marks[self.current()]
        other = "O" if mark == "X" else "X"
        empty = [i for i, v in enumerate(self.board) if not v]
        for want in (mark, other):  # win if possible, otherwise block
            for a, b, c in LINES:
                cells = [self.board[a], self.board[b], self.board[c]]
                if cells.count(want) == 2 and cells.count("") == 1:
                    self._place((a, b, c)[cells.index("")])
                    return
        for pref in (4, 0, 2, 6, 8):
            if pref in empty:
                self._place(pref)
                return
        self._place(self.rng.choice(empty))

    def remove_player(self, uid):
        if uid not in self.marks or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        return {
            "kind": "tictactoe",
            "players": [{"uid": u, "mark": self.marks[u]} for u in self.players],
            "board": self.board,
            "turn": self.current(),
            "winner": self.winner,
            "draw": self.draw,
            "line": self.line,
            "last_move": self.last_move,
        }

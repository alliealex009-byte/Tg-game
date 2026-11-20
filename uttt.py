"""Ultimate Tic-Tac-Toe: win three small boards in a row. Your move decides which small board the opponent must play in.
cell = board*9 + position (both 0..8). players[0] is X."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))


def small_winner(cells):
    for a, b, c in LINES:
        if cells[a] is not None and cells[a] == cells[b] == cells[c]:
            return cells[a]
    return None


class UltimateTTTGame(BaseGame):
    name = "uttt"
    min_players = 2
    max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Ultimate Tic-Tac-Toe needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.cells = [None] * 81        # 0 / 1 = player index
        self.boards = [None] * 9        # None open, 0/1 won, 2 = drawn
        self.active = -1                # -1 = may play anywhere
        self.turn_idx = 0
        self.winner = None
        self.finished = False
        self.draw = False
        self.line = None
        self.seq = 0
        self.last_move = None

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def legal(self):
        if self.finished:
            return []
        boards = [self.active] if self.active >= 0 else [i for i in range(9) if self.boards[i] is None]
        return [bi * 9 + p for bi in boards for p in range(9) if self.cells[bi * 9 + p] is None]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        if msg.get("t") != "place":
            raise GameError("Unknown action")
        cell = msg.get("cell")
        if isinstance(cell, bool) or not isinstance(cell, int) or not 0 <= cell < 81:
            raise GameError("Bad cell")
        if cell not in self.legal():
            raise GameError("You must play in the highlighted board" if self.active >= 0 else "Illegal square")
        self._place(cell)

    def _place(self, cell):
        me = self.turn_idx
        bi, p = divmod(cell, 9)
        self.cells[cell] = me
        won_board = None
        small = self.cells[bi * 9:bi * 9 + 9]
        w = small_winner(small)
        if w is not None:
            self.boards[bi] = w
            won_board = bi
        elif all(v is not None for v in small):
            self.boards[bi] = 2
        self.seq += 1
        self.last_move = {"uid": self.players[me], "cell": cell, "board": bi, "won_board": won_board, "seq": self.seq}
        big = [v if v in (0, 1) else None for v in self.boards]
        for a, b, c in LINES:
            if big[a] is not None and big[a] == big[b] == big[c]:
                self.winner, self.finished, self.line = self.players[big[a]], True, [a, b, c]
                return
        if all(v is not None for v in self.boards):
            a, b = self.boards.count(0), self.boards.count(1)
            self.finished = True
            if a == b:
                self.draw = True
            else:
                self.winner = self.players[0 if a > b else 1]
            return
        self.active = p if self.boards[p] is None else -1
        self.turn_idx = 1 - me

    def auto_play(self):
        if self.finished:
            return
        me = self.turn_idx
        ms = self.legal()
        if not ms:
            return

        def score(cell):
            bi, p = divmod(cell, 9)
            s = self.rng.random()
            small = list(self.cells[bi * 9:bi * 9 + 9])
            for who, wgt in ((me, 10), (1 - me, 6)):
                small[p] = who
                if small_winner(small) == who:
                    s += wgt
                small[p] = None
            if self.boards[p] is not None:
                s -= 1  # sends opponent anywhere
            else:
                t = list(self.cells[p * 9:p * 9 + 9])
                for k in range(9):  # don't hand the opponent a board win
                    if t[k] is None:
                        t[k] = 1 - me
                        if small_winner(t) == 1 - me:
                            s -= 5
                            break
                        t[k] = None
            if p == 4:
                s += 0.5
            return s
        self._place(max(ms, key=score))

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        return {
            "kind": "uttt",
            "players": [{"uid": u, "mark": m} for u, m in zip(self.players, ("X", "O"))],
            "cells": self.cells,
            "boards": self.boards,
            "active": self.active,
            "legal": self.legal(),
            "turn": self.current(),
            "line": self.line,
            "last_move": self.last_move,
            "winner": self.winner,
            "draw": self.draw,
        }

"""Dots & Boxes on a 5x5 box grid (6x6 dots). Completing a box scores it and gives another move."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

N = 5


class DotsGame(BaseGame):
    name = "dots"
    min_players = 2
    max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Dots & Boxes needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.h = [[0] * N for _ in range(N + 1)]        # horizontal edges: rows 0..N, cols 0..N-1
        self.v = [[0] * (N + 1) for _ in range(N)]      # vertical edges: rows 0..N-1, cols 0..N
        self.boxes = [[0] * N for _ in range(N)]
        self.scores = {u: 0 for u in self.players}
        self.turn_idx = 0
        self.seq = 0
        self.last_move = None
        self.winner = None
        self.finished = False
        self.draw = False

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def _sides(self, r, c):
        return (self.h[r][c] != 0) + (self.h[r + 1][c] != 0) + (self.v[r][c] != 0) + (self.v[r][c + 1] != 0)

    def free_edges(self):
        out = []
        for r in range(N + 1):
            for c in range(N):
                if not self.h[r][c]:
                    out.append(("h", r, c))
        for r in range(N):
            for c in range(N + 1):
                if not self.v[r][c]:
                    out.append(("v", r, c))
        return out

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        if msg.get("t") != "line":
            raise GameError("Unknown action")
        d, r, c = msg.get("d"), msg.get("r"), msg.get("c")
        if d not in ("h", "v") or any(isinstance(x, bool) or not isinstance(x, int) for x in (r, c)):
            raise GameError("Bad move")
        rows, cols = (N + 1, N) if d == "h" else (N, N + 1)
        if not (0 <= r < rows and 0 <= c < cols):
            raise GameError("Bad move")
        if (self.h if d == "h" else self.v)[r][c]:
            raise GameError("That line is taken")
        self._draw(d, r, c)

    def _draw(self, d, r, c):
        uid = self.current()
        (self.h if d == "h" else self.v)[r][c] = uid
        cand = [(r - 1, c), (r, c)] if d == "h" else [(r, c - 1), (r, c)]
        got = []
        for br, bc in cand:
            if 0 <= br < N and 0 <= bc < N and not self.boxes[br][bc] and self._sides(br, bc) == 4:
                self.boxes[br][bc] = uid
                self.scores[uid] += 1
                got.append([br, bc])
        self.seq += 1
        self.last_move = {"uid": uid, "d": d, "r": r, "c": c, "boxes": got, "seq": self.seq}
        if sum(self.scores.values()) == N * N:
            a, b = self.players
            self.finished = True
            if self.scores[a] != self.scores[b]:
                self.winner = a if self.scores[a] > self.scores[b] else b
            else:
                self.draw = True
            return
        if not got:
            self.turn_idx = 1 - self.turn_idx

    def auto_play(self):
        if self.finished:
            return
        free = self.free_edges()

        def completes(e):
            d, r, c = e
            cand = [(r - 1, c), (r, c)] if d == "h" else [(r, c - 1), (r, c)]
            return any(0 <= br < N and 0 <= bc < N and self._sides(br, bc) == 3 for br, bc in cand)

        def gives(e):
            d, r, c = e
            cand = [(r - 1, c), (r, c)] if d == "h" else [(r, c - 1), (r, c)]
            return any(0 <= br < N and 0 <= bc < N and self._sides(br, bc) == 2 for br, bc in cand)

        grab = [e for e in free if completes(e)]
        safe = [e for e in free if not gives(e)]
        pick = self.rng.choice(grab or safe or free)
        self._draw(*pick)

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        return {
            "kind": "dots", "n": N,
            "players": [{"uid": u, "score": self.scores[u]} for u in self.players],
            "turn": self.current(), "h": self.h, "v": self.v, "boxes": self.boxes,
            "last_move": self.last_move, "winner": self.winner, "draw": self.draw,
        }

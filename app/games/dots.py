"""Dots & Boxes on a 5x5 box grid. Completing a box scores and gives another turn."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

N = 5  # boxes per side; horizontal edges: (N+1)*N, vertical edges: N*(N+1)


def h_edge(r, c):  # r in 0..N, c in 0..N-1
    return r * N + c


def v_edge(r, c):  # r in 0..N-1, c in 0..N
    return (N + 1) * N + r * (N + 1) + c


NE = 2 * N * (N + 1)


def box_edges(r, c):
    return [h_edge(r, c), h_edge(r + 1, c), v_edge(r, c), v_edge(r, c + 1)]


class DotsGame(BaseGame):
    name = "dots"
    min_players, max_players = 2, 4

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("Dots & Boxes needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.edges = [None] * NE
        self.boxes = [None] * (N * N)
        self.score = {u: 0 for u in self.players}
        self.left = set()
        self.turn_idx = 0
        self.seq, self.last_move = 0, None
        self.winner, self.finished, self.draw = None, False, False

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def _next(self):
        for _ in range(len(self.players)):
            self.turn_idx = (self.turn_idx + 1) % len(self.players)
            if self.players[self.turn_idx] not in self.left:
                return

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        e = msg.get("edge")
        if msg.get("t") != "edge" or isinstance(e, bool) or not isinstance(e, int) or not 0 <= e < NE:
            raise GameError("Bad move")
        if self.edges[e] is not None:
            raise GameError("That line is already drawn")
        self._draw(e)

    def _sides(self, b):
        r, c = divmod(b, N)
        return sum(self.edges[x] is not None for x in box_edges(r, c))

    def _draw(self, e):
        uid = self.current()
        self.edges[e] = uid
        done = []
        for b in range(N * N):
            if self.boxes[b] is None and self._sides(b) == 4 and e in box_edges(*divmod(b, N)):
                self.boxes[b] = uid
                self.score[uid] += 1
                done.append(b)
        self.seq += 1
        self.last_move = {"seq": self.seq, "uid": uid, "edge": e, "boxes": done}
        if all(x is not None for x in self.boxes):
            self.finished = True
            best = max(self.score.values())
            top = [u for u, s in self.score.items() if s == best]
            if len(top) == 1:
                self.winner = top[0]
            else:
                self.draw = True
            return
        if not done:
            self._next()

    def auto_play(self):
        if self.finished:
            return
        free = [i for i in range(NE) if self.edges[i] is None]

        def cost(e):
            owners = [b for b in range(N * N) if self.boxes[b] is None and e in box_edges(*divmod(b, N))]
            if any(self._sides(b) == 3 for b in owners):
                return -10
            return sum(1 for b in owners if self._sides(b) == 2) * 5 + self.rng.random()
        self._draw(min(free, key=cost))

    def remove_player(self, uid):
        if uid not in self.score or uid in self.left or self.finished:
            return
        self.left.add(uid)
        act = [u for u in self.players if u not in self.left]
        if len(act) <= 1:
            self.finished, self.winner = True, act[0] if act else None
        elif self.current() == uid:
            self._next()

    def public_state(self):
        return {"kind": "dots", "n": N, "players": [{"uid": u, "score": self.score[u], "left": u in self.left} for u in self.players],
                "edges": self.edges, "boxes": self.boxes, "turn": self.current(), "last_move": self.last_move,
                "winner": self.winner, "draw": self.draw}

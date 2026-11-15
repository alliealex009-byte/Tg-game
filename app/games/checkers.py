"""Checkers (American draughts): forced captures, multi-jumps (continue with the same piece), kings."""
from __future__ import annotations

import random

from .base import BaseGame, GameError


def _on(r, c):
    return 0 <= r < 8 and 0 <= c < 8


class CheckersGame(BaseGame):
    name = "checkers"
    min_players = max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Checkers needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.side = {self.players[0]: "r", self.players[1]: "b"}  # red moves up (towards row 0)
        self.board = [""] * 64
        for r in range(8):
            for c in range(8):
                if (r + c) % 2 == 1:
                    if r < 3:
                        self.board[r * 8 + c] = "b"
                    elif r > 4:
                        self.board[r * 8 + c] = "r"
        self.turn_side = "r"
        self.chain = None
        self.idle = 0
        self.seq, self.last_move = 0, None
        self.winner, self.finished, self.draw = None, False, False

    def _uid(self, side):
        return next(u for u in self.players if self.side[u] == side)

    def current(self):
        return None if self.finished else self._uid(self.turn_side)

    def _dirs(self, p):
        if p.isupper():
            return [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        return [(-1, -1), (-1, 1)] if p == "r" else [(1, -1), (1, 1)]

    def _moves_from(self, sq, jumps_only=False):
        p = self.board[sq]
        r, c = divmod(sq, 8)
        out = []
        for dr, dc in self._dirs(p):
            r1, c1, r2, c2 = r + dr, c + dc, r + 2 * dr, c + 2 * dc
            if not (_on(r1, c1) and _on(r2, c2)):
                continue
            mid, dst = self.board[r1 * 8 + c1], self.board[r2 * 8 + c2]
            if mid and mid.lower() != p.lower() and not dst:
                out.append((r2 * 8 + c2, r1 * 8 + c1))
            elif not mid and not jumps_only:
                out.append((r1 * 8 + c1, None))
        return out

    def legal(self):
        """dict from -> list of (to, captured_sq|None)"""
        side = self.turn_side
        sqs = [self.chain] if self.chain is not None else [i for i, p in enumerate(self.board) if p and p.lower() == side]
        jumps = {s: self._moves_from(s, True) for s in sqs}
        jumps = {s: m for s, m in jumps.items() if m}
        if jumps:
            return jumps
        if self.chain is not None:
            return {}
        steps = {s: self._moves_from(s) for s in sqs}
        return {s: m for s, m in steps.items() if m}

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        if msg.get("t") != "move":
            raise GameError("Unknown action")
        f, t = msg.get("from"), msg.get("to")
        if any(isinstance(x, bool) or not isinstance(x, int) for x in (f, t)):
            raise GameError("Bad move")
        mv = next((m for m in self.legal().get(f, []) if m[0] == t), None)
        if mv is None:
            jumps_exist = any(m[1] is not None for ms in self.legal().values() for m in ms)
            raise GameError("You must capture!" if jumps_exist else "Illegal move")
        self._play(f, mv)

    def _play(self, f, mv):
        to, cap = mv
        p = self.board[f]
        self.board[f], self.board[to] = "", p
        kinged = False
        if cap is not None:
            self.board[cap] = ""
        if p.islower() and ((p == "r" and to < 8) or (p == "b" and to >= 56)):
            self.board[to] = p.upper()
            kinged = True
        self.seq += 1
        self.idle = 0 if (cap is not None or p.islower()) else self.idle + 1
        self.last_move = {"seq": self.seq, "uid": self._uid(self.turn_side), "from": f, "to": to, "captured": cap, "king": kinged}
        if cap is not None and not kinged and self._moves_from(to, True):
            self.chain = to
            return
        self.chain = None
        self.turn_side = "b" if self.turn_side == "r" else "r"
        if not self.legal():
            self.finished, self.winner = True, self._uid("b" if self.turn_side == "r" else "r")
        elif self.idle >= 80:
            self.finished = self.draw = True

    def auto_play(self):
        if self.finished:
            return
        opts = [(f, m) for f, ms in self.legal().items() for m in ms]

        def score(o):
            f, (t, cap) = o
            s = self.rng.random()
            if cap is not None:
                s += 10
            if self.board[f].islower() and ((self.turn_side == "r" and t < 8) or (self.turn_side == "b" and t >= 56)):
                s += 6
            r, c = divmod(t, 8)
            s += 1 if c in (0, 7) else 0
            return s
        f, mv = max(opts, key=score)
        self._play(f, mv)

    def remove_player(self, uid):
        if uid not in self.side or self.finished:
            return
        self.finished, self.winner = True, next(u for u in self.players if u != uid)

    def public_state(self):
        leg = {} if self.finished else {f: [m[0] for m in ms] for f, ms in self.legal().items()}
        return {"kind": "checkers", "players": [{"uid": u, "side": self.side[u]} for u in self.players],
                "board": self.board, "turn": self.current(), "dests": leg, "chain": self.chain,
                "last_move": self.last_move, "winner": self.winner, "draw": self.draw}

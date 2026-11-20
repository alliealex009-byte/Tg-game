"""Mancala (Kalah). Pits 0-5 are the first player's, 6 is their store, 7-12 the second player's, 13 their store.
Last stone in your own store = extra turn; last stone in an empty pit of yours captures the opposite pit."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

STORE = (6, 13)


class MancalaGame(BaseGame):
    name = "mancala"
    min_players = 2
    max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Mancala needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.board = [4, 4, 4, 4, 4, 4, 0, 4, 4, 4, 4, 4, 4, 0]
        self.turn_idx = 0
        self.seq = 0
        self.last_move = None
        self.winner = None
        self.finished = False
        self.draw = False

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def side(self, idx):
        return range(0, 6) if idx == 0 else range(7, 13)

    def legal(self):
        return [i for i in self.side(self.turn_idx) if self.board[i] > 0]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        if msg.get("t") != "sow":
            raise GameError("Unknown action")
        pit = msg.get("pit")
        if isinstance(pit, bool) or not isinstance(pit, int) or not 0 <= pit <= 5:
            raise GameError("Bad pit")
        i = pit + 7 * self.turn_idx
        if self.board[i] == 0:
            raise GameError("That pit is empty")
        self._sow(i)

    def _sow(self, i):
        uid, me = self.current(), self.turn_idx
        mine, theirs_store = STORE[me], STORE[1 - me]
        before = list(self.board)
        n, self.board[i] = self.board[i], 0
        path, pos = [], i
        while n:
            pos = (pos + 1) % 14
            if pos == theirs_store:
                continue
            self.board[pos] += 1
            path.append(pos)
            n -= 1
        extra, capture = pos == mine, None
        if not extra and pos in self.side(me) and self.board[pos] == 1 and self.board[12 - pos] > 0:
            got = self.board[12 - pos] + 1
            capture = {"from": 12 - pos, "to": pos, "n": got}
            self.board[mine] += got
            self.board[pos] = self.board[12 - pos] = 0
        self.seq += 1
        self.last_move = {"uid": uid, "pit": i, "path": path, "extra": extra, "capture": capture, "before": before, "sweep": None, "seq": self.seq}
        if all(self.board[k] == 0 for k in range(0, 6)) or all(self.board[k] == 0 for k in range(7, 13)):
            sweep = {}
            for s_i in (0, 1):
                tot = sum(self.board[k] for k in self.side(s_i))
                for k in self.side(s_i):
                    self.board[k] = 0
                self.board[STORE[s_i]] += tot
                sweep[s_i] = tot
            self.last_move["sweep"] = sweep
            a, b = self.board[6], self.board[13]
            self.finished = True
            if a != b:
                self.winner = self.players[0] if a > b else self.players[1]
            else:
                self.draw = True
            return
        if not extra:
            self.turn_idx = 1 - self.turn_idx

    def auto_play(self):
        if self.finished:
            return
        me, best, bi = self.turn_idx, -999, []
        for i in self.legal():
            sim = MancalaGame.__new__(MancalaGame)
            sim.__dict__ = {k: (list(v) if isinstance(v, list) else v) for k, v in self.__dict__.items() if k != "rng"}
            sim.rng = self.rng
            sim._sow(i)
            sc = sim.board[STORE[me]] - sim.board[STORE[1 - me]] + (3 if sim.last_move["extra"] and not sim.finished else 0)
            if sc > best:
                best, bi = sc, [i]
            elif sc == best:
                bi.append(i)
        self._sow(self.rng.choice(bi))

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        return {
            "kind": "mancala",
            "players": [{"uid": self.players[0], "score": self.board[6]}, {"uid": self.players[1], "score": self.board[13]}],
            "turn": self.current(), "board": list(self.board), "last_move": self.last_move,
            "winner": self.winner, "draw": self.draw,
        }

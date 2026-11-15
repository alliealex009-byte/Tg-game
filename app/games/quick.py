"""Real-time duels: Tug of War (tap as fast as you can) and Reaction Duel (tap the instant it turns green)."""
from __future__ import annotations

import random
import time

from .base import BaseGame, GameError


class TugGame(BaseGame):
    name = "tugwar"
    min_players = max_players = 2
    LEAD, CAP, MAX_BATCH, RATE = 40, 700, 4, 13.0   # win lead, total-taps cap, taps per message, taps per second

    def __init__(self, players, rng=None, clock=time.monotonic):
        if len(players) != 2:
            raise ValueError("Tug of War needs exactly 2 players")
        self.rng, self.clock = rng or random.SystemRandom(), clock
        self.players = list(players)
        self.taps = {u: 0 for u in self.players}
        self.bucket = {u: (6.0, self.clock()) for u in self.players}
        self.armed_at = self.clock() + 3.0
        self.seq = 0
        self.winner, self.finished, self.draw = None, False, False

    def current(self):
        return None if self.finished else self.players[0]

    def rope(self):
        a, b = self.players
        return self.taps[a] - self.taps[b]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid not in self.taps:
            raise GameError("You are not playing")
        if msg.get("t") != "tap":
            raise GameError("Unknown action")
        now = self.clock()
        if now < self.armed_at:
            return
        n = msg.get("n", 1)
        n = n if isinstance(n, int) and not isinstance(n, bool) else 1
        n = max(1, min(self.MAX_BATCH, n))
        tokens, last = self.bucket[uid]
        tokens = min(6.0, tokens + (now - last) * self.RATE)
        use = min(n, int(tokens))
        self.bucket[uid] = (tokens - use, now)
        if use <= 0:
            return
        self.taps[uid] += use
        self.seq += 1
        self._check()

    def _check(self):
        r = self.rope()
        a, b = self.players
        if abs(r) >= self.LEAD:
            self.finished, self.winner = True, a if r > 0 else b
        elif sum(self.taps.values()) >= self.CAP:
            self._end_by_taps()

    def _end_by_taps(self):
        a, b = self.players
        self.finished = True
        if self.taps[a] == self.taps[b]:
            self.draw = True
        else:
            self.winner = a if self.taps[a] > self.taps[b] else b

    def auto_play(self):
        if not self.finished:
            self._end_by_taps()

    def remove_player(self, uid):
        if uid not in self.taps or self.finished:
            return
        self.finished, self.winner = True, next(u for u in self.players if u != uid)

    def public_state(self):
        a, b = self.players
        return {"kind": "tugwar", "lead": self.LEAD, "rope": self.rope(), "start_in": max(0.0, self.armed_at - self.clock()),
                "players": [{"uid": u, "taps": self.taps[u]} for u in self.players], "turn": self.current(), "seq": self.seq,
                "winner": self.winner, "draw": self.draw}


class ReactionGame(BaseGame):
    name = "reaction"
    min_players = max_players = 2
    WIN, MAX_ROUNDS = 2, 5

    def __init__(self, players, rng=None, clock=time.monotonic):
        if len(players) != 2:
            raise ValueError("Reaction Duel needs exactly 2 players")
        self.rng, self.clock = rng or random.SystemRandom(), clock
        self.players = list(players)
        self.score = {u: 0 for u in self.players}
        self.round = 0
        self.seq, self.last_round = 0, None
        self.winner, self.finished, self.draw = None, False, False
        self._open()

    def _open(self):
        self.go_in = round(self.rng.uniform(1.8, 4.5), 2)
        self.go_at = self.clock() + self.go_in
        self.times = {}   # uid -> reaction seconds, or "early" / "slow"

    def current(self):
        if self.finished:
            return None
        pend = [u for u in self.players if u not in self.times]
        return pend[0] if pend else self.players[0]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid not in self.score:
            raise GameError("You are not playing")
        if msg.get("t") != "tap":
            raise GameError("Unknown action")
        if uid in self.times:
            return
        now = self.clock()
        if msg.get("early") is True or now < self.go_at:
            self.times[uid] = "early"
        else:
            self.times[uid] = round(now - self.go_at, 3)
        if len(self.times) == 2:
            self._resolve()

    def _resolve(self):
        a, b = self.players
        ta, tb = self.times[a], self.times[b]
        win = None
        num = lambda x: isinstance(x, float)
        if num(ta) and num(tb):
            win = a if ta < tb else b if tb < ta else None
        elif num(ta):
            win = a
        elif num(tb):
            win = b
        if win:
            self.score[win] += 1
        self.round += 1
        self.seq += 1
        self.last_round = {"seq": self.seq, "round": self.round, "times": {str(a): ta, str(b): tb}, "winner": win}
        if max(self.score.values()) >= self.WIN or self.round >= self.MAX_ROUNDS:
            self.finished = True
            if self.score[a] != self.score[b]:
                self.winner = a if self.score[a] > self.score[b] else b
            else:
                self.draw = True
        else:
            self._open()

    def auto_play(self):
        if self.finished:
            return
        for u in self.players:
            self.times.setdefault(u, "slow")
        self._resolve()

    def remove_player(self, uid):
        if uid not in self.score or self.finished:
            return
        self.finished, self.winner = True, next(u for u in self.players if u != uid)

    def public_state(self):
        return {"kind": "reaction", "round": min(self.round + 1, self.MAX_ROUNDS), "win": self.WIN, "go_in": self.go_in,
                "players": [{"uid": u, "score": self.score[u], "tapped": u in self.times} for u in self.players],
                "turn": self.current(), "last_round": self.last_round, "winner": self.winner, "draw": self.draw}

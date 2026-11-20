"""MathBlitz: everyone solves the same sum at once. First correct answer wins the round. First to 4 round wins."""
from __future__ import annotations

import random
import time

from .base import BaseGame, GameError

WIN = 4
MAX_ROUNDS = 9


def make_question(rng, level):
    ops = ["+", "-", "×"]
    a, b = rng.randint(2, 12 + 6 * level), rng.randint(2, 9 + 4 * level)
    op = rng.choice(ops)
    if op == "×":
        a, b = rng.randint(2, 9 + level), rng.randint(2, 9)
    if rng.random() < 0.45 and level >= 1:
        c = rng.randint(2, 9)
        op2 = rng.choice(["+", "-"])
        ans = (a * b if op == "×" else a + b if op == "+" else a - b)
        ans = ans + c if op2 == "+" else ans - c
        return f"{a} {op} {b} {op2} {c}", ans
    return f"{a} {op} {b}", (a * b if op == "×" else a + b if op == "+" else a - b)


class MathBlitzGame(BaseGame):
    name = "mathblitz"
    min_players = 2
    max_players = 6
    phase_seconds = 18

    def __init__(self, players, rng=None, clock=time.monotonic):
        if not 2 <= len(players) <= 6:
            raise ValueError("MathBlitz needs 2-6 players")
        self.rng = rng or random.SystemRandom()
        self.clock = clock
        self.players = list(players)
        self.score = {u: 0 for u in self.players}
        self.round = 0
        self.phase_id = 0
        self.seq = 0
        self.last_round = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self._start_round()

    def _start_round(self):
        self.round += 1
        self.phase_id += 1
        self.question, self.answer = make_question(self.rng, min(3, self.round // 2))
        self.t0 = self.clock()
        self.bot_at = {u: self.t0 + self.rng.uniform(3.0, 8.0) for u in self.players if u < 0}

    def current(self):
        return None if self.finished else next((u for u in self.players if u > 0), self.players[0])

    def _bot_winner(self, before):
        c = [(t, u) for u, t in self.bot_at.items() if t <= before]
        return min(c)[1] if c else None

    def bot_due(self):
        return None if self.finished or not self.bot_at else max(0.0, min(self.bot_at.values()) - self.clock())

    def bot_event(self):
        bw = self._bot_winner(self.clock())
        if bw is not None and not self.finished:
            self._end_round(bw)

    def _end_round(self, winner):
        if winner is not None:
            self.score[winner] += 1
        self.seq += 1
        self.last_round = {"seq": self.seq, "round": self.round, "winner": winner, "answer": self.answer, "q": self.question}
        top = max(self.score.values())
        if top >= WIN or self.round >= MAX_ROUNDS:
            self.finished = True
            lead = [u for u in self.players if self.score[u] == top]
            if len(lead) == 1:
                self.winner = lead[0]
            else:
                self.draw = True
            return
        self._start_round()

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The match is over")
        if uid not in self.players:
            raise GameError("You are not in this match")
        if msg.get("t") != "answer":
            raise GameError("Unknown action")
        v = msg.get("value")
        if isinstance(v, bool) or not isinstance(v, int):
            raise GameError("Enter a whole number")
        now = self.clock()
        bw = self._bot_winner(now)
        if bw is not None:
            return self._end_round(bw)
        if v != self.answer:
            raise GameError("Wrong answer")
        if now - self.t0 < 0.3:
            raise GameError("Too fast!")
        self._end_round(uid)

    def auto_play(self):
        if self.finished:
            return
        self._end_round(self._bot_winner(float("inf")))

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.players.remove(uid)
        self.score.pop(uid, None)
        self.bot_at.pop(uid, None)
        if len(self.players) < 2 or all(u < 0 for u in self.players):
            self.finished = True
            self.winner = self.players[0] if self.players else None

    def public_state(self):
        return {"kind": "mathblitz", "q": self.question, "round": self.round, "win": WIN,
                "players": [{"uid": u, "score": self.score[u]} for u in self.players],
                "turn": self.current(), "last_round": self.last_round, "winner": self.winner, "draw": self.draw}

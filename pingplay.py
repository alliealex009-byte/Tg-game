"""PingPlay: reaction duel. Wait for GO, then tap. Tapping early is a false start (you're out of that round).
Fastest tap wins the round; first to 3 wins. The server judges timing, not your phone."""
from __future__ import annotations

import random
import time

from .base import BaseGame, GameError

WIN = 3
MAX_ROUNDS = 9


class PingPlayGame(BaseGame):
    name = "pingplay"
    min_players = 2
    max_players = 4
    phase_seconds = 9

    def __init__(self, players, rng=None, clock=time.monotonic):
        if not 2 <= len(players) <= 4:
            raise ValueError("PingPlay needs 2-4 players")
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
        self._start()

    def _start(self):
        self.round += 1
        self.phase_id += 1
        self.go_at = self.clock() + self.rng.uniform(2.0, 5.0)
        self.fouled = set()
        self.bot_at = {u: self.go_at + self.rng.uniform(0.28, 0.65) for u in self.players if u < 0}

    def current(self):
        return None if self.finished else next((u for u in self.players if u > 0), self.players[0])

    def _bot_winner(self, before):
        c = [(t, u) for u, t in self.bot_at.items() if t <= before]
        return min(c)[1] if c else None

    def _end_round(self, winner, why):
        if winner is not None:
            self.score[winner] += 1
        self.seq += 1
        self.last_round = {"seq": self.seq, "round": self.round, "winner": winner, "why": why}
        top = max(self.score.values())
        if top >= WIN or self.round >= MAX_ROUNDS:
            self.finished = True
            lead = [u for u in self.players if self.score[u] == top]
            if len(lead) == 1:
                self.winner = lead[0]
            else:
                self.draw = True
            return
        self._start()

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The match is over")
        if uid not in self.players:
            raise GameError("You are not in this match")
        if msg.get("t") != "tap":
            raise GameError("Unknown action")
        if uid in self.fouled:
            return
        now = self.clock()
        if now < self.go_at:
            self.fouled.add(uid)
            self.seq += 1
            self.last_round = {"seq": self.seq, "round": self.round, "winner": None, "why": "foul", "foul": uid}
            humans = [u for u in self.players if u > 0 and u not in self.fouled]
            if not humans:
                self._end_round(self._bot_winner(float("inf")), "all fouled")
            return
        bw = self._bot_winner(now)
        self._end_round(bw if bw is not None else uid, "fastest")

    def bot_due(self):
        return None if self.finished or not self.bot_at else max(0.0, min(self.bot_at.values()) - self.clock())

    def bot_event(self):
        bw = self._bot_winner(self.clock())
        if bw is not None and not self.finished:
            self._end_round(bw, "fastest")

    def auto_play(self):
        if self.finished:
            return
        self._end_round(self._bot_winner(float("inf")), "timeout")

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.players.remove(uid)
        self.score.pop(uid, None)
        self.bot_at.pop(uid, None)
        self.fouled.discard(uid)
        if len(self.players) < 2 or all(u < 0 for u in self.players):
            self.finished = True
            self.winner = self.players[0] if self.players else None

    def public_state(self):
        now = self.clock()
        return {"kind": "pingplay", "round": self.round, "win": WIN, "go_in": round(max(0.0, self.go_at - now), 2),
                "players": [{"uid": u, "score": self.score[u], "foul": u in self.fouled} for u in self.players],
                "turn": self.current(), "last_round": self.last_round, "winner": self.winner, "draw": self.draw}

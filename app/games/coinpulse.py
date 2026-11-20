"""CoinPulse: each round a pot appears. Everyone secretly picks GRAB or WAIT.
Exactly one grabber takes the whole pot. Two or more grabbers clash and each lose 5. Waiters earn 2. If nobody grabs, the pot grows.
Most points after 8 rounds wins."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

ROUNDS = 8


class CoinPulseGame(BaseGame):
    name = "coinpulse"
    min_players = 2
    max_players = 6
    phase_seconds = 8

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 6:
            raise ValueError("CoinPulse needs 2-6 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.score = {u: 0 for u in self.players}
        self.picks = {}
        self.round = 0
        self.carry = 0
        self.phase_id = 0
        self.seq = 0
        self.last_round = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self._new_pot()
        self._bots()

    def _new_pot(self):
        self.pot = self.carry + self.rng.randint(8, 20)
        self.carry = 0

    def _pending(self):
        return [u for u in self.players if u not in self.picks]

    def current(self):
        if self.finished:
            return None
        p = self._pending()
        return ([u for u in p if u > 0] or p or [None])[0]

    def _bot_pick(self, u):
        n = len(self.players)
        p = min(0.85, (1.0 / n) * (0.9 + self.pot / 25))
        return "grab" if self.rng.random() < p else "wait"

    def _bots(self):
        while not self.finished:
            for u in self._pending():
                if u < 0:
                    self.picks[u] = self._bot_pick(u)
            if self._pending():
                return
            self._resolve()

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid not in self.players:
            raise GameError("You are not in this game")
        if msg.get("t") != "pick" or msg.get("pick") not in ("grab", "wait"):
            raise GameError("Pick grab or wait")
        if uid in self.picks:
            raise GameError("Already locked in")
        self.picks[uid] = msg["pick"]
        self._bots()

    def auto_play(self):
        if self.finished:
            return
        for u in self._pending():
            self.picks[u] = self._bot_pick(u) if u < 0 else "wait"
        self._resolve()
        self._bots()

    def _resolve(self):
        grabbers = [u for u in self.players if self.picks.get(u) == "grab"]
        pot = self.pot
        if len(grabbers) == 1:
            self.score[grabbers[0]] += pot
            out = "take"
        elif len(grabbers) > 1:
            for u in grabbers:
                self.score[u] -= 5
            self.carry = pot
            out = "clash"
        else:
            self.carry = pot
            out = "grow"
        for u in self.players:
            if self.picks.get(u) == "wait":
                self.score[u] += 2
        self.round += 1
        self.seq += 1
        self.phase_id += 1
        self.last_round = {"seq": self.seq, "round": self.round, "picks": dict(self.picks), "pot": pot, "result": out,
                           "taker": grabbers[0] if out == "take" else None}
        self.picks = {}
        if self.round >= ROUNDS:
            self.finished = True
            top = max(self.score.values())
            lead = [u for u in self.players if self.score[u] == top]
            if len(lead) == 1:
                self.winner = lead[0]
            else:
                self.draw = True
            return
        self._new_pot()

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.players.remove(uid)
        self.score.pop(uid, None)
        self.picks.pop(uid, None)
        if len(self.players) < 2 or all(u < 0 for u in self.players):
            self.finished = True
            self.winner = self.players[0] if self.players else None
            return
        self._bots()

    def public_state(self):
        return {"kind": "coinpulse", "round": self.round, "rounds": ROUNDS, "pot": self.pot,
                "players": [{"uid": u, "score": self.score[u]} for u in self.players],
                "picked": {u: u in self.picks for u in self.players}, "turn": self.current(),
                "last_round": self.last_round, "winner": self.winner, "draw": self.draw}

"""SquadDuel: two squads of 5 hidden units (Knight beats Archer, Archer beats Mage, Mage beats Knight).
Each round both secretly send one unit. Winner of the clash scores a point; same type is a tie. Most points after 5 rounds wins."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

UNITS = ("knight", "archer", "mage")
BEATS = {"knight": "archer", "archer": "mage", "mage": "knight"}
SQUAD = 5


class SquadDuelGame(BaseGame):
    name = "squadduel"
    min_players = 2
    max_players = 2
    phase_seconds = 15

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("SquadDuel needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.hands = {u: sorted(self.rng.choices(UNITS, k=SQUAD)) for u in self.players}
        self.score = {u: 0 for u in self.players}
        self.picks = {}
        self.round = 0
        self.phase_id = 0
        self.seq = 0
        self.last_round = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self._bots()

    def _pending(self):
        return [u for u in self.players if u not in self.picks]

    def current(self):
        if self.finished:
            return None
        p = self._pending()
        return ([u for u in p if u > 0] or p or [None])[0]

    def _bots(self):
        while not self.finished:
            for u in self._pending():
                if u < 0:
                    self.picks[u] = self.rng.choice(self.hands[u])
            if self._pending():
                return
            self._resolve()

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The duel is over")
        if uid not in self.players:
            raise GameError("You are not in this duel")
        if msg.get("t") != "send" or msg.get("unit") not in UNITS:
            raise GameError("Pick knight, archer or mage")
        if uid in self.picks:
            raise GameError("Already locked in")
        if msg["unit"] not in self.hands[uid]:
            raise GameError("You have no such unit left")
        self.picks[uid] = msg["unit"]
        self._bots()

    def auto_play(self):
        if self.finished:
            return
        for u in self._pending():
            self.picks[u] = self.rng.choice(self.hands[u])
        self._resolve()
        self._bots()

    def _resolve(self):
        a, b = self.players
        ua, ub = self.picks[a], self.picks[b]
        self.hands[a].remove(ua)
        self.hands[b].remove(ub)
        w = a if BEATS[ua] == ub else b if BEATS[ub] == ua else None
        if w is not None:
            self.score[w] += 1
        self.round += 1
        self.seq += 1
        self.phase_id += 1
        self.last_round = {"seq": self.seq, "round": self.round, "units": {a: ua, b: ub}, "winner": w}
        self.picks = {}
        if self.round >= SQUAD:
            self.finished = True
            if self.score[a] != self.score[b]:
                self.winner = a if self.score[a] > self.score[b] else b
            else:
                self.draw = True

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        return {"kind": "squadduel", "round": self.round, "total": SQUAD,
                "players": [{"uid": u, "score": self.score[u], "left": len(self.hands[u])} for u in self.players],
                "picked": {u: u in self.picks for u in self.players}, "turn": self.current(),
                "last_round": self.last_round, "winner": self.winner, "draw": self.draw, "hand": None}

    def view(self, uid):
        s = self.public_state()
        if uid in self.hands:
            s["hand"] = list(self.hands[uid])
        return s

"""PartyDrop (hot potato): pass the party bomb around. Nobody knows how many passes are left on the fuse.
Whoever is holding it when it goes off is out. Last player standing wins."""
from __future__ import annotations

import random

from .base import BaseGame, GameError


class PartyDropGame(BaseGame):
    name = "partydrop"
    min_players = 2
    max_players = 6

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 6:
            raise ValueError("PartyDrop needs 2-6 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.alive = list(players)
        self.out = []
        self.seq = 0
        self.last_event = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self.passes = 0
        self._arm()

    def _arm(self):
        self.fuse = self.rng.randint(3, 4 + 2 * len(self.alive))
        self.holder = self.rng.choice(self.alive)
        self.passes = 0

    def current(self):
        return None if self.finished else self.holder

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The party is over")
        if uid != self.holder:
            raise GameError("You don't have the bomb")
        if msg.get("t") != "pass":
            raise GameError("Unknown action")
        to = msg.get("to")
        if isinstance(to, bool) or to not in self.alive or to == uid:
            raise GameError("Pick another player still in")
        self._pass(uid, to)

    def _pass(self, uid, to):
        self.fuse -= 1
        self.passes += 1
        self.seq += 1
        if self.fuse <= 0:
            self.alive.remove(to)
            self.out.append(to)
            self.last_event = {"seq": self.seq, "from": uid, "to": to, "boom": True}
            if len(self.alive) == 1:
                self.finished, self.winner = True, self.alive[0]
                return
            self._arm()
        else:
            self.last_event = {"seq": self.seq, "from": uid, "to": to, "boom": False}
            self.holder = to

    def auto_play(self):
        if self.finished:
            return
        self._pass(self.holder, self.rng.choice([u for u in self.alive if u != self.holder]))

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        if uid in self.alive:
            self.alive.remove(uid)
            self.out.append(uid)
        if len(self.alive) <= 1 or all(u < 0 for u in self.alive):
            self.finished = True
            self.winner = self.alive[0] if self.alive else None
            return
        if self.holder == uid:
            self._arm()

    def public_state(self):
        return {"kind": "partydrop", "players": [{"uid": u, "out": u in self.out} for u in self.players],
                "holder": self.holder, "turn": self.current(), "passes": self.passes, "last_event": self.last_event,
                "winner": self.winner, "draw": self.draw}

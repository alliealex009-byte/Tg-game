"""Car Racing: 2-4 cars race 30 tiles. Each round everyone secretly picks Cruise / Boost / Nitro at once.
Cruise +2 and cools the engine, Boost +3 (+1 heat), Nitro +5 (+2 heat). Heat 4+ = engine stall (skip next round, heat reset).
Oil patches on the track cost 2 tiles. Same tile = bump, the car that picked the slower gear loses 1."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

GEARS = {"cruise": (2, -1), "boost": (3, 1), "nitro": (5, 2)}
LENGTH = 30


class RaceGame(BaseGame):
    name = "race"
    min_players = 2
    max_players = 4
    phase_seconds = 8

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("Racing needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.pos = {u: 0 for u in self.players}
        self.heat = {u: 0 for u in self.players}
        self.stalled = {u: False for u in self.players}
        self.oil = sorted(self.rng.sample(range(4, LENGTH - 2), 5))
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

    def _bot_pick(self, u):
        h = self.heat[u]
        w = {"cruise": 2, "boost": 3, "nitro": 2}
        if h >= 3:
            w = {"cruise": 6, "boost": 1, "nitro": 0}
        elif h == 2:
            w["nitro"] = 1
        lead = max(self.pos.values()) - self.pos[u]
        if lead >= 6 and h <= 1:
            w["nitro"] += 3
        opts = [k for k, v in w.items() if v > 0]
        return self.rng.choices(opts, weights=[w[k] for k in opts])[0]

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
            raise GameError("The race is over")
        if uid not in self.players:
            raise GameError("You are not in this race")
        if msg.get("t") != "gear" or msg.get("gear") not in GEARS:
            raise GameError("Pick cruise, boost or nitro")
        if uid in self.picks:
            raise GameError("Already locked in")
        self.picks[uid] = msg["gear"]
        self._bots()

    def auto_play(self):
        if self.finished:
            return
        for u in self._pending():
            self.picks[u] = self._bot_pick(u) if u < 0 else self.rng.choice(["cruise", "boost"])
        self._resolve()
        self._bots()

    def _resolve(self):
        moves, events = {}, []
        for u in self.players:
            if self.stalled[u]:
                self.stalled[u] = False
                self.heat[u] = 0
                moves[u] = {"gear": "stall", "gain": 0}
                events.append({"uid": u, "e": "stall"})
                continue
            g = self.picks.get(u, "cruise")
            gain, dh = GEARS[g]
            self.heat[u] = max(0, self.heat[u] + dh)
            moves[u] = {"gear": g, "gain": gain}
            if self.heat[u] >= 4:
                self.stalled[u] = True
                events.append({"uid": u, "e": "overheat"})
        for u in self.players:
            self.pos[u] = min(LENGTH, self.pos[u] + moves[u]["gain"])
            if self.pos[u] in self.oil and self.pos[u] < LENGTH:
                self.pos[u] = max(0, self.pos[u] - 2)
                events.append({"uid": u, "e": "oil"})
        by = {}
        for u in self.players:
            by.setdefault(self.pos[u], []).append(u)
        for p, us in by.items():
            if len(us) > 1 and 0 < p < LENGTH:
                slow = min(us, key=lambda x: moves[x]["gain"])
                if len({moves[x]["gain"] for x in us}) > 1:
                    self.pos[slow] = max(0, self.pos[slow] - 1)
                    events.append({"uid": slow, "e": "bump"})
        self.round += 1
        self.seq += 1
        self.phase_id += 1
        self.last_round = {"seq": self.seq, "round": self.round, "moves": moves, "events": events, "pos": dict(self.pos)}
        self.picks = {}
        top = max(self.pos.values())
        if top >= LENGTH:
            lead = [u for u in self.players if self.pos[u] == top]
            self.finished = True
            if len(lead) == 1:
                self.winner = lead[0]
            else:
                self.draw = True
        elif self.round >= 40:
            self.finished = True
            lead = [u for u in self.players if self.pos[u] == top]
            self.winner = lead[0] if len(lead) == 1 else None
            self.draw = len(lead) > 1

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        left = [u for u in self.players if u != uid]
        self.players = left if len(left) >= 1 else self.players
        for d in (self.pos, self.heat, self.stalled, self.picks):
            d.pop(uid, None)
        if len(self.players) < 2 or all(u < 0 for u in self.players):
            self.finished = True
            self.winner = self.players[0] if self.players else None
            return
        self._bots()

    def public_state(self):
        return {"kind": "race", "length": LENGTH, "oil": self.oil, "round": self.round,
                "players": [{"uid": u, "pos": self.pos[u], "heat": self.heat[u], "stalled": self.stalled[u]} for u in self.players],
                "picked": {u: u in self.picks for u in self.players}, "turn": self.current(),
                "last_round": self.last_round, "winner": self.winner, "draw": self.draw}

"""Penalty Shootout: 5 kicks each, then sudden death. Every kick the shooter picks a corner (left, centre, right)
while the keeper dives at the same time. Same side = saved, otherwise GOAL."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

DIRS = ("l", "c", "r")
KICKS = 5


class PenaltyGame(BaseGame):
    name = "penalty"
    min_players = 2
    max_players = 2
    phase_seconds = 10

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Penalty Shootout needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.goals = {u: 0 for u in self.players}
        self.taken = {u: 0 for u in self.players}
        self.kick = 0                       # 0.. alternating, players[kick % 2] shoots
        self.picks = {}
        self.phase_id = 0
        self.seq = 0
        self.last_kick = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self._bots()

    @property
    def shooter(self):
        return self.players[self.kick % 2]

    @property
    def keeper(self):
        return self.players[(self.kick + 1) % 2]

    def _pending(self):
        return [] if self.finished else [u for u in (self.shooter, self.keeper) if u not in self.picks]

    def current(self):
        if self.finished:
            return None
        p = self._pending()
        return ([u for u in p if u > 0] or p or [None])[0]

    def _bots(self):
        while not self.finished:
            for u in self._pending():
                if u < 0:
                    self.picks[u] = self.rng.choice(DIRS)
            if self._pending():
                return
            self._resolve()

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The shootout is over")
        if uid not in self.players:
            raise GameError("You are not in this shootout")
        if msg.get("t") != "dir" or msg.get("dir") not in DIRS:
            raise GameError("Pick left, centre or right")
        if uid in self.picks:
            raise GameError("Already picked")
        self.picks[uid] = msg["dir"]
        self._bots()

    def auto_play(self):
        if self.finished:
            return
        for u in self._pending():
            self.picks[u] = self.rng.choice(DIRS)
        self._resolve()
        self._bots()

    def _decided(self):
        a, b = self.players
        ta, tb = self.taken[a], self.taken[b]
        if ta <= KICKS and tb <= KICKS and not (ta == KICKS and tb == KICKS):
            # regulation: stop as soon as one side can no longer catch up
            if self.goals[a] > self.goals[b] + (KICKS - tb) or self.goals[b] > self.goals[a] + (KICKS - ta):
                return True
            return False
        return ta == tb and ta >= KICKS and self.goals[a] != self.goals[b]

    def _resolve(self):
        s, k = self.shooter, self.keeper
        shot, dive = self.picks[s], self.picks[k]
        goal = shot != dive
        self.taken[s] += 1
        if goal:
            self.goals[s] += 1
        self.kick += 1
        self.seq += 1
        self.phase_id += 1
        self.last_kick = {"seq": self.seq, "shooter": s, "keeper": k, "shot": shot, "dive": dive, "goal": goal, "n": self.kick}
        self.picks = {}
        a, b = self.players
        if self._decided():
            self.finished = True
            self.winner = a if self.goals[a] > self.goals[b] else b
        elif self.kick >= 30:
            self.finished = True
            self.draw = self.goals[a] == self.goals[b]
            if not self.draw:
                self.winner = a if self.goals[a] > self.goals[b] else b

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        return {"kind": "penalty", "players": [{"uid": u, "goals": self.goals[u], "taken": self.taken[u]} for u in self.players],
                "shooter": self.shooter, "keeper": self.keeper, "kicks": KICKS, "kick": self.kick,
                "picked": {u: u in self.picks for u in self.players}, "turn": self.current(),
                "last_kick": self.last_kick, "winner": self.winner, "draw": self.draw}

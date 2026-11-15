"""Boxing: 2 fighters pick a move each round (hidden until both are in). Jab, hook and uppercut cost stamina;
block soaks damage and recovers stamina; dodge avoids jabs and hooks and counters, but uppercuts crash through it."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

DMG = {"jab": 8, "hook": 15, "upper": 24}
COST = {"jab": 1, "hook": 2, "upper": 3, "block": 0, "dodge": 1}
MOVES = list(COST)
MAX_ROUNDS = 12
MAX_STA = 10


class BoxingGame(BaseGame):
    name = "boxing"
    min_players = max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Boxing needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.hp = {u: 100 for u in self.players}
        self.sta = {u: MAX_STA for u in self.players}
        self.picks = {}
        self.round = 0
        self.seq, self.last_round = 0, None
        self.winner, self.finished, self.draw = None, False, False

    def other(self, u):
        return self.players[1] if u == self.players[0] else self.players[0]

    def current(self):
        if self.finished:
            return None
        pend = [u for u in self.players if u not in self.picks]
        humans = [u for u in pend if u > 0]
        return (humans or pend)[0]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The fight is over")
        if uid not in self.hp:
            raise GameError("You are not fighting")
        mv = msg.get("move")
        if msg.get("t") != "pick" or mv not in COST:
            raise GameError("Pick a move")
        if uid in self.picks:
            raise GameError("Waiting for your opponent")
        if COST[mv] > self.sta[uid]:
            raise GameError("Not enough stamina for that move")
        self.picks[uid] = mv
        if len(self.picks) == 2:
            self._resolve()

    def _resolve(self):
        a, b = self.players
        pa, pb = self.picks[a], self.picks[b]
        dmg, tags = {a: 0, b: 0}, {a: [], b: []}

        def attack(att, dfn, mv, other_mv):
            if mv not in DMG:
                return
            d = DMG[mv]
            if mv == "jab" and other_mv == "upper":
                tags[att].append("stuffed")
                return
            if other_mv == "block":
                d = round(d * (0.6 if mv == "upper" else 0.35))
                tags[dfn].append("blocked")
            elif other_mv == "dodge" and mv != "upper":
                tags[dfn].append("dodged")
                dmg[att] += 6
                tags[att].append("countered")
                return
            if self.rng.random() < 0.1:
                d = round(d * 1.5)
                tags[att].append("crit")
            dmg[dfn] += d
            tags[dfn].append("hit")
        attack(a, b, pa, pb)
        attack(b, a, pb, pa)
        for u, mv in ((a, pa), (b, pb)):
            self.sta[u] = min(MAX_STA, self.sta[u] - COST[mv] + (2 if mv == "block" else 0) + 1)
            self.hp[u] = max(0, self.hp[u] - dmg[u])
        self.round += 1
        self.seq += 1
        self.last_round = {"seq": self.seq, "round": self.round, "picks": {str(a): pa, str(b): pb}, "dmg": {str(a): dmg[a], str(b): dmg[b]},
                           "tags": {str(a): tags[a], str(b): tags[b]}, "hp": {str(a): self.hp[a], str(b): self.hp[b]}}
        self.picks = {}
        ko = [u for u in self.players if self.hp[u] <= 0]
        if ko or self.round >= MAX_ROUNDS:
            self.finished = True
            if len(ko) == 1:
                self.winner = self.other(ko[0])
                self.last_round["ko"] = True
            elif self.hp[a] != self.hp[b]:
                self.winner = a if self.hp[a] > self.hp[b] else b
            else:
                self.draw = True

    def auto_play(self):
        if self.finished:
            return
        for u in self.players:
            if u in self.picks:
                continue
            ok = [m for m in MOVES if COST[m] <= self.sta[u]]
            w = [{"jab": 3, "hook": 2.2, "upper": 1.6, "block": 2.2, "dodge": 1.6}[m] * (1.5 if m in ("block",) and self.sta[u] < 4 else 1) for m in ok]
            if u > 0 and self.picks:  # AFK human: play safe
                self.picks[u] = "block"
            else:
                self.picks[u] = self.rng.choices(ok, w)[0]
        if len(self.picks) == 2:
            self._resolve()

    def remove_player(self, uid):
        if uid not in self.hp or self.finished:
            return
        self.finished, self.winner = True, self.other(uid)

    def public_state(self):
        return {"kind": "boxing", "round": min(self.round + 1, MAX_ROUNDS), "max_rounds": MAX_ROUNDS,
                "players": [{"uid": u, "hp": self.hp[u], "sta": self.sta[u], "picked": u in self.picks} for u in self.players],
                "turn": self.current(), "last_round": self.last_round, "mine": None, "winner": self.winner, "draw": self.draw}

    def view(self, uid):
        st = self.public_state()
        st["mine"] = self.picks.get(uid)
        return st

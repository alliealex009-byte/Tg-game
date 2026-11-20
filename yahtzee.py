"""Yahtzee: 2-4 players, 13 rounds each. Roll five dice up to three times (keep any you like), then score one category."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

CATS = ["ones", "twos", "threes", "fours", "fives", "sixes", "three", "four", "full", "small", "large", "yahtzee", "chance"]


def points(cat, dice):
    c = [dice.count(i) for i in range(1, 7)]
    s = sum(dice)
    if cat in CATS[:6]:
        i = CATS.index(cat) + 1
        return i * c[i - 1]
    if cat == "three":
        return s if max(c) >= 3 else 0
    if cat == "four":
        return s if max(c) >= 4 else 0
    if cat == "full":
        return 25 if sorted(x for x in c if x) == [2, 3] or max(c) == 5 else 0
    run = set(dice)
    if cat == "small":
        return 30 if any(set(range(a, a + 4)) <= run for a in (1, 2, 3)) else 0
    if cat == "large":
        return 40 if run in ({1, 2, 3, 4, 5}, {2, 3, 4, 5, 6}) else 0
    if cat == "yahtzee":
        return 50 if max(c) == 5 else 0
    if cat == "chance":
        return s
    raise ValueError(cat)


class YahtzeeGame(BaseGame):
    name = "yahtzee"
    min_players = 2
    max_players = 4

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("Yahtzee needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.card = {u: {} for u in self.players}
        self.turn_idx = 0
        self.dice = [0] * 5
        self.rolls = 0
        self.seq = 0
        self.last_move = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def total(self, u):
        c = self.card[u]
        up = sum(c.get(k, 0) for k in CATS[:6])
        return sum(c.values()) + (35 if up >= 63 else 0)

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        t = msg.get("t")
        if t == "roll":
            if self.rolls >= 3:
                raise GameError("No rolls left — pick a category")
            hold = msg.get("hold") or [False] * 5
            if not (isinstance(hold, list) and len(hold) == 5):
                raise GameError("Bad hold")
            if self.rolls == 0:
                hold = [False] * 5
            for i in range(5):
                if not hold[i]:
                    self.dice[i] = self.rng.randint(1, 6)
            self.rolls += 1
            self.seq += 1
            self.last_move = {"seq": self.seq, "uid": uid, "kind": "roll", "held": [bool(h) for h in hold]}
        elif t == "score":
            cat = msg.get("cat")
            if cat not in CATS:
                raise GameError("Unknown category")
            if self.rolls == 0:
                raise GameError("Roll first")
            if cat in self.card[uid]:
                raise GameError("Already used")
            self._score(uid, cat)
        else:
            raise GameError("Unknown action")

    def _score(self, uid, cat):
        p = points(cat, self.dice)
        self.card[uid][cat] = p
        self.seq += 1
        self.last_move = {"seq": self.seq, "uid": uid, "kind": "score", "cat": cat, "pts": p}
        self.rolls = 0
        self.dice = [0] * 5
        if all(len(self.card[u]) == len(CATS) for u in self.players):
            self.finished = True
            tot = {u: self.total(u) for u in self.players}
            top = max(tot.values())
            lead = [u for u in self.players if tot[u] == top]
            if len(lead) == 1:
                self.winner = lead[0]
            else:
                self.draw = True
            return
        self.turn_idx = (self.turn_idx + 1) % len(self.players)

    def auto_play(self):
        if self.finished:
            return
        u = self.current()
        if self.rolls == 0:
            self.handle(u, {"t": "roll"})
        # bots (and AFK humans) re-roll once keeping the most common value, then take the best open category
        if self.rolls < 3 and u < 0:
            best = max(range(1, 7), key=lambda v: (self.dice.count(v), v))
            self.handle(u, {"t": "roll", "hold": [d == best for d in self.dice]})
        open_cats = [c for c in CATS if c not in self.card[u]]
        cat = max(open_cats, key=lambda c: (points(c, self.dice) - (0.5 * sum(self.dice) if c == "chance" else 0), c == "yahtzee"))
        self._score(u, cat)

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        cur = self.current()
        i = self.players.index(uid)
        self.players.remove(uid)
        self.card.pop(uid, None)
        if len(self.players) < 2 or all(u < 0 for u in self.players):
            self.finished = True
            self.winner = self.players[0] if self.players else None
            return
        self.turn_idx = self.players.index(cur) if cur in self.players else i % len(self.players)
        self.rolls, self.dice = 0, [0] * 5

    def public_state(self):
        cur = self.current()
        return {"kind": "yahtzee", "dice": self.dice, "rolls": self.rolls, "turn": cur, "last_move": self.last_move,
                "players": [{"uid": u, "total": self.total(u), "card": self.card[u]} for u in self.players],
                "preview": {c: points(c, self.dice) for c in CATS if self.rolls and c not in self.card.get(cur, {})} if cur else {},
                "winner": self.winner, "draw": self.draw}

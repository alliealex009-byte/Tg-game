"""Liar's Dice, 2-4 players, 5 dice each. Bid a quantity of a face, or call 'liar'. Lose a die when wrong; last one standing wins."""
from __future__ import annotations

import random

from .base import BaseGame, GameError


class LiarsGame(BaseGame):
    name = "liars"
    min_players, max_players = 2, 4

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("Liar's Dice needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.count = {u: 5 for u in self.players}
        self.left = set()
        self.turn_idx = 0
        self.bid = None            # {"uid","qty","face"}
        self.seq, self.last_round, self.last_bid = 0, None, None
        self.winner, self.finished, self.draw = None, False, False
        self._roll()

    def _roll(self):
        self.dice = {u: sorted(self.rng.randint(1, 6) for _ in range(self.count[u])) for u in self.players}
        self.bid = None

    def alive(self):
        return [u for u in self.players if self.count[u] > 0 and u not in self.left]

    def total(self):
        return sum(self.count[u] for u in self.alive())

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def _next(self):
        for _ in range(len(self.players)):
            self.turn_idx = (self.turn_idx + 1) % len(self.players)
            if self.players[self.turn_idx] in self.alive():
                return

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        t = msg.get("t")
        if t == "bid":
            q, f = msg.get("qty"), msg.get("face")
            if any(isinstance(x, bool) or not isinstance(x, int) for x in (q, f)) or not 1 <= f <= 6 or not 1 <= q <= self.total():
                raise GameError("Invalid bid")
            if self.bid and not (q > self.bid["qty"] or (q == self.bid["qty"] and f > self.bid["face"])):
                raise GameError("Raise the quantity, or keep it and raise the face")
            self.bid = {"uid": uid, "qty": q, "face": f}
            self.seq += 1
            self.last_bid = dict(self.bid, seq=self.seq)
            self._next()
        elif t == "liar":
            if not self.bid:
                raise GameError("Nothing to challenge yet")
            self._call(uid)
        else:
            raise GameError("Unknown action")

    def _call(self, caller):
        b = self.bid
        actual = sum(1 for u in self.alive() for d in self.dice[u] if d == b["face"])
        bidder_right = actual >= b["qty"]
        loser = caller if bidder_right else b["uid"]
        self.count[loser] -= 1
        self.seq += 1
        self.last_round = {"seq": self.seq, "caller": caller, "bid": dict(b), "actual": actual, "loser": loser,
                           "dice": {str(u): self.dice[u] for u in self.alive() + ([loser] if self.count[loser] == 0 else [])}}
        al = self.alive()
        if len(al) <= 1:
            self.finished, self.winner = True, al[0] if al else None
            return
        self.turn_idx = self.players.index(loser) if loser in al else self.players.index(b["uid"] if b["uid"] in al else al[0])
        if self.players[self.turn_idx] not in al:
            self._next()
        self._roll()
        self.last_bid = None

    def auto_play(self):
        if self.finished:
            return
        uid = self.current()
        mine = self.dice[uid]
        others = self.total() - len(mine)
        if self.bid:
            f, q = self.bid["face"], self.bid["qty"]
            exp = sum(1 for d in mine if d == f) + others / 6
            if q > exp + 1.2 + self.rng.random() * 0.8:
                return self.handle(uid, {"t": "liar"})
        best = max(range(1, 7), key=lambda f: sum(1 for d in mine if d == f) + self.rng.random() * 0.5)
        q = max(1, round(sum(1 for d in mine if d == best) + others / 6))
        cand = [(q + k, f) for k in range(0, 3) for f in (best, *range(1, 7))]
        for qq, ff in cand:
            if qq <= self.total() and (not self.bid or qq > self.bid["qty"] or (qq == self.bid["qty"] and ff > self.bid["face"])):
                return self.handle(uid, {"t": "bid", "qty": qq, "face": ff})
        self.handle(uid, {"t": "liar"})

    def remove_player(self, uid):
        if uid not in self.count or uid in self.left or self.finished:
            return
        was = self.current() == uid
        self.left.add(uid)
        self.count[uid] = 0
        act = self.alive()
        if len(act) <= 1:
            self.finished, self.winner = True, act[0] if act else None
        elif was:
            self.bid = None if self.bid and self.bid["uid"] == uid else self.bid
            self._next()

    def public_state(self):
        return {"kind": "liars", "players": [{"uid": u, "count": self.count[u], "left": u in self.left} for u in self.players],
                "turn": self.current(), "bid": self.bid, "total": self.total(), "last_round": self.last_round,
                "last_bid": self.last_bid, "dice": None, "winner": self.winner, "draw": self.draw}

    def view(self, uid):
        st = self.public_state()
        if uid in self.dice and self.count.get(uid, 0) > 0:
            st["dice"] = self.dice[uid]
        return st

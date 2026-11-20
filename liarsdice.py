"""Liar's Dice (2-5 players). Everyone has 5 hidden dice. Bid how many dice of a face are on the whole table
(ones are NOT wild), or call the previous bidder a liar. The loser of a challenge loses a die; last player with dice wins."""
from __future__ import annotations

import math
import random

from .base import BaseGame, GameError

START_DICE = 5


class LiarsDiceGame(BaseGame):
    name = "liarsdice"
    min_players = 2
    max_players = 5

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 5:
            raise ValueError("Liar's Dice needs 2-5 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.count = {u: START_DICE for u in self.players}
        self.left = set()
        self.dice = {}
        self.bid = None            # {"uid","q","face"}
        self.round = 0
        self.turn_idx = 0
        self.seq = 0
        self.last_bid = None
        self.last_reveal = None
        self.winner = None
        self.finished = False
        self.draw = False
        self._roll_all()

    # ---------- helpers ----------
    def alive(self):
        return [u for u in self.players if self.count[u] > 0 and u not in self.left]

    def total(self):
        return sum(self.count[u] for u in self.alive())

    def _roll_all(self):
        self.round += 1
        self.bid = None
        self.dice = {u: sorted(self.rng.randint(1, 6) for _ in range(self.count[u])) if u in self.alive() else [] for u in self.players}

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def _advance(self):
        for _ in range(len(self.players)):
            self.turn_idx = (self.turn_idx + 1) % len(self.players)
            if self.players[self.turn_idx] in self.alive():
                return

    def valid_raise(self, q, face):
        if self.bid is None:
            return 1 <= q <= self.total() and 1 <= face <= 6
        return 1 <= face <= 6 and q <= self.total() and (q > self.bid["q"] or (q == self.bid["q"] and face > self.bid["face"]))

    # ---------- actions ----------
    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        t = msg.get("t")
        if t == "bid":
            q, face = msg.get("q"), msg.get("face")
            if any(isinstance(x, bool) or not isinstance(x, int) for x in (q, face)):
                raise GameError("Bad bid")
            if not self.valid_raise(q, face):
                raise GameError("Raise the quantity or the face value")
            self._bid(q, face)
        elif t == "liar":
            if self.bid is None:
                raise GameError("There is no bid to challenge yet")
            self._challenge()
        else:
            raise GameError("Unknown action")

    def _bid(self, q, face):
        uid = self.current()
        self.bid = {"uid": uid, "q": q, "face": face}
        self.seq += 1
        self.last_bid = {"uid": uid, "q": q, "face": face, "seq": self.seq}
        self._advance()

    def _challenge(self):
        challenger, bidder = self.current(), self.bid["uid"]
        actual = sum(d == self.bid["face"] for u in self.alive() for d in self.dice[u])
        bid_ok = actual >= self.bid["q"]
        loser = challenger if bid_ok else bidder
        self.seq += 1
        self.last_reveal = {
            "seq": self.seq, "challenger": challenger, "bidder": bidder, "q": self.bid["q"], "face": self.bid["face"],
            "actual": actual, "bid_ok": bid_ok, "loser": loser,
            "dice": {str(u): list(self.dice[u]) for u in self.alive()},
        }
        self.count[loser] -= 1
        alive = self.alive()
        if len(alive) <= 1:
            self.finished = True
            self.winner = alive[0] if alive else None
            self.dice = {u: [] for u in self.players}
            self.bid = None
            return
        self.turn_idx = self.players.index(loser) if loser in alive else self.players.index(challenger)
        if self.players[self.turn_idx] not in alive:
            self._advance()
        self._roll_all()

    def auto_play(self):
        if self.finished:
            return
        uid = self.current()
        mine = self.dice[uid]
        others = self.total() - len(mine)
        if self.bid is not None:
            f = self.bid["face"]
            expect = mine.count(f) + others / 6
            nxt = self._best_raise(mine, others)
            if self.bid["q"] > expect + 1.0 or nxt is None or (self.bid["q"] > expect and self.rng.random() < 0.5):
                return self._challenge()
            return self._bid(*nxt)
        face = max(range(1, 7), key=lambda f: (mine.count(f), f))
        q = max(1, min(self.total(), int(mine.count(face) + others / 6)))
        self._bid(q, face)

    def _best_raise(self, mine, others):
        cands = []
        b = self.bid
        for q in (b["q"], b["q"] + 1):
            for face in range(1, 7):
                if self.valid_raise(q, face):
                    cands.append((q, face, abs((mine.count(face) + others / 6) - q)))
        if not cands:
            return None
        cands.sort(key=lambda x: (x[2], x[0], x[1]))
        return cands[0][0], cands[0][1]

    def remove_player(self, uid):
        if uid not in self.count or uid in self.left or self.finished:
            return
        was_current = self.current() == uid
        self.left.add(uid)
        alive = self.alive()
        if len(alive) <= 1:
            self.finished = True
            self.winner = alive[0] if alive else None
            return
        if self.bid and self.bid["uid"] == uid:
            self.bid = None
        if was_current:
            self._advance()
            if self.bid and self.bid["uid"] == self.current():
                self.bid = None

    # ---------- views ----------
    def public_state(self):
        return {
            "kind": "liarsdice",
            "players": [{"uid": u, "dice": self.count[u], "left": u in self.left, "out": self.count[u] <= 0} for u in self.players],
            "turn": self.current(), "bid": self.bid, "round": self.round, "total": self.total(),
            "last_bid": self.last_bid, "last_reveal": self.last_reveal, "winner": self.winner,
            "my_dice": [],
        }

    def view(self, uid):
        s = self.public_state()
        if uid in self.dice and uid in self.alive() and not self.finished:
            s["my_dice"] = list(self.dice[uid])
        return s

"""Teen Patti (3-card Indian poker), 2-6 players. In-game chips; blind/seen play; chaal, raise, pack and show."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

SUITS = "SHDC"
START_CHIPS, BOOT, MAX_STAKE, MAX_ACTIONS = 1000, 10, 160, 60


def rank(hand):
    """Comparable tuple; higher wins. hand = three (value, suit) with A=14."""
    vs = sorted((v for v, _ in hand), reverse=True)
    flush = len({s for _, s in hand}) == 1
    seq_hi = None
    if vs[0] - vs[1] == 1 and vs[1] - vs[2] == 1:
        seq_hi = vs[0]
    elif vs == [14, 3, 2]:
        seq_hi = 13.5  # A-2-3 is the second-highest sequence
    if vs[0] == vs[1] == vs[2]:
        return (6, vs[0])
    if seq_hi and flush:
        return (5, seq_hi)
    if seq_hi:
        return (4, seq_hi)
    if flush:
        return (3, *vs)
    if vs[0] == vs[1] or vs[1] == vs[2]:
        pair = vs[1]
        kick = vs[2] if vs[0] == vs[1] else vs[0]
        return (2, pair, kick)
    return (1, *vs)


NAMES = {6: "Trail", 5: "Pure Sequence", 4: "Sequence", 3: "Colour", 2: "Pair", 1: "High Card"}


class TeenPattiGame(BaseGame):
    name = "teenpatti"
    min_players, max_players = 2, 6

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 6:
            raise ValueError("Teen Patti needs 2-6 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        deck = [(v, s) for v in range(2, 15) for s in SUITS]
        self.rng.shuffle(deck)
        self.hands = {u: [deck.pop() for _ in range(3)] for u in self.players}
        self.chips = {u: START_CHIPS - BOOT for u in self.players}
        self.pot = BOOT * len(self.players)
        self.stake = BOOT
        self.seen = {u: False for u in self.players}
        self.folded = set()
        self.turn_idx, self.actions = 0, 0
        self.seq, self.last_event, self.reveal = 0, None, None
        self.winner, self.finished, self.draw = None, False, False

    def active(self):
        return [u for u in self.players if u not in self.folded]

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def _next(self):
        for _ in range(len(self.players)):
            self.turn_idx = (self.turn_idx + 1) % len(self.players)
            if self.players[self.turn_idx] not in self.folded:
                return

    def cost(self, uid, stake=None):
        s = self.stake if stake is None else stake
        return s * 2 if self.seen[uid] else s

    def _event(self, uid, kind, amount=0):
        self.seq += 1
        self.last_event = {"seq": self.seq, "uid": uid, "kind": kind, "amount": amount, "pot": self.pot}

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid not in self.hands or uid in self.folded:
            raise GameError("You are not in this hand")
        t = msg.get("t")
        if t == "see":
            if self.seen[uid]:
                return
            self.seen[uid] = True
            self._event(uid, "see")
            return
        if uid != self.current():
            raise GameError("It's not your turn")
        n_act = len(self.active())
        if t == "pack":
            self.folded.add(uid)
            self._event(uid, "pack")
            if len(self.active()) == 1:
                return self._end(self.active()[0], "everyone else packed")
            self._next()
        elif t in ("chaal", "raise"):
            stake = self.stake
            if t == "raise":
                if self.stake >= MAX_STAKE:
                    raise GameError("Stake is already at the limit")
                stake = self.stake * 2
            c = self.cost(uid, stake)
            if c > self.chips[uid]:
                raise GameError("Not enough chips: pack or show")
            self.chips[uid] -= c
            self.pot += c
            self.stake = stake
            self._event(uid, t, c)
            self.actions += 1
            self._next()
        elif t == "show":
            if n_act != 2:
                raise GameError("Show is only possible with two players left")
            c = min(self.cost(uid), self.chips[uid])
            self.chips[uid] -= c
            self.pot += c
            self._event(uid, "show", c)
            self._showdown()
            return
        else:
            raise GameError("Unknown action")
        if self.actions >= MAX_ACTIONS and not self.finished:
            self._showdown()

    def _showdown(self):
        act = self.active()
        best = max(act, key=lambda u: rank(self.hands[u]))
        self._end(best, NAMES[rank(self.hands[best])[0]])

    def _end(self, winner, why):
        self.finished, self.winner = True, winner
        self.chips[winner] += self.pot
        self.reveal = {"why": why, "pot": self.pot, "hands": {str(u): self.hands[u] for u in self.active()},
                       "names": {str(u): NAMES[rank(self.hands[u])[0]] for u in self.active()}}
        self.pot = 0

    def auto_play(self):
        if self.finished:
            return
        uid = self.current()
        r = rank(self.hands[uid])
        strength = r[0] + (r[1] / 30 if r[0] < 3 else 0)
        if not self.seen[uid] and (self.actions >= 2 or self.rng.random() < 0.3):
            self.seen[uid] = True
            self._event(uid, "see")
        n = len(self.active())
        if self.seen[uid] and strength < 1.6 and self.rng.random() < 0.55:
            return self.handle(uid, {"t": "pack"})
        if n == 2 and (strength >= 2 or self.cost(uid) > self.chips[uid]):
            return self.handle(uid, {"t": "show"})
        if self.cost(uid) > self.chips[uid]:
            return self.handle(uid, {"t": "show"} if n == 2 else {"t": "pack"})
        if strength >= 2.5 and self.stake < MAX_STAKE and self.cost(uid, self.stake * 2) <= self.chips[uid] and self.rng.random() < 0.4:
            return self.handle(uid, {"t": "raise"})
        self.handle(uid, {"t": "chaal"})

    def remove_player(self, uid):
        if uid not in self.hands or uid in self.folded or self.finished:
            return
        was = self.current() == uid
        self.folded.add(uid)
        if len(self.active()) == 1:
            return self._end(self.active()[0], "everyone else left")
        if was:
            self._next()

    def public_state(self):
        return {"kind": "teenpatti", "players": [{"uid": u, "chips": self.chips[u], "seen": self.seen[u], "folded": u in self.folded} for u in self.players],
                "pot": self.pot, "stake": self.stake, "turn": self.current(), "n_active": len(self.active()),
                "last_event": self.last_event, "reveal": self.reveal, "hand": None, "rankname": None, "max_stake": MAX_STAKE,
                "costs": {}, "winner": self.winner, "draw": self.draw}

    def view(self, uid):
        st = self.public_state()
        if uid in self.hands:
            st["seen_me"] = self.seen[uid]
            if self.seen[uid] or self.finished:
                st["hand"] = self.hands[uid]
                st["rankname"] = NAMES[rank(self.hands[uid])[0]]
            st["costs"] = {"chaal": self.cost(uid), "raise": self.cost(uid, min(self.stake * 2, MAX_STAKE)), "show": self.cost(uid)}
        return st

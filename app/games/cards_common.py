"""Shared helpers for the card games."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

SUITS = "SHDC"
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
RVAL = {r: i + 2 for i, r in enumerate(RANKS)}  # 2..14


def deck52():
    return [r + s for s in SUITS for r in RANKS]


def rank_of(card: str) -> str:
    return card[:-1]


def suit_of(card: str) -> str:
    return card[-1]


class CardGame(BaseGame):
    """Common plumbing: rng, seq counter, safety valve against endless games."""

    MAX_STEPS = 3000

    def _init_common(self, players, rng):
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self.seq = 0
        self.steps = 0

    def _ev(self, **kw):
        """Record an event (kept in a short log so renderers can replay every event they missed, in order)."""
        kw["seq"] = self._bump()
        self.event = kw
        self.log = (getattr(self, "log", []) + [kw])[-10:]
        return kw

    def _bump(self):
        self.seq += 1
        self.steps += 1
        return self.seq

    def view(self, uid):
        return self._view(uid)

    def public_state(self):
        return self._view(None)

    @staticmethod
    def _int(v, lo=None, hi=None, what="value"):
        if isinstance(v, bool) or not isinstance(v, int):
            raise GameError(f"Bad {what}")
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            raise GameError(f"Bad {what}")
        return v

    @staticmethod
    def _str(v, what="value", allowed=None):
        if not isinstance(v, str) or len(v) > 8 or (allowed is not None and v not in allowed):
            raise GameError(f"Bad {what}")
        return v

    def _decide(self, scores):
        """scores: {uid: number}, higher is better. Fills winner / winners / draw."""
        scores = {u: scores[u] for u in self.players if u in scores}
        top = max(scores.values())
        lead = [u for u in self.players if scores.get(u) == top]
        self.finished = True
        if len(lead) == 1:
            self.winner = lead[0]
        elif len(lead) == len(self.players):
            self.draw = True
        else:
            self.winners, self.winner = lead, lead[0]

"""Bluff (a.k.a. Cheat) for 3-6 players. Everyone is dealt cards from a 52-card deck. On your turn you put 1-4 cards
face-down on the pile and CLAIM they are all of the next rank (A, 2, 3 ... round and round). Anyone may call "Bluff!".
If you lied you pick up the whole pile, otherwise the caller does. First to empty their hand wins."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = "SHDC"
CALL_WINDOW = 6.0


class BluffGame(BaseGame):
    name = "bluff"
    min_players = 3
    max_players = 6
    phase_seconds = 25

    def __init__(self, players, rng=None):
        if not 3 <= len(players) <= 6:
            raise ValueError("Bluff needs 3-6 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        deck = [r + s for r in RANKS for s in SUITS]
        self.rng.shuffle(deck)
        self.hands = {u: [] for u in self.players}
        for i, c in enumerate(deck):
            self.hands[self.players[i % len(self.players)]].append(c)
        self.pile = []
        self.turn_i = 0
        self.rank_i = 0                 # rank the current player must claim
        self.claim = None               # {"uid","n","rank","cards"} awaiting a possible call
        self.passed = set()             # players who declined to call this claim
        self.seq = 0
        self.last_event = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self._sort()

    def _sort(self):
        order = {r + s: (RANKS.index(r), s) for r in RANKS for s in SUITS}
        for h in self.hands.values():
            h.sort(key=lambda c: order[c])

    @property
    def rank(self):
        return RANKS[self.rank_i % 13]

    def current(self):
        if self.finished:
            return None
        if self.claim is not None:       # waiting for the others to call or pass; bots/AFK resolved by auto_play
            for u in self.players:
                if u != self.claim["uid"] and u not in self.passed:
                    return u
        return self.players[self.turn_i % len(self.players)]

    def _ev(self, **kw):
        self.seq += 1
        self.last_event = {"seq": self.seq, **kw}

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid not in self.hands:
            raise GameError("You are not in this game")
        t = msg.get("t")
        if self.claim is not None:
            if uid == self.claim["uid"]:
                raise GameError("Wait for the others to call or pass")
            if t == "bluff":
                return self._call(uid)
            if t == "pass":
                self.passed.add(uid)
                return self._maybe_accept()
            raise GameError("Call Bluff or pass")
        if uid != self.players[self.turn_i % len(self.players)]:
            raise GameError("Not your turn")
        if t != "play":
            raise GameError("Play 1-4 cards")
        cards = msg.get("cards")
        if not isinstance(cards, list) or not 1 <= len(cards) <= 4 or len(set(cards)) != len(cards):
            raise GameError("Pick 1 to 4 cards")
        hand = self.hands[uid]
        if any(c not in hand for c in cards):
            raise GameError("You don't have those cards")
        for c in cards:
            hand.remove(c)
        self.claim = {"uid": uid, "n": len(cards), "rank": self.rank, "cards": cards}
        self.passed = {uid}
        self.pile.extend(cards)
        self._ev(e="claim", uid=uid, n=len(cards), rank=self.rank)
        self._maybe_accept()

    def _call(self, caller):
        c = self.claim
        liar = any(card[:-1] != c["rank"] for card in c["cards"])
        loser = c["uid"] if liar else caller
        taken = len(self.pile)
        self.hands[loser].extend(self.pile)
        self.pile = []
        self._sort()
        self._ev(e="bluff", caller=caller, uid=c["uid"], liar=liar, loser=loser, cards=c["cards"], taken=taken, rank=c["rank"])
        self.claim = None
        self.passed = set()
        self.rank_i += 1
        # the liar's victim-turn rule: the player who lost the call does NOT lose their turn order - turn moves on
        self.turn_i = (self.players.index(c["uid"]) + 1) % len(self.players)
        self._check_win_after_call(c["uid"])

    def _check_win_after_call(self, claimer):
        if not self.hands[claimer]:
            if self.last_event and self.last_event.get("liar"):
                return
            self._finish(claimer)

    def _finish(self, uid):
        self.finished = True
        self.winner = uid
        self.claim = None

    def _maybe_accept(self):
        c = self.claim
        if c is None:
            return
        if all(u in self.passed for u in self.players):
            self._ev(e="accept", uid=c["uid"])
            self.claim = None
            self.passed = set()
            self.rank_i += 1
            if not self.hands[c["uid"]]:
                return self._finish(c["uid"])
            self.turn_i = (self.players.index(c["uid"]) + 1) % len(self.players)

    def auto_play(self):
        if self.finished:
            return
        if self.claim is not None:
            u = self.current()
            # computer players / AFK: suspicious of big or late claims
            c = self.claim
            mine = sum(1 for x in self.hands[u] if x[:-1] == c["rank"])
            doubt = (c["n"] + mine > 4) or (self.rng.random() < 0.18 + 0.1 * (c["n"] - 1) and len(self.hands[c["uid"]]) <= 2)
            if doubt:
                return self.handle(u, {"t": "bluff"})
            return self.handle(u, {"t": "pass"})
        u = self.players[self.turn_i % len(self.players)]
        hand = self.hands[u]
        good = [c for c in hand if c[:-1] == self.rank]
        if good:
            cards = good[: self.rng.randint(1, len(good))]
            if self.rng.random() < 0.25 and len(hand) > len(cards) and len(cards) < 4:
                extra = self.rng.choice([c for c in hand if c not in cards])
                cards = cards + [extra]
        else:
            cards = self.rng.sample(hand, 1 if len(hand) < 6 or self.rng.random() < 0.6 else 2)
        self.handle(u, {"t": "play", "cards": cards})

    def remove_player(self, uid):
        if uid not in self.hands or self.finished:
            return
        i = self.players.index(uid)
        cur = self.players[self.turn_i % len(self.players)]
        self.pile.extend(self.hands.pop(uid))     # their cards go to the pile
        self.players.remove(uid)
        self.passed.discard(uid)
        if self.claim and self.claim["uid"] == uid:
            self.claim = None
            self.passed = set()
        if len(self.players) < 2:
            return self._finish(self.players[0])
        self.turn_i = self.players.index(cur) if cur in self.players else i % len(self.players)
        if self.claim:
            self._maybe_accept()

    def public_state(self):
        return {"kind": "bluff", "players": [{"uid": u, "n": len(self.hands[u])} for u in self.players],
                "turn": self.current(), "active": self.players[self.turn_i % len(self.players)], "rank": self.rank,
                "pile": len(self.pile), "claim": ({"uid": self.claim["uid"], "n": self.claim["n"], "rank": self.claim["rank"]} if self.claim else None),
                "passed": sorted(self.passed), "last_event": self.last_event, "winner": self.winner, "draw": False}

    def view(self, uid):
        s = self.public_state()
        s["hand"] = list(self.hands.get(uid, []))
        return s

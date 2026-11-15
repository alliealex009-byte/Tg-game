"""Blackjack against the dealer, 2-4 players, 3 hands. Win +1, push 0, lose -1; best total wins the match."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

ROUNDS = 3


def total(hand):
    t, aces = 0, 0
    for v, _ in hand:
        if v == 14:
            aces += 1
            t += 11
        else:
            t += min(v, 10)
    while t > 21 and aces:
        t -= 10
        aces -= 1
    return t


class BlackjackGame(BaseGame):
    name = "blackjack"
    min_players, max_players = 2, 4

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("Blackjack needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.score = {u: 0 for u in self.players}
        self.left = set()
        self.round = 0
        self.seq, self.last_event, self.last_round = 0, None, None
        self.winner, self.finished, self.draw = None, False, False
        self.winners = None
        self._deal()

    def _card(self):
        if len(self.deck) < 12:
            self.deck = [(v, s) for v in range(2, 15) for s in "SHDC"] * 2
            self.rng.shuffle(self.deck)
        return self.deck.pop()

    def _deal(self):
        if not hasattr(self, "deck"):
            self.deck = []
        self.round += 1
        self.hands = {u: [self._card(), self._card()] for u in self.players if u not in self.left}
        self.dealer = [self._card(), self._card()]
        self.standing = set()
        self.turn_idx = -1
        self._advance()

    def _advance(self):
        """Move to the next player who still has a decision, or finish the round."""
        n = len(self.players)
        while True:
            self.turn_idx += 1
            if self.turn_idx >= n:
                return self._dealer_play()
            u = self.players[self.turn_idx]
            if u in self.left or u in self.standing:
                continue
            if total(self.hands[u]) >= 21:
                self.standing.add(u)
                continue
            return

    def current(self):
        if self.finished or self.turn_idx >= len(self.players):
            return None
        return self.players[self.turn_idx]

    def _event(self, uid, kind, card=None):
        self.seq += 1
        self.last_event = {"seq": self.seq, "uid": uid, "kind": kind, "card": card}

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        t = msg.get("t")
        if t == "hit":
            c = self._card()
            self.hands[uid].append(c)
            self._event(uid, "hit", c)
            if total(self.hands[uid]) >= 21:
                self.standing.add(uid)
                self._advance()
        elif t == "stand":
            self.standing.add(uid)
            self._event(uid, "stand")
            self._advance()
        else:
            raise GameError("Unknown action")

    def _dealer_play(self):
        live = [u for u in self.hands if total(self.hands[u]) <= 21]
        while live and total(self.dealer) < 17:
            self.dealer.append(self._card())
        dt = total(self.dealer)
        res = {}
        for u in self.hands:
            pt = total(self.hands[u])
            if pt > 21:
                r = -1
            elif dt > 21 or pt > dt:
                r = 1
            elif pt == dt:
                r = 0
            else:
                r = -1
            res[str(u)] = r
            self.score[u] += r
        self.seq += 1
        self.last_round = {"seq": self.seq, "round": self.round, "dealer": self.dealer, "hands": {str(u): h for u, h in self.hands.items()},
                           "results": res, "dealer_total": dt}
        if self.round >= ROUNDS:
            self._finish()
        else:
            self._deal()

    def _finish(self):
        self.finished = True
        pool = {u: s for u, s in self.score.items() if u not in self.left}
        best = max(pool.values())
        top = [u for u, s in pool.items() if s == best]
        if len(top) == len(pool) and len(top) > 1:
            self.draw = True
        elif len(top) == 1:
            self.winner = top[0]
        else:
            self.winners = top
            self.winner = top[0]

    def auto_play(self):
        if self.finished:
            return
        uid = self.current()
        t = total(self.hands[uid])
        self.handle(uid, {"t": "hit"} if t < 16 or (t == 16 and self.rng.random() < 0.3) else {"t": "stand"})

    def remove_player(self, uid):
        if uid not in self.score or uid in self.left or self.finished:
            return
        was = self.current() == uid
        self.left.add(uid)
        act = [u for u in self.players if u not in self.left]
        if len(act) <= 1:
            self.finished, self.winner = True, act[0] if act else None
        elif was:
            self.standing.add(uid)
            self._advance()

    def public_state(self):
        hide = self.current() is not None
        return {"kind": "blackjack", "round": self.round, "rounds": ROUNDS,
                "players": [{"uid": u, "score": self.score[u], "left": u in self.left, "cards": self.hands.get(u, []),
                             "total": total(self.hands[u]) if u in self.hands else 0, "standing": u in self.standing} for u in self.players],
                "dealer": [self.dealer[0], None] + self.dealer[2:] if hide else self.dealer,
                "dealer_total": None if hide else total(self.dealer),
                "turn": self.current(), "last_event": self.last_event, "last_round": self.last_round,
                "winner": self.winner, "draw": self.draw}

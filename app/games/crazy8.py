"""Crazy Eights: match suit or rank, eights are wild. Draw (up to 3) only when you can't play."""
from __future__ import annotations

from .base import GameError
from .cards_common import SUITS, CardGame, deck52, rank_of, suit_of

MAX_DRAWS = 3


class CrazyEightsGame(CardGame):
    name = "crazy8"
    min_players = 2
    max_players = 5

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 5:
            raise ValueError("Crazy Eights needs 2-5 players")
        self._init_common(players, rng)
        self.pile = deck52()
        self.rng.shuffle(self.pile)
        n = 7 if len(players) == 2 else 5
        self.hands = {u: [self.pile.pop() for _ in range(n)] for u in self.players}
        while True:
            c = self.pile.pop()
            if rank_of(c) != "8":
                break
            self.pile.insert(0, c)
        self.discard = [c]
        self.top, self.suit = c, suit_of(c)
        self.idx, self.draws = 0, 0
        self.event = None
        self._settle()

    def current(self):
        return None if self.finished else self.players[self.idx]

    def _legal(self, card):
        return rank_of(card) == "8" or suit_of(card) == self.suit or rank_of(card) == rank_of(self.top)

    def playable(self, uid):
        return sorted({c for c in self.hands.get(uid, []) if self._legal(c)})

    def _can_draw(self):
        return bool(self.pile) or len(self.discard) > 1

    def _take(self, uid):
        if not self.pile and len(self.discard) > 1:
            rest = self.discard[:-1]
            self.discard = [self.discard[-1]]
            self.rng.shuffle(rest)
            self.pile = rest
        if not self.pile:
            return None
        c = self.pile.pop()
        self.hands[uid].append(c)
        return c

    def _event(self, **kw):
        kw["seq"] = self._bump()
        self.event = kw

    def _next(self):
        self.idx = (self.idx + 1) % len(self.players)
        self.draws = 0

    def _settle(self):
        """Skip players who are stuck (nothing to play, nothing to draw)."""
        for _ in range(len(self.players)):
            u = self.current()
            if self.playable(u) or self._can_draw():
                break
            self._next()
        else:
            self._decide({u: -len(h) for u, h in self.hands.items()})
        if not self.finished and self.steps > self.MAX_STEPS:
            self._decide({u: -len(h) for u, h in self.hands.items()})

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        t = msg.get("t")
        if t == "play":
            card = msg.get("card")
            if not isinstance(card, str) or card not in self.hands[uid]:
                raise GameError("You don't have that card")
            if not self._legal(card):
                raise GameError("You can't play that card")
            suit = suit_of(card)
            if rank_of(card) == "8":
                suit = self._str(msg.get("suit"), "suit", set(SUITS))
            self.hands[uid].remove(card)
            self.discard.append(card)
            self.top, self.suit = card, suit
            self._event(kind="play", uid=uid, card=card, suit=suit, n_left=len(self.hands[uid]))
            if not self.hands[uid]:
                self.winner, self.finished = uid, True
                return
            self._next()
            self._settle()
        elif t == "draw":
            if self.playable(uid):
                raise GameError("You have a card you can play")
            c = self._take(uid)
            if c is None:
                raise GameError("Nothing left to draw")
            self.draws += 1
            self._event(kind="draw", uid=uid, n=1, cards=[c])
            if not self._legal(c) and (self.draws >= MAX_DRAWS or not self._can_draw()):
                self._next()
                self._settle()
        elif t == "pass":
            if self.playable(uid) or self._can_draw():
                raise GameError("You can't pass yet")
            self._next()
            self._settle()
        else:
            raise GameError("Unknown action")

    def auto_play(self):
        if self.finished:
            return
        uid = self.current()
        pl = self.playable(uid)
        if pl:
            non8 = [c for c in pl if rank_of(c) != "8"]
            card = self.rng.choice(non8 or pl)
            msg = {"t": "play", "card": card}
            if rank_of(card) == "8":
                cnt = {s: 0 for s in SUITS}
                for x in self.hands[uid]:
                    cnt[suit_of(x)] += 1
                msg["suit"] = max(SUITS, key=lambda s: cnt[s])
            return self.handle(uid, msg)
        self.handle(uid, {"t": "draw"} if self._can_draw() else {"t": "pass"})

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        p = self.players.index(uid)
        self.pile = self.hands.pop(uid) + self.pile
        self.players.remove(uid)
        if len(self.players) == 1:
            self.winner, self.finished = self.players[0], True
            return
        if p < self.idx:
            self.idx -= 1
        elif p == self.idx:
            self.draws = 0
        self.idx %= len(self.players)
        self._settle()

    def _view(self, uid):
        ev = None
        if self.event:
            ev = {k: v for k, v in self.event.items() if k != "cards"}
            if self.event.get("cards") and self.event.get("uid") == uid:
                ev["cards"] = self.event["cards"]
        mine = uid == self.current()
        return {
            "kind": "crazy8", "turn": self.current(), "top": self.top, "cur": self.suit, "draw_count": len(self.pile),
            "can_draw": bool(mine and not self.playable(uid) and self._can_draw()),
            "draws_left": MAX_DRAWS - self.draws, "event": ev,
            "players": [{"uid": u, "n": len(self.hands[u])} for u in self.players],
            "hand": list(self.hands[uid]) if uid in self.hands else [],
            "playable": self.playable(uid) if mine else [],
            "winner": self.winner, "draw": self.draw,
        }

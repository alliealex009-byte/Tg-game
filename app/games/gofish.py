"""Go Fish: ask for a rank you hold, collect books of four, most books wins."""
from __future__ import annotations

from .base import GameError
from .cards_common import RANKS, CardGame, deck52, rank_of


class GoFishGame(CardGame):
    name = "gofish"
    min_players = 2
    max_players = 4

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("Go Fish needs 2-4 players")
        self._init_common(players, rng)
        self.pile = deck52()
        self.rng.shuffle(self.pile)
        n = 7 if len(players) <= 3 else 5
        self.hands = {u: [self.pile.pop() for _ in range(n)] for u in self.players}
        self.books = {u: [] for u in self.players}
        self.idx = 0
        self.event = None
        for u in self.players:
            self._collect(u)
        self._begin_turn()

    def current(self):
        return None if self.finished else self.players[self.idx]

    def _event(self, **kw):
        kw["seq"] = self._bump()
        self.event = kw

    def _collect(self, uid):
        got = []
        for r in RANKS:
            if sum(1 for c in self.hands[uid] if rank_of(c) == r) == 4:
                self.hands[uid] = [c for c in self.hands[uid] if rank_of(c) != r]
                self.books[uid].append(r)
                got.append(r)
        return got

    def _targets(self, uid):
        return [u for u in self.players if u != uid and self.hands[u]]

    def _finish_if_done(self):
        have = [u for u in self.players if self.hands[u]]
        if (not self.pile and len(have) <= 1) or sum(len(b) for b in self.books.values()) == 13 \
                or self.steps > self.MAX_STEPS:
            self._decide({u: len(b) for u, b in self.books.items()})
            return True
        return False

    def _begin_turn(self):
        """Make sure the player to move can actually move; draw or skip otherwise."""
        for _ in range(len(self.players) + 1):
            if self._finish_if_done():
                return
            u = self.current()
            if not self.hands[u] and self.pile:
                c = self.pile.pop()
                self.hands[u].append(c)
                self._collect(u)
                self._event(kind="refill", uid=u)
            if self.hands[u] and self._targets(u):
                return
            if self.hands[u] and self.pile:  # nobody to ask: fish blindly
                c = self.pile.pop()
                self.hands[u].append(c)
                self._collect(u)
                self._event(kind="refill", uid=u)
            self.idx = (self.idx + 1) % len(self.players)
        self._decide({u: len(b) for u, b in self.books.items()})

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        if msg.get("t") != "ask":
            raise GameError("Unknown action")
        target = self._int(msg.get("target"), what="player")
        rank = self._str(msg.get("rank"), "rank", set(RANKS))
        if target == uid or target not in self.hands:
            raise GameError("Pick another player")
        if not self.hands[target]:
            raise GameError("That player has no cards")
        if not any(rank_of(c) == rank for c in self.hands[uid]):
            raise GameError("You must hold a card of the rank you ask for")
        taken = [c for c in self.hands[target] if rank_of(c) == rank]
        ev = dict(kind="ask", uid=uid, target=target, rank=rank, got=len(taken), fished=False, lucky=False)
        if taken:
            self.hands[target] = [c for c in self.hands[target] if rank_of(c) != rank]
            self.hands[uid] += taken
            again = True
        else:
            ev["fished"] = True
            again = False
            if self.pile:
                c = self.pile.pop()
                self.hands[uid].append(c)
                if rank_of(c) == rank:
                    ev["lucky"], again = True, True
        ev["books"] = self._collect(uid)
        self._event(**ev)
        if not again:
            self.idx = (self.idx + 1) % len(self.players)
        self._begin_turn()

    def auto_play(self):
        if self.finished:
            return
        uid = self.current()
        ranks = sorted({rank_of(c) for c in self.hands[uid]})
        rank = self.rng.choice(ranks)
        self.handle(uid, {"t": "ask", "target": self.rng.choice(self._targets(uid)), "rank": rank})

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        p = self.players.index(uid)
        self.pile = self.hands.pop(uid) + self.pile
        self.rng.shuffle(self.pile)
        self.players.remove(uid)
        if len(self.players) == 1:
            self.winner, self.finished = self.players[0], True
            return
        if p < self.idx:
            self.idx -= 1
        self.idx %= len(self.players)
        self._begin_turn()

    def _view(self, uid):
        return {
            "kind": "gofish", "turn": self.current(), "draw_count": len(self.pile), "event": self.event,
            "players": [{"uid": u, "n": len(self.hands[u]), "books": list(self.books[u])} for u in self.players],
            "hand": list(self.hands[uid]) if uid in self.hands else [],
            "targets": self._targets(uid) if uid == self.current() else [],
            "winner": self.winner, "winners": self.winners, "draw": self.draw,
        }

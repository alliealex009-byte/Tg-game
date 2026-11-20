"""Memory Match: 16 face-down cards (8 pairs). Flip two; a match scores and you go again.

After a mismatch the two cards stay visible until the next player's first flip, so everyone can see them.
Face-down card values are never sent to clients.
"""
from __future__ import annotations

import random

from .base import BaseGame, GameError

SYMBOLS = ["🍎", "🍌", "🍇", "🍓", "🍒", "🍉", "🥝", "🍍"]
BOT_MEMORY = 0.75  # chance the computer remembers a card it has seen


class MemoryGame(BaseGame):
    name = "memory"
    min_players = 2
    max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Memory Match needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.cards = SYMBOLS * 2
        self.rng.shuffle(self.cards)
        self.owner = {}          # card index -> uid who matched it
        self.up = []             # face-up, unmatched cards
        self.hide_pending = False
        self.seen = set()
        self.scores = {u: 0 for u in self.players}
        self.turn_idx = 0
        self.seq = 0
        self.last_flip = None
        self.winner = None
        self.finished = False
        self.draw = False

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        if msg.get("t") != "flip":
            raise GameError("Unknown action")
        i = msg.get("i")
        if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < len(self.cards):
            raise GameError("Bad card")
        if i in self.owner:
            raise GameError("That pair is already matched")
        if i in self.up and not self.hide_pending:
            raise GameError("That card is already face up")
        self._flip(i)

    def _flip(self, i):
        if self.hide_pending:
            self.up, self.hide_pending = [], False
        uid = self.current()
        self.up.append(i)
        self.seen.add(i)
        self.seq += 1
        self.last_flip = {"uid": uid, "i": i, "seq": self.seq}
        if len(self.up) < 2:
            return
        a, b = self.up
        if self.cards[a] == self.cards[b]:
            self.owner[a] = self.owner[b] = uid
            self.scores[uid] += 1
            self.up = []
            if len(self.owner) == len(self.cards):
                self.finished = True
                sa, sb = (self.scores[u] for u in self.players)
                if sa == sb:
                    self.draw = True
                else:
                    self.winner = self.players[0] if sa > sb else self.players[1]
        else:
            self.hide_pending = True
            self.turn_idx = 1 - self.turn_idx

    def auto_play(self):
        if self.finished:
            return
        if self.hide_pending:  # the cards that were showing are about to be hidden: they are "seen"
            self.up, self.hide_pending = [], False
        free = [i for i in range(len(self.cards)) if i not in self.owner and i not in self.up]
        known = [i for i in free if i in self.seen and self.rng.random() < BOT_MEMORY]
        if self.up:  # second flip: look for the partner of the first card
            first = self.cards[self.up[0]]
            partner = [i for i in known if self.cards[i] == first]
            if partner:
                return self._flip(partner[0])
            unseen = [i for i in free if i not in self.seen]
            return self._flip(self.rng.choice(unseen or free))
        by_symbol = {}
        for i in known:
            by_symbol.setdefault(self.cards[i], []).append(i)
        pairs = [v for v in by_symbol.values() if len(v) >= 2]
        if pairs:
            return self._flip(pairs[0][0])
        unseen = [i for i in free if i not in self.seen]
        self._flip(self.rng.choice(unseen or free))

    def remove_player(self, uid):
        if uid not in self.scores or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        shown = [self.cards[i] if (i in self.owner or i in self.up) else None for i in range(len(self.cards))]
        return {
            "kind": "memory",
            "players": [{"uid": u, "score": self.scores[u]} for u in self.players],
            "cards": shown,
            "owner": {str(i): u for i, u in self.owner.items()},
            "up": list(self.up),
            "turn": self.current(),
            "last_flip": self.last_flip,
            "winner": self.winner,
            "draw": self.draw,
        }

"""UNO for 2-6 players. Cards are strings: colour+value (R5, YS skip, GR reverse, BD draw-two) or WW wild / WF wild-draw-four."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

COLORS = "RYGB"


def new_deck(rng):
    d = []
    for c in COLORS:
        d.append(c + "0")
        for v in "123456789SRD":
            d += [c + v] * 2
    d += ["WW"] * 4 + ["WF"] * 4
    rng.shuffle(d)
    return d


class UnoGame(BaseGame):
    name = "uno"
    min_players, max_players = 2, 6

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 6:
            raise ValueError("UNO needs 2-6 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.deck = new_deck(self.rng)
        self.hands = {u: [self.deck.pop() for _ in range(7)] for u in self.players}
        while True:  # start card must be a plain number
            top = self.deck.pop()
            if top[0] in COLORS and top[1].isdigit():
                break
            self.deck.insert(0, top)
        self.pile = [top]
        self.color = top[0]
        self.dir = 1
        self.turn_idx = 0
        self.drawn = None       # index in the hand of a card just drawn that may be played
        self.left = set()
        self.seq, self.last_event = 0, None
        self.winner, self.finished, self.draw = None, False, False

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def _alive(self):
        return [u for u in self.players if u not in self.left]

    def _step(self, n=1):
        for _ in range(n):
            for _k in range(len(self.players)):
                self.turn_idx = (self.turn_idx + self.dir) % len(self.players)
                if self.players[self.turn_idx] not in self.left:
                    break

    def _draw(self, uid, n):
        got = []
        for _ in range(n):
            if not self.deck:
                keep = self.pile.pop()
                self.deck, self.pile = self.pile, [keep]
                self.rng.shuffle(self.deck)
                if not self.deck:
                    break
            c = self.deck.pop()
            self.hands[uid].append(c)
            got.append(c)
        return got

    def playable(self, card):
        top = self.pile[-1]
        return card[0] == "W" or card[0] == self.color or card[1] == top[1]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        t = msg.get("t")
        hand = self.hands[uid]
        if t == "play":
            i = msg.get("card")
            if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < len(hand):
                raise GameError("Bad card")
            if self.drawn is not None and i != self.drawn:
                raise GameError("Play the card you drew, or pass")
            card = hand[i]
            if not self.playable(card):
                raise GameError("That card can't be played")
            col = msg.get("color")
            if card[0] == "W" and col not in COLORS:
                raise GameError("Choose a colour")
            self._play(uid, i, col)
        elif t == "draw":
            if self.drawn is not None:
                raise GameError("You already drew")
            got = self._draw(uid, 1)
            self.seq += 1
            self.last_event = {"seq": self.seq, "uid": uid, "kind": "draw", "n": len(got)}
            if got and self.playable(got[0]):
                self.drawn = len(hand) - 1
            else:
                self._step()
        elif t == "pass":
            if self.drawn is None:
                raise GameError("Draw a card first")
            self.drawn = None
            self.seq += 1
            self.last_event = {"seq": self.seq, "uid": uid, "kind": "pass"}
            self._step()
        else:
            raise GameError("Unknown action")

    def _play(self, uid, i, col):
        card = self.hands[uid].pop(i)
        self.pile.append(card)
        self.color = col if card[0] == "W" else card[0]
        self.drawn = None
        ev = {"uid": uid, "kind": "play", "card": card, "color": self.color, "n": 0, "target": None}
        if not self.hands[uid]:
            self.seq += 1
            self.last_event = dict(ev, seq=self.seq)
            self.finished, self.winner = True, uid
            return
        v = card[1]
        if v == "R" and card[0] != "W":
            if len(self._alive()) == 2:
                self._step(2)
            else:
                self.dir *= -1
                self._step()
        elif v == "S":
            self._step()
            ev["target"] = self.current()
            self._step()
        elif v == "D" or card == "WF":
            n = 2 if v == "D" else 4
            self._step()
            tgt = self.current()
            ev["n"], ev["target"] = len(self._draw(tgt, n)), tgt
            self._step()
        else:
            self._step()
        self.seq += 1
        ev["seq"] = self.seq
        ev["uno"] = len(self.hands[uid]) == 1
        self.last_event = ev

    def auto_play(self):
        if self.finished:
            return
        uid = self.current()
        hand = self.hands[uid]
        if self.drawn is not None:
            self._play(uid, self.drawn, self._best_color(hand, self.drawn))
            return
        opts = [i for i, c in enumerate(hand) if self.playable(c)]
        if not opts:
            self.handle(uid, {"t": "draw"})
            if self.drawn is not None and not self.finished and self.current() == uid:
                self._play(uid, self.drawn, self._best_color(hand, self.drawn))
            return
        pick = max(opts, key=lambda i: (hand[i][0] != "W") * 2 + (hand[i][1] in "SRD") + self.rng.random())
        self._play(uid, pick, self._best_color(hand, pick))

    def _best_color(self, hand, skip):
        cnt = {c: 0 for c in COLORS}
        for j, c in enumerate(hand):
            if j != skip and c[0] in COLORS:
                cnt[c[0]] += 1
        return max(COLORS, key=lambda c: cnt[c] + self.rng.random() * 0.1)

    def remove_player(self, uid):
        if uid not in self.hands or uid in self.left or self.finished:
            return
        was = self.current() == uid
        self.left.add(uid)
        self.deck += self.hands[uid]
        self.rng.shuffle(self.deck)
        self.hands[uid] = []
        act = self._alive()
        if len(act) <= 1:
            self.finished, self.winner = True, act[0] if act else None
        elif was:
            self.drawn = None
            self._step()

    def public_state(self):
        return {"kind": "uno", "players": [{"uid": u, "count": len(self.hands[u]), "left": u in self.left} for u in self.players],
                "top": self.pile[-1], "color": self.color, "dir": self.dir, "turn": self.current(), "deck": len(self.deck),
                "drawn": self.drawn, "last_event": self.last_event, "hand": None, "playable": [],
                "winner": self.winner, "draw": self.draw}

    def view(self, uid):
        st = self.public_state()
        if uid in self.hands:
            h = self.hands[uid]
            st["hand"] = h
            if uid == self.current() and not self.finished:
                st["playable"] = [i for i, c in enumerate(h) if self.playable(c) and (self.drawn is None or i == self.drawn)]
        return st

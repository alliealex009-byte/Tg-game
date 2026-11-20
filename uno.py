"""UNO: 108 cards, colour choice on wilds, +4 only without a colour match, draw-then-may-play."""
from __future__ import annotations

from .base import GameError
from .cards_common import CardGame

COLORS = "RGBY"
HAND = 7


def uno_deck():
    d = []
    for c in COLORS:
        d.append(c + "0")
        for v in list("123456789") + ["S", "R", "D"]:
            d += [c + v, c + v]
    d += ["W"] * 4 + ["W4"] * 4
    return d


def is_wild(card):
    return card[0] == "W"


class UnoGame(CardGame):
    name = "uno"
    min_players = 2
    max_players = 6

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 6:
            raise ValueError("UNO needs 2-6 players")
        self._init_common(players, rng)
        self.pile = uno_deck()
        self.rng.shuffle(self.pile)
        self.hands = {u: [self.pile.pop() for _ in range(HAND)] for u in self.players}
        while True:  # the starting card must be a plain number card
            c = self.pile.pop()
            if not is_wild(c) and c[1:].isdigit():
                break
            self.pile.insert(0, c)
        self.discard = [c]
        self.top, self.color = c, c[0]
        self.dir, self.idx = 1, 0
        self.phase, self.drawn = "play", None
        self.event = None

    # ---- helpers
    def current(self):
        return None if self.finished else self.players[self.idx]

    def _legal(self, uid, card):
        if is_wild(card):
            if card == "W4":
                rest = list(self.hands[uid])
                rest.remove(card)
                return not any((not is_wild(x)) and x[0] == self.color for x in rest)
            return True
        return card[0] == self.color or (not is_wild(self.top) and card[1:] == self.top[1:])

    def playable(self, uid):
        h = self.hands.get(uid, [])
        if self.phase == "drawn":
            return [self.drawn] if self.drawn in h and self._legal(uid, self.drawn) else []
        return sorted({c for c in h if self._legal(uid, c)})

    def _take(self, uid, n):
        got = []
        for _ in range(n):
            if not self.pile and len(self.discard) > 1:
                rest = self.discard[:-1]
                self.discard = [self.discard[-1]]
                self.rng.shuffle(rest)
                self.pile = rest
            if not self.pile:
                break
            c = self.pile.pop()
            self.hands[uid].append(c)
            got.append(c)
        return got

    def _step(self, k=1):
        self.idx = (self.idx + self.dir * k) % len(self.players)

    def _event(self, **kw):
        kw["seq"] = self._bump()
        self.event = kw

    def _end_turn(self, skip=0):
        self.phase, self.drawn = "play", None
        self._step(1 + skip)
        if self.steps > self.MAX_STEPS:
            self._decide({u: -len(h) for u, h in self.hands.items()})

    # ---- actions
    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        t = msg.get("t")
        if t == "uno":
            if len(self.hands.get(uid, [])) != 1:
                raise GameError("You can only shout UNO with one card left")
            self._event(kind="uno", uid=uid)
            return
        if uid != self.current():
            raise GameError("It's not your turn")
        if t == "play":
            card = msg.get("card")
            if not isinstance(card, str) or card not in self.hands[uid]:
                raise GameError("You don't have that card")
            if self.phase == "drawn" and card != self.drawn:
                raise GameError("Play the card you drew, or pass")
            if not self._legal(uid, card):
                raise GameError("You can't play that card")
            col = None
            if is_wild(card):
                col = self._str(msg.get("color"), "colour", set(COLORS))
            self._play(uid, card, col)
        elif t == "draw":
            if self.phase != "play":
                raise GameError("You already drew")
            got = self._take(uid, 1)
            if got and self._legal(uid, got[0]):
                self.phase, self.drawn = "drawn", got[0]
                self._event(kind="draw", uid=uid, n=1, cards=got, may_play=True)
            else:
                self._event(kind="draw", uid=uid, n=len(got), cards=got)
                self._end_turn()
        elif t == "pass":
            if self.phase != "drawn":
                raise GameError("Draw a card first")
            self._event(kind="pass", uid=uid)
            self._end_turn()
        else:
            raise GameError("Unknown action")

    def _play(self, uid, card, col):
        self.hands[uid].remove(card)
        self.discard.append(card)
        self.top, self.color = card, (col or card[0])
        v = card[1:]
        skip, victim, n = 0, None, 0
        nxt = self.players[(self.idx + self.dir) % len(self.players)]
        if card == "W4":
            victim, n = nxt, 4
        elif v == "D":
            victim, n = nxt, 2
        elif v == "S":
            skip, victim = 1, nxt
        elif v == "R":
            self.dir = -self.dir
            if len(self.players) == 2:
                skip = 1  # reverse acts as skip
        if n:
            self._take(victim, n)
            skip = 1
        self._event(kind="play", uid=uid, card=card, color=self.color, victim=victim, n=n, dir=self.dir,
                    uno=len(self.hands[uid]) == 1, skip=bool(skip))
        if not self.hands[uid]:
            self.winner, self.finished = uid, True
            return
        self._end_turn(skip)

    def auto_play(self):
        if self.finished:
            return
        uid = self.current()
        pl = self.playable(uid)
        if self.phase == "drawn" and not pl:
            return self.handle(uid, {"t": "pass"})
        if not pl:
            return self.handle(uid, {"t": "draw"})
        plain = [c for c in pl if not is_wild(c)]
        acts = [c for c in plain if c[1:] in ("S", "R", "D")]
        card = self.rng.choice(acts or plain or pl)
        msg = {"t": "play", "card": card}
        if is_wild(card):
            cnt = {c: 0 for c in COLORS}
            for x in self.hands[uid]:
                if not is_wild(x):
                    cnt[x[0]] += 1
            msg["color"] = max(COLORS, key=lambda c: cnt[c])
        self.handle(uid, msg)

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
            self.phase, self.drawn = "play", None
            self.idx = (self.idx + (0 if self.dir == 1 else -1)) % len(self.players)
        self.idx %= len(self.players)

    def _view(self, uid):
        ev = None
        if self.event:
            ev = {k: v for k, v in self.event.items() if k != "cards"}
            if self.event.get("cards") and self.event.get("uid") == uid:
                ev["cards"] = self.event["cards"]
        return {
            "kind": "uno", "turn": self.current(), "dir": self.dir, "top": self.top, "cur": self.color,
            "phase": self.phase, "draw_count": len(self.pile), "event": ev,
            "players": [{"uid": u, "n": len(self.hands[u])} for u in self.players],
            "hand": list(self.hands[uid]) if uid in self.hands else [],
            "playable": self.playable(uid) if uid == self.current() else [],
            "winner": self.winner, "draw": self.draw,
        }

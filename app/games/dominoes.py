"""Dominoes (draw game, double-six). Match a tile to either end of the chain; draw when stuck.
First to empty their hand wins; if the game blocks, the lowest pip count wins."""
from __future__ import annotations

import random

from .base import BaseGame, GameError


class DominoesGame(BaseGame):
    name = "dominoes"
    min_players = 2
    max_players = 4

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("Dominoes needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        tiles = [(a, b) for a in range(7) for b in range(a, 7)]
        self.rng.shuffle(tiles)
        n = 7 if len(players) == 2 else 5
        self.hands = {u: sorted(tiles[i * n:(i + 1) * n]) for i, u in enumerate(self.players)}
        self.yard = tiles[n * len(players):]
        self.chain = []                 # oriented tiles [(a,b)...] left→right
        self.turn_idx = 0
        self.passes = 0
        self.seq = 0
        self.last_move = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self.reason = None

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def ends(self):
        return (self.chain[0][0], self.chain[-1][1]) if self.chain else (None, None)

    def _fits(self, tile):
        if not self.chain:
            return ["R"]
        l, r = self.ends()
        out = []
        if l in tile:
            out.append("L")
        if r in tile:
            out.append("R")
        return out

    def playable(self, uid):
        return [(t, e) for t in self.hands[uid] for e in self._fits(t)]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        t = msg.get("t")
        if t == "play":
            tl = msg.get("tile")
            if not (isinstance(tl, (list, tuple)) and len(tl) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in tl)):
                raise GameError("Bad tile")
            tile = tuple(sorted(tl))
            if tile not in self.hands[uid]:
                raise GameError("You don't have that tile")
            end = msg.get("end", "R")
            if not self.chain:
                end = "R"
            if end not in ("L", "R") or end not in self._fits(tile):
                raise GameError("That tile doesn't fit there")
            self._play(uid, tile, end)
        elif t == "draw":
            if self.playable(uid):
                raise GameError("You have a playable tile")
            if not self.yard:
                raise GameError("The boneyard is empty — pass")
            tile = self.yard.pop()
            self.hands[uid].append(tile)
            self.hands[uid].sort()
            self.seq += 1
            self.last_move = {"seq": self.seq, "uid": uid, "kind": "draw"}
        elif t == "pass":
            if self.playable(uid) or self.yard:
                raise GameError("You can't pass yet")
            self.passes += 1
            self.seq += 1
            self.last_move = {"seq": self.seq, "uid": uid, "kind": "pass"}
            if self.passes >= len(self.players):
                self._block()
            else:
                self._next()
        else:
            raise GameError("Unknown action")

    def _play(self, uid, tile, end):
        self.hands[uid].remove(tile)
        a, b = tile
        if not self.chain:
            self.chain.append((a, b))
        elif end == "L":
            l = self.chain[0][0]
            self.chain.insert(0, (a, b) if b == l else (b, a))
        else:
            r = self.chain[-1][1]
            self.chain.append((a, b) if a == r else (b, a))
        self.passes = 0
        self.seq += 1
        self.last_move = {"seq": self.seq, "uid": uid, "kind": "play", "tile": list(tile), "end": end}
        if not self.hands[uid]:
            self.finished, self.winner, self.reason = True, uid, "domino"
            return
        self._next()

    def _next(self):
        self.turn_idx = (self.turn_idx + 1) % len(self.players)

    def _block(self):
        pips = {u: sum(a + b for a, b in self.hands[u]) for u in self.players}
        low = min(pips.values())
        w = [u for u in self.players if pips[u] == low]
        self.finished, self.reason = True, "blocked"
        if len(w) == 1:
            self.winner = w[0]
        else:
            self.draw = True

    def auto_play(self):
        if self.finished:
            return
        u = self.current()
        while not self.playable(u) and self.yard:
            self.handle(u, {"t": "draw"})
        mv = self.playable(u)
        if mv:
            t, e = max(mv, key=lambda m: (m[0][0] == m[0][1], sum(m[0])))
            self.handle(u, {"t": "play", "tile": list(t), "end": e})
        else:
            self.handle(u, {"t": "pass"})

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        cur = self.current()
        i = self.players.index(uid)
        self.yard.extend(self.hands.pop(uid))
        self.players.remove(uid)
        if len(self.players) < 2 or all(u < 0 for u in self.players):
            self.finished, self.winner, self.reason = True, (self.players[0] if self.players else None), "forfeit"
            return
        self.turn_idx = self.players.index(cur) if cur in self.players else i % len(self.players)

    def public_state(self):
        return {"kind": "dominoes", "players": [{"uid": u, "n": len(self.hands[u])} for u in self.players], "chain": [list(t) for t in self.chain], "yard": len(self.yard),
                "counts": {u: len(self.hands[u]) for u in self.players}, "turn": self.current(),
                "last_move": self.last_move, "reason": self.reason, "winner": self.winner, "draw": self.draw,
                "hands": None, "hand": None}

    def view(self, uid):
        s = self.public_state()
        if uid in self.hands:
            s["hand"] = [list(t) for t in self.hands[uid]]
            s["can"] = [{"tile": list(t), "end": e} for t, e in self.playable(uid)] if uid == self.current() else []
        if self.finished:
            s["hands"] = {str(u): [list(t) for t in h] for u, h in self.hands.items()}
        return s

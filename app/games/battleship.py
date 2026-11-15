"""Battleship 10x10. The server places each fleet randomly. Players alternate single shots.
view(uid) only ever shows a player their own ships; spectators see no live ship positions at all."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

N = 10
FLEET = (("Carrier", 5), ("Battleship", 4), ("Cruiser", 3), ("Submarine", 3), ("Destroyer", 2))


def place_fleet(rng):
    occ, ships = set(), []
    for name, ln in FLEET:
        while True:
            horiz = rng.random() < 0.5
            r, c = rng.randrange(N - (0 if horiz else ln - 1)), rng.randrange(N - (ln - 1 if horiz else 0))
            cells = [(r + (0 if horiz else k)) * N + c + (k if horiz else 0) for k in range(ln)]
            if not occ.intersection(cells):
                occ.update(cells)
                ships.append({"name": name, "cells": cells})
                break
    return ships


class BattleshipGame(BaseGame):
    name = "battleship"
    min_players = 2
    max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Battleship needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.ships = {u: place_fleet(self.rng) for u in self.players}   # SECRET
        self.shots = {u: {} for u in self.players}  # shots fired AT this player's waters: cell -> "hit" | "miss"
        self.turn_idx = 0
        self.winner = None
        self.finished = False
        self.draw = False
        self.seq = 0
        self.last_move = None

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def _foe(self, uid):
        return self.players[1 - self.players.index(uid)]

    def _sunk(self, target):
        got = self.shots[target]
        return [s for s in self.ships[target] if all(c in got for c in s["cells"])]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        if msg.get("t") != "fire":
            raise GameError("Unknown action")
        cell = msg.get("cell")
        if isinstance(cell, bool) or not isinstance(cell, int) or not 0 <= cell < N * N:
            raise GameError("Bad cell")
        if cell in self.shots[self._foe(uid)]:
            raise GameError("You already fired there")
        self._fire(cell)

    def _fire(self, cell):
        me = self.current()
        foe = self._foe(me)
        ship = next((s for s in self.ships[foe] if cell in s["cells"]), None)
        self.shots[foe][cell] = "hit" if ship else "miss"
        sunk = None
        if ship and all(c in self.shots[foe] for c in ship["cells"]):
            sunk = {"name": ship["name"], "cells": ship["cells"]}
        self.seq += 1
        self.last_move = {"uid": me, "target": foe, "cell": cell, "hit": bool(ship), "sunk": sunk, "seq": self.seq}
        if len(self._sunk(foe)) == len(FLEET):
            self.winner, self.finished = me, True
        else:
            self.turn_idx = 1 - self.turn_idx

    def auto_play(self):
        if self.finished:
            return
        me = self.current()
        foe = self._foe(me)
        shots = self.shots[foe]
        sunk_cells = {c for s in self._sunk(foe) for c in s["cells"]}
        hits = [c for c, v in shots.items() if v == "hit" and c not in sunk_cells]
        free = [i for i in range(N * N) if i not in shots]
        cand = []
        if hits:
            hs = set(hits)
            for h in hits:
                r, c = divmod(h, N)
                for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                    rr, cc = r + dr, c + dc
                    t = rr * N + cc
                    if 0 <= rr < N and 0 <= cc < N and t not in shots:
                        # prefer extending an existing line of hits
                        pr, pc = r - dr, c - dc
                        aligned = 0 <= pr < N and 0 <= pc < N and pr * N + pc in hs
                        cand += [t] * (4 if aligned else 1)
        if not cand:
            parity = [i for i in free if (i // N + i % N) % 2 == 0]
            cand = parity or free
        self._fire(self.rng.choice(cand))

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)

    # ---- views
    def _waters(self, owner, reveal_ships):
        d = {"shots": {str(k): v for k, v in self.shots[owner].items()},
             "sunk": [{"name": s["name"], "cells": s["cells"]} for s in self._sunk(owner)],
             "left": len(FLEET) - len(self._sunk(owner))}
        if reveal_ships:
            d["ships"] = [{"name": s["name"], "cells": s["cells"]} for s in self.ships[owner]]
        return d

    def view(self, uid):
        over = self.finished
        d = {
            "kind": "battleship",
            "size": N,
            "fleet": [{"name": n, "len": ln} for n, ln in FLEET],
            "players": [{"uid": u} for u in self.players],
            "turn": self.current(),
            "last_move": self.last_move,
            "winner": self.winner,
            "draw": self.draw,
        }
        # waters[uid] = the grid that belongs to `uid`; its ships only visible to that player (or to everyone once over)
        d["waters"] = {str(u): self._waters(u, over or u == uid) for u in self.players}
        return d

    def public_state(self):
        return self.view(None)

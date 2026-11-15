"""Battleship 8x8 with hidden fleets. Shuffle your fleet, tap Ready, then take turns firing."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

N = 8
FLEET = [4, 3, 3, 2, 2]


def random_fleet(rng):
    for _ in range(500):
        occupied, ships = set(), []
        ok = True
        for ln in FLEET:
            for _t in range(200):
                horiz = rng.random() < 0.5
                r, c = rng.randrange(N - (0 if horiz else ln - 1)), rng.randrange(N - (ln - 1 if horiz else 0))
                cells = [(r, c + i) if horiz else (r + i, c) for i in range(ln)]
                halo = {(a + da, b + db) for a, b in cells for da in (-1, 0, 1) for db in (-1, 0, 1)}
                if not (halo & occupied):
                    ships.append([a * N + b for a, b in cells])
                    occupied |= set(cells)
                    break
            else:
                ok = False
                break
        if ok:
            return ships
    raise RuntimeError("fleet placement failed")


class BattleshipGame(BaseGame):
    name = "battleship"
    min_players = max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Battleship needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.fleet = {u: random_fleet(self.rng) for u in self.players}
        self.shots = {u: {} for u in self.players}   # shots FIRED BY u: cell -> "hit"/"miss"
        self.ready = {u: u < 0 for u in self.players}  # computer is always ready
        self.phase = "place"
        self.turn_idx = 0
        self.seq, self.last_shot = 0, None
        self.winner, self.finished, self.draw = None, False, False

    def other(self, u):
        return self.players[1] if u == self.players[0] else self.players[0]

    def current(self):
        if self.finished:
            return None
        if self.phase == "place":
            return next((u for u in self.players if not self.ready[u]), self.players[0])
        return self.players[self.turn_idx]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        t = msg.get("t")
        if self.phase == "place":
            if uid not in self.fleet:
                raise GameError("You are not playing")
            if self.ready[uid]:
                raise GameError("Waiting for your opponent")
            if t == "shuffle":
                self.fleet[uid] = random_fleet(self.rng)
            elif t == "ready":
                self.ready[uid] = True
                if all(self.ready.values()):
                    self.phase = "battle"
            else:
                raise GameError("Unknown action")
            return
        if uid != self.current():
            raise GameError("It's not your turn")
        c = msg.get("cell")
        if t != "fire" or isinstance(c, bool) or not isinstance(c, int) or not 0 <= c < N * N:
            raise GameError("Bad shot")
        if c in self.shots[uid]:
            raise GameError("You already fired there")
        self._fire(c)

    def _sunk(self, target, ship):
        return all(c in self.shots[self.other(target)] for c in ship)

    def _fire(self, c):
        uid = self.current()
        tgt = self.other(uid)
        ship = next((s for s in self.fleet[tgt] if c in s), None)
        res = "hit" if ship else "miss"
        self.shots[uid][c] = res
        sunk = ship if ship and self._sunk(tgt, ship) else None
        self.seq += 1
        self.last_shot = {"seq": self.seq, "uid": uid, "cell": c, "result": res, "sunk": sunk}
        if all(self._sunk(tgt, s) for s in self.fleet[tgt]):
            self.finished, self.winner = True, uid
        elif res == "miss":
            self.turn_idx ^= 1

    def auto_play(self):
        if self.finished:
            return
        if self.phase == "place":
            self.ready[self.current()] = True
            if all(self.ready.values()):
                self.phase = "battle"
            return
        uid = self.current()
        mine = self.shots[uid]
        hits = [c for c, r in mine.items() if r == "hit" and not self._sunk(self.other(uid), next(s for s in self.fleet[self.other(uid)] if c in s))]
        cand = []
        for h in hits:
            r, c = divmod(h, N)
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                rr, cc = r + dr, c + dc
                if 0 <= rr < N and 0 <= cc < N and rr * N + cc not in mine:
                    cand.append(rr * N + cc)
        if not cand:
            cand = [i for i in range(N * N) if i not in mine and ((i // N + i % N) % 2 == 0)] or [i for i in range(N * N) if i not in mine]
        self._fire(self.rng.choice(cand))

    def remove_player(self, uid):
        if uid not in self.fleet or self.finished:
            return
        self.finished, self.winner = True, self.other(uid)

    def public_state(self):  # spectators see shots only
        return {"kind": "battleship", "n": N, "fleet": FLEET, "phase": self.phase, "turn": self.current(),
                "players": [{"uid": u, "ready": self.ready[u]} for u in self.players],
                "shots": {str(u): self.shots[u] for u in self.players}, "last_shot": self.last_shot,
                "winner": self.winner, "draw": self.draw, "mine": None, "sunk": {}}

    def view(self, uid):
        st = self.public_state()
        sunk = {}
        for u in self.players:  # fleets that are fully sunk are revealed to everyone
            sunk[str(u)] = [s for s in self.fleet[u] if self._sunk(u, s)]
        st["sunk"] = sunk
        if uid in self.fleet:
            st["mine"] = self.fleet[uid]
        if self.finished:
            st["reveal"] = {str(u): self.fleet[u] for u in self.players}
        return st

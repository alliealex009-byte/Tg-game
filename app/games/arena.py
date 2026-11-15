"""Arena Shooter: 2-4 fighters on a 9x9 map with crates for cover. Each turn: move, shoot along a line, or reload.
Shots hit the first fighter in line within range unless a crate blocks them. Last one standing wins."""
from __future__ import annotations

import random
from collections import deque

from .base import BaseGame, GameError

N = 9
DIRS = {"u": (-1, 0), "d": (1, 0), "l": (0, -1), "r": (0, 1)}
STARTS = [(0, 0), (N - 1, N - 1), (0, N - 1), (N - 1, 0)]
RANGE, DMG, MAX_AMMO, MAX_TURNS = 6, 30, 3, 140


class ArenaGame(BaseGame):
    name = "arena"
    min_players, max_players = 2, 4

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("Arena needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.pos = {u: STARTS[i] for i, u in enumerate(self.players)}
        self.hp = {u: 100 for u in self.players}
        self.ammo = {u: MAX_AMMO for u in self.players}
        self.kills = {u: 0 for u in self.players}
        self.dead, self.left = set(), set()
        crates = set()
        mid = N // 2
        while len(crates) < 18:
            a, b = self.rng.randrange(N), self.rng.randrange(N)
            if (a, b) in STARTS or abs(a - mid) + abs(b - mid) < 1 or any(abs(a - s[0]) + abs(b - s[1]) < 2 for s in STARTS):
                continue
            crates |= {(a, b), (N - 1 - a, N - 1 - b)}  # symmetric, so it is fair
        self.crates = crates
        self.packs = set()
        self.turn_idx, self.turns = 0, 0
        self.seq, self.last_event = 0, None
        self.winner, self.finished, self.draw = None, False, False
        self.winners = None

    def alive(self):
        return [u for u in self.players if u not in self.dead and u not in self.left]

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def _next(self):
        self.turns += 1
        al = self.alive()
        if len(al) <= 1:
            self.finished, self.winner = True, al[0] if al else None
            return
        if self.turns % 12 == 0 and len(self.packs) < 2:
            free = [(a, b) for a in range(N) for b in range(N) if (a, b) not in self.crates and (a, b) not in self.packs and (a, b) not in self.pos.values()]
            self.packs.add(self.rng.choice(free))
        if self.turns >= MAX_TURNS:
            self.finished = True
            best = max(self.hp[u] for u in al)
            top = [u for u in al if self.hp[u] == best]
            self.winner = top[0]
            if len(top) > 1:
                self.winners = top
            return
        for _ in range(len(self.players)):
            self.turn_idx = (self.turn_idx + 1) % len(self.players)
            if self.players[self.turn_idx] in al:
                break

    def _ev(self, uid, kind, **kw):
        self.seq += 1
        self.last_event = dict(kw, seq=self.seq, uid=uid, kind=kind, pos=list(self.pos[uid]))

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The match is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        t, d = msg.get("t"), msg.get("dir")
        if t == "move":
            if d not in DIRS:
                raise GameError("Pick a direction")
            r, c = self.pos[uid]
            p = (r + DIRS[d][0], c + DIRS[d][1])
            if not (0 <= p[0] < N and 0 <= p[1] < N) or p in self.crates:
                raise GameError("Blocked")
            if p in [self.pos[o] for o in self.alive() if o != uid]:
                raise GameError("Someone is standing there")
            self.pos[uid] = p
            kind = "move"
            if p in self.packs:
                self.packs.discard(p)
                self.hp[uid] = min(100, self.hp[uid] + 30)
                kind = "heal"
            self._ev(uid, kind, dir=d)
        elif t == "shoot":
            if d not in DIRS:
                raise GameError("Pick a direction")
            if self.ammo[uid] <= 0:
                raise GameError("Out of ammo, reload!")
            self.ammo[uid] -= 1
            r, c = self.pos[uid]
            hit, steps, killed = None, 0, False
            for i in range(1, RANGE + 1):
                p = (r + DIRS[d][0] * i, c + DIRS[d][1] * i)
                if not (0 <= p[0] < N and 0 <= p[1] < N) or p in self.crates:
                    break
                steps = i
                tgt = next((o for o in self.alive() if o != uid and self.pos[o] == p), None)
                if tgt is not None:
                    hit = tgt
                    break
            if hit is not None:
                self.hp[hit] -= DMG
                if self.hp[hit] <= 0:
                    self.hp[hit] = 0
                    self.dead.add(hit)
                    self.kills[uid] += 1
                    killed = True
            self._ev(uid, "shoot", dir=d, hit=hit, steps=steps, killed=killed)
        elif t == "reload":
            self.ammo[uid] = MAX_AMMO
            self._ev(uid, "reload")
        else:
            raise GameError("Unknown action")
        self._next()

    def _path_first(self, src, targets, blocked):
        q = deque([(src, None)])
        seen = {src}
        while q:
            p, first = q.popleft()
            if p in targets and first:
                return first
            for d, v in DIRS.items():
                n = (p[0] + v[0], p[1] + v[1])
                if 0 <= n[0] < N and 0 <= n[1] < N and n not in self.crates and n not in blocked and n not in seen:
                    seen.add(n)
                    q.append((n, first or d))
        return None

    def auto_play(self):
        if self.finished:
            return
        uid = self.current()
        r, c = self.pos[uid]
        foes = [o for o in self.alive() if o != uid]
        shots = []
        for d, v in DIRS.items():
            for i in range(1, RANGE + 1):
                p = (r + v[0] * i, c + v[1] * i)
                if not (0 <= p[0] < N and 0 <= p[1] < N) or p in self.crates:
                    break
                if any(self.pos[o] == p for o in foes):
                    shots.append(d)
                    break
        if shots and self.ammo[uid] > 0 and self.rng.random() < 0.9:
            return self.handle(uid, {"t": "shoot", "dir": shots[0]})
        if self.ammo[uid] == 0 and (not shots or self.rng.random() < 0.7):
            return self.handle(uid, {"t": "reload"})
        occupied = {self.pos[o] for o in foes}
        goal = set()  # cells from which a foe is in a clear line of fire
        for o in foes:
            fr, fc = self.pos[o]
            for v in DIRS.values():
                for i in range(1, RANGE + 1):
                    q = (fr + v[0] * i, fc + v[1] * i)
                    if not (0 <= q[0] < N and 0 <= q[1] < N) or q in self.crates:
                        break
                    goal.add(q)
        goal -= occupied
        if self.hp[uid] <= 40 and self.packs:
            goal = set(self.packs)
        d = self._path_first((r, c), goal, occupied) if goal else None
        if d is None or self.rng.random() < 0.1:
            opts = [k for k, v in DIRS.items() if 0 <= r + v[0] < N and 0 <= c + v[1] < N and (r + v[0], c + v[1]) not in self.crates and (r + v[0], c + v[1]) not in occupied]
            if not opts:
                return self.handle(uid, {"t": "reload"})
            d = self.rng.choice(opts)
        p = (r + DIRS[d][0], c + DIRS[d][1])
        if p in occupied:
            return self.handle(uid, {"t": "reload"})
        self.handle(uid, {"t": "move", "dir": d})

    def remove_player(self, uid):
        if uid not in self.hp or uid in self.left or self.finished:
            return
        was = self.current() == uid
        self.left.add(uid)
        al = self.alive()
        if len(al) <= 1:
            self.finished, self.winner = True, al[0] if al else None
        elif was:
            self._next()

    def public_state(self):
        return {"kind": "arena", "n": N, "range": RANGE, "crates": sorted(f"{a},{b}" for a, b in self.crates), "packs": sorted(f"{a},{b}" for a, b in self.packs),
                "players": [{"uid": u, "pos": list(self.pos[u]), "hp": self.hp[u], "ammo": self.ammo[u], "kills": self.kills[u],
                             "dead": u in self.dead, "left": u in self.left} for u in self.players],
                "max_ammo": MAX_AMMO, "turn": self.current(), "last_event": self.last_event, "winner": self.winner, "draw": self.draw}

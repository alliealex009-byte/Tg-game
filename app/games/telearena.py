"""TeleArena: 2-4 fighters on a 7x7 grid, everyone acts at once.
Actions: n/s/e/w step one tile, tp teleport to a random empty tile (then 2 rounds cooldown), hit strike all 8 neighbours for 1 damage.
Moves resolve first (clashes bounce back), then strikes. 3 HP each. Last fighter standing wins."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

N = 7
HP0 = 3
DIRS = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}
ACTS = set(DIRS) | {"tp", "hit"}
MAX_ROUNDS = 25


class TeleArenaGame(BaseGame):
    name = "telearena"
    min_players = 2
    max_players = 4
    phase_seconds = 8

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("TeleArena needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        corners = [(0, 0), (N - 1, N - 1), (N - 1, 0), (0, N - 1)]
        self.pos = {u: corners[i] for i, u in enumerate(self.players)}
        self.hp = {u: HP0 for u in self.players}
        self.cool = {u: 0 for u in self.players}
        self.picks = {}
        self.round = 0
        self.phase_id = 0
        self.seq = 0
        self.last_round = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self._bots()

    def _alive(self):
        return [u for u in self.players if self.hp[u] > 0]

    def _pending(self):
        return [u for u in self._alive() if u not in self.picks]

    def current(self):
        if self.finished:
            return None
        p = self._pending()
        return ([u for u in p if u > 0] or p or [None])[0]

    @staticmethod
    def _adj(a, b):
        return a != b and abs(a[0] - b[0]) <= 1 and abs(a[1] - b[1]) <= 1

    def _bot_pick(self, u):
        me = self.pos[u]
        foes = [self.pos[v] for v in self._alive() if v != u]
        if any(self._adj(me, f) for f in foes) and self.rng.random() < 0.7:
            return "hit"
        tgt = min(foes, key=lambda f: abs(f[0] - me[0]) + abs(f[1] - me[1]))
        opts = []
        for d, (dx, dy) in DIRS.items():
            nx, ny = me[0] + dx, me[1] + dy
            if 0 <= nx < N and 0 <= ny < N:
                opts.append((abs(nx - tgt[0]) + abs(ny - tgt[1]), d))
        opts.sort()
        if self.hp[u] == 1 and self.cool[u] == 0 and self.rng.random() < 0.5:
            return "tp"
        return opts[0][1] if self.rng.random() < 0.8 else self.rng.choice(opts)[1]

    def _bots(self):
        while not self.finished:
            for u in self._pending():
                if u < 0:
                    self.picks[u] = self._bot_pick(u)
            if self._pending():
                return
            self._resolve()

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The fight is over")
        if uid not in self.players or self.hp[uid] <= 0:
            raise GameError("You are not fighting")
        a = msg.get("a")
        if msg.get("t") != "act" or a not in ACTS:
            raise GameError("Unknown action")
        if uid in self.picks:
            raise GameError("Already locked in")
        if a == "tp" and self.cool[uid] > 0:
            raise GameError("Teleport is recharging")
        if a in DIRS:
            dx, dy = DIRS[a]
            x, y = self.pos[uid][0] + dx, self.pos[uid][1] + dy
            if not (0 <= x < N and 0 <= y < N):
                raise GameError("That's the arena wall")
        self.picks[uid] = a
        self._bots()

    def auto_play(self):
        if self.finished:
            return
        for u in self._pending():
            self.picks[u] = self._bot_pick(u) if u < 0 else "hit"
        self._resolve()
        self._bots()

    def _resolve(self):
        alive = self._alive()
        old = dict(self.pos)
        want = {}
        events = []
        taken = set()
        for u in alive:
            a = self.picks.get(u, "hit")
            if a in DIRS:
                x, y = old[u][0] + DIRS[a][0], old[u][1] + DIRS[a][1]
                want[u] = (x, y) if 0 <= x < N and 0 <= y < N else old[u]
            else:
                want[u] = old[u]
        for u in alive:
            if self.cool[u] > 0:
                self.cool[u] -= 1
        # teleports land first on random empty tiles
        occupied = {want[u] for u in alive if self.picks.get(u) != "tp"}
        for u in alive:
            if self.picks.get(u) == "tp":
                free = [(x, y) for x in range(N) for y in range(N) if (x, y) not in occupied and (x, y) not in taken]
                want[u] = self.rng.choice(free) if free else old[u]
                taken.add(want[u])
                occupied.add(want[u])
                self.cool[u] = 2
                events.append({"uid": u, "e": "tp"})
        # step clashes: two on the same tile, or moving into a tile someone holds, bounce back
        cnt = {}
        for u in alive:
            cnt[want[u]] = cnt.get(want[u], 0) + 1
        for u in alive:
            if self.picks.get(u) in DIRS and (cnt[want[u]] > 1 or any(v != u and want[u] == old[v] and want[v] == old[v] for v in alive)):
                want[u] = old[u]
                events.append({"uid": u, "e": "bump"})
        self.pos = {u: want[u] for u in alive} | {u: self.pos[u] for u in self.players if u not in alive}
        hits = {}
        for u in alive:
            if self.picks.get(u) == "hit":
                events.append({"uid": u, "e": "hit"})
                for v in alive:
                    if v != u and self._adj(self.pos[u], self.pos[v]):
                        hits[v] = hits.get(v, 0) + 1
        for v, d in hits.items():
            self.hp[v] = max(0, self.hp[v] - d)
        self.round += 1
        self.seq += 1
        self.phase_id += 1
        self.last_round = {"seq": self.seq, "round": self.round, "acts": dict(self.picks), "hits": hits, "events": events}
        self.picks = {}
        left = self._alive()
        if len(left) <= 1:
            self.finished = True
            if left:
                self.winner = left[0]
            else:
                self.draw = True
        elif self.round >= MAX_ROUNDS:
            self.finished = True
            top = max(self.hp[u] for u in left)
            lead = [u for u in left if self.hp[u] == top]
            if len(lead) == 1:
                self.winner = lead[0]
            else:
                self.draw = True

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.hp[uid] = 0
        self.picks.pop(uid, None)
        left = self._alive()
        if len(left) <= 1 or all(u < 0 for u in left):
            self.finished = True
            self.winner = left[0] if left else None
            return
        self._bots()

    def public_state(self):
        return {"kind": "telearena", "n": N, "round": self.round,
                "players": [{"uid": u, "x": self.pos[u][0], "y": self.pos[u][1], "hp": self.hp[u], "cool": self.cool[u]} for u in self.players],
                "picked": {u: u in self.picks for u in self.players}, "turn": self.current(),
                "last_round": self.last_round, "winner": self.winner, "draw": self.draw}

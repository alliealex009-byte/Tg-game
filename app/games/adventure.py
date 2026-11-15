"""Adventure Quest: 2-4 explorers race through a dungeon. Find the key, beat monsters, dodge hidden traps and reach the exit.
Fights are decided by a dice roll (d6 + your sword bonus against the monster's power)."""
from __future__ import annotations

import random
from collections import deque

from .base import BaseGame, GameError

N = 9
DIRS = {"u": (-1, 0), "d": (1, 0), "l": (0, -1), "r": (0, 1)}
STARTS = [(0, 0), (0, N - 1), (N - 1, 0), (N - 1, N - 1)]
MAX_TURNS = 160


def _bfs(walls, src, blocked=()):
    dist = {src: 0}
    q = deque([src])
    while q:
        r, c = q.popleft()
        for dr, dc in DIRS.values():
            nr, nc = r + dr, c + dc
            if 0 <= nr < N and 0 <= nc < N and (nr, nc) not in walls and (nr, nc) not in dist and (nr, nc) not in blocked:
                dist[(nr, nc)] = dist[(r, c)] + 1
                q.append((nr, nc))
    return dist


class AdventureGame(BaseGame):
    name = "adventure"
    min_players, max_players = 2, 4

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("Adventure needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self._gen()
        self.pos = {u: STARTS[i] for i, u in enumerate(self.players)}
        self.hp = {u: 5 for u in self.players}
        self.atk = {u: 0 for u in self.players}
        self.score = {u: 0 for u in self.players}
        self.has_key = {u: False for u in self.players}
        self.left = set()
        self.turn_idx, self.turns = 0, 0
        self.seq, self.last_event = 0, None
        self.winner, self.finished, self.draw = None, False, False
        self.winners = None

    def _gen(self):
        r = self.rng
        while True:
            walls = {(a, b) for a in range(N) for b in range(N) if r.random() < 0.15}
            free = [(a, b) for a in range(N) for b in range(N) if (a, b) not in walls]
            for s in STARTS:
                walls.discard(s)
            d = _bfs(walls, (0, 0))
            if all(s in d for s in STARTS):
                reach = [p for p in d if p not in STARTS and d[p] > 3]
                if len(reach) > 24:
                    break
        r.shuffle(reach)
        far = max(reach, key=lambda p: d[p])
        reach.remove(far)
        self.walls = walls
        self.items = {far: "E"}
        key_spot = reach.pop(0)
        self.items[key_spot] = "K"
        for kind, n in (("T", 6), ("H", 3), ("S", 2), ("X", 4), ("M", 4)):
            for _ in range(n):
                self.items[reach.pop()] = kind
        self.monster = {p: r.choice([3, 4, 5]) for p, k in self.items.items() if k == "M"}
        self.revealed = set()

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def _next(self):
        self.turns += 1
        for _ in range(len(self.players)):
            self.turn_idx = (self.turn_idx + 1) % len(self.players)
            if self.players[self.turn_idx] not in self.left:
                break
        if self.turns >= MAX_TURNS and not self.finished:
            self.finished = True
            best = max(self.score[u] for u in self.players if u not in self.left)
            top = [u for u in self.players if u not in self.left and self.score[u] == best]
            if len(top) == 1:
                self.winner = top[0]
            else:
                self.winners, self.winner = top, top[0]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The quest is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        d = msg.get("dir")
        if msg.get("t") != "move" or d not in DIRS:
            raise GameError("Pick a direction")
        r, c = self.pos[uid]
        nr, nc = r + DIRS[d][0], c + DIRS[d][1]
        if not (0 <= nr < N and 0 <= nc < N) or (nr, nc) in self.walls:
            raise GameError("A wall blocks the way")
        if any(p == (nr, nc) for o, p in self.pos.items() if o != uid and o not in self.left):
            raise GameError("Another explorer is there")
        self._step(uid, (nr, nc))

    def _ev(self, uid, kind, **kw):
        self.seq += 1
        self.last_event = dict(kw, seq=self.seq, uid=uid, kind=kind, pos=list(self.pos[uid]))

    def _step(self, uid, p):
        it = self.items.get(p)
        kw = {}
        kind = "move"
        if it == "M":
            power = self.monster[p]
            roll = self.rng.randint(1, 6)
            total = roll + self.atk[uid]
            win = total >= power
            kw = {"roll": roll, "power": power, "win": win, "at": list(p)}
            if win:
                del self.items[p]
                self.monster.pop(p)
                self.score[uid] += 2
                self.pos[uid] = p
                kind = "fight_win"
            else:
                self.hp[uid] -= 1
                kind = "fight_lose"
        else:
            self.pos[uid] = p
            if it == "T":
                self.score[uid] += 1
                del self.items[p]
                kind = "treasure"
            elif it == "H":
                self.hp[uid] = min(6, self.hp[uid] + 1)
                del self.items[p]
                kind = "heal"
            elif it == "S":
                self.atk[uid] += 1
                del self.items[p]
                kind = "sword"
            elif it == "K":
                self.has_key[uid] = True
                del self.items[p]
                kind = "key"
            elif it == "X":
                self.hp[uid] -= 1
                self.revealed.add(p)
                self.items[p] = "x"
                kind = "trap"
            elif it == "E" and self.has_key[uid]:
                self._ev(uid, "exit")
                self.finished, self.winner = True, uid
                return
            elif it == "E":
                kind = "exit_locked"
        if self.hp[uid] <= 0:
            if self.has_key[uid]:
                self.items[self.pos[uid]] = "K"  # the key drops where you fell
            self.has_key[uid] = False
            kw["died_at"] = list(self.pos[uid])
            self.pos[uid] = STARTS[self.players.index(uid)]
            self.hp[uid] = 3
            kind = "died"
        self._ev(uid, kind, **kw)
        self._next()

    def auto_play(self):
        if self.finished:
            return
        uid = self.current()
        src = self.pos[uid]
        others = {p for o, p in self.pos.items() if o != uid}
        want = [p for p, k in self.items.items() if k in ("E",)] if self.has_key[uid] else [p for p, k in self.items.items() if k == "K"]
        if not want or self.rng.random() < 0.0:
            want = [p for p, k in self.items.items() if k in ("T", "H", "S")]
        dist = _bfs(self.walls, src, others | {p for p in self.revealed})
        reach = [p for p in want if p in dist]
        if self.hp[uid] <= 2:
            heals = [p for p, k in self.items.items() if k == "H" and p in dist]
            reach = heals or reach
        moves = [(d, (src[0] + v[0], src[1] + v[1])) for d, v in DIRS.items()
                 if 0 <= src[0] + v[0] < N and 0 <= src[1] + v[1] < N and (src[0] + v[0], src[1] + v[1]) not in self.walls and (src[0] + v[0], src[1] + v[1]) not in others]
        if not moves:
            return self._next()
        if reach:
            tgt = min(reach, key=lambda p: dist[p])
            back = _bfs(self.walls, tgt, others | self.revealed)
            moves.sort(key=lambda m: back.get(m[1], 999) + self.rng.random() * 0.5)
        else:
            self.rng.shuffle(moves)
        self.handle(uid, {"t": "move", "dir": moves[0][0]})

    def remove_player(self, uid):
        if uid not in self.hp or uid in self.left or self.finished:
            return
        was = self.current() == uid
        self.left.add(uid)
        act = [u for u in self.players if u not in self.left]
        if len(act) <= 1:
            self.finished, self.winner = True, act[0] if act else None
        elif was:
            self._next()

    def public_state(self):
        vis = {f"{p[0]},{p[1]}": ("." if k == "X" else k) for p, k in self.items.items()}
        mons = {f"{p[0]},{p[1]}": v for p, v in self.monster.items()}
        return {"kind": "adventure", "n": N, "walls": sorted(f"{a},{b}" for a, b in self.walls), "items": vis, "monsters": mons,
                "players": [{"uid": u, "pos": list(self.pos[u]), "hp": self.hp[u], "atk": self.atk[u], "score": self.score[u],
                             "key": self.has_key[u], "left": u in self.left} for u in self.players],
                "turn": self.current(), "last_event": self.last_event, "turns_left": MAX_TURNS - self.turns,
                "winner": self.winner, "draw": self.draw}

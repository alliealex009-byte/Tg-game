"""Tank Duel: artillery on destructible hills. Pick an angle and power; wind pushes the shell. 100 HP each."""
from __future__ import annotations

import math
import random

from .base import BaseGame, GameError

W = 36
G = 10.0
HP0 = 100


class TankGame(BaseGame):
    name = "tank"
    min_players = 2
    max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Tank Duel needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        r = self.rng
        ph = r.uniform(0, 6.28)
        self.h = [round(7 + 3 * math.sin(i / 4.5 + ph) + 1.5 * math.sin(i / 2.1 + ph * 2), 2) for i in range(W)]
        self.x = {self.players[0]: 4, self.players[1]: W - 5}
        self.hp = {u: HP0 for u in self.players}
        self.wind = r.randint(-3, 3)
        self.turn_idx = 0
        self.seq = 0
        self.last_shot = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self.shots = 0

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def _ground(self, x):
        i = min(W - 1, max(0, int(round(x))))
        return self.h[i]

    def _sim(self, uid, angle, power):
        d = 1 if uid == self.players[0] else -1
        a = math.radians(angle)
        v = power * 0.2
        px = self.x[uid] + 0.0
        py = self._ground(px) + 1.2
        vx, vy = d * v * math.cos(a), v * math.sin(a)
        path = [(round(px, 2), round(py, 2))]
        foe = self.players[1 - self.players.index(uid)]
        t = 0.0
        hit = None
        while t < 12:
            t += 0.05
            vx += self.wind * 0.05
            vy -= G * 0.05
            px += vx * 0.05
            py += vy * 0.05
            if int(t * 20) % 2 == 0:
                path.append((round(px, 2), round(py, 2)))
            if px < -2 or px > W + 1:
                hit = ("out", px, py)
                break
            if abs(px - self.x[foe]) < 1.3 and self._ground(self.x[foe]) - 0.2 <= py <= self._ground(self.x[foe]) + 2.2:
                hit = ("tank", px, py)
                break
            if t > 0.3 and py <= self._ground(px):
                hit = ("ground", px, py)
                break
        if hit is None:
            hit = ("out", px, py)
        path.append((round(hit[1], 2), round(max(hit[2], 0), 2)))
        return path, hit

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The battle is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        if msg.get("t") != "fire":
            raise GameError("Unknown action")
        a, p = msg.get("angle"), msg.get("power")
        for v in (a, p):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise GameError("Bad shot")
        self._fire(uid, max(10, min(80, float(a))), max(20, min(100, float(p))))

    def _fire(self, uid, angle, power):
        foe = self.players[1 - self.players.index(uid)]
        path, (kind, hx, hy) = self._sim(uid, angle, power)
        dmg = {uid: 0, foe: 0}
        for u in self.players:
            dist = math.hypot(hx - self.x[u], hy - (self._ground(self.x[u]) + 1))
            if kind != "out" and dist < 4.5:
                dmg[u] = max(10, round(60 * (1 - dist / 4.5)))
        if kind != "out":
            for i in range(W):                      # crater
                dx = abs(i - hx)
                if dx < 2.6:
                    self.h[i] = round(max(1.0, self.h[i] - (2.6 - dx) * 1.1), 2)
        for u in self.players:
            self.hp[u] = max(0, self.hp[u] - dmg[u])
        self.shots += 1
        self.seq += 1
        self.last_shot = {"seq": self.seq, "uid": uid, "angle": angle, "power": power, "path": path, "kind": kind,
                          "impact": [round(hx, 2), round(max(hy, 0), 2)], "dmg": dmg}
        dead = [u for u in self.players if self.hp[u] <= 0]
        if dead:
            self.finished = True
            if len(dead) == 2:
                self.draw = True
            else:
                self.winner = foe if dead[0] == uid else uid
            return
        if self.shots >= 30:
            self.finished = True
            a, b = self.players
            self.winner = a if self.hp[a] > self.hp[b] else b if self.hp[b] > self.hp[a] else None
            self.draw = self.winner is None
            return
        self.wind = max(-4, min(4, self.wind + self.rng.choice((-1, 0, 1))))
        self.turn_idx = 1 - self.turn_idx

    def _aim(self, uid):
        foe = self.players[1 - self.players.index(uid)]
        best = None
        for ang in range(25, 76, 5):
            for pw in range(35, 101, 5):
                _, (k, hx, hy) = self._sim(uid, ang, pw)
                d = math.hypot(hx - self.x[foe], hy - (self._ground(self.x[foe]) + 1)) + (0 if k != "out" else 20)
                if best is None or d < best[0]:
                    best = (d, ang, pw)
        _, ang, pw = best
        return ang + self.rng.randint(-4, 4), pw + self.rng.randint(-6, 6)

    def auto_play(self):
        if self.finished:
            return
        u = self.current()
        if u < 0 or self.rng.random() < 0.6:
            a, p = self._aim(u)
        else:
            a, p = self.rng.randint(30, 60), self.rng.randint(50, 90)
        self._fire(u, max(10, min(80, a)), max(20, min(100, p)))

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        return {"kind": "tank", "w": W, "h": self.h, "wind": self.wind,
                "players": [{"uid": u, "x": self.x[u], "hp": self.hp[u]} for u in self.players],
                "turn": self.current(), "last_shot": self.last_shot, "winner": self.winner, "draw": self.draw}

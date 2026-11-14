"""Carrom with server-side physics (simplified rules).

* Board is 800x800 units. Pockets are the four corners. Player 1 = white coins (shoots from the
  bottom), player 2 = black coins (shoots from the top). 9 white, 9 black, 1 queen.
* A turn: place the striker on your baseline, aim, choose power. The server simulates the whole shot
  and sends the recorded frames, so every client plays back the identical animation.
* Scoring: own coin +1, queen +3 (no cover rule), an opponent's coin you pocket scores +1 for THEM.
  Pocket one of your own coins (or the queen) to shoot again. Pocketing the striker is a foul (turn lost).
* First to 11 points wins (21 points exist in total, so there are no ties on a cleared board).
"""
from __future__ import annotations

import math
import random

from .base import BaseGame, GameError

SIZE = 800.0
CR, SR = 17.0, 21.0                 # coin / striker radius
POCKET_R = 40.0
POCKETS = ((0.0, 0.0), (SIZE, 0.0), (0.0, SIZE), (SIZE, SIZE))
BASE_Y = (690.0, 110.0)             # striker baseline for player index 0 / 1
X_MIN, X_MAX = 160.0, 640.0
MAX_V = 26.0                        # striker speed at full power (units per tick)
FRICTION = 0.982                    # per tick
WALL_E, COIN_E = 0.75, 0.92
SUB = 2                             # physics sub-steps per tick (stops fast coins tunnelling)
MIN_SPEED = 0.12
MAX_TICKS = 700
FRAME_EVERY = 4                     # record every 4th tick (15 fps playback)
FPS = 60 / FRAME_EVERY
WIN_SCORE = 11
MAX_SHOTS = 150
M_COIN, M_STRIKER = 1.0, 2.2


def initial_coins():
    coins = [{"id": 0, "kind": "q", "x": SIZE / 2, "y": SIZE / 2}]
    cid = 1
    for k in range(6):  # inner ring, alternating
        a = math.radians(60 * k)
        coins.append({"id": cid, "kind": "w" if k % 2 == 0 else "b", "x": 400 + 36 * math.cos(a), "y": 400 + 36 * math.sin(a)})
        cid += 1
    for k in range(12):  # outer ring, alternating
        a = math.radians(30 * k)
        coins.append({"id": cid, "kind": "w" if k % 2 == 0 else "b", "x": 400 + 72 * math.cos(a), "y": 400 + 72 * math.sin(a)})
        cid += 1
    return coins


def simulate(bodies):
    """bodies: list of [x, y, vx, vy, radius, mass]. Returns (frames, out, final).

    frames: flat int lists [x0, y0, x1, y1, ...] sampled every FRAME_EVERY ticks (frame 0 = start).
    out:    [[body_index, frame_index], ...] bodies that fell into a pocket (hidden from that frame on).
    final:  (xs, ys, alive) positions after the shot.
    """
    n = len(bodies)
    x = [b[0] for b in bodies]
    y = [b[1] for b in bodies]
    vx = [b[2] for b in bodies]
    vy = [b[3] for b in bodies]
    rad = [b[4] for b in bodies]
    inv = [1.0 / b[5] for b in bodies]
    alive = [True] * n
    dt = 1.0 / SUB
    fr = FRICTION ** dt
    pr2 = POCKET_R * POCKET_R
    min2 = MIN_SPEED * MIN_SPEED

    def snap():
        out_ = []
        for i in range(n):
            out_.append(int(round(x[i])))
            out_.append(int(round(y[i])))
        return out_

    frames = [snap()]
    out = []
    for tick in range(MAX_TICKS):
        moving = False
        for _ in range(SUB):
            idx = [i for i in range(n) if alive[i]]
            for i in idx:
                x[i] += vx[i] * dt
                y[i] += vy[i] * dt
                r = rad[i]
                if x[i] < r:
                    x[i], vx[i] = r, abs(vx[i]) * WALL_E
                elif x[i] > SIZE - r:
                    x[i], vx[i] = SIZE - r, -abs(vx[i]) * WALL_E
                if y[i] < r:
                    y[i], vy[i] = r, abs(vy[i]) * WALL_E
                elif y[i] > SIZE - r:
                    y[i], vy[i] = SIZE - r, -abs(vy[i]) * WALL_E
            for i in idx:
                for px, py in POCKETS:
                    if (x[i] - px) ** 2 + (y[i] - py) ** 2 < pr2:
                        alive[i] = False
                        vx[i] = vy[i] = 0.0
                        x[i], y[i] = px, py
                        out.append([i, len(frames)])
                        break
            idx = [i for i in idx if alive[i]]
            m = len(idx)
            for a in range(m):
                ia = idx[a]
                for b in range(a + 1, m):
                    ib = idx[b]
                    if not (vx[ia] or vy[ia] or vx[ib] or vy[ib]):
                        continue
                    dx, dy = x[ib] - x[ia], y[ib] - y[ia]
                    rr = rad[ia] + rad[ib]
                    d2 = dx * dx + dy * dy
                    if d2 >= rr * rr or d2 == 0.0:
                        continue
                    d = math.sqrt(d2)
                    nx, ny = dx / d, dy / d
                    ima, imb = inv[ia], inv[ib]
                    pen = rr - d
                    tot = ima + imb
                    x[ia] -= nx * pen * ima / tot
                    y[ia] -= ny * pen * ima / tot
                    x[ib] += nx * pen * imb / tot
                    y[ib] += ny * pen * imb / tot
                    rv = (vx[ia] - vx[ib]) * nx + (vy[ia] - vy[ib]) * ny
                    if rv > 0:
                        j = (1 + COIN_E) * rv / tot
                        vx[ia] -= j * ima * nx
                        vy[ia] -= j * ima * ny
                        vx[ib] += j * imb * nx
                        vy[ib] += j * imb * ny
            moving = False
            for i in idx:
                vx[i] *= fr
                vy[i] *= fr
                if vx[i] * vx[i] + vy[i] * vy[i] < min2:
                    vx[i] = vy[i] = 0.0
                else:
                    moving = True
        if (tick + 1) % FRAME_EVERY == 0:
            frames.append(snap())
        if not moving:
            break
    frames.append(snap())
    return frames, out, (x, y, alive)


class CarromGame(BaseGame):
    name = "carrom"
    min_players = 2
    max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Carrom needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.kind = {self.players[0]: "w", self.players[1]: "b"}
        self.coins = initial_coins()
        self.scores = {u: 0 for u in self.players}
        self.turn_idx = 0
        self.shots = 0
        self.seq = 0
        self.last_shot = None
        self.winner = None
        self.finished = False
        self.draw = False

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def _blocked(self, sx, sy):
        return any((c["x"] - sx) ** 2 + (c["y"] - sy) ** 2 < (SR + CR + 1) ** 2 for c in self.coins)

    @staticmethod
    def _num(v, name):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise GameError(f"Bad {name}")
        return float(v)

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        if msg.get("t") != "shoot":
            raise GameError("Unknown action")
        x = min(X_MAX, max(X_MIN, self._num(msg.get("x"), "position")))
        angle = self._num(msg.get("angle"), "angle")
        power = min(1.0, max(0.05, self._num(msg.get("power"), "power")))
        if self._blocked(x, BASE_Y[self.turn_idx]):
            raise GameError("A coin is in the way, slide the striker elsewhere")
        self._shoot(x, angle, power)

    def _shoot(self, sx, angle, power):
        uid = self.current()
        sy = BASE_Y[self.turn_idx]
        ids = [c["id"] for c in self.coins]
        bodies = [[sx, sy, MAX_V * power * math.cos(angle), MAX_V * power * math.sin(angle), SR, M_STRIKER]]
        bodies += [[c["x"], c["y"], 0.0, 0.0, CR, M_COIN] for c in self.coins]
        frames, out, (xs, ys, alive) = simulate(bodies)

        opp = self.players[1 - self.turn_idx]
        own_kind = self.kind[uid]
        striker_in = not alive[0]
        keep_turn = False
        survivors = []
        for k, c in enumerate(self.coins, start=1):
            if alive[k]:
                c["x"], c["y"] = xs[k], ys[k]
                survivors.append(c)
                continue
            if c["kind"] == "q":
                self.scores[uid] += 3
                keep_turn = True
            elif c["kind"] == own_kind:
                self.scores[uid] += 1
                keep_turn = True
            else:
                self.scores[opp] += 1
        self.coins = survivors
        self.shots += 1
        self.seq += 1
        self.last_shot = {
            "seq": self.seq, "uid": uid, "ids": ids, "frames": frames, "out": out,
            "striker_in": striker_in, "fps": FPS,
        }
        top = max(self.scores.values())
        if top >= WIN_SCORE or not self.coins or self.shots >= MAX_SHOTS:
            self.finished = True
            a, b = (self.scores[u] for u in self.players)
            if a == b:
                self.draw = True
            else:
                self.winner = self.players[0] if a > b else self.players[1]
            return
        if striker_in or not keep_turn:
            self.turn_idx = 1 - self.turn_idx

    def _pass_turn(self):
        self.seq += 1
        self.last_shot = None
        self.turn_idx = 1 - self.turn_idx

    def auto_play(self):
        """A simple computer player: line up the best straight shot at one of its coins."""
        if self.finished:
            return
        uid = self.current()
        own = self.kind[uid]
        sy = BASE_Y[self.turn_idx]
        xs_try = [200, 260, 320, 380, 440, 500, 560, 620]
        self.rng.shuffle(xs_try)
        xs_try = [x for x in xs_try if not self._blocked(x, sy)]
        if not xs_try:
            return self._pass_turn()
        targets = [c for c in self.coins if c["kind"] == own] or [c for c in self.coins if c["kind"] == "q"] or self.coins
        best = None
        for sx in xs_try:
            for c in targets:
                for px, py in POCKETS:
                    dx, dy = px - c["x"], py - c["y"]
                    d = math.hypot(dx, dy) or 1.0
                    gx = c["x"] - dx / d * (SR + CR)
                    gy = c["y"] - dy / d * (SR + CR)
                    vx, vy = gx - sx, gy - sy
                    dist = math.hypot(vx, vy) or 1.0
                    cut = (vx * dx + vy * dy) / (dist * d)  # 1.0 = dead straight into the pocket
                    if cut < 0.55:
                        continue
                    score = cut * 2 - dist / 1500 + self.rng.random() * 0.3
                    if best is None or score > best[0]:
                        best = (score, sx, math.atan2(vy, vx), min(1.0, 0.4 + (dist + d) / 1100))
        if best is None:
            sx = xs_try[0]
            ang = math.atan2(SIZE / 2 - sy, SIZE / 2 - sx + self.rng.uniform(-80, 80))
            best = (0, sx, ang, 0.7)
        self._shoot(best[1], best[2], best[3])

    def remove_player(self, uid):
        if uid not in self.scores or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        return {
            "kind": "carrom",
            "players": [{"uid": u, "kind": self.kind[u], "score": self.scores[u]} for u in self.players],
            "coins": [{"id": c["id"], "kind": c["kind"], "x": round(c["x"], 1), "y": round(c["y"], 1)} for c in self.coins],
            "turn": self.current(),
            "base_y": list(BASE_Y),
            "last_shot": self.last_shot,
            "winner": self.winner,
            "draw": self.draw,
        }

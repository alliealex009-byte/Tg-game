"""Ludo engine (server-authoritative).

Board model
-----------
* The shared track has 52 cells, indexed 0..51 clockwise. Seat s enters the track at START[s].
* A token's position is *relative to its own start*:
      -1        in the yard
      0..50     on the shared track (absolute cell = (START[seat] + pos) % 52)
      51..55    in its private home column
      56        home (finished)
* Seats: 0 red, 1 green, 2 yellow, 3 blue (clockwise). Two players sit opposite each other.

Rules
-----
* A 6 is needed to leave the yard.
* A 6, a capture, or reaching home gives an extra roll. Three 6s in a row forfeit the turn.
* Landing on an opponent on a non-safe cell sends it back to the yard.
* Safe cells: every start cell and every star cell (SAFE_ABS).
* A token needs an exact roll to reach home. First player to bring all 4 tokens home wins.
"""
from __future__ import annotations

import random

from .base import BaseGame, GameError

TRACK_LEN = 52
START = (0, 13, 26, 39)
SAFE_ABS = frozenset({0, 8, 13, 21, 26, 34, 39, 47})
YARD, TRACK_END, HOME = -1, 50, 56
SEATS_BY_COUNT = {2: (0, 2), 3: (0, 1, 2), 4: (0, 1, 2, 3)}


class LudoGame(BaseGame):
    name = "ludo"
    min_players = 2
    max_players = 4

    def __init__(self, players, rng=None):
        n = len(players)
        if n not in SEATS_BY_COUNT:
            raise ValueError("Ludo needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.seat = {u: s for u, s in zip(self.players, SEATS_BY_COUNT[n])}
        self.tokens = {u: [YARD] * 4 for u in self.players}
        self.left = set()
        self.turn_idx = 0
        self.phase = "roll"  # "roll" -> "move" -> back to "roll"
        self.dice = None
        self.movable = []
        self.sixes = 0
        self.seq = 0
        self.last_roll = None
        self.last_move = None
        self.winner = None
        self.finished = False
        self.draw = False

    # ---------- helpers ----------
    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def active(self):
        return [u for u in self.players if u not in self.left]

    def _movable(self, uid, roll):
        out = []
        for i, p in enumerate(self.tokens[uid]):
            if p == HOME:
                continue
            if p == YARD:
                if roll == 6:
                    out.append(i)
            elif p + roll <= HOME:
                out.append(i)
        return out

    def _distinct(self, uid):
        """Movable tokens that lead to genuinely different outcomes (yard tokens are interchangeable)."""
        seen, out = set(), []
        for i in self.movable:
            p = self.tokens[uid][i]
            if p in seen:
                continue
            seen.add(p)
            out.append(i)
        return out

    def _next_turn(self):
        n = len(self.players)
        for _ in range(n):
            self.turn_idx = (self.turn_idx + 1) % n
            if self.players[self.turn_idx] not in self.left:
                break
        self.phase, self.dice, self.movable, self.sixes = "roll", None, [], 0

    # ---------- actions ----------
    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        t = msg.get("t")
        if t == "roll":
            if self.phase != "roll":
                raise GameError("Move a token first")
            self._roll()
        elif t == "move":
            if self.phase != "move":
                raise GameError("Roll the dice first")
            ti = msg.get("token")
            if isinstance(ti, bool) or not isinstance(ti, int) or ti not in self.movable:
                raise GameError("That token can't move")
            self._move(ti)
        else:
            raise GameError("Unknown action")

    def _roll(self, forced=None):
        uid = self.current()
        v = forced if forced else self.rng.randint(1, 6)
        self.seq += 1
        self.last_roll = {"uid": uid, "value": v, "seq": self.seq}
        self.last_move = None
        self.dice = v
        self.sixes = self.sixes + 1 if v == 6 else 0
        if self.sixes >= 3:  # third six in a row: turn is lost
            self._next_turn()
            return
        self.movable = self._movable(uid, v)
        if not self.movable:
            self._next_turn()
            return
        choices = self._distinct(uid)
        if len(choices) == 1:  # only one sensible move: play it automatically
            self._move(choices[0])
        else:
            self.phase = "move"

    def _move(self, ti):
        uid = self.current()
        seat = self.seat[uid]
        roll = self.dice
        frm = self.tokens[uid][ti]
        to = 0 if frm == YARD else frm + roll
        self.tokens[uid][ti] = to

        captured = []
        if 0 <= to <= TRACK_END:
            a = (START[seat] + to) % TRACK_LEN
            if a not in SAFE_ABS:
                for ou in self.active():
                    if ou == uid:
                        continue
                    oseat = self.seat[ou]
                    for oi, op in enumerate(self.tokens[ou]):
                        if 0 <= op <= TRACK_END and (START[oseat] + op) % TRACK_LEN == a:
                            self.tokens[ou][oi] = YARD
                            captured.append({"uid": ou, "token": oi})

        self.seq += 1
        self.last_move = {"uid": uid, "token": ti, "from": frm, "to": to, "captured": captured, "seq": self.seq}
        self.movable = []
        self.phase = "roll"
        self.dice = None

        if all(p == HOME for p in self.tokens[uid]):
            self.winner, self.finished = uid, True
            return
        extra = roll == 6 or bool(captured) or to == HOME
        if not extra:
            self._next_turn()

    # ---------- bots / timeouts ----------
    def auto_play(self):
        if self.finished:
            return
        if self.phase == "roll":
            self._roll()
        else:
            self._move(self.choose_token(self.current()))

    def _threatened(self, uid, a):
        """Is absolute cell `a` 1-6 steps in front of some opponent token (and not safe)?"""
        if a in SAFE_ABS:
            return False
        for ou in self.active():
            if ou == uid:
                continue
            for op in self.tokens[ou]:
                if 0 <= op <= TRACK_END:
                    oa = (START[self.seat[ou]] + op) % TRACK_LEN
                    if 1 <= (a - oa) % TRACK_LEN <= 6:
                        return True
        return False

    def _enemy_on(self, uid, a):
        for ou in self.active():
            if ou == uid:
                continue
            for op in self.tokens[ou]:
                if 0 <= op <= TRACK_END and (START[self.seat[ou]] + op) % TRACK_LEN == a:
                    return True
        return False

    def choose_token(self, uid):
        seat, roll = self.seat[uid], self.dice
        best, best_score = self.movable[0], float("-inf")
        for ti in self.movable:
            frm = self.tokens[uid][ti]
            to = 0 if frm == YARD else frm + roll
            score = to * 0.1
            if to == HOME:
                score += 100
            elif to > TRACK_END:
                score += 25
            else:
                a = (START[seat] + to) % TRACK_LEN
                if a in SAFE_ABS:
                    score += 20
                else:
                    if self._enemy_on(uid, a):
                        score += 60
                    if self._threatened(uid, a):
                        score -= 15
            if frm == YARD:
                score += 40
            elif 0 <= frm <= TRACK_END and self._threatened(uid, (START[seat] + frm) % TRACK_LEN):
                score += 15
            if score > best_score:
                best, best_score = ti, score
        return best

    def remove_player(self, uid):
        if uid not in self.seat or uid in self.left or self.finished:
            return
        self.left.add(uid)
        act = self.active()
        if len(act) <= 1:
            self.finished = True
            self.winner = act[0] if act else None
            return
        if self.current() == uid:
            self._next_turn()

    # ---------- view ----------
    def public_state(self):
        return {
            "kind": "ludo",
            "players": [
                {"uid": u, "seat": self.seat[u], "tokens": self.tokens[u], "left": u in self.left}
                for u in self.players
            ],
            "turn": self.current(),
            "phase": self.phase,
            "dice": self.dice,
            "movable": self.movable,
            "last_roll": self.last_roll,
            "last_move": self.last_move,
            "winner": self.winner,
        }

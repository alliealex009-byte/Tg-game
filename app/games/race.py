"""Brain races: Word Scramble and Math Duel. Everyone sees the same puzzle; the first correct answer scores the round."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

WORDS = ["planet", "jungle", "guitar", "bridge", "rocket", "garden", "pirate", "castle", "dragon", "monkey", "silver", "tomato",
         "window", "laptop", "cheese", "forest", "desert", "island", "camera", "doctor", "orange", "purple", "yellow", "school",
         "pencil", "winter", "summer", "market", "button", "candle", "dinner", "flower", "hammer", "jacket", "kitten", "magnet",
         "rabbit", "turtle", "wizard", "pillow", "ladder", "basket", "coffee", "mirror", "bottle", "spider"]


class RaceGame(BaseGame):
    min_players, max_players = 2, 4
    rounds = 5
    solve_p = 0.5   # chance a computer opponent solves a round nobody else cracked

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError(f"{self.name} needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.score = {u: 0 for u in self.players}
        self.left = set()
        self.round = 0
        self.seq, self.last_round, self.last_guess = 0, None, None
        self.winner, self.finished, self.draw = None, False, False
        self.winners = None
        self._new()

    def _live(self):
        return [u for u in self.players if u not in self.left]

    def current(self):
        if self.finished:
            return None
        live = self._live()
        return next((u for u in live if u > 0), live[0])

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid not in self.score or uid in self.left:
            raise GameError("You are not playing")
        txt = msg.get("text")
        if msg.get("t") != "guess" or not isinstance(txt, str) or not txt.strip() or len(txt) > 24:
            raise GameError("Type your answer")
        ok = self._check(txt.strip())
        self.seq += 1
        self.last_guess = {"seq": self.seq, "uid": uid, "ok": ok}
        if ok:
            self._end_round(uid)

    def _end_round(self, winner):
        if winner is not None:
            self.score[winner] += 1
        self.seq += 1
        self.last_round = {"seq": self.seq, "round": self.round + 1, "answer": self.answer, "winner": winner}
        self.round += 1
        if self.round >= self.rounds:
            self.finished = True
            pool = {u: s for u, s in self.score.items() if u not in self.left}
            best = max(pool.values())
            top = [u for u, s in pool.items() if s == best]
            if len(top) == 1:
                self.winner = top[0]
            elif len(top) == len(pool):
                self.draw = True
            else:
                self.winners, self.winner = top, top[0]
        else:
            self._new()

    def auto_play(self):
        if self.finished:
            return
        bots = [u for u in self._live() if u < 0]
        if bots and self.rng.random() < self.solve_p:
            return self._end_round(self.rng.choice(bots))
        self._end_round(None)

    def remove_player(self, uid):
        if uid not in self.score or uid in self.left or self.finished:
            return
        self.left.add(uid)
        act = self._live()
        if len(act) <= 1:
            self.finished, self.winner = True, act[0] if act else None

    def public_state(self):
        return {"kind": self.name, "rounds": self.rounds, "round": min(self.round + 1, self.rounds), "puzzle": self.puzzle,
                "players": [{"uid": u, "score": self.score[u], "left": u in self.left} for u in self.players],
                "turn": self.current(), "last_round": self.last_round, "last_guess": self.last_guess,
                "winner": self.winner, "draw": self.draw}


class ScrambleGame(RaceGame):
    name = "scramble"
    rounds = 5

    def _new(self):
        used = getattr(self, "used", set())
        w = self.rng.choice([x for x in WORDS if x not in used])
        self.used = used | {w}
        letters = list(w)
        for _ in range(20):
            self.rng.shuffle(letters)
            if "".join(letters) != w:
                break
        self.answer, self.puzzle = w, "".join(letters).upper()

    def _check(self, txt):
        return txt.lower() == self.answer


class MathGame(RaceGame):
    name = "mathduel"
    rounds = 8
    solve_p = 0.6

    def _new(self):
        r = self.rng
        k = r.choice("+-*")
        if k == "+":
            a, b = r.randint(12, 89), r.randint(12, 89)
            v = a + b
        elif k == "-":
            a, b = r.randint(40, 99), r.randint(11, 39)
            v = a - b
        else:
            a, b = r.randint(3, 13), r.randint(3, 12)
            v = a * b
        self.answer, self.puzzle = str(v), f"{a} {'×' if k == '*' else k} {b}"

    def _check(self, txt):
        return txt.strip() == self.answer

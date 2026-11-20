"""Mastermind duel: both players try to crack the SAME secret code (4 pegs, 6 colours, repeats allowed),
alternating guesses, 10 each. First to crack wins; if nobody does it is a draw."""
from __future__ import annotations

import itertools
import random

from .base import BaseGame, GameError

COLORS, LEN, MAX_GUESSES = 6, 4, 10


def score(secret, guess):
    black = sum(a == b for a, b in zip(secret, guess))
    common = sum(min(secret.count(c), guess.count(c)) for c in range(COLORS))
    return black, common - black


class MastermindGame(BaseGame):
    name = "mastermind"
    min_players = 2
    max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Mastermind needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.secret = [self.rng.randrange(COLORS) for _ in range(LEN)]
        self.guesses = {u: [] for u in self.players}
        self.turn = self.players[0]
        self.seq = 0
        self.last_guess = None
        self.winner = None
        self.finished = False
        self.draw = False

    def current(self):
        return None if self.finished else self.turn

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.turn:
            raise GameError("It's not your turn")
        if msg.get("t") != "guess":
            raise GameError("Unknown action")
        code = msg.get("code")
        if (not isinstance(code, list) or len(code) != LEN
                or any(isinstance(c, bool) or not isinstance(c, int) or not 0 <= c < COLORS for c in code)):
            raise GameError("Pick 4 colours")
        self._guess(uid, list(code))

    def _guess(self, uid, code):
        black, white = score(self.secret, code)
        self.guesses[uid].append({"code": code, "black": black, "white": white})
        self.seq += 1
        self.last_guess = {"seq": self.seq, "uid": uid, "n": len(self.guesses[uid]), "black": black, "white": white}
        if black == LEN:
            self.winner, self.finished = uid, True
            return
        other = next(u for u in self.players if u != uid)
        if all(len(g) >= MAX_GUESSES for g in self.guesses.values()):
            self.finished, self.draw = True, True
            return
        self.turn = other if len(self.guesses[other]) < MAX_GUESSES else uid

    def auto_play(self):
        if self.finished:
            return
        mine = self.guesses[self.turn]
        # a code consistent with every previous answer (so computer players are decent)
        cands = [c for c in itertools.product(range(COLORS), repeat=LEN)
                 if all(score(list(c), g["code"]) == (g["black"], g["white"]) for g in mine)]
        self._guess(self.turn, list(self.rng.choice(cands) if cands else [self.rng.randrange(COLORS) for _ in range(LEN)]))

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        return {
            "kind": "mastermind", "players": [{"uid": u, "guesses": self.guesses[u]} for u in self.players],
            "turn": self.turn if not self.finished else None, "colors": COLORS, "len": LEN, "max": MAX_GUESSES,
            "seq": self.seq, "last_guess": self.last_guess,
            "secret": self.secret if self.finished else None,
            "winner": self.winner, "draw": self.draw,
        }

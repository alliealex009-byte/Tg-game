"""Rock-Paper-Scissors, first to 2 round wins (max 9 rounds). Picks stay hidden until both are in."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

BEATS = {"rock": "scissors", "scissors": "paper", "paper": "rock"}
WIN_SCORE = 2
MAX_ROUNDS = 9


class RPSGame(BaseGame):
    name = "rps"
    min_players = 2
    max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Rock-Paper-Scissors needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.scores = {u: 0 for u in self.players}
        self.picks = {}
        self.rounds = 0
        self.seq = 0
        self.last_round = None
        self.winner = None
        self.finished = False
        self.draw = False

    def current(self):
        if self.finished:
            return None
        return next(u for u in self.players if u not in self.picks)

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid not in self.scores:
            raise GameError("You are not playing")
        if uid in self.picks:
            raise GameError("You already picked, wait for your opponent")
        if msg.get("t") != "pick":
            raise GameError("Unknown action")
        choice = msg.get("choice")
        if choice not in BEATS:
            raise GameError("Pick rock, paper or scissors")
        self._pick(uid, choice)

    def _pick(self, uid, choice):
        self.picks[uid] = choice
        if len(self.picks) < 2:
            return
        a, b = self.players
        ca, cb = self.picks[a], self.picks[b]
        win = None
        if ca != cb:
            win = a if BEATS[ca] == cb else b
            self.scores[win] += 1
        self.rounds += 1
        self.seq += 1
        self.last_round = {"seq": self.seq, "round": self.rounds, "picks": {a: ca, b: cb}, "winner": win}
        self.picks = {}
        if win is not None and self.scores[win] >= WIN_SCORE:
            self.winner, self.finished = win, True
        elif self.rounds >= MAX_ROUNDS:
            self.finished = True
            if self.scores[a] != self.scores[b]:
                self.winner = a if self.scores[a] > self.scores[b] else b
            else:
                self.draw = True

    def auto_play(self):
        if not self.finished:
            self._pick(self.current(), self.rng.choice(list(BEATS)))

    def remove_player(self, uid):
        if uid not in self.scores or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        return {
            "kind": "rps",
            "players": [{"uid": u, "score": self.scores[u]} for u in self.players],
            "picked": {u: u in self.picks for u in self.players},  # never the choice itself
            "turn": self.current(),
            "round": self.rounds + 1,
            "win_score": WIN_SCORE,
            "last_round": self.last_round,
            "winner": self.winner,
            "draw": self.draw,
        }

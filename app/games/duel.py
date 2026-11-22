"""Two quick betting duels. Coin Flip Duel: call heads or tails; a correct call scores. Dice Duel: both roll, the higher die scores.
First to WIN_SCORE round wins (max MAX_ROUNDS rounds). The server flips / rolls, so nobody can cheat."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

WIN_SCORE = 3
MAX_ROUNDS = 9


class _Duel(BaseGame):
    kind = ""
    min_players = 2
    max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("A duel needs exactly 2 players")
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

    def _valid(self, msg):
        raise NotImplementedError

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid not in self.players:
            raise GameError("You are not playing")
        if uid in self.picks:
            raise GameError("You already played, wait for your opponent")
        self._pick(uid, self._valid(msg))

    def _resolve(self):
        raise NotImplementedError

    def _pick(self, uid, choice):
        self.picks[uid] = choice
        if len(self.picks) < 2:
            return
        a, b = self.players
        extra, win = self._resolve()
        if win is not None:
            self.scores[win] += 1
        self.rounds += 1
        self.seq += 1
        self.last_round = {"seq": self.seq, "round": self.rounds, "picks": dict(self.picks), "winner": win, **extra}
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
            u = self.current()
            self._pick(u, self._auto())

    def remove_player(self, uid):
        if uid not in self.scores or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        return {
            "kind": self.kind,
            "players": [{"uid": u, "score": self.scores[u]} for u in self.players],
            "picked": {u: u in self.picks for u in self.players},  # never the choice itself
            "turn": self.current(),
            "round": self.rounds + 1,
            "win_score": WIN_SCORE,
            "last_round": self.last_round,
            "winner": self.winner,
            "draw": self.draw,
        }


class CoinDuelGame(_Duel):
    name = kind = "coinduel"

    def _valid(self, msg):
        if msg.get("t") != "call" or msg.get("side") not in ("heads", "tails"):
            raise GameError("Call heads or tails")
        return msg["side"]

    def _auto(self):
        return self.rng.choice(["heads", "tails"])

    def _resolve(self):
        a, b = self.players
        coin = self.rng.choice(["heads", "tails"])
        ra, rb = self.picks[a] == coin, self.picks[b] == coin
        win = a if ra and not rb else b if rb and not ra else None
        return {"coin": coin}, win


class DiceDuelGame(_Duel):
    name = kind = "diceduel"

    def _valid(self, msg):
        if msg.get("t") != "roll":
            raise GameError("Tap ROLL")
        return "roll"

    def _auto(self):
        return "roll"

    def _resolve(self):
        a, b = self.players
        dice = {a: self.rng.randint(1, 6), b: self.rng.randint(1, 6)}
        win = a if dice[a] > dice[b] else b if dice[b] > dice[a] else None
        return {"dice": dice}, win

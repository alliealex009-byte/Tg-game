"""Would You Rather: everyone votes on a dilemma at once. Players on the bigger side score a point (go with the crowd!). 8 rounds."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

QUESTIONS = [
    ("Be able to fly", "Be invisible"), ("Never use a phone again", "Never watch a screen again"), ("Always be 10 minutes late", "Always be 20 minutes early"),
    ("Live without music", "Live without movies"), ("Have unlimited pizza", "Have unlimited ice cream"), ("Speak every language", "Talk to animals"),
    ("Be famous", "Be rich and unknown"), ("Live in the past", "Live in the future"), ("Always be too hot", "Always be too cold"),
    ("Lose your phone for a month", "Lose your wallet for a month"), ("Have a rewind button", "Have a pause button"), ("Be the funniest person", "Be the smartest person"),
    ("Only eat sweet food", "Only eat salty food"), ("Live by the sea", "Live in the mountains"), ("Never sleep but never get tired", "Sleep 14 hours but be super energetic"),
    ("Know how you die", "Know when you die"), ("Fight 1 horse-sized duck", "Fight 100 duck-sized horses"), ("Have no homework ever", "Have no exams ever"),
    ("Be a superhero", "Be a billionaire"), ("Always win at board games", "Always win at video games"), ("Teleport anywhere", "Time travel once"),
    ("Have free internet forever", "Have free food forever"), ("Be a wizard", "Be a space explorer"), ("Only text", "Only call"),
]
ROUNDS = 8


class WouldYouRatherGame(BaseGame):
    name = "wyr"
    min_players = 2
    max_players = 8
    phase_seconds = 20

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 8:
            raise ValueError("Would You Rather needs 2-8 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.score = {u: 0 for u in self.players}
        self.qs = self.rng.sample(QUESTIONS, ROUNDS)
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

    def _pending(self):
        return [u for u in self.players if u not in self.picks]

    def current(self):
        if self.finished:
            return None
        p = self._pending()
        return ([u for u in p if u > 0] or p or [None])[0]

    def _bots(self):
        while not self.finished:
            for u in self._pending():
                if u < 0:
                    self.picks[u] = self.rng.choice("ab")
            if self._pending():
                return
            self._resolve()

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid not in self.players:
            raise GameError("You are not in this game")
        if msg.get("t") != "vote" or msg.get("pick") not in ("a", "b"):
            raise GameError("Vote a or b")
        if uid in self.picks:
            raise GameError("Already voted")
        self.picks[uid] = msg["pick"]
        self._bots()

    def auto_play(self):
        if self.finished:
            return
        for u in self._pending():
            self.picks[u] = self.rng.choice("ab")
        self._resolve()
        self._bots()

    def _resolve(self):
        a = [u for u in self.players if self.picks.get(u) == "a"]
        b = [u for u in self.players if self.picks.get(u) == "b"]
        win = a if len(a) > len(b) else b if len(b) > len(a) else []
        for u in win:
            self.score[u] += 1
        self.round += 1
        self.seq += 1
        self.phase_id += 1
        self.last_round = {"seq": self.seq, "round": self.round, "a": a, "b": b, "win": "a" if win is a and win else "b" if win is b and win else None}
        self.picks = {}
        if self.round >= ROUNDS:
            self.finished = True
            top = max(self.score.values())
            lead = [u for u in self.players if self.score[u] == top]
            if len(lead) == 1:
                self.winner = lead[0]
            else:
                self.draw = True

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.players.remove(uid)
        self.score.pop(uid, None)
        self.picks.pop(uid, None)
        if len(self.players) < 2 or all(u < 0 for u in self.players):
            self.finished = True
            self.winner = self.players[0] if self.players else None
            return
        self._bots()

    def public_state(self):
        q = self.qs[min(self.round, ROUNDS - 1)]
        return {"kind": "wyr", "round": self.round, "rounds": ROUNDS, "q": {"a": q[0], "b": q[1]},
                "players": [{"uid": u, "score": self.score[u]} for u in self.players],
                "picked": {u: u in self.picks for u in self.players}, "turn": self.current(),
                "last_round": self.last_round, "prev_q": ({"a": self.qs[self.round - 1][0], "b": self.qs[self.round - 1][1]} if self.round else None),
                "winner": self.winner, "draw": self.draw}

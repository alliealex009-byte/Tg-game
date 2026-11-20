"""EmojiQuiz: guess the movie, phrase or thing from the emojis. First correct answer wins the round. First to 3 round wins."""
from __future__ import annotations

import random
import re
import time

from .base import BaseGame, GameError

PUZZLES = [
    ("🦁👑", ["lion king", "the lion king"]), ("🧊❄️👸", ["frozen"]), ("🕷️🧑", ["spiderman", "spider man", "spider-man"]), ("🦈🌊😱", ["jaws"]),
    ("👻🚫", ["ghostbusters", "ghost busters"]), ("🧙‍♂️💍🌋", ["lord of the rings", "the lord of the rings"]), ("🐠🔍", ["finding nemo", "nemo"]),
    ("🚢🧊💔", ["titanic"]), ("🤖🚗", ["transformers"]), ("🧞‍♂️🪔", ["aladdin"]), ("🐼🥋", ["kung fu panda"]), ("🦇🧑🌃", ["batman"]),
    ("⭐⚔️🌌", ["star wars"]), ("🍫🏭", ["charlie and the chocolate factory", "willy wonka", "chocolate factory"]), ("🧸🤠🚀", ["toy story"]),
    ("🌧️☔", ["umbrella", "rain"]), ("☀️🌻", ["sunflower"]), ("🍎📱", ["iphone", "apple"]), ("🏏🇮🇳", ["cricket"]), ("🎬🍿", ["cinema", "movie", "movies"]),
    ("🌙⭐😴", ["sleep", "goodnight", "good night"]), ("🍕🇮🇹", ["pizza"]), ("🐝🍯", ["honey", "bee"]), ("🌍✈️", ["travel", "trip", "world tour"]),
    ("🔥🐉👸", ["game of thrones", "dragon"]), ("🧛🦇", ["dracula", "vampire"]), ("🐒🍌", ["monkey", "banana"]), ("🚀🌕", ["moon", "moon landing", "apollo"]),
    ("🎂🎉", ["birthday", "birthday party"]), ("☕📖", ["coffee and book", "reading", "cafe"]),
]
WIN, MAX_ROUNDS = 3, 7


def norm(t):
    return re.sub(r"[^a-z0-9 ]", "", t.lower().replace("-", " ")).strip()


class EmojiQuizGame(BaseGame):
    name = "emojiquiz"
    min_players = 2
    max_players = 6
    phase_seconds = 25

    def __init__(self, players, rng=None, clock=time.monotonic):
        if not 2 <= len(players) <= 6:
            raise ValueError("EmojiQuiz needs 2-6 players")
        self.rng = rng or random.SystemRandom()
        self.clock = clock
        self.players = list(players)
        self.score = {u: 0 for u in self.players}
        self.deck = self.rng.sample(PUZZLES, MAX_ROUNDS)
        self.round = 0
        self.phase_id = 0
        self.seq = 0
        self.last_round = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self._start_round()

    def _start_round(self):
        self.round += 1
        self.phase_id += 1
        self.emoji, self.answers = self.deck[self.round - 1]
        self.t0 = self.clock()
        self.bot_at = {u: self.t0 + self.rng.uniform(4.0, 10.0) for u in self.players if u < 0 and self.rng.random() < 0.5}

    def current(self):
        return None if self.finished else next((u for u in self.players if u > 0), self.players[0])

    def _bot_winner(self, before):
        c = [(t, u) for u, t in self.bot_at.items() if t <= before]
        return min(c)[1] if c else None

    def bot_due(self):
        return None if self.finished or not self.bot_at else max(0.0, min(self.bot_at.values()) - self.clock())

    def bot_event(self):
        bw = self._bot_winner(self.clock())
        if bw is not None and not self.finished:
            self._end_round(bw)

    def _end_round(self, winner):
        if winner is not None:
            self.score[winner] += 1
        self.seq += 1
        self.last_round = {"seq": self.seq, "round": self.round, "winner": winner, "answer": self.answers[0], "emoji": self.emoji}
        top = max(self.score.values())
        if top >= WIN or self.round >= MAX_ROUNDS:
            self.finished = True
            lead = [u for u in self.players if self.score[u] == top]
            if len(lead) == 1:
                self.winner = lead[0]
            else:
                self.draw = True
            return
        self._start_round()

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The match is over")
        if uid not in self.players:
            raise GameError("You are not in this match")
        t = msg.get("text")
        if msg.get("t") != "answer" or not isinstance(t, str):
            raise GameError("Type your answer")
        now = self.clock()
        bw = self._bot_winner(now)
        if bw is not None:
            return self._end_round(bw)
        if norm(t) not in {norm(a) for a in self.answers}:
            raise GameError("Not it — try again")
        if now - self.t0 < 0.4:
            raise GameError("Too fast!")
        self._end_round(uid)

    def auto_play(self):
        if self.finished:
            return
        self._end_round(self._bot_winner(float("inf")))

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.players.remove(uid)
        self.score.pop(uid, None)
        self.bot_at.pop(uid, None)
        if len(self.players) < 2 or all(u < 0 for u in self.players):
            self.finished = True
            self.winner = self.players[0] if self.players else None

    def public_state(self):
        return {"kind": "emojiquiz", "emoji": self.emoji, "round": self.round, "win": WIN,
                "players": [{"uid": u, "score": self.score[u]} for u in self.players],
                "turn": self.current(), "last_round": self.last_round, "winner": self.winner, "draw": self.draw}

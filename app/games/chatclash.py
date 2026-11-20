"""ChatClash: typing race. Everyone sees the same phrase; the first to type it exactly wins the round. First to 3 round wins."""
from __future__ import annotations

import random
import time

from .base import BaseGame, GameError

PHRASES = """the quick brown fox jumps over the lazy dog
good games start with good friends
never gonna let the bomb explode
roll the dice and take your chance
bring snacks and bring your best moves
keep calm and play another round
fortune favors the fast fingers
winners never quit and quitters never win
one more game before we sleep
check mate is a dish best served cold
a pocket full of coins and a heart full of hope
tap tap tap and the game is yours
every tile counts in the final round
sharing is caring but winning is better
the dragon sleeps beneath the castle
send the invite and fill the room
slow and steady never wins this race
type fast or lose the round""".split("\n")
WIN_ROUNDS = 3
MAX_ROUNDS = 7


class ChatClashGame(BaseGame):
    name = "chatclash"
    min_players = 2
    max_players = 6
    phase_seconds = 25

    def __init__(self, players, rng=None, clock=time.monotonic):
        if not 2 <= len(players) <= 6:
            raise ValueError("ChatClash needs 2-6 players")
        self.rng = rng or random.SystemRandom()
        self.clock = clock
        self.players = list(players)
        self.score = {u: 0 for u in self.players}
        self.round = 0
        self.phase_id = 0
        self.seq = 0
        self.last_round = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self._used = []
        self._start_round()

    def _start_round(self):
        left = [p for p in PHRASES if p not in self._used] or PHRASES
        self.phrase = self.rng.choice(left)
        self._used.append(self.phrase)
        self.round += 1
        self.phase_id += 1
        self.t0 = self.clock()
        self.bot_at = {u: self.t0 + len(self.phrase) * self.rng.uniform(0.28, 0.5) for u in self.players if u < 0}

    def current(self):
        return None if self.finished else next((u for u in self.players if u > 0), self.players[0])

    def _bot_winner(self, before):
        c = [(t, u) for u, t in self.bot_at.items() if t <= before]
        return min(c)[1] if c else None

    def _win(self, uid):
        self.score[uid] += 1
        self.seq += 1
        self.last_round = {"seq": self.seq, "round": self.round, "winner": uid, "phrase": self.phrase}
        self._after()

    def _after(self):
        top = max(self.score.values())
        if top >= WIN_ROUNDS or self.round >= MAX_ROUNDS:
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
        if msg.get("t") != "type":
            raise GameError("Unknown action")
        txt = msg.get("text")
        if not isinstance(txt, str):
            raise GameError("Type the phrase")
        now = self.clock()
        bw = self._bot_winner(now)
        if bw is not None:
            self._win(bw)
            return
        if " ".join(txt.lower().split()) != self.phrase:
            raise GameError("Not quite — check for typos")
        if now - self.t0 < len(self.phrase) * 0.04:     # faster than any human can type: ignore
            raise GameError("Too fast!")
        self._win(uid)

    def bot_due(self):
        return None if self.finished or not self.bot_at else max(0.0, min(self.bot_at.values()) - self.clock())

    def bot_event(self):
        bw = self._bot_winner(self.clock())
        if bw is not None and not self.finished:
            self._win(bw)

    def auto_play(self):
        if self.finished:
            return
        bw = self._bot_winner(float("inf"))
        self.seq += 1
        self.last_round = {"seq": self.seq, "round": self.round, "winner": bw, "phrase": self.phrase}
        if bw is not None:
            self.score[bw] += 1
        self._after()

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
        return {"kind": "chatclash", "phrase": self.phrase, "round": self.round, "win": WIN_ROUNDS,
                "players": [{"uid": u, "score": self.score[u]} for u in self.players],
                "turn": self.current(), "last_round": self.last_round, "winner": self.winner, "draw": self.draw}

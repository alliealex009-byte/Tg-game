"""Trivia: 10 multiple-choice questions, everybody answers at once (15 s). Faster correct answers score more,
streaks add a bonus. The correct answer and other players' picks stay hidden until the reveal."""
from __future__ import annotations

import random
import time

from .base import BaseGame, GameError
from .trivia_bank import Q

QUESTIONS, ASK_S, REVEAL_S = 10, 15, 4


class TriviaGame(BaseGame):
    name = "trivia"
    min_players = 2
    max_players = 6
    ticker = True  # timeouts are normal here, not AFK strikes

    def __init__(self, players, rng=None, clock=time.monotonic):
        if not 2 <= len(players) <= 6:
            raise ValueError("Trivia needs 2-6 players")
        self.rng, self.clock = rng or random.SystemRandom(), clock
        self.players = list(players)
        self.left = set()
        self.scores = {u: 0 for u in self.players}
        self.streak = {u: 0 for u in self.players}
        self.order = self.rng.sample(range(len(Q)), QUESTIONS)
        self.qi = -1
        self.phase = "ask"
        self.phase_id = 0
        self.phase_seconds = ASK_S
        self.picks, self.gained = {}, {}
        self.seq = 0
        self.last_reveal = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self._next_question()

    def _q(self):
        return Q[self.order[self.qi]]

    def _active(self):
        return [u for u in self.players if u not in self.left]

    def _next_question(self):
        self.qi += 1
        self.phase = "ask"
        self.phase_id += 1
        self.phase_seconds = ASK_S
        self.picks, self.gained, self.t0 = {}, {}, self.clock()
        correct = self._q()[3]
        for u in self._active():
            if u < 0:  # computer players answer instantly with a believable time
                ok = self.rng.random() < 0.6
                c = correct if ok else self.rng.choice([i for i in range(4) if i != correct])
                self.picks[u] = (c, self.rng.uniform(2.5, 11.0))
        if not self._pending():
            self._reveal()

    def _pending(self):
        return [u for u in self._active() if u not in self.picks]

    def current(self):
        if self.finished:
            return None
        pend = [u for u in self._pending() if u > 0]
        if self.phase == "ask" and pend:
            return pend[0]
        act = [u for u in self._active() if u > 0] or self._active() or self.players
        return act[0]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid not in self.players or uid in self.left:
            raise GameError("You are not in this game")
        if msg.get("t") != "answer":
            raise GameError("Unknown action")
        if self.phase != "ask":
            raise GameError("Wait for the next question")
        c = msg.get("choice")
        if isinstance(c, bool) or not isinstance(c, int) or not 0 <= c < 4:
            raise GameError("Pick one of the four answers")
        if uid in self.picks:
            raise GameError("You already answered")
        self.picks[uid] = (c, max(0.0, min(ASK_S, self.clock() - self.t0)))
        if not self._pending():
            self._reveal()

    def _reveal(self):
        correct = self._q()[3]
        for u in self._active():
            p = self.picks.get(u)
            if p is not None and p[0] == correct:
                self.streak[u] += 1
                pts = 100 + int(100 * max(0.0, ASK_S - p[1]) / ASK_S) + 20 * min(self.streak[u] - 1, 5)
                self.gained[u] = pts
                self.scores[u] += pts
            else:
                self.streak[u] = 0
                self.gained[u] = 0
        self.phase = "reveal"
        self.phase_id += 1
        self.phase_seconds = REVEAL_S
        self.seq += 1
        self.last_reveal = {"seq": self.seq, "q": self.qi, "correct": correct,
                            "picks": {str(u): (self.picks[u][0] if u in self.picks else None) for u in self._active()},
                            "gained": {str(u): g for u, g in self.gained.items()}}

    def auto_play(self):
        if self.finished:
            return
        if self.phase == "ask":
            self._reveal()
        elif self.qi + 1 >= QUESTIONS:
            self._finish()
        else:
            self._next_question()

    def _finish(self):
        self.finished, self.phase = True, "over"
        act = self._active() or self.players
        top = max(self.scores[u] for u in act)
        w = [u for u in act if self.scores[u] == top]
        self.winners = w
        self.winner = w[0] if len(w) == 1 else None

    def remove_player(self, uid):
        if uid not in self.players or self.finished or uid in self.left:
            return
        self.left.add(uid)
        act = self._active()
        if len(act) < 2:
            self.finished, self.phase = True, "over"
            self.winners = act
            self.winner = act[0] if act else None
        elif self.phase == "ask" and not self._pending():
            self._reveal()

    def public_state(self):
        q = self._q()
        rev = self.phase in ("reveal", "over")
        return {
            "kind": "trivia",
            "players": [{"uid": u, "score": self.scores[u], "streak": self.streak[u], "left": u in self.left,
                         "answered": u in self.picks} for u in self.players],
            "phase": self.phase, "turn": None, "q": self.qi + 1, "total": QUESTIONS, "category": q[0], "question": q[1],
            "options": q[2], "seq": self.seq, "reveal": self.last_reveal if rev else None,
            "winner": self.winner, "winners": self.winners if (self.winners and len(self.winners) > 1) else None, "draw": False,
        }

    def view(self, uid):
        st = self.public_state()
        p = self.picks.get(uid)
        st["my_pick"] = p[0] if p else None
        return st

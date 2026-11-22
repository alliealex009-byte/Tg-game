"""Hand Cricket (the 90s school-bench classic). Batter and bowler secretly pick 1-6 at the same moment.
Same number = OUT. Different numbers = the batter scores the number he picked.
Two innings of 2 overs (12 balls) and 2 wickets each; the chaser wins by passing the target."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

BALLS = 12
WICKETS = 2


class CricketGame(BaseGame):
    name = "cricket"
    min_players = 2
    max_players = 2
    phase_seconds = 10

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Hand Cricket needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.innings = 1
        self.runs = {u: 0 for u in self.players}
        self.balls = 0
        self.wkts = 0
        self.target = None
        self.picks = {}
        self.phase_id = 0
        self.seq = 0
        self.last_ball = None
        self.history = []          # runs per ball of the current innings: int or "W"
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self._bots()

    @property
    def batter(self):
        return self.players[0] if self.innings == 1 else self.players[1]

    @property
    def bowler(self):
        return self.players[1] if self.innings == 1 else self.players[0]

    def _pending(self):
        return [] if self.finished else [u for u in (self.batter, self.bowler) if u not in self.picks]

    def current(self):
        if self.finished:
            return None
        p = self._pending()
        return ([u for u in p if u > 0] or p or [None])[0]

    def _bots(self):
        while not self.finished:
            for u in self._pending():
                if u < 0:
                    self.picks[u] = self.rng.choice((1, 2, 3, 4, 5, 6, 4, 6, 3))
            if self._pending():
                return
            self._resolve()

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The match is over")
        if uid not in self.players:
            raise GameError("You are not in this match")
        n = msg.get("n")
        if msg.get("t") != "num" or not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 6:
            raise GameError("Pick a number from 1 to 6")
        if uid in self.picks:
            raise GameError("Already picked")
        self.picks[uid] = n
        self._bots()

    def auto_play(self):
        if self.finished:
            return
        for u in self._pending():
            self.picks[u] = self.rng.randint(1, 6)
        self._resolve()
        self._bots()

    def _resolve(self):
        bat, bowl = self.batter, self.bowler
        nb, nw = self.picks[bat], self.picks[bowl]
        out = nb == nw
        self.balls += 1
        if out:
            self.wkts += 1
            self.history.append("W")
        else:
            self.runs[bat] += nb
            self.history.append(nb)
        self.seq += 1
        self.phase_id += 1
        self.last_ball = {"seq": self.seq, "innings": self.innings, "ball": self.balls, "batter": bat, "bowler": bowl,
                          "bat": nb, "bowl": nw, "out": out, "runs": 0 if out else nb}
        self.picks = {}
        over = self.balls >= BALLS or self.wkts >= WICKETS
        chased = self.innings == 2 and self.runs[bat] > self.target
        if self.innings == 1 and over:
            self.target = self.runs[bat]
            self.innings, self.balls, self.wkts, self.history = 2, 0, 0, []
            self.last_ball["innings_over"] = True
        elif self.innings == 2 and (over or chased):
            self.finished = True
            a, b = self.players
            if self.runs[a] == self.runs[b]:
                self.draw = True
            else:
                self.winner = a if self.runs[a] > self.runs[b] else b

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        return {"kind": "cricket", "players": [{"uid": u, "runs": self.runs[u]} for u in self.players],
                "innings": self.innings, "batter": self.batter, "bowler": self.bowler, "balls": self.balls,
                "total_balls": BALLS, "wkts": self.wkts, "total_wkts": WICKETS, "target": self.target,
                "history": self.history, "picked": {u: u in self.picks for u in self.players}, "turn": self.current(),
                "last_ball": self.last_ball, "winner": self.winner, "draw": self.draw}

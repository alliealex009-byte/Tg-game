"""Scribble: draw and guess. One player draws a secret word on a shared canvas; everyone else types guesses.
Faster correct guesses earn more points and the artist earns points for every player who gets it. Everyone draws, twice with 4 players or fewer."""
from __future__ import annotations

import random
import re
import time

from .base import BaseGame, GameError

WORDS = """apple banana pizza burger cake icecream coffee egg carrot cheese bread cookie candy donut
cat dog fish bird horse cow pig sheep duck rabbit snake frog turtle monkey elephant lion tiger bear whale shark butterfly spider
house car bus train plane boat bicycle rocket tree flower sun moon star cloud rain rainbow snowman mountain river beach
phone clock key door chair table bed lamp book pencil scissors umbrella glasses hat shoe sock shirt crown ring
guitar piano drum ball kite balloon gift robot castle bridge tent fire volcano island
heart smile eye hand foot tooth nose ear""".split()
TURN_SECONDS = 70
MAX_POINTS = 3000
MAX_STROKE_POINTS = 400
COLORS = ("#111111", "#e53935", "#fb8c00", "#fdd835", "#43a047", "#1e88e5", "#8e24aa", "#ffffff")


def norm(t):
    return re.sub(r"[^a-z]", "", t.lower())


class ScribbleGame(BaseGame):
    name = "scribble"
    min_players = 2
    max_players = 8

    def __init__(self, players, rng=None, clock=time.monotonic):
        if not 2 <= len(players) <= 8:
            raise ValueError("Scribble needs 2-8 players")
        self.rng = rng or random.SystemRandom()
        self.clock = clock
        self.players = list(players)
        self.score = {u: 0 for u in self.players}
        humans = [u for u in self.players if u > 0]
        artists = humans if humans else list(self.players)   # computer players guess, they don't draw
        self.order = artists * (2 if len(self.players) <= 4 else 1)
        self.turn_no = 0
        self.phase_id = 0
        self.seq = 0
        self.last_turn = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self.words_left = self.rng.sample(sorted(set(WORDS)), len(self.order))
        self.guessed = set()
        self.chat = []
        self._begin_turn()

    @property
    def phase_seconds(self):
        return TURN_SECONDS

    # ---- turn flow
    def _begin_turn(self):
        while self.turn_no < len(self.order) and self.order[self.turn_no] not in self.players:
            self.turn_no += 1
        if self.turn_no >= len(self.order):
            return self._finish()
        self.drawer = self.order[self.turn_no]
        self.word = self.words_left[self.turn_no]
        self.strokes = []
        self.npoints = 0
        self.guessed = set()
        self.chat = []
        self.t0 = self.clock()
        self.phase_id += 1
        self.bot_at = {u: self.t0 + self.rng.uniform(12, 50) for u in self.players if u < 0 and u != self.drawer and self.rng.random() < 0.85}
        # computer players also throw in a couple of wrong guesses first, so the chat feels alive
        decoys = [w for w in sorted(set(WORDS)) if w != self.word]
        self.bot_wrong = []
        for u, t_ok in self.bot_at.items():
            for _ in range(self.rng.choice((1, 2, 2, 3))):
                self.bot_wrong.append((self.t0 + self.rng.uniform(4, max(5, t_ok - self.t0 - 1)), u, self.rng.choice(decoys)))
        self.bot_wrong.sort()

    def _end_turn(self, why):
        self.seq += 1
        self.last_turn = {"seq": self.seq, "drawer": self.drawer, "word": self.word, "guessed": sorted(self.guessed), "why": why}
        self.turn_no += 1
        self._begin_turn()

    def _finish(self):
        self.finished = True
        top = max(self.score.values())
        lead = [u for u in self.players if self.score[u] == top]
        if len(lead) == 1 and top > 0:
            self.winner = lead[0]
        else:
            self.draw = True

    def current(self):
        return None if self.finished else self.drawer

    def _guessers(self):
        return [u for u in self.players if u != self.drawer]

    # ---- actions
    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid not in self.players:
            raise GameError("You are not in this game")
        t = msg.get("t")
        if t == "stroke":
            return self._stroke(uid, msg)
        if t == "clear":
            self._need_drawer(uid)
            self.strokes, self.npoints = [], 0
            self.seq += 1
        elif t == "undo":
            self._need_drawer(uid)
            if self.strokes:
                self.npoints -= len(self.strokes.pop()["p"])
            self.seq += 1
        elif t == "guess":
            self._guess(uid, msg.get("text"))
        else:
            raise GameError("Unknown action")

    def _need_drawer(self, uid):
        if uid != self.drawer:
            raise GameError("Only the artist can draw")

    def _stroke(self, uid, msg):
        self._need_drawer(uid)
        pts, sid = msg.get("p"), msg.get("id")
        col, w = msg.get("c"), msg.get("w")
        if not isinstance(pts, list) or not 1 <= len(pts) <= 80 or isinstance(sid, bool) or not isinstance(sid, int):
            raise GameError("Bad stroke")
        clean = []
        for p in pts:
            if not (isinstance(p, list) and len(p) == 2 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in p)):
                raise GameError("Bad stroke")
            clean.append([round(min(1.0, max(0.0, float(p[0]))), 3), round(min(1.0, max(0.0, float(p[1]))), 3)])
        if self.npoints + len(clean) > MAX_POINTS:
            raise GameError("The canvas is full — clear it")
        cur = self.strokes[-1] if self.strokes and self.strokes[-1]["id"] == sid else None
        if cur is None:
            cur = {"id": sid, "c": col if col in COLORS else COLORS[0], "w": 2 if w == 2 else 6 if w == 6 else 4, "p": []}
            self.strokes.append(cur)
        if len(cur["p"]) + len(clean) > MAX_STROKE_POINTS:
            raise GameError("Stroke too long")
        cur["p"].extend(clean)
        self.npoints += len(clean)
        self.seq += 1

    def _award(self, uid):
        left = max(0.0, TURN_SECONDS - (self.clock() - self.t0))
        pts = 40 + int(60 * left / TURN_SECONDS)
        self.score[uid] += pts
        self.score[self.drawer] += 25
        self.guessed.add(uid)
        return pts

    def _guess(self, uid, text):
        if uid == self.drawer:
            raise GameError("You're drawing!")
        if uid in self.guessed:
            raise GameError("You already got it")
        if not isinstance(text, str) or not text.strip():
            raise GameError("Type a guess")
        if norm(text) == self.word:
            pts = self._award(uid)
            self.chat.append({"uid": uid, "ok": True, "pts": pts})
            self.seq += 1
            if len(self.guessed) >= len(self._guessers()):
                self._end_turn("all guessed")
        else:
            self.chat.append({"uid": uid, "text": text.strip()[:24]})
            self.chat = self.chat[-14:]
            self.seq += 1

    # ---- timers / bots
    def bot_due(self):
        c = [t for u, t in self.bot_at.items() if u not in self.guessed] + [t for t, u, _ in self.bot_wrong if u not in self.guessed]
        return None if self.finished or not c else max(0.0, min(c) - self.clock())

    def bot_event(self):
        now = self.clock()
        while self.bot_wrong and self.bot_wrong[0][0] <= now:
            _, u, w = self.bot_wrong.pop(0)
            if u in self.players and u not in self.guessed:
                self.chat.append({"uid": u, "text": w})
                self.chat = self.chat[-14:]
                self.seq += 1
                return
        for u, t in sorted(self.bot_at.items(), key=lambda kv: kv[1]):
            if t <= now and u not in self.guessed and u in self.players:
                pts = self._award(u)
                self.chat.append({"uid": u, "ok": True, "pts": pts})
                self.seq += 1
                if len(self.guessed) >= len(self._guessers()):
                    self._end_turn("all guessed")
                return

    def auto_play(self):
        if not self.finished:
            self._end_turn("time")

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        was_drawer = uid == self.drawer
        self.players.remove(uid)
        self.guessed.discard(uid)
        self.bot_at.pop(uid, None)
        if len(self.players) < 2 or all(u < 0 for u in self.players):
            self.finished = True
            self.winner = max(self.players, key=lambda u: self.score[u]) if self.players else None
            return
        if was_drawer:
            self._end_turn("artist left")
        elif len(self.guessed) >= len(self._guessers()):
            self._end_turn("all guessed")

    # ---- state
    def public_state(self):
        return {"kind": "scribble", "drawer": self.drawer if not self.finished else None, "turn": self.current(),
                "turn_no": min(self.turn_no + 1, len(self.order)), "turns": len(self.order),
                "len": len(self.word) if not self.finished else 0, "word": None, "strokes": self.strokes if not self.finished else [],
                "left": round(max(0.0, TURN_SECONDS - (self.clock() - self.t0)), 1), "total": TURN_SECONDS,
                "guessed": sorted(self.guessed), "chat": self.chat[-10:], "colors": list(COLORS),
                "players": [{"uid": u, "score": self.score[u]} for u in self.players],
                "last_turn": self.last_turn, "winner": self.winner, "draw": self.draw}

    def view(self, uid):
        s = self.public_state()
        if not self.finished and (uid == self.drawer or uid in self.guessed):
            s["word"] = self.word
        return s

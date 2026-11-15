"""Hangman for 2-4 players. Take turns guessing letters; a correct letter scores per occurrence and keeps your turn.
After 7 wrong guesses the man is hanged; the player with the most letters wins."""
from __future__ import annotations

import random
import string

from .base import BaseGame, GameError

WORDS = ["elephant", "volcano", "notebook", "football", "mountain", "umbrella", "chocolate", "treasure", "adventure", "keyboard",
         "universe", "pyramid", "dolphin", "fireworks", "lightning", "backpack", "rainbow", "sandwich", "telescope", "penguin",
         "butterfly", "airplane", "festival", "diamond", "elevator", "hospital", "kangaroo", "lantern", "monsoon", "pancake"]
MAX_WRONG = 7


class HangmanGame(BaseGame):
    name = "hangman"
    min_players, max_players = 2, 4

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("Hangman needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.word = self.rng.choice(WORDS)
        self.guessed = []
        self.wrong = 0
        self.score = {u: 0 for u in self.players}
        self.left = set()
        self.turn_idx = 0
        self.seq, self.last_guess = 0, None
        self.winner, self.finished, self.draw = None, False, False
        self.winners = None

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def _next(self):
        for _ in range(len(self.players)):
            self.turn_idx = (self.turn_idx + 1) % len(self.players)
            if self.players[self.turn_idx] not in self.left:
                return

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        ch = msg.get("letter")
        if msg.get("t") != "letter" or not isinstance(ch, str) or len(ch) != 1 or ch.lower() not in string.ascii_lowercase:
            raise GameError("Pick a letter")
        ch = ch.lower()
        if ch in self.guessed:
            raise GameError("That letter was already tried")
        self._guess(uid, ch)

    def _guess(self, uid, ch):
        self.guessed.append(ch)
        n = self.word.count(ch)
        self.seq += 1
        self.last_guess = {"seq": self.seq, "uid": uid, "letter": ch, "hits": n}
        if n:
            self.score[uid] += n
        else:
            self.wrong += 1
        solved = all(c in self.guessed for c in self.word)
        if solved or self.wrong >= MAX_WRONG:
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
        elif not n:
            self._next()

    def auto_play(self):
        if self.finished:
            return
        pat = [c if c in self.guessed else None for c in self.word]
        cands = [w for w in WORDS if len(w) == len(self.word) and all(p is None or p == c for p, c in zip(pat, w))
                 and not any(g in w for g in self.guessed if g not in pat)]
        freq = {}
        for w in cands or [self.word]:
            for c in set(w):
                if c not in self.guessed:
                    freq[c] = freq.get(c, 0) + 1
        letters = [c for c in string.ascii_lowercase if c not in self.guessed]
        self._guess(self.current(), max(freq, key=lambda c: freq[c] + self.rng.random()) if freq and self.rng.random() < 0.8 else self.rng.choice(letters))

    def remove_player(self, uid):
        if uid not in self.score or uid in self.left or self.finished:
            return
        was = self.current() == uid
        self.left.add(uid)
        act = [u for u in self.players if u not in self.left]
        if len(act) <= 1:
            self.finished, self.winner = True, act[0] if act else None
        elif was:
            self._next()

    def public_state(self):
        return {"kind": "hangman", "max_wrong": MAX_WRONG, "wrong": self.wrong, "guessed": self.guessed,
                "word": "".join(c if (c in self.guessed or self.finished) else "_" for c in self.word),
                "players": [{"uid": u, "score": self.score[u], "left": u in self.left} for u in self.players],
                "turn": self.current(), "last_guess": self.last_guess, "winner": self.winner, "draw": self.draw}

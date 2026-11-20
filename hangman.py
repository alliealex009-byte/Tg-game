"""Hangman for 2-6 players. One shared word; players take turns guessing letters. A correct letter lets you
go again and scores per occurrence (+3 for finishing the word); a wrong letter adds to the shared gallows and
passes the turn. 6 wrong guesses lose the word. Best of 3 words by score."""
from __future__ import annotations

import random

from .base import BaseGame, GameError
from .words import ALL_WORDS

ROUNDS, MAX_WRONG = 3, 6
FREQ = "etaoinshrdlcumwfgypbvkjxqz"


class HangmanGame(BaseGame):
    name = "hangman"
    min_players = 2
    max_players = 6

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 6:
            raise ValueError("Hangman needs 2-6 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.scores = {u: 0 for u in self.players}
        self.left = set()
        self.round = 0
        self.used_words = set()
        self.idx = 0
        self.seq = 0
        self.last_guess = None
        self.last_word = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self._new_word()

    # ---- helpers
    def _active(self):
        return [u for u in self.players if u not in self.left]

    def _new_word(self):
        self.round += 1
        pool = [cw for cw in ALL_WORDS if cw[1] not in self.used_words]
        self.category, self.word = self.rng.choice(pool)
        self.used_words.add(self.word)
        self.guessed, self.wrong = [], 0
        act = self._active()
        self.turn = act[(self.round - 1) % len(act)]

    def current(self):
        return None if self.finished else self.turn

    def _next_turn(self):
        act = self._active()
        i = act.index(self.turn) if self.turn in act else -1
        self.turn = act[(i + 1) % len(act)]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.turn:
            raise GameError("It's not your turn")
        if msg.get("t") != "guess":
            raise GameError("Unknown action")
        l = msg.get("letter")
        if not isinstance(l, str) or len(l) != 1 or not ("a" <= l.lower() <= "z"):
            raise GameError("Pick a letter A-Z")
        l = l.lower()
        if l in self.guessed:
            raise GameError("That letter was already guessed")
        self._guess(uid, l)

    def _guess(self, uid, l):
        self.guessed.append(l)
        cnt = self.word.count(l)
        self.seq += 1
        self.last_guess = {"seq": self.seq, "uid": uid, "letter": l, "hit": cnt > 0, "count": cnt}
        if cnt:
            self.scores[uid] += cnt
            if all(c in self.guessed for c in self.word):
                self.scores[uid] += 3
                return self._end_word(uid)
            return  # go again
        self.wrong += 1
        if self.wrong >= MAX_WRONG:
            return self._end_word(None)
        self._next_turn()

    def _end_word(self, solver):
        self.seq += 1
        self.last_word = {"seq": self.seq, "word": self.word, "solved_by": solver, "round": self.round}
        if self.round >= ROUNDS:
            return self._finish()
        self._new_word()

    def _finish(self):
        self.finished = True
        act = self._active() or self.players
        top = max(self.scores[u] for u in act)
        w = [u for u in act if self.scores[u] == top]
        if len(w) == 1:
            self.winner, self.winners = w[0], w
        else:
            self.draw = True

    def auto_play(self):
        if self.finished:
            return
        cand = [x for x in FREQ if x not in self.guessed]
        self._guess(self.turn, cand[min(len(cand) - 1, int(self.rng.random() ** 2 * 5))])

    def remove_player(self, uid):
        if uid not in self.scores or self.finished or uid in self.left:
            return
        self.left.add(uid)
        act = self._active()
        if len(act) < 2:
            self.finished = True
            if act:
                self.winner, self.winners = act[0], act
            return
        if self.turn == uid:
            i = self.players.index(uid)
            self.turn = next(self.players[(i + k) % len(self.players)] for k in range(1, len(self.players) + 1)
                             if self.players[(i + k) % len(self.players)] not in self.left)

    def public_state(self):
        return {
            "kind": "hangman",
            "players": [{"uid": u, "score": self.scores[u], "left": u in self.left} for u in self.players],
            "mask": [c if c in self.guessed else None for c in self.word],
            "category": self.category, "guessed": list(self.guessed), "wrong": self.wrong, "max_wrong": MAX_WRONG,
            "round": self.round, "rounds": ROUNDS, "turn": self.turn if not self.finished else None,
            "seq": self.seq, "last_guess": self.last_guess, "last_word": self.last_word,
            "winner": self.winner, "winners": self.winners, "draw": self.draw,
        }

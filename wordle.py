"""Word Duel: everyone guesses the same secret 5-letter word at the same time, 6 rounds.
Feedback per letter: g = right spot, y = wrong spot, x = not in word. First to solve wins; ties on the same round are a draw."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

WORDS = """about above actor adult after again alarm album alert alive angle angry apple arrow aside baker beach beard begin below bench black blade blame blank blast blaze bless blind block blood board boast brain brave bread break brick bride brief bring brown brush build burst cabin cable candy carry catch chain chair chalk charm chase cheap check cheek chest chief child chill claim class clean clear clerk click cliff climb clock close cloud coach coast color count court cover crane crash crazy cream crown crush cycle daily dance death delay depth dirty dozen draft drama dream dress drink drive eager early earth eight elite empty enemy enjoy enter equal error event every exact extra faith false fancy fever field fight final flame flash fleet floor focus force frame fresh front fruit funny ghost giant given glass globe glory grace grade grand grape grass great green greet group guard guess guest guide happy heart heavy honey horse hotel house human ideal image index input issue ivory jelly joint judge juice knife known label laser later laugh layer learn least leave level light limit local logic loose lucky lunch magic major maker march match maybe mayor media metal might minor model money month moral motor mount mouse mouth movie music naked nerve never night noble noise north novel nurse ocean offer olive onion opera order other outer owner paint panel paper party peace pearl phase phone photo piano pilot pitch place plain plane plant plate point power press price pride prime print prize proof proud queen quick quiet radio raise range rapid ratio reach ready river robot rough round route royal rural salad scale scene scope score sense serve seven shade shape share sharp sheet shelf shell shift shine shirt shock shoot short sight silly since skill sleep slice slide small smart smile smoke snake solid solve sound south space spare speak speed spend spice split sport staff stage stair stamp stand start state steam steel stick still stone store storm story strip study style sugar super sweet swing table taste teach thank theme thick thing think third three throw thumb tiger tight title toast today tooth topic total touch tough tower trace track trade trail train treat trend trial tribe truck truly trust truth twice uncle under union unity upper urban usual valid value video virus visit vital voice waste watch water wheel white whole woman world worry worth would wound write wrong young youth zebra""".split()
WORDS = sorted({w for w in WORDS if len(w) == 5})
ROUNDS = 6


def score(secret: str, guess: str) -> str:
    res = ["x"] * 5
    left = list(secret)
    for i, c in enumerate(guess):
        if secret[i] == c:
            res[i] = "g"
            left.remove(c)
    for i, c in enumerate(guess):
        if res[i] == "x" and c in left:
            res[i] = "y"
            left.remove(c)
    return "".join(res)


class WordleGame(BaseGame):
    name = "wordle"
    min_players = 2
    max_players = 4
    phase_seconds = 40

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("Word Duel needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.secret = self.rng.choice(WORDS)
        self.guesses = {u: [] for u in self.players}   # [(word, fb)]
        self.solved = {}                                # uid -> round solved
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

    def _active(self):
        return [u for u in self.players if u not in self.solved]

    def _pending(self):
        return [u for u in self._active() if u not in self.picks]

    def current(self):
        if self.finished:
            return None
        p = self._pending()
        return ([u for u in p if u > 0] or p or [None])[0]

    def _bot_guess(self, u):
        cands = [w for w in WORDS if all(score(w, g) == fb for g, fb in self.guesses[u])]
        if self.round >= 1 and self.rng.random() < 0.18 * self.round:
            pass
        return self.rng.choice(cands or WORDS)

    def _bots(self):
        while not self.finished:
            for u in self._pending():
                if u < 0:
                    self.picks[u] = self._bot_guess(u)
            if self._pending():
                return
            self._resolve()

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid not in self.players:
            raise GameError("You are not in this game")
        if msg.get("t") != "guess":
            raise GameError("Unknown action")
        w = msg.get("word")
        w = w.strip().lower() if isinstance(w, str) else ""
        if len(w) != 5 or not w.isalpha() or not w.isascii():
            raise GameError("Enter a 5-letter word")
        if uid in self.solved or uid in self.picks:
            raise GameError("Already guessed this round")
        self.picks[uid] = w
        self._bots()

    def auto_play(self):
        if self.finished:
            return
        for u in self._pending():
            self.picks[u] = self._bot_guess(u)
        self._resolve()
        self._bots()

    def _resolve(self):
        self.round += 1
        out = {}
        for u, w in self.picks.items():
            fb = score(self.secret, w)
            self.guesses[u].append((w, fb))
            out[u] = fb
            if w == self.secret:
                self.solved[u] = self.round
        self.picks = {}
        self.seq += 1
        self.phase_id += 1
        self.last_round = {"seq": self.seq, "round": self.round, "fb": out}
        if self.solved:
            top = [u for u, r in self.solved.items() if r == self.round]
            self.finished = True
            if len(top) == 1:
                self.winner = top[0]
            else:
                self.draw = True
        elif self.round >= ROUNDS:
            self.finished = True
            self.draw = True

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.players = [u for u in self.players if u != uid]
        self.picks.pop(uid, None)
        if len(self.players) < 2 or all(u < 0 for u in self.players):
            self.finished = True
            self.winner = self.players[0] if self.players else None
            return
        self._bots()

    def public_state(self, reveal=False):
        done = self.finished
        return {"kind": "wordle", "rounds": ROUNDS, "round": self.round, "secret": self.secret if done else None,
                "players": [{"uid": u, "guesses": [{"word": w if (u == self._viewer or done) else None, "fb": fb} for w, fb in self.guesses[u]],
                             "solved": self.solved.get(u)} for u in self.players],
                "picked": {u: u in self.picks for u in self.players}, "turn": self.current(),
                "last_round": self.last_round, "winner": self.winner, "draw": self.draw}

    _viewer = None

    def view(self, uid):
        self._viewer = uid
        try:
            return self.public_state()
        finally:
            self._viewer = None

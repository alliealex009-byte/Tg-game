"""Join-request verification (captcha). Pure logic, no Telegram imports, so it is unit-tested."""
from __future__ import annotations

import random
import time

TTL = 15 * 60
MAX_TRIES = 3
EMOJI = ["🍎", "🚗", "🐶", "⭐", "🎈", "🍕", "⚽", "🌙", "🔑", "🎵", "🐱", "🌸"]
NAMES = {"🍎": "apple", "🚗": "car", "🐶": "dog", "⭐": "star", "🎈": "balloon", "🍕": "pizza",
         "⚽": "ball", "🌙": "moon", "🔑": "key", "🎵": "music note", "🐱": "cat", "🌸": "flower"}


class Challenge:
    def __init__(self, question: str, options: list, answer: int):
        self.question, self.options, self.answer = question, options, answer


def new_challenge(rng=None) -> Challenge:
    rng = rng or random.SystemRandom()
    if rng.random() < 0.5:
        target = rng.choice(EMOJI)
        opts = rng.sample([e for e in EMOJI if e != target], 5) + [target]
        rng.shuffle(opts)
        return Challenge(f"Tap the {NAMES[target]}  {target}", opts, opts.index(target))
    a, b = rng.randint(2, 9), rng.randint(2, 9)
    ans = a + b
    wrong = set()
    while len(wrong) < 5:
        w = ans + rng.choice([-3, -2, -1, 1, 2, 3, 4])
        if w != ans and w > 0:
            wrong.add(w)
    opts = [str(x) for x in wrong] + [str(ans)]
    rng.shuffle(opts)
    return Challenge(f"What is {a} + {b} ?", opts, opts.index(str(ans)))


class Verifier:
    def __init__(self, rng=None, clock=time.time):
        self.rng, self.clock = rng, clock
        self.pending: dict = {}  # (uid, chat_id) -> dict

    def start(self, uid: int, chat_id: int, chat_title: str = "") -> Challenge:
        ch = new_challenge(self.rng)
        self.pending[(uid, chat_id)] = {"ch": ch, "tries": 0, "ts": self.clock(), "title": chat_title}
        return ch

    def open_for(self, uid: int) -> list:
        self._purge()
        return [k[1] for k in self.pending if k[0] == uid]

    def title(self, uid: int, chat_id: int) -> str:
        p = self.pending.get((uid, chat_id))
        return p["title"] if p else ""

    def _purge(self):
        now = self.clock()
        for k in [k for k, v in self.pending.items() if now - v["ts"] > TTL]:
            del self.pending[k]

    def check(self, uid: int, chat_id: int, choice: int):
        """Returns ('ok'|'wrong'|'failed'|'none', Challenge-or-None). A wrong answer issues a fresh challenge."""
        self._purge()
        p = self.pending.get((uid, chat_id))
        if p is None:
            return "none", None
        if choice == p["ch"].answer:
            del self.pending[(uid, chat_id)]
            return "ok", None
        p["tries"] += 1
        if p["tries"] >= MAX_TRIES:
            del self.pending[(uid, chat_id)]
            return "failed", None
        p["ch"] = new_challenge(self.rng)
        return "wrong", p["ch"]

    def cancel(self, uid: int, chat_id: int):
        self.pending.pop((uid, chat_id), None)

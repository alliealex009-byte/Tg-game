"""Quiz race: 7 questions, everyone answers at once. Correct answers score, the fastest score a bonus."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

BANK = [
    ("What is the capital of Australia?", "Canberra", ["Sydney", "Melbourne", "Perth"]),
    ("Which is the largest planet in our solar system?", "Jupiter", ["Saturn", "Neptune", "Earth"]),
    ("How many continents are there?", "7", ["5", "6", "8"]),
    ("What is the chemical symbol for gold?", "Au", ["Ag", "Gd", "Go"]),
    ("Who painted the Mona Lisa?", "Leonardo da Vinci", ["Michelangelo", "Raphael", "Picasso"]),
    ("Which is the largest ocean?", "Pacific", ["Atlantic", "Indian", "Arctic"]),
    ("What is the fastest land animal?", "Cheetah", ["Lion", "Horse", "Leopard"]),
    ("What is the hardest natural substance?", "Diamond", ["Quartz", "Iron", "Granite"]),
    ("What is the smallest prime number?", "2", ["0", "1", "3"]),
    ("What is the national animal of India?", "Tiger", ["Lion", "Elephant", "Peacock"]),
    ("Which gas do plants absorb from the air?", "Carbon dioxide", ["Oxygen", "Nitrogen", "Helium"]),
    ("What is the currency of Japan?", "Yen", ["Won", "Yuan", "Dollar"]),
    ("How many sides does a hexagon have?", "6", ["5", "7", "8"]),
    ("Who wrote Romeo and Juliet?", "William Shakespeare", ["Charles Dickens", "Mark Twain", "Jane Austen"]),
    ("At what temperature does water boil at sea level (°C)?", "100", ["90", "110", "212"]),
    ("Which planet is known as the Red Planet?", "Mars", ["Venus", "Mercury", "Jupiter"]),
    ("In which city is the Taj Mahal?", "Agra", ["Delhi", "Jaipur", "Lucknow"]),
    ("Which mountain range contains Mount Everest?", "Himalayas", ["Andes", "Alps", "Rockies"]),
    ("What is the largest mammal?", "Blue whale", ["Elephant", "Giraffe", "Hippo"]),
    ("Which organ pumps blood around the body?", "Heart", ["Liver", "Lungs", "Kidney"]),
    ("In which year did India become independent?", "1947", ["1942", "1950", "1935"]),
    ("Which sport is played at Wimbledon?", "Tennis", ["Cricket", "Golf", "Badminton"]),
    ("How many players per side are on the field in football (soccer)?", "11", ["9", "10", "12"]),
    ("What is 5 in binary?", "101", ["110", "011", "111"]),
    ("What does HTML stand for?", "HyperText Markup Language", ["High Tech Modern Language", "HyperTransfer Markup Logic", "Home Tool Markup Language"]),
    ("Which planet is famous for its rings?", "Saturn", ["Mars", "Mercury", "Venus"]),
    ("What is the square root of 144?", "12", ["14", "11", "13"]),
    ("Who is credited with discovering gravity after watching an apple fall?", "Isaac Newton", ["Albert Einstein", "Galileo", "Nikola Tesla"]),
    ("Who is credited with inventing the telephone?", "Alexander Graham Bell", ["Thomas Edison", "Nikola Tesla", "Marconi"]),
    ("What is the capital of France?", "Paris", ["Lyon", "Marseille", "Nice"]),
    ("What is the largest hot desert in the world?", "Sahara", ["Gobi", "Kalahari", "Thar"]),
    ("How many strings does a standard guitar have?", "6", ["4", "5", "7"]),
    ("Which bird is the fastest in a dive?", "Peregrine falcon", ["Eagle", "Hummingbird", "Ostrich"]),
    ("How many squares are on a chessboard?", "64", ["32", "81", "100"]),
    ("Which vitamin do we get from sunlight?", "Vitamin D", ["Vitamin C", "Vitamin A", "Vitamin B12"]),
    ("Which is the largest country by area?", "Russia", ["Canada", "China", "USA"]),
    ("What is the chemical formula of water?", "H2O", ["CO2", "O2", "HO"]),
    ("What is the capital of Japan?", "Tokyo", ["Kyoto", "Osaka", "Seoul"]),
    ("What is 7 × 8?", "56", ["54", "49", "64"]),
    ("Which planet is closest to the Sun?", "Mercury", ["Venus", "Earth", "Mars"]),
    ("What is the tallest animal?", "Giraffe", ["Elephant", "Camel", "Ostrich"]),
    ("Who is known as the Father of the Nation in India?", "Mahatma Gandhi", ["Jawaharlal Nehru", "Subhas Chandra Bose", "Sardar Patel"]),
]
ROUNDS = 7
BONUS = [60, 30]


class TriviaGame(BaseGame):
    name = "trivia"
    min_players, max_players = 2, 6

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 6:
            raise ValueError("Quiz needs 2-6 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.score = {u: 0 for u in self.players}
        self.left = set()
        self.qs = []
        for q, a, wrong in self.rng.sample(BANK, ROUNDS):
            opts = [a] + list(wrong)
            self.rng.shuffle(opts)
            self.qs.append({"q": q, "options": opts, "c": opts.index(a)})
        self.round = 0
        self.seq, self.last_round = 0, None
        self.winner, self.finished, self.draw = None, False, False
        self.winners = None
        self._open()

    def _open(self):
        self.answers = {}   # uid -> option index (or -1 for no answer), in arrival order
        for u in self.players:
            if u < 0:  # computers answer instantly, correct about 65% of the time
                c = self.qs[self.round]["c"]
                self.answers[u] = c if self.rng.random() < 0.65 else self.rng.choice([i for i in range(4) if i != c])

    def _live(self):
        return [u for u in self.players if u not in self.left]

    def current(self):
        if self.finished:
            return None
        pend = [u for u in self._live() if u not in self.answers]
        humans = [u for u in pend if u > 0]
        return (humans or pend or [None])[0]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid not in self.score or uid in self.left:
            raise GameError("You are not playing")
        i = msg.get("i")
        if msg.get("t") != "answer" or isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < 4:
            raise GameError("Pick an answer")
        if uid in self.answers:
            raise GameError("You already answered")
        self.answers[uid] = i
        self._maybe_close()

    def _maybe_close(self):
        if all(u in self.answers for u in self._live()):
            self._close()

    def _close(self):
        q = self.qs[self.round]
        gains, order = {}, [u for u in self.answers if self.answers[u] == q["c"] and u in self._live()]
        # humans' arrival order is dict order; bots were inserted first, so give bonus to humans first
        order.sort(key=lambda u: (u < 0))
        for k, u in enumerate(order):
            gains[u] = 100 + (BONUS[k] if k < len(BONUS) else 0)
            self.score[u] += gains[u]
        for u in self._live():
            self.answers.setdefault(u, -1)
        self.seq += 1
        self.last_round = {"seq": self.seq, "round": self.round + 1, "q": q["q"], "options": q["options"], "c": q["c"],
                           "answers": {str(u): a for u, a in self.answers.items()}, "gains": {str(u): g for u, g in gains.items()}}
        self.round += 1
        if self.round >= ROUNDS:
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
        else:
            self._open()

    def auto_play(self):
        if self.finished:
            return
        for u in self._live():
            if u not in self.answers:
                self.answers[u] = self.rng.randrange(4) if u < 0 else -1
        self._close()

    def remove_player(self, uid):
        if uid not in self.score or uid in self.left or self.finished:
            return
        self.left.add(uid)
        act = self._live()
        if len(act) <= 1:
            self.finished, self.winner = True, act[0] if act else None
        else:
            self._maybe_close()

    def public_state(self):
        q = None if self.finished else self.qs[self.round]
        return {"kind": "trivia", "rounds": ROUNDS, "round": min(self.round + 1, ROUNDS),
                "players": [{"uid": u, "score": self.score[u], "answered": u in self.answers, "left": u in self.left} for u in self.players],
                "q": q["q"] if q else None, "options": q["options"] if q else [], "turn": self.current(),
                "last_round": self.last_round, "mine": None, "winner": self.winner, "draw": self.draw}

    def view(self, uid):
        st = self.public_state()
        if uid in self.answers:
            st["mine"] = self.answers[uid]
        return st

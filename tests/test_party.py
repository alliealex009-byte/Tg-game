import random
import unittest

from app.games.base import GameError
from app.games.hangman import HangmanGame
from app.games.mafia import MafiaGame, role_counts
from app.games.mastermind import LEN, MastermindGame, score
from app.games.trivia import TriviaGame
from app.games.trivia_bank import Q
from app.games.words import ALL_WORDS

N = 300


def bots(n, humans=0):
    return list(range(1, humans + 1)) + [-(i + 1) for i in range(n - humans)]


class Bank(unittest.TestCase):
    def test_trivia_bank(self):
        self.assertGreaterEqual(len(Q), 80)
        self.assertEqual(len({q[1] for q in Q}), len(Q))
        for cat, q, opts, ans in Q:
            self.assertEqual(len(opts), 4)
            self.assertEqual(len(set(opts)), 4, q)
            self.assertTrue(0 <= ans < 4)

    def test_words(self):
        self.assertGreaterEqual(len(ALL_WORDS), 150)
        for c, w in ALL_WORDS:
            self.assertTrue(w.isalpha() and w.islower(), w)


class Mastermind(unittest.TestCase):
    def test_score_duplicates(self):
        self.assertEqual(score([1, 1, 2, 3], [1, 2, 1, 1]), (1, 2))
        self.assertEqual(score([0, 0, 0, 0], [0, 0, 0, 0]), (4, 0))
        self.assertEqual(score([0, 1, 2, 3], [3, 2, 1, 0]), (0, 4))
        self.assertEqual(score([1, 1, 2, 2], [2, 2, 1, 1]), (0, 4))

    def test_flow(self):
        g = MastermindGame([1, 2], random.Random(1))
        self.assertIsNone(g.public_state()["secret"])
        with self.assertRaises(GameError):
            g.handle(2, {"t": "guess", "code": [0, 0, 0, 0]})
        g.handle(1, {"t": "guess", "code": g.secret})
        self.assertEqual(g.winner, 1)
        self.assertEqual(g.public_state()["secret"], g.secret)

    def test_full_games(self):
        for seed in range(N):
            g = MastermindGame([1, -2], random.Random(seed))
            n = 0
            while not g.finished and n < 50:
                g.auto_play(); n += 1
            self.assertTrue(g.finished)
            self.assertTrue(g.winner is not None or g.draw)

    def test_fuzz(self):
        g = MastermindGame([1, 2], random.Random(2))
        for bad in (None, [], [0] * 3, [0] * 5, [6, 0, 0, 0], [-1, 0, 0, 0], [True, 0, 0, 0], ["a"] * 4, "0000", {}):
            with self.assertRaises(GameError):
                g.handle(1, {"t": "guess", "code": bad})
        with self.assertRaises(GameError):
            g.handle(1, {"t": "nope"})


class Hangman(unittest.TestCase):
    def test_mask_hides_word(self):
        g = HangmanGame([1, 2], random.Random(3))
        self.assertTrue(all(c is None for c in g.public_state()["mask"]))
        self.assertNotIn(g.word, str(g.public_state()))

    def test_rules(self):
        g = HangmanGame([1, 2], random.Random(4))
        first = g.turn
        letter = g.word[0]
        g.handle(first, {"t": "guess", "letter": letter.upper()})
        self.assertEqual(g.turn, first)                       # hit = go again
        with self.assertRaises(GameError):
            g.handle(first, {"t": "guess", "letter": letter})
        miss = next(c for c in "abcdefghijklmnopqrstuvwxyz" if c not in g.word)
        g.handle(first, {"t": "guess", "letter": miss})
        self.assertNotEqual(g.turn, first)
        self.assertEqual(g.wrong, 1)

    def test_fuzz(self):
        g = HangmanGame([1, 2], random.Random(5))
        for bad in (None, "", "ab", 1, True, "1", "é", ["a"]):
            with self.assertRaises(GameError):
                g.handle(g.turn, {"t": "guess", "letter": bad})
        with self.assertRaises(GameError):
            g.handle(3 - g.turn, {"t": "guess", "letter": "a"})

    def test_full_games(self):
        for seed in range(N):
            n = 2 + seed % 5
            g = HangmanGame(bots(n, 1), random.Random(seed))
            for _ in range(400):
                if g.finished:
                    break
                g.auto_play()
            self.assertTrue(g.finished)
            self.assertEqual(g.last_word["round"], 3)

    def test_leave(self):
        g = HangmanGame([1, 2, 3], random.Random(6))
        g.remove_player(g.turn)
        self.assertNotIn(g.turn, g.left)
        g.remove_player(next(u for u in (1, 2, 3) if u not in g.left))
        self.assertTrue(g.finished and g.winner is not None)


class Trivia(unittest.TestCase):
    def make(self, n=3, seed=1):
        t = [0.0]
        return TriviaGame(list(range(1, n + 1)), random.Random(seed), clock=lambda: t[0]), t

    def test_hidden_until_reveal(self):
        g, t = self.make()
        st = g.view(1)
        self.assertIsNone(st["reveal"])
        self.assertNotIn("correct", str(st))
        g.handle(2, {"t": "answer", "choice": 1})
        self.assertIsNone(g.view(1)["my_pick"])
        self.assertEqual(g.view(2)["my_pick"], 1)
        self.assertTrue(g.view(1)["players"][1]["answered"])

    def test_scoring_speed_and_streak(self):
        g, t = self.make(2)
        c = g._q()[3]
        t[0] = 1.5
        g.handle(1, {"t": "answer", "choice": c})
        t[0] = 12
        g.handle(2, {"t": "answer", "choice": c})
        self.assertEqual(g.phase, "reveal")
        self.assertGreater(g.gained[1], g.gained[2])
        self.assertEqual(g.gained[1], 100 + int(100 * 13.5 / 15))
        g.auto_play()
        c2 = g._q()[3]
        t[0] = 0
        g.t0 = 0
        g.handle(1, {"t": "answer", "choice": c2})
        g.handle(2, {"t": "answer", "choice": (c2 + 1) % 4})
        self.assertEqual(g.gained[1], 100 + 100 + 20)          # streak bonus
        self.assertEqual(g.streak[2], 0)

    def test_errors(self):
        g, t = self.make()
        for bad in (None, 4, -1, True, "1", 1.5):
            with self.assertRaises(GameError):
                g.handle(1, {"t": "answer", "choice": bad})
        g.handle(1, {"t": "answer", "choice": 0})
        with self.assertRaises(GameError):
            g.handle(1, {"t": "answer", "choice": 0})
        with self.assertRaises(GameError):
            g.handle(99, {"t": "answer", "choice": 0})

    def test_full_games(self):
        for seed in range(N):
            n = 2 + seed % 5
            g = TriviaGame(bots(n, 1 + seed % 2), random.Random(seed))
            for _ in range(60):
                if g.finished:
                    break
                if seed % 3 == 0 and g.phase == "ask" and 1 in g._pending():
                    g.handle(1, {"t": "answer", "choice": random.Random(seed).randrange(4)})
                else:
                    g.auto_play()
            self.assertTrue(g.finished, seed)
            self.assertTrue(g.winners)
            self.assertEqual(g.q if hasattr(g, "q") else g.qi + 1, 10)

    def test_tie_multiwinner(self):
        g, t = self.make(2)
        for _ in range(10):
            g.auto_play(); g.auto_play()
        self.assertTrue(g.finished)
        self.assertEqual(sorted(g.winners), [1, 2])
        self.assertIsNone(g.winner)


class Mafia(unittest.TestCase):
    def test_role_counts(self):
        for n in range(4, 11):
            c = role_counts(n)
            self.assertEqual(sum(c.values()), n)
            self.assertGreaterEqual(c["villager"], 1)
            self.assertLess(c["mafia"], n - c["mafia"])

    def roles_of(self, g, r):
        return [u for u in g.players if g.roles[u] == r]

    def test_doctor_save(self):
        g = MafiaGame([1, 2, 3, 4], random.Random(1))
        mafia, doc = self.roles_of(g, "mafia")[0], self.roles_of(g, "doctor")[0]
        victim = next(u for u in g.players if g.roles[u] != "mafia")
        g.handle(mafia, {"t": "kill", "target": victim})
        g.handle(doc, {"t": "save", "target": victim})
        self.assertEqual(g.phase, "day")
        self.assertIn(victim, g.alive)
        self.assertTrue(g.last_event["saved"] or g.last_event["kind"] == "dawn")

    def test_kill_and_town_win_by_vote(self):
        g = MafiaGame([1, 2, 3, 4], random.Random(2))
        mafia, doc = self.roles_of(g, "mafia")[0], self.roles_of(g, "doctor")[0]
        victim = next(u for u in g.players if g.roles[u] == "villager")
        g.handle(mafia, {"t": "kill", "target": victim})
        g.handle(doc, {"t": "save", "target": mafia})
        self.assertNotIn(victim, g.alive)
        for u in list(g.alive):
            g.handle(u, {"t": "skip"})
        self.assertEqual(g.phase, "vote")
        for u in list(g.alive):
            g.handle(u, {"t": "vote", "target": mafia if u != mafia else next(x for x in g.alive if x != mafia)})
        self.assertTrue(g.finished)
        self.assertEqual(g.win_team, "town")
        self.assertEqual(sorted(g.winners), sorted(u for u in g.players if g.roles[u] != "mafia"))

    def test_detective_and_tie(self):
        g = MafiaGame([1, 2, 3, 4, 5], random.Random(3))
        det = self.roles_of(g, "detective")[0]
        mafia = self.roles_of(g, "mafia")[0]
        g.handle(det, {"t": "probe", "target": mafia})
        self.assertEqual(g.view(det)["me"]["probes"][-1], {"target": mafia, "team": "mafia"})
        with self.assertRaises(GameError):
            g.handle(det, {"t": "probe", "target": mafia})
        with self.assertRaises(GameError):
            g.handle(mafia, {"t": "probe", "target": det})

    def test_view_secrecy(self):
        g = MafiaGame([1, 2, 3, 4, 5, 6], random.Random(4))
        spec = g.view(99)
        self.assertIsNone(spec["me"])
        self.assertTrue(all(p["role"] is None for p in spec["players"]))
        self.assertIsNone(spec["turn"])
        for u in g.players:
            v = g.view(u)
            known = {p["uid"] for p in v["players"] if p["role"]}
            self.assertEqual(known, set(self.roles_of(g, "mafia")) if g.roles[u] == "mafia" else set())
            self.assertEqual(v["me"]["role"], g.roles[u])
            self.assertEqual(v["me"]["probes"] != [] and g.roles[u] != "detective", False)
        self.assertNotIn("kill_picks", str(spec))

    def test_full_games(self):
        for seed in range(N):
            n = 4 + seed % 7
            humans = 1 + seed % min(n, 4)
            g = MafiaGame(bots(n, humans), random.Random(seed))
            for step in range(200):
                if g.finished:
                    break
                if seed % 2 == 0:       # humans act through handle
                    for u in list(g.alive):
                        if u > 0 and u in g._pending():
                            r = g.roles[u]
                            alive = [x for x in g.alive if x != u]
                            try:
                                if g.phase == "night":
                                    if r == "mafia":
                                        g.handle(u, {"t": "kill", "target": random.Random(step).choice([x for x in alive if g.roles[x] != "mafia"] or alive)})
                                    elif r == "doctor":
                                        g.handle(u, {"t": "save", "target": random.Random(step).choice(alive)})
                                    elif r == "detective":
                                        g.handle(u, {"t": "probe", "target": random.Random(step).choice(alive)})
                                elif g.phase == "day":
                                    g.handle(u, {"t": "skip"})
                                elif g.phase == "vote":
                                    g.handle(u, {"t": "vote", "target": random.Random(step).choice(alive)})
                            except GameError:
                                pass
                            if g.finished:
                                break
                g.auto_play() if not g.finished and g.phase_seconds is not None and step % 2 else None
            while not g.finished and step < 400:
                g.auto_play(); step += 1
            self.assertTrue(g.finished, (seed, n))
            self.assertTrue(g.winners is not None and g.win_team in ("town", "mafia"))

    def test_fuzz(self):
        g = MafiaGame([1, 2, 3, 4], random.Random(7))
        for m in ({}, {"t": 5}, {"t": "kill"}, {"t": "kill", "target": "x"}, {"t": "kill", "target": True},
                  {"t": "vote", "target": 1}, {"t": "skip"}, {"t": "save", "target": 99}):
            for u in (1, 2, 3, 4, 99):
                try:
                    g.handle(u, m)
                except GameError:
                    pass

    def test_leave(self):
        g = MafiaGame([1, 2, 3, 4, 5, 6], random.Random(8))
        gone = set()
        for u in (1, 2, 3):
            if not g.finished:
                g.remove_player(u); gone.add(u)
        for _ in range(50):
            if g.finished:
                break
            g.auto_play()
        self.assertTrue(g.finished)
        self.assertFalse(set(g.winners or []) & gone)


if __name__ == "__main__":
    unittest.main()

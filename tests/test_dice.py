import json
import random
import unittest

from app.games import GAMES
from app.games.base import GameError
from app.games.bingo import BingoGame, LINES
from app.games.dots import DotsGame
from app.games.liarsdice import LiarsDiceGame
from app.games.mancala import MancalaGame
from app.games.nim import NimGame
from app.games.pig import PigGame

KEYS = ["pig", "liarsdice", "bingo", "nim", "mancala", "dots"]
NP = {"pig": (2, 4), "liarsdice": (2, 5), "bingo": (2, 6), "nim": (2, 2), "mancala": (2, 2), "dots": (2, 2)}


def mk(key, n, seed):
    return GAMES[key](list(range(1, n + 1)), rng=random.Random(seed))


def random_action(key, g, rnd):
    """Apply one legal random action for the current player (via handle). Returns False if auto_play is needed."""
    u = g.current()
    if key == "pig":
        g.handle(u, {"t": "hold"} if g.turn_total > 0 and rnd.random() < 0.15 else {"t": "roll"})
    elif key == "liarsdice":
        if g.bid and rnd.random() < 0.3:
            g.handle(u, {"t": "liar"})
        else:
            opts = [(q, f) for q in range(1, g.total() + 1) for f in range(1, 7) if g.valid_raise(q, f)]
            if opts:
                q, f = rnd.choice(opts[: 6])
                g.handle(u, {"t": "bid", "q": q, "face": f})
            else:
                g.handle(u, {"t": "liar"})
    elif key == "nim":
        h = rnd.choice([i for i, v in enumerate(g.heaps) if v])
        g.handle(u, {"t": "take", "heap": h, "n": rnd.randint(1, g.heaps[h])})
    elif key == "mancala":
        g.handle(u, {"t": "sow", "pit": rnd.choice(g.legal()) - 7 * g.turn_idx})
    elif key == "dots":
        d, r, c = rnd.choice(g.free_edges())
        g.handle(u, {"t": "line", "d": d, "r": r, "c": c})


class RandomGames(unittest.TestCase):
    def test_random_handle_games(self):
        for key in KEYS:
            if key == "bingo":
                continue
            lo, hi = NP[key]
            for seed in range(300):
                rnd = random.Random(seed)
                g = mk(key, rnd.randint(lo, hi), seed)
                steps = 0
                while not g.finished:
                    random_action(key, g, rnd)
                    steps += 1
                    self.assertLess(steps, 5000, key)
                json.dumps(g.public_state())
                for u in g.players:
                    json.dumps(g.view(u))

    def test_auto_play_games(self):
        for key in KEYS:
            lo, hi = NP[key]
            for seed in range(300):
                rnd = random.Random(seed)
                g = mk(key, rnd.randint(lo, hi), seed)
                steps = 0
                while not g.finished:
                    g.auto_play()
                    steps += 1
                    self.assertLess(steps, 5000, key)
                self.assertTrue(g.winner is not None or g.draw)

    def test_bingo_full_games(self):
        for seed in range(300):
            rnd = random.Random(seed)
            n = rnd.randint(2, 6)
            g = mk("bingo", n, seed)
            humans = g.players
            steps = 0
            while not g.finished:
                for u in humans:
                    if g.finished:
                        break
                    for x in g.called:
                        if g.finished:
                            break
                        if x in sum(g.cards[u], []) and x not in g.marks[u] and rnd.random() < 0.9:
                            g.handle(u, {"t": "mark", "n": x})
                    if rnd.random() < 0.3 and not g.finished:
                        try:
                            g.handle(u, {"t": "bingo"})
                        except GameError:
                            pass
                if not g.finished:
                    g.auto_play()
                steps += 1
                self.assertLess(steps, 200)
            self.assertTrue(g.winner is not None or g.draw)


class Fuzz(unittest.TestCase):
    def test_fuzz(self):
        junk = [None, True, False, -1, 0, 1, 99, 1.5, "x", [], {}, [1], {"a": 1}, 10 ** 12, float("inf")]
        rnd = random.Random(5)
        for key in KEYS:
            lo, hi = NP[key]
            for seed in range(30):
                g = mk(key, hi, seed)
                for _ in range(300):
                    msg = {"t": rnd.choice(["roll", "hold", "bid", "liar", "mark", "bingo", "take", "sow", "line", "x", 5, None])}
                    for f in ("q", "face", "n", "heap", "pit", "d", "r", "c"):
                        if rnd.random() < 0.7:
                            msg[f] = rnd.choice(junk)
                    uid = rnd.choice(list(g.players) + [999, -5])
                    try:
                        g.handle(uid, msg)
                    except GameError:
                        pass
                    if g.finished:
                        break


class PigRules(unittest.TestCase):
    def test_bust_and_hold(self):
        g = PigGame([1, 2], rng=random.Random(1))
        g.rng = type("R", (), {"randint": lambda s, a, b: 1})()
        g.handle(1, {"t": "roll"})
        self.assertEqual(g.current(), 2)
        self.assertEqual(g.scores[1], 0)
        g.rng = type("R", (), {"randint": lambda s, a, b: 4})()
        g.handle(2, {"t": "roll"})
        g.handle(2, {"t": "roll"})
        self.assertEqual(g.turn_total, 8)
        g.handle(2, {"t": "hold"})
        self.assertEqual(g.scores[2], 8)
        self.assertEqual(g.current(), 1)
        with self.assertRaises(GameError):
            g.handle(1, {"t": "hold"})

    def test_win_at_100(self):
        g = PigGame([1, 2], rng=random.Random(1))
        g.scores[1] = 96
        g.rng = type("R", (), {"randint": lambda s, a, b: 5})()
        g.handle(1, {"t": "roll"})
        self.assertTrue(g.finished)
        self.assertEqual(g.winner, 1)


class LiarRules(unittest.TestCase):
    def setUp(self):
        self.g = LiarsDiceGame([1, 2, 3], rng=random.Random(3))

    def test_raise_rules(self):
        g = self.g
        g.handle(1, {"t": "bid", "q": 3, "face": 4})
        with self.assertRaises(GameError):
            g.handle(2, {"t": "bid", "q": 3, "face": 4})
        with self.assertRaises(GameError):
            g.handle(2, {"t": "bid", "q": 2, "face": 6})
        g.handle(2, {"t": "bid", "q": 3, "face": 5})
        g.handle(3, {"t": "bid", "q": 4, "face": 1})

    def test_cannot_challenge_first(self):
        with self.assertRaises(GameError):
            self.g.handle(1, {"t": "liar"})

    def test_challenge_resolution(self):
        g = self.g
        g.dice = {1: [2, 2, 2, 2, 2], 2: [3, 3, 3, 3, 3], 3: [5, 5, 5, 5, 5]}
        g.handle(1, {"t": "bid", "q": 6, "face": 2})   # actual 5 -> false
        g.handle(2, {"t": "liar"})
        self.assertEqual(g.count[1], 4)
        self.assertEqual(g.current(), 1)               # loser starts next round
        self.assertTrue(g.last_reveal["dice"]["2"] == [3, 3, 3, 3, 3])
        self.assertEqual(g.round, 2)

    def test_true_bid_hurts_challenger(self):
        g = self.g
        g.dice = {1: [2, 2, 2, 2, 2], 2: [3] * 5, 3: [5] * 5}
        g.handle(1, {"t": "bid", "q": 5, "face": 2})
        g.handle(2, {"t": "liar"})
        self.assertEqual(g.count[2], 4)
        self.assertEqual(g.current(), 2)

    def test_ones_not_wild(self):
        g = self.g
        g.dice = {1: [1, 1, 1, 1, 1], 2: [3] * 5, 3: [5] * 5}
        g.handle(1, {"t": "bid", "q": 2, "face": 3})  # 5 threes actually, ones not wild
        g.handle(2, {"t": "liar"})
        self.assertTrue(g.last_reveal["actual"] == 5)

    def test_elimination_and_winner(self):
        g = LiarsDiceGame([1, 2], rng=random.Random(1))
        g.count = {1: 1, 2: 1}
        g.dice = {1: [2], 2: [3]}
        g.handle(1, {"t": "bid", "q": 2, "face": 2})
        g.handle(2, {"t": "liar"})
        self.assertTrue(g.finished)
        self.assertEqual(g.winner, 2)

    def test_secrecy(self):
        g = self.g
        for uid in (1, 2, 3, 777):
            s = json.dumps(g.view(uid))
            for other in (1, 2, 3):
                if other != uid and g.dice[other]:
                    self.assertNotIn(json.dumps(g.dice[other]), s.replace(json.dumps(g.view(uid)["my_dice"]), "") if uid == other else s)
        self.assertEqual(g.view(777)["my_dice"], [])
        self.assertEqual(g.view(1)["my_dice"], g.dice[1])
        self.assertNotIn("dice\": [", json.dumps(g.public_state()["players"]))
        # after a challenge the dice are public
        g.handle(1, {"t": "bid", "q": 1, "face": 2})
        g.handle(2, {"t": "liar"})
        self.assertIn("2", g.view(777)["last_reveal"]["dice"])


class BingoRules(unittest.TestCase):
    def test_card_valid(self):
        g = BingoGame([1, 2], rng=random.Random(2))
        for u in (1, 2):
            c = g.cards[u]
            for col in range(5):
                nums = [c[r][col] for r in range(5) if (r, col) != (2, 2)]
                self.assertTrue(all(1 + 15 * col <= x <= 15 + 15 * col for x in nums))
                self.assertEqual(len(set(nums)), len(nums))
            self.assertEqual(c[2][2], 0)

    def test_mark_validation_and_false_claim(self):
        g = BingoGame([1, 2], rng=random.Random(2))
        notcalled = next(x for x in g.cards[1][0] if x not in g.called)
        with self.assertRaises(GameError):
            g.handle(1, {"t": "mark", "n": notcalled})
        g.handle(1, {"t": "bingo"})  # false claim
        self.assertFalse(g.finished)
        self.assertFalse(g.last_claim["ok"])
        with self.assertRaises(GameError):
            g.handle(1, {"t": "bingo"})
        for _ in range(3):
            g.auto_play()
        g.handle(1, {"t": "bingo"})

    def test_valid_claim_wins(self):
        g = BingoGame([1, 2], rng=random.Random(2))
        row = [x for x in g.cards[1][2] if x]
        g.called = list(row)
        for x in row:
            g.handle(1, {"t": "mark", "n": x})
        g.handle(1, {"t": "bingo"})
        self.assertEqual(g.winner, 1)
        self.assertIsNotNone(g.reveal)

    def test_secrecy(self):
        g = BingoGame([1, 2], rng=random.Random(2))
        for viewer, other in ((1, 2), (2, 1), (999, 1)):
            s = g.view(viewer)
            self.assertNotEqual(s["card"], g.cards[other])
            self.assertNotIn(json.dumps(g.cards[other]), json.dumps(s))
        self.assertIsNone(g.view(999)["card"])
        self.assertEqual(g.view(1)["card"], g.cards[1])

    def test_ticker_metadata(self):
        g = BingoGame([-1, 5, 6], rng=random.Random(2))
        self.assertTrue(g.ticker)
        self.assertEqual(g.current(), 5)
        a = g.phase_id
        g.auto_play()
        self.assertEqual(g.phase_id, a + 1)


class NimRules(unittest.TestCase):
    def test_optimal_wins(self):
        for seed in range(50):
            g = NimGame([1, 2], rng=random.Random(seed))
            rnd = random.Random(seed)
            while not g.finished:
                if g.current() == 1:   # perfect player
                    g.auto_play()
                else:
                    h = rnd.choice([i for i, v in enumerate(g.heaps) if v])
                    g.handle(2, {"t": "take", "heap": h, "n": rnd.randint(1, g.heaps[h])})
            # 3^5^7 = 1: first player wins against anything when he plays perfectly
            self.assertEqual(g.winner, 1)

    def test_last_take_wins(self):
        g = NimGame([1, 2])
        g.heaps = [0, 0, 2]
        g.handle(1, {"t": "take", "heap": 2, "n": 2})
        self.assertEqual(g.winner, 1)


class MancalaRules(unittest.TestCase):
    def test_extra_turn(self):
        g = MancalaGame([1, 2])
        g.handle(1, {"t": "sow", "pit": 2})   # 4 stones from pit 2 end in the store (2+4=6)
        self.assertEqual(g.board[6], 1)
        self.assertEqual(g.current(), 1)
        self.assertTrue(g.last_move["extra"])

    def test_capture(self):
        g = MancalaGame([1, 2])
        g.board = [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 5, 0, 0, 0]
        g.board[12 - 1] = 5
        g.handle(1, {"t": "sow", "pit": 0})
        self.assertEqual(g.board[6], 6)
        self.assertEqual(g.board[1], 0)
        self.assertEqual(g.board[11], 0)

    def test_skips_opponent_store(self):
        g = MancalaGame([1, 2])
        g.board = [0, 0, 0, 0, 0, 9, 0, 0, 0, 0, 0, 0, 1, 0]
        g.handle(1, {"t": "sow", "pit": 5})
        self.assertEqual(g.board[13], 0)
        self.assertEqual(sum(g.board), 10)

    def test_sweep_end(self):
        g = MancalaGame([1, 2])
        g.board = [0, 0, 0, 0, 0, 1, 10, 3, 0, 0, 0, 0, 0, 5]
        g.handle(1, {"t": "sow", "pit": 5})
        self.assertTrue(g.finished)
        self.assertEqual(g.board[6], 11)
        self.assertEqual(g.board[13], 8)
        self.assertEqual(g.winner, 1)
        self.assertEqual(sum(g.board), 19)

    def test_stone_conservation(self):
        for seed in range(100):
            g = mk("mancala", 2, seed)
            while not g.finished:
                g.auto_play()
                self.assertEqual(sum(g.board), 48)


class DotsRules(unittest.TestCase):
    def test_box_gives_extra_move(self):
        g = DotsGame([1, 2])
        g.handle(1, {"t": "line", "d": "h", "r": 0, "c": 0})
        g.handle(2, {"t": "line", "d": "h", "r": 1, "c": 0})
        g.handle(1, {"t": "line", "d": "v", "r": 0, "c": 0})
        g.handle(2, {"t": "line", "d": "v", "r": 0, "c": 1})   # completes box (0,0) for player 2
        self.assertEqual(g.boxes[0][0], 2)
        self.assertEqual(g.scores[2], 1)
        self.assertEqual(g.current(), 2)
        self.assertEqual(g.last_move["boxes"], [[0, 0]])

    def test_edge_counts_and_total(self):
        g = DotsGame([1, 2])
        self.assertEqual(len(g.free_edges()), 60)
        while not g.finished:
            g.auto_play()
        self.assertEqual(sum(g.scores.values()), 25)
        self.assertFalse(g.draw)

    def test_taken_line(self):
        g = DotsGame([1, 2])
        g.handle(1, {"t": "line", "d": "h", "r": 0, "c": 0})
        with self.assertRaises(GameError):
            g.handle(2, {"t": "line", "d": "h", "r": 0, "c": 0})


class Leaving(unittest.TestCase):
    def test_remove_player_ends_or_continues(self):
        for key in KEYS:
            lo, hi = NP[key]
            g = mk(key, lo, 1)
            g.remove_player(g.players[0])
            if lo == 2:
                self.assertTrue(g.finished)
                self.assertEqual(g.winner, g.players[1])
            g = mk(key, hi, 1)
            for u in g.players[:-1]:
                g.remove_player(u)
            self.assertTrue(g.finished)
            self.assertEqual(g.winner, g.players[-1])


if __name__ == "__main__":
    unittest.main()

"""Tests for Snakes & Ladders, Connect Four, Rock-Paper-Scissors, Memory Match and Carrom."""
import json
import math
import random
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.games import GAME_INFO, GAMES
from app.games import carrom
from app.games.base import GameError
from app.games.connect4 import COLS, ROWS, ConnectFourGame, find_four
from app.games.memory import SYMBOLS, MemoryGame
from app.games.rps import MAX_ROUNDS, RPSGame
from app.games.snakes import LADDERS, SNAKES, SnakesGame


class Seq:
    def __init__(self, vals):
        self.vals = list(vals)

    def randint(self, a, b):
        return self.vals.pop(0)

    def choice(self, seq):
        return seq[0]

    def shuffle(self, x):
        pass

    def random(self):
        return 0.0

    def uniform(self, a, b):
        return 0.0


class RegistryTests(unittest.TestCase):
    def test_every_game_registered_and_serialisable(self):
        self.assertEqual(set(GAMES), set(GAME_INFO))
        cmds = [i["cmd"] for i in GAME_INFO.values()]
        self.assertEqual(len(cmds), len(set(cmds)))
        for name, cls in GAMES.items():
            info = GAME_INFO[name]
            g = cls(list(range(1, info["min"] + 1)))
            json.dumps(g.public_state())  # must be JSON-safe
            self.assertEqual(g.current(), 1)


class SnakesTests(unittest.TestCase):
    def test_board_is_consistent(self):
        self.assertFalse(set(SNAKES) & set(LADDERS))
        self.assertTrue(all(h > t for h, t in SNAKES.items()))
        self.assertTrue(all(b < t <= 100 for b, t in LADDERS.items()))
        self.assertFalse((set(SNAKES) | set(LADDERS)) & set(SNAKES.values()) & set(LADDERS))
        self.assertNotIn(100, SNAKES)

    def test_ladder_snake_overshoot_win(self):
        g = SnakesGame([1, 2], rng=Seq([1]))
        g.handle(1, {"t": "roll"})
        self.assertEqual((g.pos[1], g.last_move["kind"]), (38, "ladder"))
        g = SnakesGame([1, 2], rng=Seq([6]))
        g.pos[1] = 10
        g.handle(1, {"t": "roll"})
        self.assertEqual((g.pos[1], g.last_move["kind"]), (6, "snake"))
        g = SnakesGame([1, 2], rng=Seq([5, 2]))
        g.pos[1] = 97
        g.handle(1, {"t": "roll"})  # 97+5=102 overshoot
        self.assertEqual(g.pos[1], 97)
        self.assertEqual(g.current(), 2)
        g.pos[2] = 5
        g.turn_idx = 0
        g.pos[1] = 98
        g.handle(1, {"t": "roll"})  # 98+2=100
        self.assertTrue(g.finished and g.winner == 1)

    def test_six_rolls_again_third_six_forfeits(self):
        g = SnakesGame([1, 2], rng=Seq([6, 2]))
        g.pos[1] = 20
        g.handle(1, {"t": "roll"})
        self.assertEqual(g.current(), 1)
        g.handle(1, {"t": "roll"})
        self.assertEqual(g.current(), 2)
        g = SnakesGame([1, 2], rng=Seq([6, 6, 6]))
        g.pos[1] = 20
        for _ in range(3):
            g.handle(1, {"t": "roll"})
        self.assertEqual(g.current(), 2)
        self.assertEqual(g.pos[1], 32)  # two 6s moved, the third was forfeited

    def test_turn_order_and_errors(self):
        g = SnakesGame([1, 2, 3], rng=Seq([2, 2, 2]))
        with self.assertRaises(GameError):
            g.handle(2, {"t": "roll"})
        with self.assertRaises(GameError):
            g.handle(1, {"t": "jump"})
        for u in (1, 2, 3):
            g.handle(u, {"t": "roll"})
        self.assertEqual(g.current(), 1)

    def test_leaving(self):
        g = SnakesGame([1, 2, 3])
        g.remove_player(1)
        self.assertEqual(g.current(), 2)
        g.remove_player(2)
        self.assertTrue(g.finished and g.winner == 3)

    def test_random_games_finish(self):
        for n in (2, 3, 4):
            for seed in range(20):
                g = SnakesGame(list(range(1, n + 1)), rng=random.Random(seed))
                steps = 0
                while not g.finished:
                    g.auto_play()
                    steps += 1
                    self.assertLess(steps, 5000)
                self.assertEqual(g.pos[g.winner], 100)


class Connect4Tests(unittest.TestCase):
    def play(self, g, cols):
        for c in cols:
            g.handle(g.current(), {"t": "drop", "col": c})

    def test_vertical_horizontal_diagonal(self):
        g = ConnectFourGame([1, 2])
        self.play(g, [0, 1, 0, 1, 0, 1, 0])
        self.assertEqual((g.winner, len(g.line)), (1, 4))
        g = ConnectFourGame([1, 2])
        self.play(g, [0, 0, 1, 1, 2, 2, 3])
        self.assertEqual(g.winner, 1)
        g = ConnectFourGame([1, 2])
        self.play(g, [0, 1, 1, 2, 3, 2, 2, 3, 3, 6, 3])  # P1 builds a rising diagonal 0..3
        self.assertEqual(g.winner, 1)

    def test_draw_pattern_has_no_four_and_engine_declares_draw(self):
        g = ConnectFourGame([1, 2])
        for r in range(ROWS):
            for c in range(COLS):
                g.board[r * COLS + c] = g.players[(r // 2 + c) % 2]
        self.assertIsNone(find_four(g.board, 1))
        self.assertIsNone(find_four(g.board, 2))
        g.board[0] = None  # leave the last cell
        g.handle(1, {"t": "drop", "col": 0})
        self.assertTrue(g.finished and g.draw and g.winner is None)

    def test_errors(self):
        g = ConnectFourGame([1, 2])
        for who, col in ((2, 0), (1, 7), (1, -1), (1, "0"), (1, True)):
            with self.assertRaises(GameError):
                g.handle(who, {"t": "drop", "col": col})
        for _ in range(3):
            self.play(g, [0, 0])
        with self.assertRaises(GameError):
            g.handle(g.current(), {"t": "drop", "col": 0})  # column full

    def test_ai_wins_blocks_and_finishes(self):
        g = ConnectFourGame([1, 2], rng=random.Random(1))
        for c in (0, 1, 2):
            g.board[(ROWS - 1) * COLS + c] = 2
        g.turn_idx = 0  # P1 to move must block at column 3
        g.auto_play()
        self.assertEqual(g.board[(ROWS - 1) * COLS + 3], 1)
        for seed in range(20):
            g = ConnectFourGame([1, 2], rng=random.Random(seed))
            n = 0
            while not g.finished:
                g.auto_play()
                n += 1
                self.assertLess(n, 60)


class RPSTests(unittest.TestCase):
    def test_round_and_hidden_picks(self):
        g = RPSGame([1, 2])
        g.handle(1, {"t": "pick", "choice": "rock"})
        st = json.dumps(g.public_state())
        self.assertNotIn("rock", st)  # opponent must not see the pick
        self.assertEqual(g.current(), 2)
        with self.assertRaises(GameError):
            g.handle(1, {"t": "pick", "choice": "paper"})
        g.handle(2, {"t": "pick", "choice": "scissors"})
        self.assertEqual(g.scores, {1: 1, 2: 0})
        self.assertEqual(g.last_round["winner"], 1)
        self.assertEqual(g.last_round["picks"], {1: "rock", 2: "scissors"})

    def test_first_to_two_wins(self):
        g = RPSGame([1, 2])
        for _ in range(2):
            g.handle(1, {"t": "pick", "choice": "paper"})
            g.handle(2, {"t": "pick", "choice": "rock"})
        self.assertTrue(g.finished and g.winner == 1)

    def test_draws_replay_then_cap(self):
        g = RPSGame([1, 2])
        for _ in range(MAX_ROUNDS):
            g.handle(1, {"t": "pick", "choice": "rock"})
            g.handle(2, {"t": "pick", "choice": "rock"})
        self.assertTrue(g.finished and g.draw)

    def test_bad_choice_and_bot(self):
        g = RPSGame([1, 2])
        with self.assertRaises(GameError):
            g.handle(1, {"t": "pick", "choice": "lizard"})
        for seed in range(20):
            g = RPSGame([1, 2], rng=random.Random(seed))
            while not g.finished:
                g.auto_play()
            self.assertTrue(g.draw or g.winner in (1, 2))


class MemoryTests(unittest.TestCase):
    def fresh(self):
        g = MemoryGame([1, 2], rng=random.Random(0))
        g.cards = [s for s in SYMBOLS for _ in (0, 1)]  # pairs are (0,1), (2,3), ...
        return g

    def test_match_keeps_turn_mismatch_passes_and_hides_later(self):
        g = self.fresh()
        g.handle(1, {"t": "flip", "i": 0})
        g.handle(1, {"t": "flip", "i": 1})
        self.assertEqual((g.scores[1], g.current()), (1, 1))
        g.handle(1, {"t": "flip", "i": 2})
        g.handle(1, {"t": "flip", "i": 4})  # mismatch
        self.assertEqual(g.current(), 2)
        st = g.public_state()
        self.assertEqual((st["cards"][2], st["cards"][4]), (SYMBOLS[1], SYMBOLS[2]))  # both still visible
        g.handle(2, {"t": "flip", "i": 6})
        self.assertEqual(g.public_state()["up"], [6])  # old pair flipped back down

    def test_face_down_values_never_leak(self):
        g = self.fresh()
        shown = g.public_state()["cards"]
        self.assertTrue(all(c is None for c in shown))
        g.handle(1, {"t": "flip", "i": 5})
        self.assertEqual(sum(c is not None for c in g.public_state()["cards"]), 1)

    def test_errors(self):
        g = self.fresh()
        g.handle(1, {"t": "flip", "i": 0})
        g.handle(1, {"t": "flip", "i": 1})
        for who, i in ((2, 2), (1, 0), (1, 16), (1, -1), (1, "2"), (1, True)):
            with self.assertRaises(GameError):
                g.handle(who, {"t": "flip", "i": i})
        g.handle(1, {"t": "flip", "i": 2})
        with self.assertRaises(GameError):
            g.handle(1, {"t": "flip", "i": 2})  # already face up

    def test_bot_games_finish_with_8_pairs(self):
        for seed in range(30):
            g = MemoryGame([1, 2], rng=random.Random(seed))
            n = 0
            while not g.finished:
                g.auto_play()
                n += 1
                self.assertLess(n, 500)
            self.assertEqual(sum(g.scores.values()), 8)
            self.assertEqual(g.draw, g.scores[1] == g.scores[2])


class CarromTests(unittest.TestCase):
    def test_layout(self):
        coins = carrom.initial_coins()
        kinds = [c["kind"] for c in coins]
        self.assertEqual((kinds.count("w"), kinds.count("b"), kinds.count("q")), (9, 9, 1))
        for i, a in enumerate(coins):
            for b in coins[i + 1:]:
                self.assertGreaterEqual(math.hypot(a["x"] - b["x"], a["y"] - b["y"]), 2 * carrom.CR - 0.01)

    def test_physics_pockets_and_is_deterministic(self):
        def run():
            return carrom.simulate([[150, 150, -10, -10, carrom.SR, carrom.M_STRIKER], [60, 60, 0, 0, carrom.CR, carrom.M_COIN]])
        frames, out, (x, y, alive) = run()
        self.assertFalse(alive[1], "the coin should fall into the corner pocket")
        self.assertIn(1, [b for b, _ in out])
        self.assertEqual(run()[0], frames)  # same input, identical frames
        self.assertTrue(all(len(f) == 4 for f in frames))

    def test_physics_comes_to_rest_and_stays_on_board(self):
        rng = random.Random(3)
        coins = carrom.initial_coins()
        bodies = [[400, 690, 0.8 * carrom.MAX_V * math.cos(-1.4), 0.8 * carrom.MAX_V * math.sin(-1.4), carrom.SR, carrom.M_STRIKER]]
        bodies += [[c["x"], c["y"], 0, 0, carrom.CR, carrom.M_COIN] for c in coins]
        frames, out, (x, y, alive) = carrom.simulate(bodies)
        self.assertLess(len(frames), carrom.MAX_TICKS // carrom.FRAME_EVERY + 3)
        for i in range(len(bodies)):
            if alive[i]:
                self.assertTrue(0 <= x[i] <= carrom.SIZE and 0 <= y[i] <= carrom.SIZE)

    def scored(self, kind, striker_in=False, extra_coin=True):
        g = carrom.CarromGame([1, 2])
        g.coins = [{"id": 5, "kind": kind, "x": 100.0, "y": 100.0}, {"id": 6, "kind": "w", "x": 400.0, "y": 300.0}, {"id": 7, "kind": "b", "x": 500.0, "y": 300.0}]
        xs, ys = [400.0, 0.0, 400.0, 500.0], [690.0, 0.0, 300.0, 300.0]
        alive = [not striker_in, False, True, True]
        fake = ([[0] * 8, [0] * 8], [[1, 1]], (xs, ys, alive))
        with mock.patch.object(carrom, "simulate", return_value=fake):
            g._shoot(400, -1.5, 0.5)
        return g

    def test_scoring_rules(self):
        g = self.scored("w")       # player 1 is white and pockets own coin: +1 and shoots again
        self.assertEqual((g.scores[1], g.scores[2], g.current()), (1, 0, 1))
        g = self.scored("b")       # pockets opponent's coin: opponent +1, turn passes
        self.assertEqual((g.scores[1], g.scores[2], g.current()), (0, 1, 2))
        g = self.scored("q")       # queen: +3 and shoot again
        self.assertEqual((g.scores[1], g.current()), (3, 1))
        g = self.scored("w", striker_in=True)  # foul: points stand, turn lost
        self.assertEqual((g.scores[1], g.current()), (1, 2))

    def test_game_ends_at_11_and_clearing_board(self):
        g = carrom.CarromGame([1, 2])
        g.scores[1] = 10
        g = self.scored_from(g)
        self.assertTrue(g.finished and g.winner == 1)

    def scored_from(self, g):
        g.coins = [{"id": 5, "kind": "w", "x": 100.0, "y": 100.0}, {"id": 6, "kind": "b", "x": 400.0, "y": 300.0}]
        fake = ([[0] * 6, [0] * 6], [[1, 1]], ([400.0, 0.0, 400.0], [690.0, 0.0, 300.0], [True, False, True]))
        with mock.patch.object(carrom, "simulate", return_value=fake):
            g._shoot(400, -1.5, 0.5)
        return g

    def test_validation(self):
        g = carrom.CarromGame([1, 2])
        ok = {"t": "shoot", "x": 400, "angle": -1.5, "power": 0.5}
        for bad in (dict(ok, x="a"), dict(ok, angle=float("nan")), dict(ok, power=True), dict(ok, t="roll")):
            with self.assertRaises(GameError):
                g.handle(1, bad)
        with self.assertRaises(GameError):
            g.handle(2, ok)  # not your turn
        g.coins.append({"id": 99, "kind": "w", "x": 400.0, "y": 690.0})
        with self.assertRaises(GameError):
            g.handle(1, ok)  # striker spot blocked

    def test_valid_shot_produces_frames(self):
        g = carrom.CarromGame([1, 2])
        g.handle(1, {"t": "shoot", "x": 400, "angle": -math.pi / 2, "power": 1})
        shot = g.last_shot
        self.assertEqual(shot["uid"], 1)
        self.assertEqual(len(shot["frames"][0]), 2 * (1 + len(shot["ids"])))
        self.assertLess(len(json.dumps(g.public_state())), 120_000)

    def test_bot_vs_bot_finishes(self):
        for seed in (1, 2):
            g = carrom.CarromGame([1, 2], rng=random.Random(seed))
            n = 0
            while not g.finished:
                g.auto_play()
                n += 1
                self.assertLessEqual(n, carrom.MAX_SHOTS + 5)
            self.assertTrue(g.draw or g.winner in (1, 2))
            self.assertLessEqual(sum(g.scores.values()), 21)

    def test_leaving(self):
        g = carrom.CarromGame([1, 2])
        g.remove_player(2)
        self.assertTrue(g.finished and g.winner == 1)


if __name__ == "__main__":
    unittest.main()

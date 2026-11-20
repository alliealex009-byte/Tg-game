import json
import random
import unittest

from app.games import GAMES, GAME_INFO
from app.games.base import GameError
from app.games.boxing import BoxingGame


class BoxingTests(unittest.TestCase):
    def g(self, p=(1, 2)):
        return BoxingGame(list(p), rng=random.Random(3))

    def test_registered(self):
        self.assertIn("boxing", GAMES)
        self.assertEqual(GAME_INFO["boxing"]["cat"], "Action")

    def test_simultaneous_resolve_and_hidden_picks(self):
        g = self.g()
        g.handle(1, {"t": "move", "move": "jab"})
        st = g.view(2)
        self.assertTrue(st["picked"][1])
        self.assertNotIn("jab", json.dumps(st["picked"]))
        g.handle(2, {"t": "move", "move": "dodge"})
        self.assertEqual(g.last_exchange["dmg"][2], g.last_exchange["dmg"][2])
        self.assertGreater(g.last_exchange["dmg"][2], 0)  # jab can't be dodged

    def test_errors(self):
        g = self.g()
        with self.assertRaises(GameError):
            g.handle(1, {"t": "move", "move": "kick"})
        g.handle(1, {"t": "move", "move": "jab"})
        with self.assertRaises(GameError):
            g.handle(1, {"t": "move", "move": "jab"})
        with self.assertRaises(GameError):
            g.handle(9, {"t": "move", "move": "jab"})

    def test_full_fight_finishes(self):
        for seed in range(20):
            g = BoxingGame([1, 2], rng=random.Random(seed))
            for _ in range(200):
                if g.finished:
                    break
                g.auto_play()
            self.assertTrue(g.finished)
            self.assertTrue(g.winner in (1, 2) or g.draw)

    def test_bot_fight_and_forfeit(self):
        g = BoxingGame([1, -1], rng=random.Random(1))
        g.handle(1, {"t": "move", "move": "block"})
        self.assertEqual(g.last_exchange["n"], 1)
        g.remove_player(1)
        self.assertEqual(g.winner, -1)
        json.dumps(g.public_state())


if __name__ == "__main__":
    unittest.main()

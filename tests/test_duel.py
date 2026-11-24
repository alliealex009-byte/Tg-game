import random
import unittest

from app.games.base import GameError
from app.games.duel import CoinDuelGame, DiceDuelGame


class DuelTests(unittest.TestCase):
    def test_coin_duel_finishes_with_one_winner(self):
        for seed in range(30):
            g = CoinDuelGame([1, 2], random.Random(seed))
            n = 0
            while not g.finished and n < 40:
                g.handle(1, {"t": "call", "side": "heads"}); g.handle(2, {"t": "call", "side": "tails"}); n += 1
            self.assertTrue(g.finished)
            self.assertTrue(g.winner in (1, 2) and not g.draw)               # opposite calls always split the point
            self.assertEqual(g.public_state()["kind"], "coinduel")

    def test_coin_duel_rules(self):
        g = CoinDuelGame([1, 2], random.Random(1))
        with self.assertRaises(GameError): g.handle(1, {"t": "call", "side": "edge"})
        g.handle(1, {"t": "call", "side": "heads"})
        with self.assertRaises(GameError): g.handle(1, {"t": "call", "side": "tails"})
        self.assertNotIn("heads", str(g.public_state()))                      # pick stays hidden

    def test_dice_duel(self):
        g = DiceDuelGame([1, 2], random.Random(3))
        while not g.finished:
            g.handle(1, {"t": "roll"}); g.handle(2, {"t": "roll"})
        self.assertTrue(max(g.scores.values()) == 3 or g.rounds == 9)
        lr = g.last_round
        self.assertTrue(all(1 <= v <= 6 for v in lr["dice"].values()))

    def test_leave_and_auto(self):
        g = DiceDuelGame([1, 2]); g.remove_player(1)
        self.assertEqual(g.winner, 2)
        g = CoinDuelGame([1, 2])
        for _ in range(40):
            if g.finished: break
            g.auto_play()
        self.assertTrue(g.finished)


if __name__ == "__main__":
    unittest.main()


class BotIdentityTests(unittest.TestCase):
    def test_bot_names_half_girls_with_dp(self):
        import os
        from app import rooms
        girls = 0
        for _ in range(200):
            n, ph = rooms.pick_bot_identity(set())
            self.assertTrue(os.path.exists(os.path.join(os.path.dirname(os.path.dirname(__file__)), "webapp", ph.lstrip("/"))), ph)
            self.assertEqual(n in rooms.GIRL_NAMES, ph.startswith("/avatars/g"))
            girls += n in rooms.GIRL_NAMES
        self.assertTrue(70 < girls < 130)

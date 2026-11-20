import unittest

from app.arcade import DAILY_CAP, Arcade
from app.db import DB


class ArcadeTests(unittest.TestCase):
    def setUp(self):
        self.db = DB(":memory:", 1000, 200)
        self.db.upsert_user(1, "a", "a", None)
        self.t = [1_000_000.0]
        self.a = Arcade(self.db, clock=lambda: self.t[0])

    def test_new_games_capped(self):
        from app.arcade import GAMES
        for g in ("byteblock", "tiledash", "neonslice", "minttap", "turbocoin"):
            self.assertIn(g, GAMES)
            self.a.start(1, g)
            with self.assertRaises(ValueError):
                self.a.claim(1, g, 5)               # too short
            self.a.start(1, g)
            self.t[0] += 60
            r = self.a.claim(1, g, 10**9)           # hacked score is clamped
            self.assertLessEqual(r["coins"], GAMES[g][3])

    def test_claim_needs_run_and_time(self):
        with self.assertRaises(ValueError):
            self.a.claim(1, "bricks", 10)
        self.a.start(1, "bricks")
        self.t[0] += 5
        with self.assertRaises(ValueError):
            self.a.claim(1, "bricks", 10)

    def test_claim_is_capped_by_rate_and_run(self):
        self.a.start(1, "bricks")
        self.t[0] += 20
        r = self.a.claim(1, "bricks", 10**9)  # hacked score
        self.assertLessEqual(r["coins"], 60)
        self.assertEqual(self.db.get_user(1)["coins"], 1000 + r["coins"])

    def test_bad_scores(self):
        self.a.start(1, "bricks")
        self.t[0] += 30
        for bad in (True, "9", float("nan"), None):
            with self.assertRaises(ValueError):
                self.a.claim(1, "bricks", bad)
            self.a.start(1, "bricks"); self.t[0] += 30

    def test_daily_cap(self):
        for _ in range(100):
            self.a.start(1, "bricks"); self.t[0] += 120
            self.a.claim(1, "bricks", 10**6)
        self.assertLessEqual(self.db.get_user(1)["coins"] - 1000, DAILY_CAP)
        self.t[0] += 86400
        self.assertEqual(self.a.left_today(1), DAILY_CAP)

    def test_tap_energy_and_rate(self):
        self.t[0] += 10
        r = self.a.tap(1, 10_000)
        self.assertLessEqual(r["earned"], 150)       # <= 15/s * 10s
        self.t[0] += 0.1
        self.assertLessEqual(self.a.tap(1, 500)["earned"], 6)
        with self.assertRaises(ValueError):
            self.a.tap(1, True)

    def test_upgrade(self):
        self.a.tap_upgrade(1)
        self.assertEqual(self.db.get_user(1)["tap_level"], 2)
        self.assertEqual(self.db.get_user(1)["coins"], 850)

    def test_farm(self):
        self.a.farm_act(1, 0, "plant")
        with self.assertRaises(ValueError):
            self.a.farm_act(1, 0, "harvest")
        self.t[0] += 61
        self.a.farm_act(1, 0, "harvest")
        self.assertEqual(self.db.get_user(1)["coins"], 1030)
        with self.assertRaises(ValueError):
            self.a.farm_act(1, 9, "plant")


if __name__ == "__main__":
    unittest.main()

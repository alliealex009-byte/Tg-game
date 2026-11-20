import random
import unittest

from app.arcade import Arcade
from app.db import DB
from app.idle import Idle


class IdleTests(unittest.TestCase):
    def setUp(self):
        self.db = DB(":memory:", 1000, 200)
        self.db.upsert_user(1, "a", "a", None)
        self.t = [1_000_000.0]
        self.a = Arcade(self.db, clock=lambda: self.t[0])
        self.i = Idle(self.a, clock=lambda: self.t[0], rng=random.Random(1))

    def coins(self):
        return self.db.get_user(1)["coins"]

    def test_sprout_grows_offline_and_caps(self):
        self.i.state("sprout", 1)
        with self.assertRaises(ValueError):
            self.i.act("sprout", 1, "collect")
        self.t[0] += 3600
        self.assertEqual(self.i.state("sprout", 1)["ready"], 30)
        self.t[0] += 10 * 3600
        self.assertEqual(self.i.state("sprout", 1)["ready"], 180)    # capped at 6h
        before = self.coins()
        self.i.act("sprout", 1, "collect")
        self.assertEqual(self.coins(), before + 180)
        self.assertEqual(self.i.state("sprout", 1)["ready"], 0)

    def test_sprout_upgrade_costs_and_banks(self):
        self.i.state("sprout", 1)
        self.t[0] += 3600
        st = self.i.act("sprout", 1, "upgrade")
        self.assertEqual(st["lvl"], 2)
        self.assertEqual(self.coins(), 1000 - 200 + 30)
        self.db.c.execute("UPDATE users SET coins=0 WHERE id=1")
        with self.assertRaises(ValueError):
            self.i.act("sprout", 1, "upgrade")

    def test_paws(self):
        st = self.i.state("paws", 1)
        self.assertEqual(st["mood"], "sad")
        self.i.act("paws", 1, "feed")
        self.i.act("paws", 1, "play")
        with self.assertRaises(ValueError):
            self.i.act("paws", 1, "feed")
        st = self.i.state("paws", 1)
        self.assertEqual(st["mood"], "happy")
        before = self.coins()
        self.i.act("paws", 1, "claim")
        self.assertEqual(self.coins(), before + 18)
        with self.assertRaises(ValueError):
            self.i.act("paws", 1, "claim")

    def test_world(self):
        with self.assertRaises(ValueError):
            self.i.act("world", 1, "build", {"idx": 99, "type": "house"})
        self.i.act("world", 1, "build", {"idx": 0, "type": "house"})
        with self.assertRaises(ValueError):
            self.i.act("world", 1, "build", {"idx": 0, "type": "farm"})
        self.t[0] += 3600
        self.assertEqual(self.i.state("world", 1)["ready"], 10)
        self.i.act("world", 1, "collect")
        self.assertEqual(self.coins(), 1000 - 60 + 10)

    def test_realm(self):
        self.i.act("realm", 1, "start", "scout")
        with self.assertRaises(ValueError):
            self.i.act("realm", 1, "start", "raid")
        with self.assertRaises(ValueError):
            self.i.act("realm", 1, "claim")
        self.t[0] += 301
        st = self.i.act("realm", 1, "claim")
        self.assertIsNone(st["mission"])
        self.assertGreaterEqual(st["xp"], 1)

    def test_unknown_and_daily_cap(self):
        with self.assertRaises(ValueError):
            self.i.state("nope", 1)
        self.db.c.execute("UPDATE users SET arc_day=?, arc_earned=6000 WHERE id=1", (self.a._day(),))
        self.i.state("sprout", 1)
        self.t[0] += 7200
        before = self.coins()
        with self.assertRaises(ValueError):
            self.i.act("sprout", 1, "collect")        # daily arcade cap reached: nothing paid, nothing lost
        self.assertEqual(self.coins(), before)
        self.assertGreater(self.i.state("sprout", 1)["ready"], 0)


if __name__ == "__main__":
    unittest.main()

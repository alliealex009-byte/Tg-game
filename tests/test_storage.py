"""The same wallet/referral/leaderboard behaviour must hold on SQLite and on MongoDB."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db import DB  # noqa: E402
from app.mongo import MongoDB  # noqa: E402
from app.rewards import referral_reward  # noqa: E402
from fake_mongo import FakeClient  # noqa: E402


class Contract:
    def make(self):
        raise NotImplementedError

    def setUp(self):
        self.db = self.make()
        for i in (1, 2, 3, 4, 5, 6, 7, 8):
            self.db.upsert_user(i, f"U{i}", f"u{i}", None)

    def test_welcome_and_no_duplicate_welcome(self):
        self.assertEqual(self.db.get_user(1)["coins"], 1000)
        self.db.upsert_user(1, "Renamed", None, None)
        u = self.db.get_user(1)
        self.assertEqual((u["name"], u["coins"], u["username"]), ("Renamed", 1000, "u1"))

    def test_coins_never_negative(self):
        self.assertEqual(self.db.add_coins(1, -400, "t"), 600)
        self.assertIsNone(self.db.add_coins(1, -601, "t"))
        self.assertEqual(self.db.get_user(1)["coins"], 600)
        self.assertIsNone(self.db.add_coins(999, 5, "t"))

    def test_charge_all_is_all_or_nothing(self):
        self.db.add_coins(2, -950, "t")  # user 2 has 50
        self.assertEqual(self.db.charge_all([1, 2, 3], 100, "bet"), 2)
        self.assertEqual([self.db.get_user(i)["coins"] for i in (1, 3)], [1000, 1000])
        self.assertIsNone(self.db.charge_all([1, 3], 100, "bet"))
        self.assertEqual([self.db.get_user(i)["coins"] for i in (1, 3)], [900, 900])

    def test_daily_and_streak(self):
        ok, coins, wait = self.db.claim_daily(1)
        self.assertTrue(ok)
        self.assertEqual(coins, 1000 + 200)
        ok, _, wait = self.db.claim_daily(1)
        self.assertFalse(ok)
        self.assertGreater(wait, 80000)

    def test_referral_ladder_up_to_700(self):
        earned = []
        for new in (2, 3, 4, 5, 6, 7):
            earned.append(self.db.set_referrer(new, 1, 700))
        self.assertEqual(earned, [300, 400, 500, 600, 700, 700])
        self.assertEqual(self.db.get_user(1)["refs"], 6)
        self.assertEqual(self.db.get_user(1)["coins"], 1000 + sum(earned))
        self.assertEqual(self.db.get_user(2)["coins"], 1000 + 150)

    def test_referral_guards(self):
        self.assertTrue(self.db.set_referrer(2, 1, 700))
        self.assertFalse(self.db.set_referrer(2, 3, 700))   # only once
        self.assertFalse(self.db.set_referrer(1, 1, 700))   # not yourself
        self.db.record_result("ludo", "R", 0, [4], 4, 0)
        self.assertFalse(self.db.set_referrer(4, 1, 700))   # already played, not a new user
        self.assertFalse(self.db.set_referrer(99, 1, 700))  # unknown user

    def test_results_leaderboard_stats(self):
        self.db.record_result("chess", "A", 100, [1, 2], 1, 180)
        self.db.record_result("uno", "B", 0, [1, 2, 3], None, 0, [2, 3])
        lb = self.db.leaderboard(5)
        self.assertEqual({r["id"] for r in lb}, {1, 2, 3})
        self.assertEqual(lb[0]["wins"], 1)
        st = self.db.stats()
        self.assertEqual((st["users"], st["matches"]), (8, 2))
        self.assertEqual(self.db.get_user(2)["wins"], 1)

    def test_ban_dm_chats_kv(self):
        self.assertTrue(self.db.set_ban(3, True))
        self.assertTrue(self.db.is_banned(3))
        self.assertNotIn(3, self.db.user_ids())
        self.db.mark_dm(4, False)
        self.assertNotIn(4, self.db.user_ids())
        self.assertIn(4, self.db.user_ids(only_dm_ok=False))
        self.db.upsert_chat(-100, "Group", "supergroup")
        self.db.upsert_chat(-101, "Other", "group")
        self.db.set_chat_active(-101, False)
        self.assertEqual(self.db.chat_ids(), [-100])
        self.assertEqual([c["title"] for c in self.db.chat_list()], ["Group"])
        self.assertEqual(self.db.kv_get("x", "d"), "d")
        self.db.kv_set("x", 1)
        self.assertEqual(self.db.kv_get("x"), "1")


class SqliteStorage(Contract, unittest.TestCase):
    def make(self):
        return DB(":memory:", 1000, 200)


class MongoStorage(Contract, unittest.TestCase):
    def make(self):
        return MongoDB("", "t", 1000, 200, client=FakeClient())


class Rewards(unittest.TestCase):
    def test_ladder(self):
        self.assertEqual([referral_reward(n) for n in range(7)], [300, 400, 500, 600, 700, 700, 700])
        self.assertEqual(referral_reward(0, 200), 200)


if __name__ == "__main__":
    unittest.main()

import asyncio
import random
import unittest

from app.broadcast import run
from app.db import DB
from app.verify import MAX_TRIES, Verifier, new_challenge


class VerifyTests(unittest.TestCase):
    def test_challenge_has_one_correct_option(self):
        for seed in range(200):
            ch = new_challenge(random.Random(seed))
            self.assertEqual(len(ch.options), 6)
            self.assertEqual(len(set(ch.options)), 6)
            self.assertTrue(0 <= ch.answer < 6)

    def test_flow(self):
        v = Verifier(random.Random(1))
        ch = v.start(5, -100, "Group")
        self.assertEqual(v.open_for(5), [-100])
        self.assertEqual(v.check(5, -100, ch.answer)[0], "ok")
        self.assertEqual(v.check(5, -100, 0)[0], "none")

    def test_fail_after_three(self):
        v = Verifier(random.Random(2))
        ch = v.start(5, -100)
        res = []
        for _ in range(MAX_TRIES):
            wrong = (ch.answer + 1) % 6
            r, nxt = v.check(5, -100, wrong)
            res.append(r)
            ch = nxt or ch
        self.assertEqual(res, ["wrong", "wrong", "failed"])
        self.assertEqual(v.open_for(5), [])

    def test_expiry(self):
        t = [0]
        v = Verifier(random.Random(3), clock=lambda: t[0])
        ch = v.start(1, 2)
        t[0] = 10_000
        self.assertEqual(v.check(1, 2, ch.answer)[0], "none")


class BroadcastTests(unittest.TestCase):
    def test_counts_and_retry(self):
        calls = {}

        async def send(t):
            calls[t] = calls.get(t, 0) + 1
            if t == 2:
                return "blocked"
            if t == 3:
                return ("retry", 0) if calls[t] == 1 else "ok"
            if t == 4:
                return "gone"
            return "ok"

        res = asyncio.run(run([1, 2, 3, 4, 5], send, delay=0))
        self.assertEqual((res["ok"], res["blocked"], res["gone"], res["fail"]), (3, 1, 1, 0))
        self.assertEqual(res["blocked_ids"], [2])


class DbBotTests(unittest.TestCase):
    def setUp(self):
        self.db = DB(":memory:", 1000, 200)
        for i in (1, 2, 3):
            self.db.upsert_user(i, f"u{i}", f"u{i}", None)

    def test_ban(self):
        self.assertFalse(self.db.is_banned(1))
        self.db.set_ban(1, True)
        self.assertTrue(self.db.is_banned(1))
        self.assertNotIn(1, self.db.user_ids())

    def test_referral_once(self):
        self.assertTrue(self.db.set_referrer(2, 1, 300))
        self.assertFalse(self.db.set_referrer(2, 3, 300))
        self.assertFalse(self.db.set_referrer(1, 1, 300))
        self.assertEqual(self.db.get_user(1)["coins"], 1300)
        self.assertEqual(self.db.get_user(2)["coins"], 1150)
        self.assertEqual(self.db.get_user(1)["refs"], 1)

    def test_streak(self):
        ok, c, _ = self.db.claim_daily(1)
        self.assertTrue(ok)
        self.assertEqual(self.db.get_user(1)["streak"], 1)
        self.db.c.execute("UPDATE users SET last_daily=last_daily-90000 WHERE id=1")
        ok, c, _ = self.db.claim_daily(1)
        self.assertEqual(self.db.get_user(1)["streak"], 2)
        self.assertEqual(self.db.last_bonus, 250)

    def test_chats_kv(self):
        self.db.upsert_chat(-10, "G", "supergroup")
        self.assertEqual(self.db.chat_ids(), [-10])
        self.db.set_chat_active(-10, False)
        self.assertEqual(self.db.chat_ids(), [])
        self.db.kv_set("verify", "1")
        self.assertEqual(self.db.kv_get("verify"), "1")


if __name__ == "__main__":
    unittest.main()

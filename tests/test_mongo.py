import unittest

from app.db import DB
from app.mongo_sync import MongoSync


class FakeColl:
    def __init__(self):
        self.docs = {}

    def find(self, q):
        return [dict(d) for d in self.docs.values()]

    def replace_one(self, flt, doc, upsert=False):
        self.docs[flt["_id"]] = dict(doc)

    def find_one(self, sort=None):
        return dict(self.docs[max(self.docs)]) if self.docs else None


class FakeDb(dict):
    def __missing__(self, k):
        self[k] = FakeColl()
        return self[k]


class MongoSyncTests(unittest.TestCase):
    def test_mirror_and_restore(self):
        mdb = FakeDb()
        a = DB(":memory:", 1000, 200)
        for i in (1, 2):
            a.upsert_user(i, f"u{i}", f"u{i}", None)
        a.add_coins(1, 500, "test")
        a.record_result("ludo", "ROOM1", 0, [1, 2], 1, 0)
        a.upsert_chat(-5, "Grp", "supergroup")
        a.kv_set("verify_default", "0")
        a.set_ban(2, True)
        sync = MongoSync(a, mdb)
        self.assertGreater(sync.flush(), 5)
        self.assertEqual(sync.flush(), 0)          # nothing changed: nothing written
        a.add_coins(1, 5, "again")
        self.assertGreaterEqual(sync.flush(), 2)   # user row + tx row only
        self.assertEqual(len(mdb["users"].docs), 2)

        b = DB(":memory:", 1000, 200)              # brand-new empty disk
        self.assertGreater(MongoSync(b, mdb).restore(), 5)
        self.assertEqual(b.get_user(1)["coins"], 1505)
        self.assertTrue(b.is_banned(2))
        self.assertEqual(b.kv_get("verify_default"), "0")
        self.assertEqual(b.chat_ids(), [-5])
        self.assertEqual(b.c.execute("SELECT COUNT(*) FROM matches").fetchone()[0], 1)

    def test_restore_skips_when_data_exists(self):
        mdb = FakeDb()
        a = DB(":memory:", 1000, 200)
        a.upsert_user(1, "x", "x", None)
        s = MongoSync(a, mdb)
        s.flush()
        self.assertEqual(s.restore(), 0)

    def test_restart_does_not_duplicate_tx(self):
        mdb = FakeDb()
        a = DB(":memory:", 1000, 200)
        a.upsert_user(1, "x", "x", None)
        MongoSync(a, mdb).flush()
        s2 = MongoSync(a, mdb)       # new process, same disk: tx already in mongo
        n_tx = len(mdb["tx"].docs)
        s2.flush()
        self.assertEqual(len(mdb["tx"].docs), n_tx)
        self.assertEqual(s2.last_id["tx"], max(mdb["tx"].docs))


if __name__ == "__main__":
    unittest.main()

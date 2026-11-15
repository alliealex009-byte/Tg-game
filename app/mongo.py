"""MongoDB storage with the same interface as db.DB (users, coin ledger, matches, chats, kv).

Uses pymongo (synchronous, like the SQLite layer) so the rest of the app doesn't change. Coin changes are single-document
atomic updates guarded by a balance filter; `charge_all` charges one by one and refunds on failure, because
multi-document transactions need a replica set and most small deployments (Atlas free tier aside) run standalone.
"""
from __future__ import annotations

import time

from .rewards import referral_reward


class MongoDB:
    def __init__(self, uri: str, dbname: str = "gamely", starting_coins: int = 1000, daily_bonus: int = 200, client=None):
        if client is None:
            try:
                from pymongo import MongoClient
            except ImportError as e:  # pragma: no cover
                raise RuntimeError("MONGO_URI is set but pymongo is not installed (pip install pymongo)") from e
            client = MongoClient(uri, serverSelectionTimeoutMS=8000, tz_aware=False)
            try:
                client.admin.command("ping")
            except Exception as e:  # pragma: no cover
                raise RuntimeError(f"Could not connect to MongoDB: {e}") from e
        self.client, self.d = client, client[dbname]
        self.users, self.tx, self.matches = self.d["users"], self.d["tx"], self.d["matches"]
        self.chats, self.kv = self.d["chats"], self.d["kv"]
        self.starting_coins, self.daily_bonus = starting_coins, daily_bonus
        self.last_bonus = daily_bonus
        try:
            self.tx.create_index("user_id")
            self.users.create_index([("wins", -1), ("coins", -1)])
        except Exception:  # pragma: no cover
            pass

    # ---------- helpers ----------
    @staticmethod
    def _user(doc):
        if not doc:
            return None
        d = dict(doc)
        d["id"] = d.pop("_id")
        return d

    def _tx(self, uid, amount, reason):
        self.tx.insert_one({"user_id": uid, "amount": amount, "reason": reason, "ts": time.time()})

    # ---------- bot admin helpers ----------
    def kv_get(self, k, default=None):
        r = self.kv.find_one({"_id": k})
        return r["v"] if r else default

    def kv_set(self, k, v):
        self.kv.update_one({"_id": k}, {"$set": {"v": str(v)}}, upsert=True)

    def set_ban(self, uid: int, banned: bool) -> bool:
        return self.users.update_one({"_id": uid}, {"$set": {"banned": 1 if banned else 0}}).matched_count > 0

    def is_banned(self, uid: int) -> bool:
        r = self.users.find_one({"_id": uid})
        return bool(r and r.get("banned"))

    def set_verified(self, uid: int):
        self.users.update_one({"_id": uid}, {"$set": {"verified": 1}})

    def mark_dm(self, uid: int, ok: bool):
        self.users.update_one({"_id": uid}, {"$set": {"dm_ok": 1 if ok else 0}})

    def user_ids(self, only_dm_ok: bool = True):
        q = {"banned": 0}
        if only_dm_ok:
            q["dm_ok"] = 1
        return [r["_id"] for r in self.users.find(q)]

    def upsert_chat(self, cid: int, title: str, ctype: str, active: bool = True):
        self.chats.update_one({"_id": cid}, {"$set": {"title": title, "type": ctype, "active": 1 if active else 0},
                                              "$setOnInsert": {"added": time.time()}}, upsert=True)

    def chat_ids(self):
        return [r["_id"] for r in self.chats.find({"active": 1})]

    def chat_list(self, limit: int = 30):
        rows = self.chats.find({"active": 1}).sort([("added", -1)]).limit(limit)
        return [{"title": r.get("title"), "type": r.get("type")} for r in rows]

    def set_chat_active(self, cid: int, active: bool):
        self.chats.update_one({"_id": cid}, {"$set": {"active": 1 if active else 0}})

    def set_referrer(self, uid: int, ref: int, bonus: int = 700) -> int:
        if uid == ref:
            return 0
        u, r = self.get_user(uid), self.get_user(ref)
        if not u or not r or u.get("referrer") is not None or u["games"] > 0:
            return 0
        # claim the referral atomically so a double /start can't pay twice
        got = self.users.update_one({"_id": uid, "referrer": None}, {"$set": {"referrer": ref}})
        if got.matched_count == 0:
            return 0
        reward = referral_reward(r["refs"], bonus)
        self.users.update_one({"_id": ref}, {"$inc": {"refs": 1}})
        self.add_coins(ref, reward, f"referral:{uid}")
        self.add_coins(uid, reward // 2, f"referred:{ref}")
        return reward

    # ---------- users ----------
    def get_user(self, uid: int):
        return self._user(self.users.find_one({"_id": uid}))

    def upsert_user(self, uid: int, name: str, username, photo):
        now = time.time()
        if self.users.find_one({"_id": uid}) is None:
            res = self.users.update_one(
                {"_id": uid},
                {"$setOnInsert": {"name": name, "username": username, "photo": photo, "coins": self.starting_coins, "games": 0,
                                  "wins": 0, "last_daily": 0.0, "created": now, "last_seen": now, "banned": 0, "streak": 0,
                                  "referrer": None, "refs": 0, "verified": 0, "dm_ok": 1}},
                upsert=True)
            if res.upserted_id is not None:
                self._tx(uid, self.starting_coins, "welcome")
        else:
            doc = {"name": name, "last_seen": now}
            if username:
                doc["username"] = username
            if photo:
                doc["photo"] = photo
            self.users.update_one({"_id": uid}, {"$set": doc})
        return self.get_user(uid)

    # ---------- coins ----------
    def add_coins(self, uid: int, delta: int, reason: str):
        res = self.users.update_one({"_id": uid, "coins": {"$gte": -delta}}, {"$inc": {"coins": delta}})
        if res.matched_count == 0:
            return None
        self._tx(uid, delta, reason)
        return self.get_user(uid)["coins"]

    def charge_all(self, uids, amount: int, reason: str):
        done = []
        for u in uids:
            res = self.users.update_one({"_id": u, "coins": {"$gte": amount}}, {"$inc": {"coins": -amount}})
            if res.matched_count == 0:
                for d in done:  # roll back the ones already charged
                    self.users.update_one({"_id": d}, {"$inc": {"coins": amount}})
                return u
            done.append(u)
        for u in done:
            self._tx(u, -amount, reason)
        return None

    def claim_daily(self, uid: int):
        now = time.time()
        u = self.get_user(uid)
        wait = u["last_daily"] + 86400 - now
        if wait > 0:
            return False, u["coins"], int(wait)
        streak = u["streak"] + 1 if u["last_daily"] and now - u["last_daily"] < 2 * 86400 else 1
        bonus = self.daily_bonus + min(streak - 1, 6) * 50
        res = self.users.update_one({"_id": uid, "last_daily": u["last_daily"]},
                                    {"$set": {"last_daily": now, "streak": streak}, "$inc": {"coins": bonus}})
        if res.matched_count == 0:  # a parallel claim won
            return False, self.get_user(uid)["coins"], 86400
        self._tx(uid, bonus, "daily")
        self.last_bonus = bonus
        return True, self.get_user(uid)["coins"], 0

    def daily_wait(self, uid: int) -> int:
        u = self.get_user(uid)
        return max(0, int(u["last_daily"] + 86400 - time.time()))

    # ---------- results ----------
    def record_result(self, game, room, bet, human_uids, winner, prize, winners=None):
        for u in human_uids:
            self.users.update_one({"_id": u}, {"$inc": {"games": 1}})
        for w in (winners if winners else ([winner] if winner is not None and winner > 0 else [])):
            if w and w > 0:
                self.users.update_one({"_id": w}, {"$inc": {"wins": 1}})
        self.matches.insert_one({"game": game, "room": room, "bet": bet, "players": list(human_uids), "winner": winner,
                                 "prize": prize, "ts": time.time()})

    def leaderboard(self, limit: int = 20):
        rows = self.users.find({"games": {"$gt": 0}}).sort([("wins", -1), ("coins", -1)]).limit(limit)
        return [{"id": r["_id"], "name": r["name"], "username": r.get("username"), "photo": r.get("photo"),
                 "wins": r["wins"], "games": r["games"], "coins": r["coins"]} for r in rows]

    def stats(self):
        agg = list(self.users.aggregate([{"$group": {"_id": None, "s": {"$sum": "$coins"}}}]))
        return {
            "users": self.users.count_documents({}),
            "matches": self.matches.count_documents({}),
            "coins_in_circulation": agg[0]["s"] if agg else 0,
            "chats": self.chats.count_documents({"active": 1}),
            "banned": self.users.count_documents({"banned": 1}),
            "new_today": self.users.count_documents({"created": {"$gt": time.time() - 86400}}),
        }

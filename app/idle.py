"""Idle / pet games that keep growing while you are away: IdleSprout, PixelPaws, TinyWorld, MiniRealm.
State lives in the kv table (key idle:<kind>:<uid>). Payouts go through Arcade._grant so the daily cap applies."""
from __future__ import annotations

import json
import random
import time

KINDS = ("sprout", "paws", "world", "realm")
SPROUT_CAP_H = 6
SPROUT_RATE = 30                 # coins / hour at level 1, times level
SPROUT_MAX = 10
BUILD = {"house": (60, 10), "farm": (120, 24), "mill": (300, 65), "tower": (800, 190)}   # cost, coins/hour
WORLD_SLOTS = 9
WORLD_CAP_H = 8
PAW_FEED_CD, PAW_PLAY_CD, PAW_CLAIM_CD, PAW_FEED_COST, PAW_MOOD_H = 120, 60, 1800, 10, 8
MISSIONS = {"scout": (300, 45, 0.9), "raid": (900, 150, 0.7), "siege": (3600, 700, 0.5)}  # seconds, reward, win chance


class Idle:
    def __init__(self, arcade, clock=time.time, rng=None):
        self.arc, self.db, self.clock = arcade, arcade.db, clock
        self.rng = rng or random.SystemRandom()

    # ---- storage
    def _load(self, kind, uid):
        try:
            s = json.loads(self.db.kv_get(f"idle:{kind}:{uid}") or "null")
        except ValueError:
            s = None
        return s if isinstance(s, dict) else {}

    def _save(self, kind, uid, s):
        self.db.kv_set(f"idle:{kind}:{uid}", json.dumps(s))

    def _pay(self, uid, coins, why):
        return self.arc._grant(uid, int(coins), why)

    def _collect(self, uid, coins, why):
        if self._pay(uid, coins, why) <= 0 and coins > 0:
            raise ValueError("Daily arcade limit reached — come back tomorrow")

    def _spend(self, uid, cost, why):
        if self.db.add_coins(uid, -cost, why) is None:
            raise ValueError("Not enough coins")

    def _coins(self, uid):
        return self.db.get_user(uid)["coins"]

    # ---- dispatch
    def state(self, kind, uid):
        if kind not in KINDS:
            raise ValueError("Unknown game")
        return getattr(self, "_s_" + kind)(uid)

    def act(self, kind, uid, action, arg=None):
        if kind not in KINDS:
            raise ValueError("Unknown game")
        getattr(self, "_a_" + kind)(uid, action, arg)
        return self.state(kind, uid)

    # ---- IdleSprout
    def _sprout(self, uid):
        s = self._load("sprout", uid)
        s.setdefault("lvl", 1)
        s.setdefault("t", self.clock())
        return s

    def _s_sprout(self, uid):
        s, now = self._sprout(uid), self.clock()
        rate = SPROUT_RATE * s["lvl"]
        hrs = min(SPROUT_CAP_H, max(0.0, (now - s["t"]) / 3600))
        self._save("sprout", uid, s)
        return {"kind": "sprout", "lvl": s["lvl"], "rate": rate, "ready": int(rate * hrs), "cap_h": SPROUT_CAP_H,
                "full": hrs >= SPROUT_CAP_H, "up_cost": None if s["lvl"] >= SPROUT_MAX else 200 * s["lvl"] ** 2, "coins": self._coins(uid)}

    def _a_sprout(self, uid, action, arg):
        s, now = self._sprout(uid), self.clock()
        if action == "collect":
            ready = self._s_sprout(uid)["ready"]
            if ready < 1:
                raise ValueError("Nothing to collect yet")
            self._collect(uid, ready, "idle:sprout")
            s["t"] = now
        elif action == "upgrade":
            if s["lvl"] >= SPROUT_MAX:
                raise ValueError("Max level")
            ready = self._s_sprout(uid)["ready"]       # bank what has grown so far at the old rate
            self._spend(uid, 200 * s["lvl"] ** 2, "idle:sprout-up")
            if ready:
                self._pay(uid, ready, "idle:sprout")
            s["lvl"] += 1
            s["t"] = now
        else:
            raise ValueError("Bad action")
        self._save("sprout", uid, s)

    # ---- PixelPaws
    def _paws(self, uid):
        s = self._load("paws", uid)
        for k, v in (("xp", 0), ("fed", 0), ("played", 0), ("claimed", 0)):
            s.setdefault(k, v)
        return s

    def _s_paws(self, uid):
        s, now = self._paws(uid), self.clock()
        lvl = min(8, 1 + s["xp"] // 10)
        happy = now - s["fed"] < PAW_MOOD_H * 3600 and now - s["played"] < PAW_MOOD_H * 3600
        return {"kind": "paws", "lvl": lvl, "xp": s["xp"] % 10 if lvl < 8 else 10, "next_xp": 10, "mood": "happy" if happy else "sad",
                "feed_cd": max(0, int(s["fed"] + PAW_FEED_CD - now)), "play_cd": max(0, int(s["played"] + PAW_PLAY_CD - now)),
                "claim_cd": max(0, int(s["claimed"] + PAW_CLAIM_CD - now)), "claim_reward": (10 + 8 * lvl) if happy else 3,
                "feed_cost": PAW_FEED_COST, "coins": self._coins(uid)}

    def _a_paws(self, uid, action, arg):
        s, now = self._paws(uid), self.clock()
        st = self._s_paws(uid)
        if action == "feed":
            if st["feed_cd"]:
                raise ValueError("Not hungry yet")
            self._spend(uid, PAW_FEED_COST, "idle:paws-food")
            s["fed"] = now
            s["xp"] += 1
        elif action == "play":
            if st["play_cd"]:
                raise ValueError("Your pet is tired — wait a bit")
            s["played"] = now
            s["xp"] += 1
        elif action == "claim":
            if st["claim_cd"]:
                raise ValueError("Your pet hasn't found anything yet")
            self._collect(uid, st["claim_reward"], "idle:paws")
            s["claimed"] = now
        else:
            raise ValueError("Bad action")
        self._save("paws", uid, s)

    # ---- TinyWorld
    def _world(self, uid):
        s = self._load("world", uid)
        sl = s.get("slots")
        if not (isinstance(sl, list) and len(sl) == WORLD_SLOTS):
            s["slots"] = [None] * WORLD_SLOTS
        s.setdefault("t", self.clock())
        return s

    def _world_rate(self, s):
        return sum(BUILD[b][1] for b in s["slots"] if b in BUILD)

    def _s_world(self, uid):
        s, now = self._world(uid), self.clock()
        rate = self._world_rate(s)
        hrs = min(WORLD_CAP_H, max(0.0, (now - s["t"]) / 3600))
        return {"kind": "world", "slots": s["slots"], "build": {k: {"cost": v[0], "rate": v[1]} for k, v in BUILD.items()},
                "rate": rate, "ready": int(rate * hrs), "cap_h": WORLD_CAP_H, "coins": self._coins(uid)}

    def _a_world(self, uid, action, arg):
        s, now = self._world(uid), self.clock()
        if action == "collect":
            ready = self._s_world(uid)["ready"]
            if ready < 1:
                raise ValueError("Nothing to collect yet")
            self._collect(uid, ready, "idle:world")
            s["t"] = now
        elif action == "build":
            idx, typ = (arg or {}).get("idx"), (arg or {}).get("type")
            if isinstance(idx, bool) or not isinstance(idx, int) or not 0 <= idx < WORLD_SLOTS or typ not in BUILD:
                raise ValueError("Bad build")
            if s["slots"][idx] is not None:
                raise ValueError("That plot is taken")
            ready = self._s_world(uid)["ready"]
            self._spend(uid, BUILD[typ][0], "idle:world-build")
            if ready:
                self._pay(uid, ready, "idle:world")
            s["slots"][idx] = typ
            s["t"] = now
        else:
            raise ValueError("Bad action")
        self._save("world", uid, s)

    # ---- MiniRealm
    def _realm(self, uid):
        s = self._load("realm", uid)
        s.setdefault("xp", 0)
        s.setdefault("mission", None)
        return s

    def _s_realm(self, uid):
        s, now = self._realm(uid), self.clock()
        lvl = min(10, 1 + s["xp"] // 5)
        m = s["mission"]
        mm = None if not m else {"id": m["id"], "left": max(0, int(m["end"] - now)), "done": now >= m["end"]}
        return {"kind": "realm", "lvl": lvl, "xp": s["xp"], "mission": mm, "coins": self._coins(uid),
                "missions": {k: {"secs": v[0], "reward": int(v[1] * (1 + 0.1 * (lvl - 1))), "chance": int(v[2] * 100)} for k, v in MISSIONS.items()}}

    def _a_realm(self, uid, action, arg):
        s, now = self._realm(uid), self.clock()
        st = self._s_realm(uid)
        if action == "start":
            if s["mission"]:
                raise ValueError("Your heroes are already out")
            if arg not in MISSIONS:
                raise ValueError("Unknown mission")
            s["mission"] = {"id": arg, "end": now + MISSIONS[arg][0]}
        elif action == "claim":
            m = s["mission"]
            if not m:
                raise ValueError("No mission running")
            if now < m["end"]:
                raise ValueError("Heroes are not back yet")
            win = self.rng.random() < MISSIONS[m["id"]][2]
            if win:
                self._pay(uid, st["missions"][m["id"]]["reward"], "idle:realm")
            s["xp"] += 2 if win else 1
            s["mission"] = None
            s["last"] = "win" if win else "lose"
        else:
            raise ValueError("Bad action")
        self._save("realm", uid, s)

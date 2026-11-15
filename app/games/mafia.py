"""Mafia (4-10 players). Night: mafia choose a victim, the doctor protects, the detective investigates.
Day: everyone votes someone out. Town wins when the mafia is gone; mafia wins when it reaches parity."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

ROLE_INFO = {"mafia": "🔪 Mafia", "doctor": "💉 Doctor", "detective": "🕵️ Detective", "villager": "🧑‍🌾 Villager"}


class MafiaGame(BaseGame):
    name = "mafia"
    min_players, max_players = 4, 10

    def __init__(self, players, rng=None):
        n = len(players)
        if not 4 <= n <= 10:
            raise ValueError("Mafia needs 4-10 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        n_maf = 1 if n < 6 else 2 if n < 9 else 3
        roles = ["mafia"] * n_maf + ["doctor", "detective"] + ["villager"] * (n - n_maf - 2)
        self.rng.shuffle(roles)
        self.role = dict(zip(self.players, roles))
        self.alive = set(self.players)
        self.phase = "night"
        self.day = 0
        self.night = {}     # uid -> target (mafia kill votes, doctor save, detective check)
        self.votes = {}     # day votes uid -> target uid or 0 (skip)
        self.found = {}     # detective uid -> {target: is_mafia}
        self.last_night = None
        self.last_vote = None
        self.seq = 0
        self.log = []
        self.winner, self.finished, self.draw = None, False, False
        self.winners = None
        self.reason = ""
        self._say("night", "🌙 Night falls. The town sleeps…")

    def _say(self, kind, text):
        self.seq += 1
        self.log = (self.log + [{"seq": self.seq, "kind": kind, "text": text}])[-8:]

    def team(self, uid):
        return "mafia" if self.role[uid] == "mafia" else "town"

    def _pending(self):
        if self.phase == "night":
            return [u for u in self.players if u in self.alive and self.role[u] != "villager" and u not in self.night]
        return [u for u in self.players if u in self.alive and u not in self.votes]

    def current(self):
        if self.finished:
            return None
        p = self._pending()
        if not p:
            return None
        humans = [u for u in p if u > 0]
        return (humans or p)[0]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid not in self.players or uid not in self.alive:
            raise GameError("You are out of the game")
        t = msg.get("t")
        tgt = msg.get("target")
        if t == "night":
            if self.phase != "night":
                raise GameError("It's daytime")
            if self.role[uid] == "villager":
                raise GameError("Villagers sleep through the night")
            if uid in self.night:
                raise GameError("You already acted tonight")
            if tgt not in self.alive:
                raise GameError("Pick a living player")
            if self.role[uid] == "mafia" and self.role.get(tgt) == "mafia":
                raise GameError("You can't target your own team")
            if self.role[uid] == "detective" and tgt == uid:
                raise GameError("Investigate someone else")
            self.night[uid] = tgt
            if not self._pending():
                self._resolve_night()
        elif t == "vote":
            if self.phase != "day":
                raise GameError("Voting happens during the day")
            if uid in self.votes:
                raise GameError("You already voted")
            if tgt != 0 and (tgt not in self.alive or tgt == uid):
                raise GameError("Pick someone else, or skip")
            self.votes[uid] = tgt
            self._say("vote", "voted")
            if not self._pending():
                self._resolve_day()
        else:
            raise GameError("Unknown action")

    def _resolve_night(self):
        kills = [t for u, t in self.night.items() if self.role[u] == "mafia"]
        saves = [t for u, t in self.night.items() if self.role[u] == "doctor"]
        for u, t in self.night.items():
            if self.role[u] == "detective":
                self.found.setdefault(u, {})[t] = self.role[t] == "mafia"
        victim = None
        if kills:
            tally = {}
            for k in kills:
                tally[k] = tally.get(k, 0) + 1
            top = max(tally.values())
            victim = self.rng.choice([k for k, v in tally.items() if v == top])
        saved = victim is not None and victim in saves
        died = None
        if victim is not None and not saved:
            self.alive.discard(victim)
            died = victim
        self.last_night = {"died": died, "died_role": self.role[died] if died else None, "saved": saved, "day": self.day + 1}
        self.day += 1
        self.phase, self.night, self.votes = "day", {}, {}
        self._say("day", "☀️ Morning: " + ("someone was killed in the night!" if died else "nobody died tonight." + (" The doctor saved a life!" if saved else "")))
        if not self._check_win():
            pass

    def _resolve_day(self):
        tally = {}
        for v, t in self.votes.items():
            if t:
                tally[t] = tally.get(t, 0) + 1
        out = None
        if tally:
            top = max(tally.values())
            leaders = [k for k, v in tally.items() if v == top]
            if len(leaders) == 1:
                out = leaders[0]
        self.last_vote = {"votes": dict((str(k), v) for k, v in self.votes.items()), "out": out, "role": self.role[out] if out else None, "day": self.day}
        if out:
            self.alive.discard(out)
        self.phase, self.night, self.votes = "night", {}, {}
        self._say("vote", "🗳 The town voted someone out!" if out else "🗳 The vote was tied. Nobody leaves.")
        if not self._check_win():
            self._say("night", "🌙 Night falls again…")

    def _check_win(self):
        maf = [u for u in self.alive if self.role[u] == "mafia"]
        town = [u for u in self.alive if self.role[u] != "mafia"]
        win = None
        if not maf:
            win, self.reason = "town", "All the mafia were caught"
        elif len(maf) >= len(town):
            win, self.reason = "mafia", "The mafia took over the town"
        if win is None:
            return False
        self.finished = True
        self.winners = [u for u in self.players if self.team(u) == win]
        self.winner = self.winners[0]
        return True

    def auto_play(self):
        if self.finished:
            return
        uid = self.current()
        if uid is None:
            return
        al = [u for u in self.alive if u != uid]
        if self.phase == "night":
            r = self.role[uid]
            if r == "mafia":
                tgt = self.rng.choice([u for u in al if self.role[u] != "mafia"])
            elif r == "detective":
                known = self.found.get(uid, {})
                tgt = self.rng.choice([u for u in al if u not in known] or al)
            else:
                tgt = self.rng.choice(list(self.alive))
            return self.handle(uid, {"t": "night", "target": tgt})
        pool = al
        if self.role[uid] == "mafia":
            pool = [u for u in al if self.role[u] != "mafia"] or al
        elif self.role[uid] == "detective":
            hits = [u for u in al if self.found.get(uid, {}).get(u)]
            pool = hits or al
        self.handle(uid, {"t": "vote", "target": self.rng.choice(pool)})

    def remove_player(self, uid):
        if uid not in self.alive or self.finished:
            return
        self.alive.discard(uid)
        self.night.pop(uid, None)
        self.votes.pop(uid, None)
        self.votes = {v: t for v, t in self.votes.items() if t != uid}
        self._say("left", "A player left the game")
        if not self._check_win() and not self._pending():
            self._resolve_night() if self.phase == "night" else self._resolve_day()

    def public_state(self):
        return {"kind": "mafia", "phase": self.phase, "day": self.day, "turn": self.current(),
                "players": [{"uid": u, "alive": u in self.alive, "role": None if u in self.alive else self.role[u],
                             "voted": u in self.votes if self.phase == "day" else None} for u in self.players],
                "votes": {str(k): v for k, v in self.votes.items()}, "last_night": self.last_night, "last_vote": self.last_vote,
                "log": self.log, "n_mafia": sum(1 for r in self.role.values() if r == "mafia"), "role": None, "mates": [],
                "found": {}, "can_act": False, "reason": self.reason, "winner": self.winner, "draw": self.draw}

    def view(self, uid):
        st = self.public_state()
        if self.finished:
            for p in st["players"]:
                p["role"] = self.role[p["uid"]]
        if uid in self.role:
            r = self.role[uid]
            st["role"] = r
            if r == "mafia":
                st["mates"] = [u for u in self.players if self.role[u] == "mafia" and u != uid]
                for p in st["players"]:
                    if p["uid"] in st["mates"] or p["uid"] == uid:
                        p["role"] = "mafia"
            if r == "detective":
                st["found"] = {str(k): v for k, v in self.found.get(uid, {}).items()}
            if uid in self.alive:
                st["can_act"] = (self.phase == "night" and r != "villager" and uid not in self.night) or (self.phase == "day" and uid not in self.votes)
            st["acted"] = uid in (self.night if self.phase == "night" else self.votes)
        return st

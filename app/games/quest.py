"""Adventure Quest: co-op dungeon. 2-4 heroes fight 3 floors of monsters; everyone picks a move at once each round.
attack (solid hit), power (big hit, costs 2 mana, can miss), heal (restore yourself 18), guard (take half damage).
Every 3rd round the monster roars and hurts everyone. Beat the floor-3 boss to win together; if all heroes fall the quest fails."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

MOVES = ("attack", "power", "heal", "guard")
FLOORS = [("Goblin Cave", "👺", 55), ("Haunted Crypt", "💀", 80), ("Dragon Lair", "🐉", 115)]
HERO_HP = 70


class QuestGame(BaseGame):
    name = "quest"
    min_players = 2
    max_players = 4
    phase_seconds = 12

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 4:
            raise ValueError("Quest needs 2-4 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.hp = {u: HERO_HP for u in self.players}
        self.mana = {u: 3 for u in self.players}
        self.floor = 0
        self.boss_hp = self._boss_max()
        self.round = 0
        self.picks = {}
        self.phase_id = 0
        self.seq = 0
        self.last_round = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self.result = None
        self._bots()

    def _boss_max(self):
        return int(FLOORS[self.floor][2] * (0.45 + 0.25 * len(self.players)))

    def _alive(self):
        return [u for u in self.players if self.hp[u] > 0]

    def _pending(self):
        return [u for u in self._alive() if u not in self.picks]

    def current(self):
        if self.finished:
            return None
        p = self._pending()
        return ([u for u in p if u > 0] or p or [None])[0]

    def _bot_pick(self, u):
        if self.hp[u] < 25:
            return self.rng.choice(("heal", "heal", "guard"))
        if self.mana[u] >= 2 and self.rng.random() < 0.4:
            return "power"
        return self.rng.choice(("attack", "attack", "guard"))

    def _bots(self):
        while not self.finished:
            for u in self._pending():
                if u < 0:
                    self.picks[u] = self._bot_pick(u)
            if self._pending():
                return
            self._resolve()

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The quest is over")
        if uid not in self.players:
            raise GameError("You are not in this party")
        if self.hp[uid] <= 0:
            raise GameError("You are down")
        if msg.get("t") != "act" or msg.get("move") not in MOVES:
            raise GameError("Pick attack, power, heal or guard")
        if uid in self.picks:
            raise GameError("Already locked in")
        if msg["move"] == "power" and self.mana[uid] < 2:
            raise GameError("Not enough mana")
        self.picks[uid] = msg["move"]
        self._bots()

    def auto_play(self):
        if self.finished:
            return
        for u in self._pending():
            self.picks[u] = self._bot_pick(u) if u < 0 else self.rng.choice(("attack", "guard"))
        self._resolve()
        self._bots()

    def _resolve(self):
        self.round += 1
        dmg_out, heals, ev = {}, {}, []
        for u, m in self.picks.items():
            if m == "attack":
                dmg_out[u] = self.rng.randint(9, 15)
            elif m == "power":
                self.mana[u] = max(0, self.mana[u] - 2)
                dmg_out[u] = 0 if self.rng.random() < 0.2 else self.rng.randint(22, 30)
            elif m == "heal":
                heals[u] = 18
            self.mana[u] = min(5, self.mana[u] + 1)
        for u, h in heals.items():
            self.hp[u] = min(HERO_HP, self.hp[u] + h)
        total = sum(dmg_out.values())
        self.boss_hp = max(0, self.boss_hp - total)
        hits = {}
        if self.boss_hp > 0:
            alive = self._alive()
            f = self.floor
            t = self.rng.choice(alive)
            hits[t] = self.rng.randint(12, 18) + 4 * f
            if self.round % 3 == 0:
                for u in alive:
                    hits[u] = hits.get(u, 0) + 6 + 2 * f
                ev.append("roar")
            for u, d in list(hits.items()):
                if self.picks.get(u) == "guard":
                    d //= 2
                hits[u] = d
                self.hp[u] = max(0, self.hp[u] - d)
        self.seq += 1
        self.phase_id += 1
        self.last_round = {"seq": self.seq, "round": self.round, "moves": dict(self.picks), "dmg": dmg_out, "hits": hits,
                           "events": ev, "boss_hp": self.boss_hp, "floor": self.floor}
        self.picks = {}
        if self.boss_hp <= 0:
            if self.floor + 1 >= len(FLOORS):
                self.finished = True
                self.winners = list(self.players)
                self.winner = self._alive()[0] if self._alive() else self.players[0]
                self.result = "victory"
                return
            self.floor += 1
            self.boss_hp = self._boss_max()
            self.last_round["next_floor"] = self.floor
            for u in self.players:
                self.hp[u] = min(HERO_HP, self.hp[u] + 25)
        elif not self._alive():
            self.finished = True
            self.draw = True
            self.result = "defeat"

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.hp[uid] = 0
        self.picks.pop(uid, None)
        humans = [u for u in self._alive() if u > 0]
        if not humans:
            self.finished = True
            self.draw = True
            self.result = "defeat"
            return
        self._bots()

    def public_state(self):
        name, emo, _ = FLOORS[min(self.floor, len(FLOORS) - 1)]
        return {"kind": "quest", "floor": self.floor + 1, "floors": len(FLOORS), "boss": {"name": name, "emoji": emo, "hp": self.boss_hp, "max": self._boss_max()},
                "players": [{"uid": u, "hp": self.hp[u], "mana": self.mana[u], "down": self.hp[u] <= 0} for u in self.players],
                "picked": {u: u in self.picks for u in self.players}, "turn": self.current(), "round": self.round,
                "last_round": self.last_round, "result": self.result, "winner": self.winner, "draw": self.draw}

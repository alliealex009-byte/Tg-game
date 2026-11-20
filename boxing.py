"""Boxing: 3 rounds of 8 exchanges. Both fighters secretly pick a move each exchange; the server resolves it.

Moves: jab / hook / uppercut (attacks, cost stamina), block / dodge (defence).
Attack triangle when both attack: jab cuts a hook in half, hook cuts an uppercut in half, uppercut cuts a jab in half.
Defence: block stops a jab, halves a hook, but an uppercut breaks it (+ stamina loss). Dodge beats hook and uppercut
(and counters the hook for a little damage) but a jab is too quick to dodge.
"""
from __future__ import annotations

import random

from .base import BaseGame, GameError

MOVES = ("jab", "hook", "uppercut", "block", "dodge")
DMG = {"jab": 6, "hook": 12, "uppercut": 18}
COST = {"jab": 5, "hook": 12, "uppercut": 20, "block": 0, "dodge": 8}
ROUNDS = 3
EXCHANGES = 8
HP0 = 100
STAM0 = 100
GETUP_HP = (30, 22, 15)
HALVES = {"jab": "hook", "hook": "uppercut", "uppercut": "jab"}  # key beats value (value is halved)


class BoxingGame(BaseGame):
    name = "boxing"
    min_players = 2
    max_players = 2
    phase_seconds = 12

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Boxing needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.hp = {u: HP0 for u in self.players}
        self.stamina = {u: STAM0 for u in self.players}
        self.kd = {u: 0 for u in self.players}
        self.round = 1
        self.exch = 0               # exchanges finished in this round
        self.round_dmg = {u: 0 for u in self.players}
        self.total_dmg = {u: 0 for u in self.players}
        self.round_wins = {u: 0 for u in self.players}
        self.round_log = []         # [{round, dmg:{uid:n}, winner}]
        self.picks = {}
        self.phase_id = 0
        self.seq = 0
        self.last_exchange = None
        self.method = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self._bots_pick()

    # ------------------------------------------------------------------ flow
    def _pending(self):
        return [u for u in self.players if u not in self.picks]

    def current(self):
        if self.finished:
            return None
        pend = self._pending()
        humans = [u for u in pend if u > 0]
        return (humans or pend or [None])[0]

    def _bots_pick(self):
        while not self.finished:
            for u in self._pending():
                if u < 0:
                    self.picks[u] = self._bot_move(u)
            if len(self.picks) == 2:
                self._resolve()
                continue
            break

    def _bot_move(self, u):
        o = next(x for x in self.players if x != u)
        st = self.stamina[u]
        w = {"jab": 3.0, "hook": 2.5, "uppercut": 2.0, "block": 2.2, "dodge": 2.0}
        if st < 20:
            w.update(uppercut=0, hook=0.3, block=4, dodge=2)
        elif st < 35:
            w.update(uppercut=0.5, hook=1.0, block=3)
        if self.stamina[o] < 15:
            w.update(block=1, dodge=1, jab=4)
        if self.hp[u] < 30:
            w.update(block=4, dodge=3)
        last = self.last_exchange["moves"].get(o) if self.last_exchange else None
        if last:  # counter the opponent's habit
            counter = {"jab": "block", "hook": "dodge", "uppercut": "dodge", "block": "uppercut", "dodge": "jab"}[last]
            w[counter] += 1.5
        opts = [m for m in MOVES if COST[m] <= st and w.get(m, 0) > 0]
        return self.rng.choices(opts, weights=[w[m] for m in opts])[0]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The fight is over")
        if uid not in self.players:
            raise GameError("You are not in this fight")
        if msg.get("t") != "move":
            raise GameError("Unknown action")
        mv = msg.get("move")
        if not isinstance(mv, str) or mv not in MOVES:
            raise GameError("Pick jab, hook, uppercut, block or dodge")
        if uid in self.picks:
            raise GameError("Already locked in")
        if COST[mv] > self.stamina[uid]:
            raise GameError("Too tired for that")
        self.picks[uid] = mv
        self._bots_pick()
        if len(self.picks) == 2 and not self.finished:
            self._resolve()
            self._bots_pick()

    def auto_play(self):
        if self.finished:
            return
        for u in self._pending():
            ok = [m for m in MOVES if COST[m] <= self.stamina[u]]
            self.picks[u] = self._bot_move(u) if u < 0 else self.rng.choice([m for m in ok if m != "uppercut"] or ["block"])
        self._resolve()
        self._bots_pick()

    # ------------------------------------------------------------------ resolution
    def _damage(self, att, a, d):
        """Damage `a` (attacker move) deals against defender move `d`. Returns (dmg, note)."""
        if a not in DMG:
            return 0, None
        base = DMG[a]
        if d in DMG:
            if HALVES[d] == a:       # defender's attack cuts ours
                return base // 2, "trade"
            return base, "trade"
        if d == "block":
            if a == "jab":
                return 0, "blocked"
            if a == "hook":
                return base // 2, "glance"
            return base, "broke"
        # dodge
        if a == "jab":
            return base, "hit"
        return 0, "dodged"

    def _resolve(self):
        a, b = self.players
        ma, mb = self.picks[a], self.picks[b]
        dmg = {a: 0, b: 0}         # damage TAKEN
        notes = {a: None, b: None}
        for att, dfn in ((a, b), (b, a)):
            m_att, m_def = self.picks[att], self.picks[dfn]
            d, note = self._damage(att, m_att, m_def)
            if d:
                d = max(1, d + self.rng.randint(-1, 1))
                if self.stamina[dfn] < 15:
                    d = int(d * 1.25)  # exhausted fighters are easy to hit
            dmg[dfn] += d
            if note:
                notes[dfn] = note if note != "hit" else "hit"
            if note in ("dodged",) and m_def == "dodge" and m_att == "hook":
                dmg[att] += 4   # counter punch
                notes[att] = "counter"
        # stamina
        for u in self.players:
            mv = self.picks[u]
            other = self.picks[a if u == b else b]
            st = self.stamina[u] - COST[mv]
            st += 12 if mv == "block" else 8
            if mv == "block" and other == "uppercut":
                st -= 10
            self.stamina[u] = max(0, min(STAM0, st))
        knockdown = None
        for u in self.players:
            self.hp[u] = max(0, self.hp[u] - dmg[u])
            o = a if u == b else b
            self.round_dmg[o] += dmg[u]
            self.total_dmg[o] += dmg[u]
        self.seq += 1
        self.phase_id += 1
        self.picks_done = dict(self.picks)
        self.picks = {}
        self.exch += 1
        for u in self.players:
            if self.hp[u] <= 0 and not self.finished:
                knockdown = u
                self.kd[u] += 1
                if self.kd[u] >= 3:
                    self.finished, self.winner = True, a if u == b else b
                    self.method = "TKO"
                else:
                    self.hp[u] = GETUP_HP[self.kd[u] - 1]
                    self.stamina[u] = max(self.stamina[u], 30)
        # simultaneous knockdowns cancel into the one who was hit harder; keep it simple: first one wins ties
        self.last_exchange = {
            "seq": self.seq, "round": self.round, "n": self.exch,
            "moves": dict(self.picks_done), "dmg": dmg, "notes": notes,
            "knockdown": knockdown, "count": self.kd[knockdown] if knockdown is not None else 0,
            "ko": bool(self.finished and self.method == "TKO"),
            "round_end": False,
        }
        if self.finished:
            return
        if self.exch >= EXCHANGES:
            self._end_round()

    def _end_round(self):
        a, b = self.players
        ra, rb = self.round_dmg[a], self.round_dmg[b]
        w = a if ra > rb else b if rb > ra else None
        if w is not None:
            self.round_wins[w] += 1
        self.round_log.append({"round": self.round, "dmg": dict(self.round_dmg), "winner": w})
        self.last_exchange["round_end"] = True
        self.last_exchange["round_winner"] = w
        if self.round >= ROUNDS:
            self.finished = True
            wa, wb = self.round_wins[a], self.round_wins[b]
            if wa != wb:
                self.winner = a if wa > wb else b
            elif self.total_dmg[a] != self.total_dmg[b]:
                self.winner = a if self.total_dmg[a] > self.total_dmg[b] else b
            else:
                self.draw = True
            self.method = "decision"
            return
        self.round += 1
        self.exch = 0
        self.round_dmg = {u: 0 for u in self.players}
        for u in self.players:
            self.stamina[u] = STAM0
            self.hp[u] = min(HP0, self.hp[u] + 15)

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished = True
        self.winner = next(u for u in self.players if u != uid)
        self.method = "forfeit"

    # ------------------------------------------------------------------ views
    def public_state(self):
        return {
            "kind": "boxing",
            "players": [{"uid": u, "hp": self.hp[u], "stamina": self.stamina[u], "kd": self.kd[u],
                         "round_dmg": self.round_dmg[u], "total": self.total_dmg[u], "rounds": self.round_wins[u]}
                        for u in self.players],
            "round": self.round, "rounds": ROUNDS, "exch": self.exch, "exchanges": EXCHANGES,
            "picked": {u: u in self.picks for u in self.players},   # never the move itself
            "turn": self.current(), "last_exchange": self.last_exchange, "round_log": self.round_log,
            "method": self.method, "winner": self.winner, "draw": self.draw,
        }

    def view(self, uid):
        return self.public_state()

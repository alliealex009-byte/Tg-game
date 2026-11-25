"""Football: a 2-player tactical match. Snake-draft a squad from a roster of world stars, then play two halves of
attacks. Every attack is a chain of phases (build-up -> midfield -> final third -> shot): the attacker secretly picks an
action AND which player takes it, the defender secretly picks a stance AND whom to mark; both are revealed together and
resolved from the involved players' ratings, stamina, a matchup table and the (injectable) rng. A tied match goes to a
penalty shootout (shoot left/centre/right vs dive). Player names are plain text labels, ratings are approximate."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

ATTACKS_PER_HALF = 8          # attack slots per half (alternating, so 4 each)
SQUAD = 6                     # 1 GK + 5 outfield; the best 4 outfield start, one sits on the bench
MAX_PHASES = 6                # an attack that goes round in circles is called off after this many phases
PEN_KICKS = 5
PEN_CAP = 30
ACTS = ("short", "through", "dribble", "long", "cross", "shoot")
STANCES = ("press", "hold", "intercept", "tackle", "drop", "mark")
DIRS = ("l", "c", "r")
ZONE_ACTS = {0: ("short", "through", "dribble", "long"), 1: ("short", "through", "dribble", "long", "shoot"),
             2: ("short", "through", "dribble", "cross", "shoot")}

# id, name, flag, role, pace, shooting, passing, dribbling, defending, goalkeeping (approximate, own ratings)
_RAW = [
    ("courtois", "Courtois", "🇧🇪", "GK", 40, 18, 62, 35, 30, 91),
    ("alisson", "Alisson", "🇧🇷", "GK", 42, 20, 74, 38, 32, 90),
    ("donnarumma", "Donnarumma", "🇮🇹", "GK", 45, 18, 66, 36, 30, 89),
    ("oblak", "Oblak", "🇸🇮", "GK", 41, 15, 60, 33, 30, 89),
    ("maignan", "Maignan", "🇫🇷", "GK", 50, 20, 72, 42, 32, 88),
    ("neuer", "Neuer", "🇩🇪", "GK", 48, 22, 78, 50, 34, 86),
    ("vandijk", "Van Dijk", "🇳🇱", "DEF", 80, 60, 72, 70, 91, 10),
    ("dias", "Rúben Dias", "🇵🇹", "DEF", 76, 45, 70, 66, 90, 10),
    ("saliba", "Saliba", "🇫🇷", "DEF", 82, 40, 72, 68, 88, 10),
    ("marquinhos", "Marquinhos", "🇧🇷", "DEF", 78, 50, 74, 72, 88, 10),
    ("rudiger", "Rüdiger", "🇩🇪", "DEF", 83, 48, 66, 64, 87, 10),
    ("gvardiol", "Gvardiol", "🇭🇷", "DEF", 80, 55, 74, 74, 86, 10),
    ("hakimi", "Hakimi", "🇲🇦", "DEF", 95, 72, 78, 84, 78, 10),
    ("trent", "Alexander-Arnold", "🏴", "DEF", 77, 68, 92, 76, 76, 10),
    ("theo", "Theo Hernández", "🇫🇷", "DEF", 93, 72, 78, 82, 77, 10),
    ("davies", "Alphonso Davies", "🇨🇦", "DEF", 97, 58, 70, 82, 76, 10),
    ("bellingham", "Bellingham", "🏴", "MID", 82, 82, 82, 86, 76, 10),
    ("debruyne", "De Bruyne", "🇧🇪", "MID", 72, 88, 95, 86, 64, 10),
    ("rodri", "Rodri", "🇪🇸", "MID", 62, 78, 90, 80, 88, 10),
    ("modric", "Modrić", "🇭🇷", "MID", 68, 76, 91, 89, 72, 10),
    ("pedri", "Pedri", "🇪🇸", "MID", 74, 72, 89, 90, 70, 10),
    ("valverde", "Valverde", "🇺🇾", "MID", 90, 80, 82, 80, 80, 10),
    ("kimmich", "Kimmich", "🇩🇪", "MID", 70, 74, 91, 80, 82, 10),
    ("bruno", "Bruno Fernandes", "🇵🇹", "MID", 72, 85, 91, 82, 68, 10),
    ("odegaard", "Ødegaard", "🇳🇴", "MID", 70, 80, 91, 90, 62, 10),
    ("musiala", "Musiala", "🇩🇪", "MID", 80, 78, 82, 93, 58, 10),
    ("wirtz", "Wirtz", "🇩🇪", "MID", 80, 80, 86, 91, 56, 10),
    ("kante", "Kanté", "🇫🇷", "MID", 80, 62, 78, 82, 90, 10),
    ("messi", "Messi", "🇦🇷", "FWD", 78, 90, 93, 96, 34, 10),
    ("ronaldo", "Ronaldo", "🇵🇹", "FWD", 80, 93, 80, 82, 34, 10),
    ("mbappe", "Mbappé", "🇫🇷", "FWD", 98, 92, 82, 92, 38, 10),
    ("haaland", "Haaland", "🇳🇴", "FWD", 92, 95, 68, 78, 45, 10),
    ("kane", "Kane", "🏴", "FWD", 70, 93, 86, 82, 48, 10),
    ("salah", "Salah", "🇪🇬", "FWD", 90, 90, 82, 89, 45, 10),
    ("vinicius", "Vinícius Jr", "🇧🇷", "FWD", 96, 84, 80, 95, 36, 10),
    ("lewandowski", "Lewandowski", "🇵🇱", "FWD", 76, 92, 78, 82, 42, 10),
    ("neymar", "Neymar", "🇧🇷", "FWD", 85, 86, 88, 95, 32, 10),
    ("son", "Son", "🇰🇷", "FWD", 91, 88, 80, 86, 42, 10),
    ("lautaro", "Lautaro Martínez", "🇦🇷", "FWD", 82, 89, 78, 84, 52, 10),
    ("yamal", "Lamine Yamal", "🇪🇸", "FWD", 90, 82, 84, 93, 36, 10),
    ("osimhen", "Osimhen", "🇳🇬", "FWD", 93, 87, 68, 80, 40, 10),
]
_W = {"GK": None, "DEF": (("dfn", .45), ("pac", .15), ("pas", .15), ("dri", .15), ("sho", .10)),
      "MID": (("pas", .30), ("dri", .25), ("dfn", .15), ("sho", .15), ("pac", .15)),
      "FWD": (("sho", .38), ("dri", .27), ("pac", .22), ("pas", .13))}


def _mk(r):
    p = dict(zip(("id", "name", "flag", "role", "pac", "sho", "pas", "dri", "dfn", "gk"), r))
    p["ovr"] = p["gk"] if p["role"] == "GK" else round(sum(p[k] * w for k, w in _W[p["role"]]))
    return p


ROSTER = {r[0]: _mk(r) for r in _RAW}
ROSTER_ORDER = [r[0] for r in _RAW]

ACT_BIAS = {"short": 9, "through": -3, "dribble": 0, "long": -7, "cross": -2}
ADV = {"short": 1, "through": 2, "dribble": 1, "long": 2}
STAM_COST = {"short": 4, "through": 7, "dribble": 9, "long": 6, "cross": 6, "shoot": 6}
#                 short through dribble long cross shoot   (added to the defender's score)
DEF_MOD = {
    "press":     {"short": 8, "through": -8, "dribble": 4, "long": -10, "cross": -4, "shoot": -2},
    "hold":      {"short": 0, "through": 4, "dribble": 2, "long": 3, "cross": 4, "shoot": 2},
    "intercept": {"short": -4, "through": 8, "dribble": -4, "long": 6, "cross": 6, "shoot": -6},
    "tackle":    {"short": 4, "through": -2, "dribble": 9, "long": -6, "cross": -6, "shoot": 6},
    "drop":      {"short": -6, "through": 6, "dribble": 3, "long": 8, "cross": 4, "shoot": 5},
    "mark":      {"short": -2, "through": 0, "dribble": 0, "long": 0, "cross": 2, "shoot": 2},
}
FOUL_P = {"press": .30, "tackle": .38, "mark": .18, "intercept": .16, "hold": .10, "drop": .06}
DEF_STAM = {"press": 8, "tackle": 8, "intercept": 6, "mark": 6, "hold": 4, "drop": 3}
PAIR = {"FWD": "DEF", "MID": "MID", "DEF": "FWD", "GK": "MID"}      # who marks whom
ZONE_ROLES = {0: ("FWD", "MID"), 1: ("MID", "DEF"), 2: ("DEF", "MID")}
BLOCK_T, OFF_T, SAVE_T = 34, 46, 76

VERB = {"short": "plays it forward", "through": "threads a through ball", "dribble": "dribbles at the defence",
        "long": "launches a long ball", "cross": "whips in a cross", "shoot": "lets fly"}
STAGE_SECONDS = {"draft": 22, "play": 16, "sub": 15, "pens": 10}


def _dict(p, stam=100, yc=0, off=False):
    d = dict(p)
    d.update(stam=round(stam), yc=yc, off=off)
    return d


class FootballGame(BaseGame):
    name = "football"
    min_players = 2
    max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Football needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        a, b = self.players
        self.stage = "draft"                 # draft -> play -> sub (half time) -> play -> pens? -> done
        self.pool = list(ROSTER_ORDER)
        self.squad = {u: [] for u in self.players}
        self.lineup = {u: [] for u in self.players}
        self.bench = {u: None for u in self.players}
        order = []
        for rnd in range(SQUAD):
            order += [a, b] if rnd % 2 == 0 else [b, a]
        self.draft_order, self.draft_i = order, 0
        self.stam = {p: 100.0 for p in ROSTER}
        self.yc = {}
        self.off = set()
        self.score = {u: 0 for u in self.players}
        self.stats = {u: {"shots": 0, "on": 0, "fouls": 0, "corners": 0, "yc": 0, "poss": 0} for u in self.players}
        self.half, self.slot = 1, 0
        self.attack = None
        self.picks = {}
        self.phase_id = 0
        self.seq = 0
        self.events = []
        self.last = None
        self.log = []
        self.pens = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self._bots()

    # ------------------------------------------------------------------ helpers
    @property
    def phase_seconds(self):
        return STAGE_SECONDS.get(self.stage, 15)

    def _other(self, u):
        return self.players[1] if u == self.players[0] else self.players[0]

    def _new_phase(self):
        self.picks = {}
        self.phase_id += 1

    def _ev(self, type_, **kw):
        self.seq += 1
        ev = {"seq": self.seq, "type": type_, "minute": self._minute(), "half": self.half, **kw}
        self.events = (self.events + [ev])[-6:]
        self.last = ev
        return ev

    def _say(self, icon, text):
        self.log = (self.log + [{"m": self._minute(), "i": icon, "t": text}])[-16:]

    def _minute(self):
        base = 45 * (self.half - 1)
        if self.stage in ("pens", "done") or (self.stage == "sub"):
            return base + 45 if self.stage != "pens" else 90
        n = self.attack["phase"] if self.attack else 0
        frac = (self.slot + min(n, 4) / 5.0) / ATTACKS_PER_HALF
        return base + max(1, min(45, int(45 * frac)))

    def _tri(self):
        return self.rng.random() + self.rng.random() - 1.0

    def _men_down(self, u):
        return sum(1 for p in self.lineup[u] if p in self.off)

    def _eff(self, u, pid, val):
        return val * (0.82 + 0.18 * self.stam[pid] / 100.0) * (1 - 0.05 * self._men_down(u))

    def _active(self, u):
        return [p for p in self.lineup[u] if p not in self.off]

    def _outfield(self, u):
        return [p for p in self._active(u) if ROSTER[p]["role"] != "GK"]

    def _gk(self, u):
        return next(p for p in self.lineup[u] if ROSTER[p]["role"] == "GK")

    @staticmethod
    def _astat(p, act):
        if act == "short":
            return .7 * p["pas"] + .3 * p["dri"]
        if act == "through":
            return .5 * p["pas"] + .25 * p["pac"] + .25 * p["dri"]
        if act == "dribble":
            return .65 * p["dri"] + .35 * p["pac"]
        if act == "long":
            return .55 * p["pas"] + .45 * p["pac"]
        if act == "cross":
            return .6 * p["pas"] + .2 * p["dri"] + .2 * p["sho"]
        return .85 * p["sho"] + .15 * p["dri"]

    @staticmethod
    def _dstat(p):
        return .75 * p["dfn"] + .25 * p["pac"]

    def _pd(self, pid):
        return _dict(ROSTER[pid], self.stam[pid], self.yc.get(pid, 0), pid in self.off)

    # ------------------------------------------------------------------ interface
    def _pending(self):
        if self.finished:
            return []
        if self.stage == "draft":
            return [self.draft_order[self.draft_i]]
        if self.stage == "play":
            a = self.attack
            return [u for u in (a["team"], self._other(a["team"])) if u not in self.picks]
        if self.stage == "sub":
            return [u for u in self.players if u not in self.picks]
        if self.stage == "pens":
            return [u for u in (self._shooter(), self._keeper()) if u not in self.picks]
        return []

    def current(self):
        if self.finished:
            return None
        p = self._pending()
        return ([u for u in p if u > 0] or p or [None])[0]

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The match is over")
        if uid not in self.players:
            raise GameError("You are not playing")
        t = msg.get("t")
        if self.stage == "draft":
            if t != "pick":
                raise GameError("Pick a player for your squad")
            if uid != self.draft_order[self.draft_i]:
                raise GameError("Wait for your pick")
            pid = msg.get("id")
            if not self._can_pick(uid, pid):
                raise GameError("You can't pick that player")
            self._draft_pick(uid, pid)
        elif self.stage == "play":
            if uid in self.picks:
                raise GameError("Already chosen, wait for your opponent")
            self.picks[uid] = self._validate_play(uid, msg)
        elif self.stage == "sub":
            if uid in self.picks:
                raise GameError("Already chosen")
            self.picks[uid] = self._validate_sub(uid, msg)
        elif self.stage == "pens":
            if t != "dir" or msg.get("dir") not in DIRS:
                raise GameError("Pick left, centre or right")
            if uid in self.picks:
                raise GameError("Already picked")
            self.picks[uid] = msg["dir"]
        self._bots()

    def auto_play(self):
        if self.finished:
            return
        if self.stage == "draft":
            u = self.draft_order[self.draft_i]
            self._draft_pick(u, self._auto_draft(u))
        else:
            for u in self._pending():
                self.picks[u] = self._choose(u)
            if not self._pending():
                self._resolve_stage()
        self._bots()

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished = True
        self.stage = "done"
        self.winner = self._other(uid)

    def _bots(self):
        for _ in range(600):
            if self.finished:
                return
            pend = self._pending()
            if self.stage == "draft":
                if pend and pend[0] < 0:
                    self._draft_pick(pend[0], self._auto_draft(pend[0]))
                    continue
                return
            for u in pend:
                if u < 0:
                    self.picks[u] = self._choose(u)
            if self._pending():
                return
            self._resolve_stage()

    def _resolve_stage(self):
        {"play": self._resolve_phase, "sub": self._resolve_sub, "pens": self._resolve_pen}[self.stage]()

    # ------------------------------------------------------------------ draft
    def _can_pick(self, u, pid):
        if pid not in self.pool:
            return False
        roles = [ROSTER[p]["role"] for p in self.squad[u]] + [ROSTER[pid]["role"]]
        if roles.count("GK") > 1:
            return False
        need = (roles.count("GK") == 0) + sum(1 for r in ("DEF", "MID", "FWD") if r not in roles)
        return need <= SQUAD - len(roles)

    def _draft_pick(self, u, pid):
        self.pool.remove(pid)
        self.squad[u].append(pid)
        self.draft_i += 1
        p = ROSTER[pid]
        self._ev("pick", uid=u, pid=pid, n=self.draft_i)
        self._say("📋", f"{p['name']} {p['flag']} joins the squad")
        self._new_phase()
        if self.draft_i >= len(self.draft_order):
            self._start_match()

    def _auto_draft(self, u):
        ok = [p for p in self.pool if self._can_pick(u, p)]
        have = [ROSTER[p]["role"] for p in self.squad[u]]

        def val(p):
            r = ROSTER[p]
            v = r["ovr"] + self.rng.random() * 3
            if r["role"] == "GK":
                v -= 12 if len(self.squad[u]) < 3 else 4      # goalkeepers can wait a little
            if r["role"] in have and r["role"] != "GK":
                v -= 1.5 * have.count(r["role"])
            return v
        ok.sort(key=val, reverse=True)
        top = ok[:3]
        return self.rng.choices(top, weights=[5, 2, 1][:len(top)])[0]

    def _start_match(self):
        for u in self.players:
            sq = self.squad[u]
            gk = next(p for p in sq if ROSTER[p]["role"] == "GK")
            out = sorted((p for p in sq if p != gk), key=lambda p: ROSTER[p]["ovr"], reverse=True)
            start = []
            for role in ("FWD", "MID", "DEF"):
                best = next(p for p in out if ROSTER[p]["role"] == role)
                start.append(best)
            rest = [p for p in out if p not in start]
            start.append(rest[0])
            self.bench[u] = rest[1]
            order = {"DEF": 0, "MID": 1, "FWD": 2}
            self.lineup[u] = [gk] + sorted(start, key=lambda p: order[ROSTER[p]["role"]])
        self.stage = "play"
        self._ev("kickoff")
        self._say("🔔", "Kick-off! First half")
        self._start_attack()

    # ------------------------------------------------------------------ attacks
    def _start_attack(self, team=None, counter=False):
        team = team if team is not None else self.players[(self.slot + self.half - 1) % 2]
        self.attack = {"team": team, "zone": 1 if counter else 0, "phase": 0, "counter": counter, "opening": False, "holder": None}
        self._new_phase()

    def _finish_attack(self, counter_for=None):
        if not self.attack["counter"]:
            self.slot += 1
        if counter_for is not None:
            self._start_attack(counter_for, True)
            return
        self.attack = None
        if self.slot >= ATTACKS_PER_HALF:
            self._period_end()
        else:
            self._start_attack()

    def _period_end(self):
        if self.half == 1:
            self.stage = "sub"
            self._ev("halftime", score=dict(self.score))
            self._say("⏸️", "Half-time")
            self._new_phase()
            return
        a, b = self.players
        self._ev("fulltime", score=dict(self.score))
        self._say("🏁", "Full time")
        if self.score[a] != self.score[b]:
            self.winner = a if self.score[a] > self.score[b] else b
            self.finished, self.stage = True, "done"
            return
        self.stage = "pens"
        self.pens = {"order": {}, "taken": {u: 0 for u in self.players}, "goals": {u: 0 for u in self.players}, "n": 0, "history": []}
        for u in self.players:
            lu = sorted(self.lineup[u], key=lambda p: (ROSTER[p]["role"] == "GK", -ROSTER[p]["sho"]))
            self.pens["order"][u] = lu
        self._say("🥅", "Penalty shootout!")
        self._new_phase()

    def _avail(self, u):
        a = self.attack
        acts = ZONE_ACTS[a["zone"]]
        return acts

    def _validate_play(self, uid, msg):
        a = self.attack
        t = msg.get("t")
        if uid == a["team"]:
            if t != "act":
                raise GameError("Choose your action and who takes it")
            act, who = msg.get("act"), msg.get("who")
            if act not in ZONE_ACTS[a["zone"]]:
                raise GameError("You can't do that from here")
            ok = self._outfield(uid) + ([self._gk(uid)] if a["zone"] == 0 and act in ("short", "long") else [])
            if who not in ok:
                raise GameError("Choose one of your available players")
            return {"act": act, "who": who}
        if t != "def":
            raise GameError("Choose your defensive stance")
        stance, mark = msg.get("stance"), msg.get("mark")
        if stance not in STANCES:
            raise GameError("Unknown stance")
        if mark is not None and mark not in self._outfield(a["team"]):
            raise GameError("Choose an attacker to mark")
        if stance == "mark" and mark is None:
            raise GameError("Choose who to man-mark")
        return {"stance": stance, "mark": mark}

    def _pick_defender(self, du, zone, who, stance, mark):
        outs = self._outfield(du)
        if stance == "mark" and mark is not None:
            want = PAIR[ROSTER[mark]["role"]]
            cands = [p for p in outs if ROSTER[p]["role"] == want] or outs
            return max(cands, key=lambda p: ROSTER[p]["dfn"])
        cands = [p for p in outs if ROSTER[p]["role"] in ZONE_ROLES[zone]] or outs
        return self.rng.choices(cands, weights=[ROSTER[p]["dfn"] + 20 for p in cands])[0]

    def _resolve_phase(self):
        at = self.attack
        au, du = at["team"], self._other(at["team"])
        ap, dp = self.picks[au], self.picks[du]
        act, wid, stance, mark = ap["act"], ap["who"], dp["stance"], dp["mark"]
        W = ROSTER[wid]
        zone0 = at["zone"]
        D = self._pick_defender(du, zone0, wid, stance, mark)
        Dp = ROSTER[D]
        self.stats[au]["poss"] += 1
        at["phase"] += 1
        marked = mark == wid
        ev = {"att": au, "def": du, "zone": zone0, "act": act, "who": wid, "stance": stance, "mark": mark, "defender": D,
              "result": None, "shots": [], "foul": None, "card": None, "counter": False, "corner": False, "counter_run": at["counter"]}
        a = self._eff(au, wid, self._astat(W, act)) + ACT_BIAS.get(act, 0) + (5 if at["opening"] and zone0 == 2 and act != "shoot" else 0)
        d = self._eff(du, D, self._dstat(Dp)) + DEF_MOD[stance][act]
        if stance == "mark":
            d += 12 if marked else -5
        elif marked:
            d += 4
        x = a - d + self._tri() * 20
        ev["x"] = round(x)
        self.stam[wid] = max(20, self.stam[wid] - STAM_COST[act])
        self.stam[D] = max(20, self.stam[D] - DEF_STAM[stance])
        nm, dn = W["name"], Dp["name"]
        counter_for = None
        end = False
        if act == "shoot":
            kind = "range" if zone0 == 1 else "shot"
            bonus = -20 if kind == "range" else (6 if at["opening"] else 0)
            self._shot(ev, au, du, wid, kind, bonus, D, stance, marked)
            end = True
        elif x > 0:
            if act == "cross":
                shooter = wid
                self._shot(ev, au, du, shooter, "header", min(x, 20) * .3 - 2, D, stance, marked)
                end = True
            else:
                adv = ADV[act] + (1 if x > 26 and act in ("short", "dribble") else 0)
                at["zone"] = min(2, at["zone"] + adv)
                at["holder"] = wid
                if zone0 == 2 or at["zone"] == 2 and zone0 == 1 and adv > 1:
                    at["opening"] = True
                ev["result"] = "open" if at["zone"] == 2 else "adv"
                self._say("➡️", f"{nm} {VERB[act]}" + (f", {dn} beaten" if act == "dribble" else ""))
        else:
            if self.rng.random() < FOUL_P[stance] + (.08 if act == "dribble" else 0) and act != "cross":
                end = self._foul(ev, au, du, W, D, stance, marked)
            else:
                end = True
                self._turnover(ev, au, du, W, D, act, stance, zone0)
                if ev["counter"]:
                    counter_for = du
        if not end and at["phase"] >= MAX_PHASES:
            ev["result"] = "wasted"
            self._say("🧤", f"{self._pn(au)} run out of ideas, the keeper claims it")
            end = True
        ev["zone2"] = at["zone"]
        ev["score"] = dict(self.score)
        if ev["result"] is None:
            ev["result"] = "adv"
        text = self.log[-1]["t"] if self.log else ""
        ev["text"] = text
        self._ev("phase", **ev)
        self._new_phase()
        if end:
            self._finish_attack(counter_for)

    def _pn(self, u):
        return "Home" if u == self.players[0] else "Away"

    def _turnover(self, ev, au, du, W, D, act, stance, zone):
        pc = .28 + {"press": .06, "intercept": .16, "tackle": .12}.get(stance, 0) - (.08 if act in ("short",) else 0)
        ev["result"] = "lost"
        if self.attack["counter"]:
            pc = 0
        ev["counter"] = self.rng.random() < pc
        if act == "long":
            self._say("🛡️", f"{ROSTER[D]['name']} wins the long ball")
        elif stance == "intercept":
            self._say("✂️", f"{ROSTER[D]['name']} intercepts!")
        elif act == "dribble":
            self._say("🦵", f"{ROSTER[D]['name']} robs {W['name']}")
        else:
            self._say("🛡️", f"{ROSTER[D]['name']} wins it back")
        if ev["counter"]:
            self._say("⚡", "Quick break! Counter-attack")

    def _foul(self, ev, au, du, W, D, stance, marked):
        a = self.attack
        zone = a["zone"]
        self.stats[du]["fouls"] += 1
        ev["result"] = "foul"
        ev["foul"] = {"by": D, "on": W["id"], "kind": "foul"}
        self._say("🟨" if False else "🚩", f"Foul by {ROSTER[D]['name']} on {W['name']}")
        if self.rng.random() < (.30 + .10 * (self.yc.get(D, 0))):
            self.yc[D] = self.yc.get(D, 0) + 1
            self.stats[du]["yc"] += 1
            kind = "yellow"
            if self.yc[D] >= 2 and len(self._outfield(du)) > 2:
                kind = "red"
                self.off.add(D)
            ev["card"] = {"pid": D, "kind": kind}
            self._say("🟥" if kind == "red" else "🟨", f"{'RED CARD' if kind == 'red' else 'Yellow card'} for {ROSTER[D]['name']}")
        if zone == 2:
            if ev["card"] is None and self.rng.random() < .22 and ev.get("act") in ("dribble", "through"):
                ev["foul"]["kind"] = "pen"
            elif self.rng.random() < .55:
                ev["foul"]["kind"] = "pen" if ev["act"] in ("dribble", "through") and self.rng.random() < .35 else "fk"
        elif zone == 1:
            ev["foul"]["kind"] = "fk" if self.rng.random() < .35 else "foul"
            if ev["foul"]["kind"] == "fk":
                ev["foul"]["kind"] = "adv"
        k = ev["foul"]["kind"]
        if k == "pen":
            self._penalty_kick(ev, au, du)
            return True
        if k == "fk":
            sh = max(self._outfield(au), key=lambda p: ROSTER[p]["sho"])
            self._say("🎯", f"Free kick in a dangerous position, {ROSTER[sh]['name']} steps up")
            self._shot(ev, au, du, sh, "freekick", -8, D, "hold", False)
            return True
        if k == "adv":            # free kick on the edge of the area: play moves into the final third
            a["zone"] = 2
            a["opening"] = True
        return False

    def _penalty_kick(self, ev, au, du):
        sh = max(self._outfield(au), key=lambda p: ROSTER[p]["sho"])
        gk = self._gk(du)
        S, G = ROSTER[sh], ROSTER[gk]
        p = max(.55, min(.9, .76 + (self._eff(au, sh, S["sho"]) - 80) / 300 - (self._eff(du, gk, G["gk"]) - 80) / 400))
        r = self.rng.random()
        outcome = "goal" if r < p else "saved" if r < p + (1 - p) * .7 else "off"
        self._say("⚠️", f"PENALTY! {S['name']} steps up")
        self._record_shot(ev, au, du, sh, gk, "penalty", outcome, 0)

    def _shot(self, ev, au, du, sid, kind, bonus, D, stance, marked):
        S = ROSTER[sid]
        gk = self._gk(du)
        G = ROSTER[gk]
        s = self._eff(au, sid, S["sho"]) + bonus
        d = .5 * self._eff(du, D["id"] if isinstance(D, dict) else D, self._dstat(D if isinstance(D, dict) else ROSTER[D])) \
            + DEF_MOD[stance]["shoot"] + (6 if marked else 0)
        if kind == "freekick":
            d = 40
        x = s - d + self._tri() * 20
        if x < BLOCK_T:
            outcome = "blocked"
        elif x < OFF_T:
            outcome = "off"
        else:
            g = self._eff(du, gk, G["gk"]) + (3 if stance == "drop" else 0)
            power = (x - OFF_T) + (S["sho"] - 80) * .3
            outcome = "saved" if g + self._tri() * 24 > SAVE_T + power else "goal"
        self._record_shot(ev, au, du, sid, gk, kind, outcome, x)

    def _record_shot(self, ev, au, du, sid, gk, kind, outcome, x):
        S, G = ROSTER[sid], ROSTER[gk]
        st = self.stats[au]
        st["shots"] += 1
        if outcome in ("goal", "saved"):
            st["on"] += 1
        shot = {"shooter": sid, "keeper": gk, "kind": kind, "outcome": outcome, "dir": self.rng.choice(DIRS), "x": round(x)}
        ev["shots"].append(shot)
        self.stam[sid] = max(20, self.stam[sid] - 3)
        if outcome == "goal":
            self.score[au] += 1
            ev["result"] = "goal"
            self._say("⚽", f"GOAL! {S['name']} {S['flag']} scores!" + (" (penalty)" if kind == "penalty" else ""))
            return
        if outcome == "saved":
            self._say("🧤", f"Great save by {G['name']}!")
        elif outcome == "blocked":
            self._say("🛡️", f"{S['name']}'s shot is blocked")
        else:
            self._say("💨", f"{S['name']} fires wide")
        ev["result"] = outcome
        if outcome in ("saved", "blocked") and kind in ("shot", "range", "header") and not ev["corner"] and self.rng.random() < .30:
            ev["corner"] = True
            st["corners"] += 1
            outs = sorted(self._outfield(au), key=lambda p: (ROSTER[p]["sho"] + ROSTER[p]["dfn"] * .3), reverse=True)
            h = outs[0]
            self._say("🚩", "Corner kick")
            self._shot(ev, au, du, h, "corner", -6 if False else -4, self._outfield(du)[0], "hold", False)
        elif outcome in ("saved", "blocked") and ev["result"] != "goal":
            pass

    # ------------------------------------------------------------------ half time
    def _validate_sub(self, uid, msg):
        if msg.get("t") != "sub":
            raise GameError("Make a substitution or keep the team")
        out = msg.get("out")
        if out is None:
            return None
        if out not in self.lineup[uid] or ROSTER[out]["role"] == "GK" or self.bench[uid] is None:
            raise GameError("Choose an outfield player to take off")
        if out in self.off:
            raise GameError("That player was sent off")
        return out

    def _resolve_sub(self):
        subs = {}
        for u in self.players:
            out = self.picks.get(u)
            if out is not None:
                inn = self.bench[u]
                self.lineup[u][self.lineup[u].index(out)] = inn
                self.bench[u] = out
                self.stam[inn] = 100
                subs[u] = {"out": out, "in": inn}
                self._say("🔁", f"{ROSTER[inn]['name']} replaces {ROSTER[out]['name']}")
            else:
                subs[u] = None
            for p in self.squad[u]:
                self.stam[p] = min(100, self.stam[p] + 25)
        self.half, self.slot = 2, 0
        self.stage = "play"
        self._ev("sub", subs=subs)
        self._say("🔔", "Second half underway")
        self._start_attack()

    # ------------------------------------------------------------------ shootout
    def _shooter(self):
        return self.players[self.pens["n"] % 2]

    def _keeper(self):
        return self._other(self._shooter())

    def _resolve_pen(self):
        P = self.pens
        s, k = self._shooter(), self._keeper()
        shot, dive = self.picks[s], self.picks[k]
        taker = P["order"][s][P["taken"][s] % len(P["order"][s])]
        gk = self._gk(k)
        T, G = ROSTER[taker], ROSTER[gk]
        if shot == dive:
            saved = self.rng.random() < max(.55, min(.93, .82 + (G["gk"] - T["sho"]) / 200))
            outcome = "saved" if saved else "goal"
        else:
            miss = self.rng.random() < max(.04, min(.25, .09 + (80 - T["sho"]) / 200))
            outcome = "off" if miss else "goal"
        P["taken"][s] += 1
        if outcome == "goal":
            P["goals"][s] += 1
        P["n"] += 1
        h = {"uid": s, "pid": taker, "keeper": gk, "shot": shot, "dive": dive, "outcome": outcome}
        P["history"] = (P["history"] + [h])[-40:]
        self._ev("pen", **h, goals=dict(P["goals"]), taken=dict(P["taken"]))
        self._say("🥅", f"{T['name']}: {'scores' if outcome == 'goal' else 'saved' if outcome == 'saved' else 'misses'}")
        self._new_phase()
        a, b = self.players
        ta, tb = P["taken"][a], P["taken"][b]
        ga, gb = P["goals"][a], P["goals"][b]
        done = False
        if ta <= PEN_KICKS and tb <= PEN_KICKS and not (ta == PEN_KICKS and tb == PEN_KICKS):
            done = ga > gb + (PEN_KICKS - tb) or gb > ga + (PEN_KICKS - ta)
        else:
            done = ta == tb and ga != gb
        if done:
            self.winner = a if ga > gb else b
        elif P["n"] >= PEN_CAP:
            self.winner = a if ga > gb else b if gb > ga else self.rng.choice(self.players)
            done = True
        if done:
            self.finished, self.stage = True, "done"

    # ------------------------------------------------------------------ bots / auto play
    def _choose(self, u):
        if self.stage == "play":
            return self._bot_play(u)
        if self.stage == "sub":
            return self._bot_sub(u)
        return self.rng.choice(DIRS)

    def _bot_play(self, u):
        a = self.attack
        zone = a["zone"]
        if u == a["team"]:
            W = {0: {"short": 5, "long": 2, "through": 1.5, "dribble": 1.5},
                 1: {"short": 3, "through": 3, "dribble": 2.5, "long": .8, "shoot": 1.0},
                 2: {"shoot": 4, "cross": 2.5, "through": 1.5, "short": 1.2, "dribble": 2}}[zone]
            if a["opening"] and zone == 2:
                W = dict(W, shoot=W["shoot"] + 2.5)
            acts = list(W)
            act = self.rng.choices(acts, weights=[W[k] for k in acts])[0]
            pool = self._outfield(u) + ([self._gk(u)] if zone == 0 and act in ("short", "long") else [])
            ws = [max(1.0, 1.0 + (self._eff(u, p, self._astat(ROSTER[p], act)) - 60) / 6) ** 1.6 for p in pool]
            return {"act": act, "who": self.rng.choices(pool, weights=ws)[0]}
        W = {0: {"press": 3, "hold": 3, "intercept": 1.5, "drop": 1, "tackle": .6, "mark": .5},
             1: {"hold": 3, "press": 2, "intercept": 2, "tackle": 2, "drop": 1, "mark": 1},
             2: {"mark": 2, "tackle": 2.5, "hold": 2.5, "drop": 2.5, "intercept": 1, "press": .5}}[zone]
        stance = self.rng.choices(list(W), weights=list(W.values()))[0]
        outs = self._outfield(a["team"])
        ws = [(ROSTER[p]["ovr"] - 50) ** 2 for p in outs]
        mark = self.rng.choices(outs, weights=ws)[0]
        return {"stance": stance, "mark": mark if (stance == "mark" or self.rng.random() < .6) else None}

    def _bot_sub(self, u):
        if self.bench[u] is None:
            return None
        outs = self._outfield(u)
        worst = min(outs, key=lambda p: self.stam[p] * .6 + ROSTER[p]["ovr"] * .4)
        b = ROSTER[self.bench[u]]
        w = ROSTER[worst]
        if b["ovr"] * 1.0 > w["ovr"] * (0.82 + .18 * self.stam[worst] / 100) + 1:
            return worst
        return None

    # ------------------------------------------------------------------ state
    def public_state(self):
        at = self.attack
        st = {"kind": "football", "stage": self.stage, "phase": self.stage, "phase_id": self.phase_id,
              "phase_seconds": self.phase_seconds, "pending": self._pending(), "seq": self.seq,
              "players": [{"uid": u, "score": self.score[u]} for u in self.players],
              "turn": self.current(), "picked": {u: u in self.picks for u in self.players},   # never the choice itself
              "half": self.half, "minute": self._minute(), "slot": self.slot, "per_half": ATTACKS_PER_HALF,
              "attack": ({"team": at["team"], "zone": at["zone"], "phase": at["phase"], "counter": at["counter"],
                          "opening": at["opening"], "holder": at["holder"]} if at else None),
              "last": self.last, "events": self.events, "log": self.log, "stats": self.stats,
              "squads": {u: [self._pd(p) for p in self.squad[u]] for u in self.players},
              "lineup": self.lineup, "bench": self.bench, "pool": self.pool,
              "draft": {"order": self.draft_order, "i": self.draft_i},
              "winner": self.winner, "draw": self.draw}
        if self.stage == "draft":
            st["roster"] = [ROSTER[p] for p in ROSTER_ORDER]
        if self.pens:
            P = self.pens
            st["pens"] = {"goals": P["goals"], "taken": P["taken"], "n": P["n"], "kicks": PEN_KICKS, "history": P["history"],
                          "order": P["order"], "shooter": self._shooter() if not self.finished else None}
        return st

    def view(self, uid):
        s = self.public_state()
        if uid in self.picks:
            s["my_pick"] = self.picks[uid]
        return s

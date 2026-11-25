"""Cricket (T10-style, 2 players). Each side drafts a squad from a roster of world-class cricketers (snake draft),
then plays two innings (OVERS overs of BALLS balls, wickets = TEAM-1) with a target chase.

Every ball is a hidden duel: the bowler secretly picks a delivery + line, the batter secretly picks a shot + direction.
The server resolves it from the player ratings, the delivery/shot matchup, line-vs-direction, the bowler's field setting,
powerplay and death-over pressure. Runs / wickets / extras / free hits / strike rotation / partnerships / scorecards
are all server-side. Computer players (uid < 0) pick sensibly; auto_play covers AFK humans. Pass `rng` for determinism."""
from __future__ import annotations

import math
import random

from .base import BaseGame, GameError

OVERS = 2                # overs per innings
BALLS = 6                # legal balls per over
TEAM = 5                 # squad size; innings ends when TEAM-1 wickets are down
POWERPLAY = 1            # first N overs: two fielders out only (boundaries easier, no defensive field)
MAX_PER_BOWLER = 1       # overs per bowler
DRAFT_SECONDS, OVER_SECONDS, BALL_SECONDS = 25, 15, 14
WIDE_P, NOBALL_P = 0.03, 0.012

# id, name, short, flag, batting, bowling, bowler type, batting style
ROSTER_RAW = [
    ("kohli", "Virat Kohli", "Kohli", "🇮🇳", 96, 16, "pace", "anchor"),
    ("rohit", "Rohit Sharma", "Rohit", "🇮🇳", 91, 20, "spin", "aggressive"),
    ("sachin", "Sachin Tendulkar", "Tendulkar", "🇮🇳", 97, 38, "spin", "anchor"),
    ("dhoni", "MS Dhoni", "Dhoni", "🇮🇳", 89, 8, "pace", "aggressive"),
    ("dravid", "Rahul Dravid", "Dravid", "🇮🇳", 90, 6, "spin", "anchor"),
    ("surya", "Suryakumar Yadav", "Surya", "🇮🇳", 93, 10, "spin", "aggressive"),
    ("bumrah", "Jasprit Bumrah", "Bumrah", "🇮🇳", 24, 97, "pace", "anchor"),
    ("hardik", "Hardik Pandya", "Pandya", "🇮🇳", 80, 74, "pace", "aggressive"),
    ("jadeja", "Ravindra Jadeja", "Jadeja", "🇮🇳", 70, 85, "spin", "anchor"),
    ("ashwin", "R Ashwin", "Ashwin", "🇮🇳", 52, 87, "spin", "anchor"),
    ("babar", "Babar Azam", "Babar", "🇵🇰", 93, 8, "spin", "anchor"),
    ("shaheen", "Shaheen Afridi", "S Afridi", "🇵🇰", 22, 91, "swing", "anchor"),
    ("shahid", "Shahid Afridi", "Afridi", "🇵🇰", 78, 74, "spin", "aggressive"),
    ("wasim", "Wasim Akram", "Wasim", "🇵🇰", 44, 96, "swing", "aggressive"),
    ("imran", "Imran Khan", "Imran", "🇵🇰", 60, 93, "swing", "anchor"),
    ("rashid", "Rashid Khan", "Rashid", "🇦🇫", 52, 96, "spin", "aggressive"),
    ("smith", "Steve Smith", "Smith", "🇦🇺", 91, 42, "spin", "anchor"),
    ("warner", "David Warner", "Warner", "🇦🇺", 88, 8, "pace", "aggressive"),
    ("maxwell", "Glenn Maxwell", "Maxwell", "🇦🇺", 86, 62, "spin", "aggressive"),
    ("cummins", "Pat Cummins", "Cummins", "🇦🇺", 38, 92, "pace", "anchor"),
    ("starc", "Mitchell Starc", "Starc", "🇦🇺", 28, 93, "swing", "aggressive"),
    ("warne", "Shane Warne", "Warne", "🇦🇺", 31, 97, "spin", "anchor"),
    ("ponting", "Ricky Ponting", "Ponting", "🇦🇺", 92, 10, "pace", "anchor"),
    ("gilly", "Adam Gilchrist", "Gilchrist", "🇦🇺", 91, 3, "pace", "aggressive"),
    ("lee", "Brett Lee", "B Lee", "🇦🇺", 30, 93, "pace", "aggressive"),
    ("root", "Joe Root", "Root", "🏴", 91, 40, "spin", "anchor"),
    ("stokes", "Ben Stokes", "Stokes", "🏴", 85, 80, "pace", "aggressive"),
    ("buttler", "Jos Buttler", "Buttler", "🏴", 92, 5, "pace", "aggressive"),
    ("archer", "Jofra Archer", "Archer", "🏴", 33, 93, "pace", "aggressive"),
    ("anderson", "James Anderson", "Anderson", "🏴", 22, 94, "swing", "anchor"),
    ("williamson", "Kane Williamson", "Williamson", "🇳🇿", 91, 34, "spin", "anchor"),
    ("boult", "Trent Boult", "Boult", "🇳🇿", 21, 91, "swing", "anchor"),
    ("abd", "AB de Villiers", "de Villiers", "🇿🇦", 97, 22, "pace", "aggressive"),
    ("dekock", "Quinton de Kock", "de Kock", "🇿🇦", 87, 4, "pace", "aggressive"),
    ("steyn", "Dale Steyn", "Steyn", "🇿🇦", 18, 96, "pace", "aggressive"),
    ("rabada", "Kagiso Rabada", "Rabada", "🇿🇦", 28, 92, "pace", "aggressive"),
    ("kallis", "Jacques Kallis", "Kallis", "🇿🇦", 90, 78, "pace", "anchor"),
    ("gayle", "Chris Gayle", "Gayle", "🇯🇲", 93, 34, "spin", "aggressive"),
    ("russell", "Andre Russell", "Russell", "🇯🇲", 84, 78, "pace", "aggressive"),
    ("narine", "Sunil Narine", "Narine", "🇹🇹", 60, 92, "spin", "aggressive"),
    ("viv", "Viv Richards", "Richards", "🇦🇬", 96, 38, "spin", "aggressive"),
    ("lara", "Brian Lara", "Lara", "🇹🇹", 95, 8, "spin", "anchor"),
    ("murali", "Muttiah Muralitharan", "Murali", "🇱🇰", 14, 98, "spin", "anchor"),
    ("sanga", "Kumar Sangakkara", "Sangakkara", "🇱🇰", 92, 4, "pace", "anchor"),
    ("malinga", "Lasith Malinga", "Malinga", "🇱🇰", 22, 93, "pace", "aggressive"),
    ("shakib", "Shakib Al Hasan", "Shakib", "🇧🇩", 75, 85, "spin", "anchor"),
]
ROSTER = {r[0]: {"id": r[0], "name": r[1], "short": r[2], "flag": r[3], "bat": r[4], "bowl": r[5], "type": r[6], "style": r[7]}
          for r in ROSTER_RAW}

SHOTS = ["defend", "drive", "cut", "pull", "loft", "sweep", "leave"]
DIRS = ["off", "straight", "leg"]
LINES = ["off", "middle", "leg"]
FIELDS = ["attack", "balanced", "defensive"]
BOWL_SETS = {
    "pace": ["yorker", "bouncer", "length", "slower"],
    "swing": ["yorker", "length", "inswing", "outswing"],
    "spin": ["offbreak", "legbreak", "googly", "flighted"],
}

# how well a shot suits a delivery, from the batter's side: -1 (terrible) .. +1 (ideal)
SUIT = {
    "yorker":   {"defend": .3, "drive": -.1, "cut": -.6, "pull": -.8, "loft": -.7, "sweep": -.9, "leave": -.6},
    "bouncer":  {"defend": -.2, "drive": -.8, "cut": .5, "pull": .7, "loft": -.1, "sweep": -.8, "leave": .3},
    "length":   {"defend": .2, "drive": .5, "cut": -.3, "pull": -.4, "loft": .3, "sweep": -.7, "leave": .1},
    "slower":   {"defend": .3, "drive": -.5, "cut": .3, "pull": .2, "loft": -.6, "sweep": -.4, "leave": -.2},
    "inswing":  {"defend": .0, "drive": -.3, "cut": -.7, "pull": .0, "loft": -.3, "sweep": -.7, "leave": -.7},
    "outswing": {"defend": -.2, "drive": -.5, "cut": -.1, "pull": .2, "loft": .3, "sweep": -.7, "leave": .4},
    "offbreak": {"defend": .2, "drive": .4, "cut": -.2, "pull": .1, "loft": -.1, "sweep": .5, "leave": -.3},
    "legbreak": {"defend": .1, "drive": -.3, "cut": .5, "pull": -.2, "loft": .1, "sweep": -.5, "leave": .2},
    "googly":   {"defend": -.3, "drive": -.4, "cut": -.3, "pull": .3, "loft": -.5, "sweep": .1, "leave": -.5},
    "flighted": {"defend": .2, "drive": -.4, "cut": .0, "pull": -.2, "loft": .5, "sweep": .3, "leave": -.2},
}
LINE_FIT = {"off": {"off": .35, "straight": 0.0, "leg": -.5},
            "middle": {"off": -.1, "straight": .35, "leg": -.1},
            "leg": {"off": -.5, "straight": 0.0, "leg": .35}}
NATURAL = {"cut": "off", "pull": "leg", "sweep": "leg"}      # shots with a natural side; the other sides feel awkward
BASE = {                                                      # raw outcome weights per shot (0 = dot ball)
    "defend": {0: .72, 1: .20, 2: .03, 3: .0, 4: .01, 6: .0, "W": .04},
    "drive":  {0: .22, 1: .24, 2: .13, 3: .02, 4: .24, 6: .04, "W": .11},
    "cut":    {0: .24, 1: .22, 2: .12, 3: .02, 4: .22, 6: .05, "W": .13},
    "pull":   {0: .20, 1: .13, 2: .08, 3: .02, 4: .22, 6: .20, "W": .15},
    "loft":   {0: .20, 1: .08, 2: .05, 3: .02, 4: .14, 6: .33, "W": .18},
    "sweep":  {0: .22, 1: .24, 2: .12, 3: .02, 4: .18, 6: .09, "W": .13},
    "leave":  {0: .93, 1: .0, 2: .0, 3: .0, 4: .0, 6: .0, "W": .07},
}
KQ = {0: -.35, 1: .35, 2: .5, 3: .5, 4: .8, 6: 1.0, "W": -.9}   # how strongly shot quality q scales each outcome
FIELD_MUL = {
    "attack": {0: 1.05, 1: .85, 2: .9, 3: .9, 4: 1.15, 6: 1.0, "W": 1.3},
    "balanced": {},
    "defensive": {0: 1.0, 1: 1.15, 2: 1.0, 3: 1.0, 4: .7, 6: .85, "W": .78},
}
OUTCOMES = (0, 1, 2, 3, 4, 6, "W")


def overs_txt(balls):
    return f"{balls // BALLS}.{balls % BALLS}"


class CricketMatch(BaseGame):
    name = "cricket"
    min_players = 2
    max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Cricket needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        a, b = self.players
        self.order = [a, b, b, a] * TEAM
        self.order = self.order[: 2 * TEAM]            # snake draft: A B B A A B B A A B ...
        self.pool = list(ROSTER)
        self.teams = {u: [] for u in self.players}
        self.phase = "draft"
        self.phase_id = 0
        self.picks = {}
        self.seq = 0
        self.last_ball = None
        self.last_event = None
        self.inns = []
        self.bat_first = self.rng.choice(self.players)
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self.result_text = ""
        self._bots()

    # ------------------------------------------------------------------ helpers
    @property
    def phase_seconds(self):
        return {"draft": DRAFT_SECONDS, "over": OVER_SECONDS}.get(self.phase, BALL_SECONDS)

    @property
    def inn(self):
        return self.inns[-1] if self.inns else None

    def _other(self, uid):
        return self.players[1] if uid == self.players[0] else self.players[0]

    def _picker(self):
        return self.order[len(self.order) - (2 * TEAM - sum(len(t) for t in self.teams.values()))] if self.phase == "draft" else None

    def _pending(self):
        if self.finished:
            return []
        if self.phase == "draft":
            return [self._picker()]
        if self.phase == "over":
            return [self.inn["bowl"]]
        if self.phase == "ball":
            return [u for u in (self.inn["bowl"], self.inn["bat"]) if u not in self.picks]
        return []

    def current(self):
        p = self._pending()
        if not p:
            return None
        return ([u for u in p if u > 0] or p)[0]

    def _new_phase(self, phase):
        self.phase = phase
        self.picks = {}
        self.phase_id += 1

    def _ev(self, **kw):
        self.seq += 1
        self.last_event = {"seq": self.seq, **kw}

    # ------------------------------------------------------------------ draft
    def _value(self, pid, team, noise):
        r = ROSTER[pid]
        strong = sum(1 for p in team if ROSTER[p]["bowl"] >= 75)
        need = max(0, 2 - strong)
        left = TEAM - len(team)
        if need and need >= left:
            v = r["bowl"] * 1.0 + r["bat"] * 0.1
        else:
            v = r["bat"] * 0.55 + r["bowl"] * 0.45 + (r["bowl"] - 60) * 0.35 * (1 if need else 0.15)
            if not need:
                v += (r["bat"] - 60) * 0.2
        return v + (self.rng.uniform(-noise, noise) if noise else 0.0)

    def _best_pick(self, uid, noise=0.0):
        team = self.teams[uid]
        return max(self.pool, key=lambda pid: (self._value(pid, team, noise), pid))

    def _do_pick(self, uid, pid):
        self.pool.remove(pid)
        self.teams[uid].append(pid)
        self._ev(e="pick", uid=uid, pid=pid)
        if all(len(t) >= TEAM for t in self.teams.values()):
            self._start_match()
        else:
            self.phase_id += 1

    # ------------------------------------------------------------------ match flow
    def _batting_order(self, uid):
        return sorted(self.teams[uid], key=lambda p: (-ROSTER[p]["bat"], p))

    def _start_innings(self, bat, bowl, target=None):
        order = self._batting_order(bat)
        inn = {"bat": bat, "bowl": bowl, "runs": 0, "wkts": 0, "balls": 0, "extras": 0, "order": order, "next": 2,
               "striker": order[0], "non": order[1], "bat_st": {p: {"r": 0, "b": 0, "f": 0, "s": 0, "out": None} for p in order},
               "bowl_st": {p: {"b": 0, "r": 0, "w": 0, "o": 0} for p in self.teams[bowl]}, "bowler": None, "prev_bowler": None,
               "field": "balanced", "part": {"r": 0, "b": 0}, "fow": [], "over": [], "hist": [], "free_hit": False,
               "target": target, "done": False}
        self.inns.append(inn)
        self._new_phase("over")

    def _start_match(self):
        bat = self.bat_first
        self._start_innings(bat, self._other(bat))
        self._ev(e="toss", uid=bat)

    def _eligible_bowlers(self):
        inn = self.inn
        team = self.teams[inn["bowl"]]
        ok = [p for p in team if p != inn["prev_bowler"] and inn["bowl_st"][p]["o"] < MAX_PER_BOWLER]
        return ok or [p for p in team if p != inn["prev_bowler"]] or list(team)

    def _set_over(self, uid, pid, field):
        inn = self.inn
        if pid not in self._eligible_bowlers():
            raise GameError("That bowler cannot bowl this over")
        if field not in FIELDS:
            raise GameError("Pick a field: attacking, balanced or defensive")
        if field == "defensive" and len(inn["hist"]) < POWERPLAY:
            raise GameError("Powerplay: you cannot set a defensive field")
        inn["bowler"], inn["field"] = pid, field
        self._ev(e="over", uid=uid, pid=pid, field=field, over=len(inn["hist"]) + 1)
        self._new_phase("ball")

    # ------------------------------------------------------------------ actions
    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The match is over")
        if uid not in self.players:
            raise GameError("You are not playing")
        t = msg.get("t")
        if self.phase == "draft":
            if self._picker() != uid:
                raise GameError("Not your pick")
            if t == "quick":
                pid = self._best_pick(uid)
            elif t == "pick":
                pid = msg.get("id")
                if pid not in self.pool:
                    raise GameError("That player is not available")
            else:
                raise GameError("Pick a player for your squad")
            self._do_pick(uid, pid)
        elif self.phase == "over":
            if self.inn["bowl"] != uid:
                raise GameError("The fielding captain is choosing the bowler")
            if t == "quick":
                pid, field = self._ai_over(uid)
            elif t == "over":
                pid, field = msg.get("bowler"), msg.get("field", "balanced")
            else:
                raise GameError("Choose a bowler and a field")
            self._set_over(uid, pid, field)
        elif self.phase == "ball":
            if uid in self.picks:
                raise GameError("Already locked in, wait for your opponent")
            if t == "quick":
                self.picks[uid] = self._ai_ball(uid)
            elif t == "ball":
                self.picks[uid] = self._valid_pick(uid, msg)
            else:
                raise GameError("Pick your ball")
        else:
            raise GameError("Nothing to do right now")
        self._bots()

    def _valid_pick(self, uid, msg):
        inn = self.inn
        if uid == inn["bowl"]:
            d, line = msg.get("delivery"), msg.get("line")
            if d not in BOWL_SETS[ROSTER[inn["bowler"]]["type"]]:
                raise GameError("This bowler cannot bowl that delivery")
            if line not in LINES:
                raise GameError("Pick a line: off, middle or leg")
            return {"delivery": d, "line": line}
        shot, dr = msg.get("shot"), msg.get("dir", "straight")
        if shot not in SHOTS:
            raise GameError("Pick a shot")
        if dr not in DIRS:
            raise GameError("Pick a direction: off, straight or leg")
        if shot in ("defend", "leave"):
            dr = "straight"
        return {"shot": shot, "dir": dr}

    def auto_play(self):
        if self.finished:
            return
        if self.phase == "draft":
            u = self._picker()
            self._do_pick(u, self._best_pick(u, noise=3.0 if u < 0 else 0.0))
        elif self.phase == "over":
            u = self.inn["bowl"]
            self._set_over(u, *self._ai_over(u))
        elif self.phase == "ball":
            for u in self._pending():
                self.picks[u] = self._ai_ball(u)
        self._bots()

    def _bots(self):
        """Computer players act the moment it is their turn (their picks stay hidden until the ball resolves)."""
        guard = 0
        while not self.finished and guard < 200:
            guard += 1
            if self.phase == "draft":
                u = self._picker()
                if u < 0:
                    self._do_pick(u, self._best_pick(u, noise=3.0))
                    continue
            elif self.phase == "over":
                u = self.inn["bowl"]
                if u < 0:
                    self._set_over(u, *self._ai_over(u))
                    continue
            elif self.phase == "ball":
                for u in self._pending():
                    if u < 0:
                        self.picks[u] = self._ai_ball(u)
                if not self._pending():
                    self._resolve()
                    continue
            return

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished = True
        self.winner = self._other(uid)
        self.result_text = "Opponent left the match"
        self.phase = "done"
        self._ev(e="left", uid=uid)

    # ------------------------------------------------------------------ computer brain
    def _ai_over(self, uid):
        inn = self.inn
        pool = self._eligible_bowlers()
        w = [(ROSTER[p]["bowl"] / 50.0) ** 4 for p in pool]
        pid = self.rng.choices(pool, w)[0]
        over_no = len(inn["hist"])
        field = "balanced"
        if over_no < POWERPLAY:
            field = "attack" if self.rng.random() < 0.6 else "balanced"
        elif inn["target"] is not None:
            need = inn["target"] - inn["runs"]
            left = OVERS * BALLS - inn["balls"]
            field = "defensive" if need > left * 1.6 else ("attack" if need <= left * 0.9 else "balanced")
        elif self.rng.random() < 0.3:
            field = "attack"
        return pid, field

    def _ai_ball(self, uid):
        inn = self.inn
        if uid == inn["bowl"]:
            b = ROSTER[inn["bowler"]]
            bat = ROSTER[inn["striker"]]
            opts = BOWL_SETS[b["type"]]
            aggr = bat["style"] == "aggressive"
            wt = {"yorker": 3.0 if aggr else 2.0, "bouncer": 2.0 if aggr else 3.0, "length": 1.5 if aggr else 2.0, "slower": 3.0 if aggr else 2.0,
                  "inswing": 2.5, "outswing": 2.0, "offbreak": 2.0, "legbreak": 2.0, "googly": 2.5, "flighted": 3.0 if aggr else 1.5}
            d = self.rng.choices(opts, [wt[o] for o in opts])[0]
            return {"delivery": d, "line": self.rng.choices(LINES, [.35, .40, .25])[0]}
        bat = ROSTER[inn["striker"]]
        a = 0.45 + (0.22 if bat["style"] == "aggressive" else -0.12)
        left = OVERS * BALLS - inn["balls"]
        if inn["target"] is not None:
            need = inn["target"] - inn["runs"]
            a += max(-0.2, min(0.4, (need / max(1, left) * BALLS - 9) * 0.07))
        if len(inn["hist"]) >= OVERS - 1:
            a += 0.1
        a -= 0.07 * max(0, inn["wkts"] - 1)
        a = max(0.1, min(0.95, a))
        spin = ROSTER[inn["bowler"]]["type"] == "spin"
        wts = {"defend": (1 - a) * 3.0, "drive": 2.2, "cut": 1.2, "pull": 1.0 + a, "loft": 2.6 * a, "sweep": 1.4 if spin else 0.25,
               "leave": 0.25 * (1 - a)}
        shot = self.rng.choices(SHOTS, [wts[s] for s in SHOTS])[0]
        if shot in ("defend", "leave"):
            return {"shot": shot, "dir": "straight"}
        nat = NATURAL.get(shot)
        if nat:
            probs = {"off": [.6, .3, .1], "leg": [.1, .3, .6]}[nat]
        else:
            probs = [.34, .4, .26]
        return {"shot": shot, "dir": self.rng.choices(DIRS, probs)[0]}

    # ------------------------------------------------------------------ ball resolution
    def _quality(self, shot, delivery, line, dr, bat, bowl, faced):
        q = SUIT[delivery][shot]
        if shot not in ("defend", "leave"):
            q += LINE_FIT[line][dr]
            nat = NATURAL.get(shot)
            if nat and dr != nat and dr != "straight":
                q -= 0.35
        q += max(-0.9, min(0.9, (bat["bat"] - bowl["bowl"]) / 80.0))
        if bat["style"] == "aggressive":
            q += 0.12 if shot in ("loft", "pull", "cut", "sweep") else -0.1
        else:
            q += 0.12 if shot in ("defend", "drive") else -0.1 * (shot == "loft")
        q += min(0.3, 0.06 * faced)
        return max(-1.8, min(1.8, q))

    def _weights(self, shot, q, field, over_no, free_hit):
        w = {}
        fm = FIELD_MUL[field]
        for o in OUTCOMES:
            v = BASE[shot][o] * math.exp(KQ[o] * q) * fm.get(o, 1.0)
            if over_no < POWERPLAY and o in (4, 6):
                v *= 1.15
            if over_no == OVERS - 1 and o in (6, "W"):
                v *= 1.1
            w[o] = v
        if free_hit:
            w["W"] = 0.0
        return w

    def _sample(self, w):
        tot = sum(w.values())
        x = self.rng.random() * tot
        for o in OUTCOMES:
            x -= w[o]
            if x < 0:
                return o
        return 0

    def _wicket_kind(self, shot, delivery, line, dr, field):
        spin = delivery in BOWL_SETS["spin"]
        w = {"bowled": 1.0, "lbw": 0.4, "caught": 1.5, "stumped": 0.0}
        if delivery == "yorker":
            w["bowled"] *= 2.5
            w["lbw"] *= 1.4
        if delivery in ("inswing", "outswing"):
            w["bowled"] *= 1.5
        if shot == "leave":
            w["bowled"] *= 4
            w["caught"] *= .05
        if shot == "defend":
            w["bowled"] *= 1.5
            w["caught"] *= .3
        if shot in ("loft", "pull"):
            w["caught"] *= 3.0 if shot == "loft" else 2.2
            w["lbw"] *= .2
        if shot in ("cut", "drive"):
            w["caught"] *= 1.5
        if shot == "sweep":
            w["lbw"] *= 2.5
        if line != "off" and dr != line and shot not in ("leave",):
            w["lbw"] *= 1.8
        if spin:
            w["lbw"] *= 1.6
            if shot in ("drive", "loft", "sweep"):
                w["stumped"] = 0.7
        if delivery == "bouncer":
            w["caught"] *= 1.4
        if field == "attack":
            w["caught"] *= 1.3
        kinds = list(w)
        return self.rng.choices(kinds, [w[k] for k in kinds])[0]

    def _geometry(self, shot, dr, outcome, kind):
        """Where the ball goes (for the renderer): angle in degrees (0 = straight, + = off side), distance (1 = rope), airborne."""
        base = {"off": 38, "straight": 0, "leg": -38}[dr]
        shift = {"cut": 42, "pull": -42, "sweep": -50}.get(shot, 0)
        ang = base + shift + self.rng.uniform(-14, 14)
        if shot in ("defend", "leave"):
            ang = self.rng.uniform(-25, 25)
        if outcome == 6:
            dist, air = self.rng.uniform(1.12, 1.3), True
        elif outcome == 4:
            dist, air = 1.0, shot in ("loft",) and self.rng.random() < 0.4
        elif outcome == 3:
            dist, air = self.rng.uniform(.72, .85), False
        elif outcome == 2:
            dist, air = self.rng.uniform(.5, .66), False
        elif outcome == 1:
            dist, air = self.rng.uniform(.28, .48), False
        elif outcome == "W":
            if kind == "caught":
                dist, air = self.rng.uniform(.35, .85), True
            elif kind == "runout":
                dist, air = self.rng.uniform(.3, .55), False
            else:
                dist, air = self.rng.uniform(0.0, .12), False
        else:
            dist, air = self.rng.uniform(.04, .2), False
        return round(max(-135, min(135, ang)), 1), round(dist, 2), air

    def _resolve(self):
        inn = self.inn
        bp, tp = self.picks[inn["bowl"]], self.picks[inn["bat"]]
        bowl, bat = ROSTER[inn["bowler"]], ROSTER[inn["striker"]]
        delivery, line, shot, dr = bp["delivery"], bp["line"], tp["shot"], tp["dir"]
        over_no = len(inn["hist"])
        facing = inn["striker"]
        st = inn["bat_st"][facing]
        free_hit = inn["free_hit"]
        extra, wicket, runs, bat_runs, outcome = None, None, 0, 0, 0
        contact = "pushed"
        wide_p = WIDE_P * (1.6 if bowl["bowl"] < 45 else 1.0) * (1.4 if delivery in ("bouncer", "googly") else 1.0)
        nb_p = NOBALL_P if bowl["type"] != "spin" else 0.004
        r = self.rng.random()
        if r < wide_p:
            extra, runs, outcome = "wide", 1, "Wd"
            ang, dist, air, kind = self.rng.uniform(-70, 70), 0.0, False, None
            contact = "wide"
        else:
            noball = r < wide_p + nb_p
            q = self._quality(shot, delivery, line, dr, bat, bowl, st["b"])
            w = self._weights(shot, q, inn["field"], over_no, free_hit or noball)
            outcome = self._sample(w)
            kind = None
            if outcome in (1, 2) and self.rng.random() < {"attack": .04, "balanced": .028, "defensive": .016}[inn["field"]]:
                outcome, kind = "W", "runout"
            elif outcome == "W":
                kind = self._wicket_kind(shot, delivery, line, dr, inn["field"])
            ang, dist, air = self._geometry(shot, dr, outcome, kind)
            if outcome == "W":
                bat_runs = 1 if kind == "runout" and self.rng.random() < .35 else 0
                wicket = {"kind": kind}
                contact = {"bowled": "beaten", "lbw": "beaten", "stumped": "beaten", "caught": "edged", "runout": "pushed"}[kind]
            else:
                bat_runs = outcome
                contact = ("middled" if outcome == 6 else "timed" if outcome in (3, 4) or (outcome == 2 and q > .3) else
                           "pushed" if outcome in (1, 2, 0) and q > -.2 else "mistimed")
            runs = bat_runs
            if noball:
                extra, runs = "noball", bat_runs + 1
        legal = extra is None
        # --- apply to the scoreboard
        inn["runs"] += runs
        inn["extras"] += (1 if extra else 0)
        inn["part"]["r"] += runs
        bs = inn["bowl_st"][inn["bowler"]]
        bs["r"] += runs
        if extra != "wide":
            st["b"] += 1
            inn["part"]["b"] += 1
        st["r"] += bat_runs
        if bat_runs == 4:
            st["f"] += 1
        if bat_runs == 6:
            st["s"] += 1
        if extra != "wide":                  # a wide does not use up the free hit
            inn["free_hit"] = extra == "noball"
        label = {"Wd": "Wd"}.get(outcome, str(outcome))
        if extra == "noball":
            label = "Nb" + (str(bat_runs) if bat_runs else "")
        crossed = bat_runs % 2 == 1 and not wicket
        new_batter = None
        if legal:
            inn["balls"] += 1
            bs["b"] += 1
        if wicket:
            inn["wkts"] += 1
            kind = wicket["kind"]
            out_pid = inn["striker"]
            if kind == "runout" and self.rng.random() < 0.4:
                out_pid = inn["non"]
            wicket["who"] = out_pid
            fielders = [p for p in self.teams[inn["bowl"]] if p != inn["bowler"]]
            fld = self.rng.choice(fielders) if fielders else inn["bowler"]
            bn = ROSTER[inn["bowler"]]["short"]
            if kind == "caught":
                wicket["fielder"] = fld if self.rng.random() > 0.2 else inn["bowler"]
                txt = f"c & b {bn}" if wicket["fielder"] == inn["bowler"] else f"c {ROSTER[wicket['fielder']]['short']} b {bn}"
            elif kind == "runout":
                wicket["fielder"] = fld
                txt = f"run out ({ROSTER[fld]['short']})"
            else:
                txt = {"bowled": f"b {bn}", "lbw": f"lbw b {bn}", "stumped": f"st b {bn}"}[kind]
            inn["bat_st"][out_pid]["out"] = txt
            if kind != "runout":
                bs["w"] += 1
            inn["fow"].append({"runs": inn["runs"], "wk": inn["wkts"], "pid": out_pid, "over": overs_txt(inn["balls"])})
            inn["part"] = {"r": 0, "b": 0}
            label = "W"
            if inn["wkts"] < TEAM - 1:
                new_batter = inn["order"][inn["next"]]
                inn["next"] += 1
                if out_pid == inn["striker"]:
                    inn["striker"] = new_batter
                else:
                    inn["non"] = new_batter
        elif crossed:
            inn["striker"], inn["non"] = inn["non"], inn["striker"]
        inn["over"].append(label)
        # --- milestones
        ms = None
        if not wicket and bat_runs:
            for m in (30, 20, 10):
                if st["r"] - bat_runs < m <= st["r"]:
                    ms = m
                    break
        end_over = legal and inn["balls"] % BALLS == 0
        if end_over:
            inn["striker"], inn["non"] = inn["non"], inn["striker"]
            bs["o"] += 1
            inn["prev_bowler"] = inn["bowler"]
            inn["hist"].append(list(inn["over"]))
            inn["over"] = []
        # --- end of innings / match?
        chase_done = inn["target"] is not None and inn["runs"] >= inn["target"]
        all_out = inn["wkts"] >= TEAM - 1
        overs_done = inn["balls"] >= OVERS * BALLS
        end_inn = chase_done or all_out or overs_done
        self.seq += 1
        self.last_ball = {
            "seq": self.seq, "inn": len(self.inns), "over": len(inn["hist"]) + (0 if end_over else 1), "n": inn["balls"],
            "bat_uid": inn["bat"], "bowler": inn["bowler"], "batter": facing, "bowl_uid": inn["bowl"],
            "delivery": delivery, "line": line, "shot": shot, "dir": dr, "label": label, "runs": runs, "bat_runs": bat_runs,
            "extra": extra, "wicket": wicket, "contact": contact, "ang": ang, "dist": dist, "air": air, "free_hit": free_hit,
            "end_over": end_over, "end_innings": end_inn, "field": inn["field"], "pp": over_no < POWERPLAY, "milestone": ms,
            "new_batter": new_batter,
        }
        self.picks = {}
        if end_inn:
            inn["done"] = True
            self._after_innings()
        elif end_over:
            inn["bowler"] = None
            self._new_phase("over")
        else:
            self._new_phase("ball")
        return self.last_ball

    # ------------------------------------------------------------------ end of innings / match
    def _after_innings(self):
        inn = self.inn
        if len(self.inns) == 1:
            self._start_innings(inn["bowl"], inn["bat"], target=inn["runs"] + 1)
            self._ev(e="break", target=inn["runs"] + 1)
            return
        first = self.inns[0]
        self.finished = True
        self.phase = "done"
        self.picks = {}
        if inn["runs"] >= inn["target"]:
            self.winner = inn["bat"]
            left = TEAM - 1 - inn["wkts"]
            self.result_text = f"won by {left} wicket{'s' if left != 1 else ''}"
        elif inn["runs"] == first["runs"]:
            self.draw = True
            self.result_text = "Match tied"
        else:
            self.winner = first["bat"]
            d = first["runs"] - inn["runs"]
            self.result_text = f"won by {d} run{'s' if d != 1 else ''}"
        self._ev(e="end", winner=self.winner, draw=self.draw, text=self.result_text)

    # ------------------------------------------------------------------ state
    @staticmethod
    def _inn_view(inn):
        d = {k: inn[k] for k in ("bat", "bowl", "runs", "wkts", "balls", "extras", "order", "striker", "non", "bowler", "field",
                                 "part", "fow", "over", "hist", "free_hit", "target", "done")}
        d["bat_st"] = {p: dict(v) for p, v in inn["bat_st"].items()}
        d["bowl_st"] = {p: dict(v) for p, v in inn["bowl_st"].items()}
        total = OVERS * BALLS
        d["rr"] = round(inn["runs"] * BALLS / inn["balls"], 2) if inn["balls"] else 0.0
        d["balls_left"] = total - inn["balls"]
        if inn["target"] is not None:
            d["need"] = max(0, inn["target"] - inn["runs"])
            d["rrr"] = round(d["need"] * BALLS / d["balls_left"], 2) if d["balls_left"] else 0.0
        return d

    def public_state(self):
        inn = self.inn
        st = {
            "kind": "cricket", "phase": self.phase, "phase_id": self.phase_id, "phase_seconds": self.phase_seconds,
            "overs": OVERS, "balls_per_over": BALLS, "team_size": TEAM, "powerplay": POWERPLAY, "max_per_bowler": MAX_PER_BOWLER,
            "players": [{"uid": u, "squad": [ROSTER[p] for p in self.teams[u]]} for u in self.players],
            "picker": self._picker(), "bat_first": self.bat_first, "turn": self.current(),
            "pending": self._pending(), "picked": {u: u in self.picks for u in self.players},
            "innings": [self._inn_view(i) for i in self.inns], "inn_no": len(self.inns),
            "last_ball": self.last_ball, "last_event": self.last_event, "winner": self.winner, "draw": self.draw,
            "result_text": self.result_text, "seq": self.seq,
        }
        if self.phase == "draft":
            st["pool"] = [ROSTER[p] for p in self.pool]
        if inn and self.phase in ("over", "ball"):
            st["pp"] = len(inn["hist"]) < POWERPLAY
            st["over_no"] = len(inn["hist"]) + 1
            if self.phase == "over":
                st["eligible"] = self._eligible_bowlers()
            if inn["bowler"]:
                st["bowl_set"] = BOWL_SETS[ROSTER[inn["bowler"]]["type"]]
        return st

    def view(self, uid):
        s = self.public_state()
        if self.phase == "ball" and uid in self.picks:
            s["my_pick"] = dict(self.picks[uid])
        return s

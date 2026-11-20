"""Mafia (4-10 players). Night: mafia kill, doctor saves, detective investigates (simultaneous).
Day: announcement + discussion (room chat), then a vote. Roles are hidden per viewer via view().

Phases are timed by the room through `phase_id` / `phase_seconds`; when the timer fires auto_play()
resolves every pending action of the phase. Computer players (negative uids) act instantly at phase start.
"""
from __future__ import annotations

import random

from .base import BaseGame, GameError

NIGHT_S, DAY_S, VOTE_S, QUICK_S, BOT_ONLY_S = 25, 40, 25, 6, 3


def role_counts(n: int) -> dict:
    mafia = {4: 1, 5: 1, 6: 2, 7: 2, 8: 2, 9: 3, 10: 3}.get(n, 1)
    doctor = 1
    detective = 1 if n >= 5 else 0
    return {"mafia": mafia, "doctor": doctor, "detective": detective, "villager": n - mafia - doctor - detective}


def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


class MafiaGame(BaseGame):
    name = "mafia"
    min_players = 4
    max_players = 10
    ticker = True  # phases are timed; timeouts must not count as AFK strikes

    def __init__(self, players, rng=None):
        if not 4 <= len(players) <= 10:
            raise ValueError("Mafia needs 4-10 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        cnt = role_counts(len(players))
        pool = [r for r, c in cnt.items() for _ in range(c)]
        self.rng.shuffle(pool)
        self.roles = dict(zip(self.players, pool))
        self.alive = set(self.players)
        self.dead_info = {}        # uid -> "killed" | "voted" | "left"
        self.left = set()
        self.day = 0
        self.phase = "night"
        self.phase_id = 0
        self.phase_seconds = NIGHT_S
        self.kill_picks, self.save_pick, self.skips, self.votes = {}, None, set(), {}
        self.last_saved = None
        self.probes = {}           # detective uid -> [{"target", "team"}]
        self.night_humans = False
        self.seq = 0
        self.last_event = None
        self.log = []
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self.win_team = None
        self._event("start")
        self._start_night()

    # ---------------- helpers ----------------
    def _is_bot(self, uid):
        return uid < 0

    def _team(self, uid):
        return "mafia" if self.roles[uid] == "mafia" else "town"

    def _alive_list(self):
        return [u for u in self.players if u in self.alive]

    def _event(self, kind, **kw):
        self.seq += 1
        self.last_event = {"seq": self.seq, "kind": kind, "day": self.day, **kw}
        self.log = (self.log + [self.last_event])[-30:]

    def _secs(self, base):
        return base if any(not self._is_bot(u) for u in self.alive) else BOT_ONLY_S

    def _night_actors(self):
        return [u for u in self._alive_list() if self.roles[u] in ("mafia", "doctor", "detective")]

    def _acted(self, u):
        r = self.roles[u]
        if r == "mafia":
            return u in self.kill_picks
        if r == "doctor":
            return self.save_pick is not None
        if r == "detective":
            return len(self.probes.get(u, [])) >= self.day
        return True

    def _pending(self):
        if self.phase == "night":
            return [u for u in self._night_actors() if not self._acted(u)]
        if self.phase == "day":
            return [u for u in self._alive_list() if u not in self.skips]
        if self.phase == "vote":
            return [u for u in self._alive_list() if u not in self.votes]
        return []

    def current(self):
        if self.finished:
            return None
        pend = [u for u in self._pending() if not self._is_bot(u)]
        if pend:
            return pend[0]
        humans = [u for u in self.players if not self._is_bot(u)]
        alive_h = [u for u in humans if u in self.alive]
        return (alive_h or humans or self.players)[0]

    # ---------------- phases ----------------
    def _new_phase(self, phase, seconds):
        self.phase = phase
        self.phase_id += 1
        self.phase_seconds = self._secs(seconds)

    def _start_night(self):
        self.day += 1
        self.kill_picks, self.save_pick = {}, None
        self._new_phase("night", NIGHT_S)
        alive = self._alive_list()
        town = [u for u in alive if self.roles[u] != "mafia"]
        bot_target = self.rng.choice(town) if town else None
        for u in self._night_actors():
            if not self._is_bot(u):
                continue
            r = self.roles[u]
            if r == "mafia" and bot_target is not None:
                self.kill_picks[u] = bot_target
            elif r == "doctor":
                self.save_pick = self.rng.choice([x for x in alive if x != self.last_saved] or alive)
            elif r == "detective":
                seen = {p["target"] for p in self.probes.get(u, [])}
                opts = [x for x in alive if x != u and x not in seen]
                if opts:
                    self._probe(u, self.rng.choice(opts))
                else:
                    self.probes.setdefault(u, []).append({"target": 0, "team": None})
        self.night_humans = any(not self._is_bot(u) for u in self._night_actors())
        if not self.night_humans:
            self.phase_seconds = self._secs(QUICK_S)
        elif not self._pending():
            self._resolve_night()

    def _probe(self, u, target):
        self.probes.setdefault(u, []).append({"target": target, "team": self._team(target)})

    def _resolve_night(self):
        alive = self._alive_list()
        town = [u for u in alive if self.roles[u] != "mafia"]
        # fill anything missing (timeouts)
        mafia_alive = [u for u in alive if self.roles[u] == "mafia"]
        for u in mafia_alive:
            if u not in self.kill_picks and town:
                self.kill_picks[u] = self.rng.choice(town)
        if self.save_pick is None and any(self.roles[u] == "doctor" for u in alive):
            self.save_pick = self.rng.choice([x for x in alive if x != self.last_saved] or alive)
        for u in alive:
            if self.roles[u] == "detective" and not self._acted(u):
                seen = {p["target"] for p in self.probes.get(u, [])}
                opts = [x for x in alive if x != u and x not in seen]
                if opts:
                    self._probe(u, self.rng.choice(opts))
                else:
                    self.probes.setdefault(u, []).append({"target": 0, "team": None})
        target = None
        picks = [t for u, t in self.kill_picks.items() if u in self.alive and t in self.alive]
        if picks:
            top = max(picks.count(t) for t in set(picks))
            target = self.rng.choice(sorted(t for t in set(picks) if picks.count(t) == top))
        saved = target is not None and target == self.save_pick
        self.last_saved = self.save_pick
        killed = None
        if target is not None and not saved:
            killed = target
            self.alive.discard(killed)
            self.dead_info[killed] = "killed"
        self._event("dawn", killed=killed, role=self.roles[killed] if killed else None, saved=bool(saved))
        if self._check_win():
            return
        self._start_day()

    def _start_day(self):
        self.skips = set()
        for u in self._alive_list():
            if self._is_bot(u):
                self.skips.add(u)
        self._new_phase("day", DAY_S)
        if not self._pending():
            self._start_vote()

    def _start_vote(self):
        self.votes = {}
        self._new_phase("vote", VOTE_S)
        alive = self._alive_list()
        town = [u for u in alive if self.roles[u] != "mafia"]
        for u in alive:
            if not self._is_bot(u):
                continue
            pool = town if self.roles[u] == "mafia" else [x for x in alive if x != u]
            pool = [x for x in pool if x != u]
            self.votes[u] = self.rng.choice(pool) if pool else 0
        self._maybe_resolve_vote()

    def _maybe_resolve_vote(self):
        if self.phase == "vote" and not self._pending():
            self._resolve_vote()

    def _resolve_vote(self):
        tally = {}
        for v in self.votes.values():
            tally[v] = tally.get(v, 0) + 1
        out = None
        if tally:
            top = max(tally.values())
            leaders = [t for t, c in tally.items() if c == top]
            if len(leaders) == 1 and leaders[0] != 0:
                out = leaders[0]
        if out is not None:
            self.alive.discard(out)
            self.dead_info[out] = "voted"
        self._event("vote", eliminated=out, role=self.roles[out] if out else None,
                    tally={str(k): v for k, v in tally.items()}, votes={str(k): v for k, v in self.votes.items()})
        if self._check_win():
            return
        self._start_night()

    def _check_win(self):
        m = sum(1 for u in self.alive if self.roles[u] == "mafia")
        t = len(self.alive) - m
        team = "town" if m == 0 else ("mafia" if m >= t else None)
        if team is None:
            return False
        self.finished, self.phase, self.win_team = True, "over", team
        self.winners = [u for u in self.players if self._team(u) == team and u not in self.left]
        self.winner = next((u for u in self.winners if u > 0), None)
        self._event("over", team=team)
        return True

    # ---------------- actions ----------------
    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid not in self.players:
            raise GameError("You are not in this game")
        if uid not in self.alive:
            raise GameError("You are out of the game")
        t = msg.get("t")
        role = self.roles[uid]
        if t in ("kill", "save", "probe"):
            if self.phase != "night":
                raise GameError("It's not night")
            need = {"kill": "mafia", "save": "doctor", "probe": "detective"}[t]
            if role != need:
                raise GameError("That's not your role")
            tg = _int(msg.get("target"))
            if tg is None or tg not in self.alive:
                raise GameError("Pick a living player")
            if t == "kill":
                if self.roles[tg] == "mafia":
                    raise GameError("You can't target your own team")
                self.kill_picks[uid] = tg
            elif t == "save":
                if tg == self.last_saved and self.last_saved is not None:
                    raise GameError("You can't protect the same player two nights in a row")
                self.save_pick = tg
            else:
                if self._acted(uid):
                    raise GameError("You already investigated tonight")
                if tg == uid:
                    raise GameError("Investigate someone else")
                self._probe(uid, tg)
            if self.night_humans and not self._pending():
                self._resolve_night()
        elif t == "skip":
            if self.phase != "day":
                raise GameError("Nothing to skip")
            self.skips.add(uid)
            if not self._pending():
                self._start_vote()
        elif t == "vote":
            if self.phase != "vote":
                raise GameError("It's not voting time")
            tg = _int(msg.get("target"))
            if tg is None or (tg != 0 and (tg not in self.alive or tg == uid)):
                raise GameError("Pick a living player (not yourself) or skip")
            self.votes[uid] = tg
            self._maybe_resolve_vote()
        else:
            raise GameError("Unknown action")

    def auto_play(self):
        if self.finished:
            return
        if self.phase == "night":
            self._resolve_night()
        elif self.phase == "day":
            self._start_vote()
        elif self.phase == "vote":
            for u in self._alive_list():
                self.votes.setdefault(u, 0)
            self._resolve_vote()

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.left.add(uid)
        if uid not in self.alive:
            return
        self.alive.discard(uid)
        self.dead_info[uid] = "left"
        self.kill_picks.pop(uid, None)
        self.votes.pop(uid, None)
        self.skips.discard(uid)
        self._event("left", uid=uid, role=self.roles[uid])
        if self._check_win():
            return
        if self.phase == "night" and self.night_humans and not self._pending():
            self._resolve_night()
        elif self.phase == "day" and not self._pending():
            self._start_vote()
        elif self.phase == "vote":
            self._maybe_resolve_vote()

    # ---------------- state ----------------
    def public_state(self):
        reveal = self.finished
        return {
            "kind": "mafia",
            "players": [{"uid": u, "alive": u in self.alive, "left": u in self.left,
                         "role": self.roles[u] if (reveal or u not in self.alive) else None,
                         "out": self.dead_info.get(u)} for u in self.players],
            "phase": self.phase, "day": self.day, "turn": None, "seq": self.seq,  # never expose who is still to act
            "last_event": self.last_event, "log": self.log,
            "votes": {str(k): v for k, v in self.votes.items()} if self.phase == "vote" else {},
            "skipped": len(self.skips) if self.phase == "day" else 0,
            "counts": role_counts(len(self.players)),
            "winner": self.winner, "winners": self.winners, "win_team": self.win_team, "draw": False,
        }

    def view(self, uid):
        st = self.public_state()
        me = None
        if uid in self.players:
            role = self.roles[uid]
            alive = uid in self.alive
            me = {"role": role, "alive": alive, "team_known": role == "mafia",
                  "mates": [u for u in self.players if self.roles[u] == "mafia"] if role == "mafia" else [],
                  "pending": alive and uid in self._pending() and self.phase != "day",
                  "vote": self.votes.get(uid), "skipped": uid in self.skips,
                  "probes": self.probes.get(uid, []) if role == "detective" else [],
                  "can_save_not": self.last_saved if role == "doctor" else None}
            if self.phase == "night" and alive:
                if role == "mafia":
                    me["picks"] = {str(k): v for k, v in self.kill_picks.items()}
                    me["pick"] = self.kill_picks.get(uid)
                elif role == "doctor":
                    me["pick"] = self.save_pick
                elif role == "detective":
                    me["pick"] = (self.probes.get(uid) or [{}])[-1].get("target") if self._acted(uid) else None
            if role == "mafia":
                for p in st["players"]:
                    if p["uid"] in me["mates"]:
                        p["role"] = "mafia"
        st["me"] = me
        return st

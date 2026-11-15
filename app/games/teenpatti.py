"""Teen Patti (Indian 3-card poker). 2-6 players, 1000 in-game chips each, up to 5 rounds.
Boot ante, blind/seen play, chaal (optionally raising the stake), pack, show. Hands are hidden per viewer."""
from __future__ import annotations

from .base import GameError
from .cards_common import RANKS, RVAL, CardGame, deck52, rank_of, suit_of

START_STACK = 1000
BOOT = 20
MAX_STAKE = BOOT * 4
ROUNDS = 5
MAX_ACTIONS = 36  # per round; after that the remaining players are forced to a showdown
CAT_NAMES = {6: "Trail", 5: "Pure sequence", 4: "Sequence", 3: "Colour", 2: "Pair", 1: "High card"}


def seq_top(vals):
    """Top value of a 3-card run (A-K-Q=15 > A-2-3=14 > K-Q-J=13 ... 4-3-2=4) or None."""
    v = sorted(vals)
    if v == [2, 3, 14]:
        return 14
    if v[2] - v[1] == 1 and v[1] - v[0] == 1:
        return 15 if v == [12, 13, 14] else v[2]
    return None


def hand_rank(cards):
    """Comparable tuple, bigger is better."""
    vals = sorted((RVAL[rank_of(c)] for c in cards), reverse=True)
    flush = len({suit_of(c) for c in cards}) == 1
    top = seq_top(vals)
    if vals[0] == vals[2]:
        return (6, vals[0])
    if top and flush:
        return (5, top)
    if top:
        return (4, top)
    if flush:
        return (3, *vals)
    if vals[0] == vals[1] or vals[1] == vals[2]:
        pair = vals[1]
        kick = vals[2] if vals[0] == vals[1] else vals[0]
        return (2, pair, kick)
    return (1, *vals)


class TeenPattiGame(CardGame):
    name = "teenpatti"
    min_players = 2
    max_players = 6

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 6:
            raise ValueError("Teen Patti needs 2-6 players")
        self._init_common(players, rng)
        self.stack = {u: START_STACK for u in self.players}
        self.hands, self.seen, self.packed, self.put = {}, {}, {}, {}
        self.pot = 0
        self.stake = BOOT
        self.round = 0
        self.dealer = -1
        self.idx = 0
        self.actions = 0
        self.log, self.event, self.last_round = [], None, None
        self._start_round()

    # ------------------------------------------------------------ flow
    def current(self):
        return None if self.finished else self.players[self.idx]

    def _active(self):
        return [u for u in self.players if u in self.hands and not self.packed.get(u)]

    def _start_round(self):
        able = [u for u in self.players if self.stack[u] >= BOOT]
        if self.round >= ROUNDS or len(able) < 2:
            self._decide(dict(self.stack))
            return
        self.round += 1
        self.dealer = (self.dealer + 1) % len(self.players)
        while self.stack[self.players[self.dealer]] < BOOT:
            self.dealer = (self.dealer + 1) % len(self.players)
        deck = deck52()
        self.rng.shuffle(deck)
        self.hands = {u: [deck.pop() for _ in range(3)] for u in able}
        self.seen = {u: False for u in able}
        self.packed = {u: False for u in able}
        self.put = {u: BOOT for u in able}
        for u in able:
            self.stack[u] -= BOOT
        self.pot = BOOT * len(able)
        self.stake = BOOT
        self.actions = 0
        self.idx = self.dealer
        self._next_idx()
        self._ev(kind="deal", round=self.round, players=able, pot=self.pot)

    def _next_idx(self):
        n = len(self.players)
        for _ in range(n):
            self.idx = (self.idx + 1) % n
            u = self.players[self.idx]
            if u in self.hands and not self.packed.get(u):
                return

    def _cost(self, uid, raise_=False):
        stake = min(self.stake * 2, MAX_STAKE) if raise_ else self.stake
        return stake, stake * (2 if self.seen[uid] else 1)

    def _pay(self, uid, amount):
        amount = min(amount, self.stack[uid])
        self.stack[uid] -= amount
        self.put[uid] += amount
        self.pot += amount
        return amount

    def _end_round(self, winners, reason, reveal):
        share = self.pot // len(winners)
        for w in winners:
            self.stack[w] += share
        self.stack[winners[0]] += self.pot - share * len(winners)
        hands = {u: list(self.hands[u]) for u in reveal}
        ranks = {u: CAT_NAMES[hand_rank(self.hands[u])[0]] for u in reveal}
        self.last_round = {"seq": self._bump(), "round": self.round, "winners": winners, "pot": self.pot,
                           "reason": reason, "hands": hands, "ranks": ranks}
        self._ev(kind="round_end", winners=winners, pot=self.pot, reason=reason)
        self.hands, self.packed, self.seen = {}, {}, {}
        self.pot = 0
        self._start_round()

    def _showdown(self, asker=None, reason="show"):
        act = self._active()
        ranks = {u: hand_rank(self.hands[u]) for u in act}
        top = max(ranks.values())
        win = [u for u in act if ranks[u] == top]
        if len(win) > 1 and asker in win:  # a tie goes against the player who asked for the show
            win = [u for u in win if u != asker] or win
        self._end_round(win, reason, act)

    # ------------------------------------------------------------ actions
    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        t = msg.get("t")
        if uid not in self.hands or self.packed.get(uid):
            raise GameError("You are not in this hand")
        if t == "see":
            if self.seen[uid]:
                raise GameError("You already looked at your cards")
            self.seen[uid] = True
            self._ev(kind="see", uid=uid)
            return
        if uid != self.current():
            raise GameError("It's not your turn")
        act = self._active()
        if t == "pack":
            self.packed[uid] = True
            self._ev(kind="pack", uid=uid)
            rest = self._active()
            if len(rest) == 1:
                return self._end_round(rest, "last", [])
            self._after_action()
        elif t == "chaal":
            rs = bool(msg.get("raise")) if "raise" in msg else False
            if "raise" in msg and not isinstance(msg["raise"], bool):
                raise GameError("Bad value")
            stake, cost = self._cost(uid, rs)
            if cost > self.stack[uid]:
                raise GameError("Not enough chips: pack or show")
            self.stake = stake
            self._pay(uid, cost)
            self._ev(kind="raise" if rs and stake > 0 and cost else "chaal", uid=uid, amount=cost, stake=self.stake,
                     blind=not self.seen[uid])
            self._after_action()
        elif t == "show":
            if len(act) != 2:
                raise GameError("You can only ask for a show when two players are left")
            _, cost = self._cost(uid)
            paid = self._pay(uid, cost)
            self._ev(kind="show", uid=uid, amount=paid)
            self._showdown(asker=uid)
        else:
            raise GameError("Unknown action")

    def _after_action(self):
        self.actions += 1
        if self.actions >= MAX_ACTIONS:
            return self._showdown(reason="forced")
        self._next_idx()

    def auto_play(self):
        if self.finished:
            return
        uid = self.current()
        rank = hand_rank(self.hands[uid])
        _, cost = self._cost(uid)
        act = self._active()
        can = cost <= self.stack[uid]
        strong = rank[0] >= 2 or rank[1] >= 12 or (not self.seen[uid] and self.rng.random() < 0.75)
        if len(act) == 2 and (rank[0] >= 2 or not can):
            return self.handle(uid, {"t": "show"})
        if not can:
            return self.handle(uid, {"t": "pack"})
        if not strong and self.rng.random() < 0.7:
            return self.handle(uid, {"t": "pack"})
        if rank[0] >= 4 and self.stake < MAX_STAKE and self.stack[uid] >= self._cost(uid, True)[1] and self.rng.random() < 0.5:
            return self.handle(uid, {"t": "chaal", "raise": True})
        self.handle(uid, {"t": "chaal"})

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        cur = self.current() == uid
        if uid in self.hands and not self.packed.get(uid):
            self.packed[uid] = True
            rest = self._active()
            if len(rest) == 1:
                self.stack[uid] = 0
                self._end_round(rest, "last", [])
                cur = False
            elif cur:
                self._next_idx()
        self.stack[uid] = 0
        if self.players.count(uid) and not self.finished:
            able = [u for u in self.players if self.stack[u] >= BOOT]
            if len(able) < 2 and not self.hands:
                self._decide(dict(self.stack))

    # ------------------------------------------------------------ views
    def _view(self, uid):
        mine = uid in self.hands and not self.packed.get(uid)
        cost = raise_cost = None
        if mine and uid == self.current() and not self.finished:
            cost = self._cost(uid)[1]
            raise_cost = self._cost(uid, True)[1]
        rows = []
        for u in self.players:
            if u in self.hands:
                st = "packed" if self.packed[u] else ("seen" if self.seen[u] else "blind")
            else:
                st = "out" if self.stack[u] < BOOT else "wait"
            rows.append({"uid": u, "stack": self.stack[u], "put": self.put.get(u, 0), "state": st, "n": 3 if u in self.hands else 0})
        hand = list(self.hands[uid]) if (uid in self.hands and self.seen.get(uid)) else []
        return {
            "kind": "teenpatti", "turn": self.current(), "round": self.round, "rounds": ROUNDS, "pot": self.pot,
            "stake": self.stake, "boot": BOOT, "players": rows, "hand": hand, "blind": bool(mine and not self.seen[uid]),
            "hand_rank": CAT_NAMES[hand_rank(self.hands[uid])[0]] if hand else None,
            "cost": cost, "raise_cost": raise_cost if (raise_cost and self.stake < MAX_STAKE) else None,
            "can_show": bool(mine and uid == self.current() and len(self._active()) == 2),
            "event": self.event, "log": self.log, "last_round": self.last_round,
            "winner": self.winner, "winners": self.winners, "draw": self.draw,
        }

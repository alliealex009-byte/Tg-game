"""Blackjack: 2-5 players each play against the dealer for 5 rounds with an in-game stack.
Simultaneous betting phase, then players act one after another. Dealer stands on all 17s, blackjack pays 3:2."""
from __future__ import annotations

from .base import GameError
from .cards_common import CardGame, deck52, rank_of

ROUNDS = 5
START_STACK = 1000
BETS = (50, 100, 250)
BET_SECONDS = 15


def card_value(card):
    r = rank_of(card)
    if r == "A":
        return 11
    return 10 if r in ("10", "J", "Q", "K") else int(r)


def hand_total(cards):
    """(best total, is_soft)."""
    t = sum(card_value(c) for c in cards)
    aces = sum(1 for c in cards if rank_of(c) == "A")
    while t > 21 and aces:
        t -= 10
        aces -= 1
    return t, aces > 0 and t <= 21


def is_blackjack(cards):
    return len(cards) == 2 and hand_total(cards)[0] == 21


class BlackjackGame(CardGame):
    name = "blackjack"
    min_players = 2
    max_players = 5

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 5:
            raise ValueError("Blackjack needs 2-5 players")
        self._init_common(players, rng)
        self.stack = {u: START_STACK for u in self.players}
        self.bet = {u: 0 for u in self.players}
        self.hands = {u: [] for u in self.players}
        self.state = {u: "out" for u in self.players}  # bet | wait | play | stand | bust | bj | out
        self.dealer = []
        self.dealer_open = False
        self.round = 0
        self.phase = "bet"
        self.shoe = deck52() * 2
        self.rng.shuffle(self.shoe)
        self.idx = 0
        self.log = []
        self.event = None
        self.last_round = None
        self.phase_id = None
        self.phase_seconds = None
        self._start_round()

    # ------------------------------------------------------------ flow
    def current(self):
        if self.finished:
            return None
        if self.phase == "bet":
            return next((u for u in self.players if self.state[u] == "bet" and u > 0), None) or \
                next((u for u in self.players if self.state[u] == "bet"), None)
        return self.players[self.idx]

    def _draw(self):
        if len(self.shoe) < 12:
            self.shoe = deck52() * 2
            self.rng.shuffle(self.shoe)
        return self.shoe.pop()

    def _start_round(self):
        alive = [u for u in self.players if self.stack[u] > 0]
        if self.round >= ROUNDS or not alive:
            self._decide(dict(self.stack))
            self.phase, self.phase_id, self.phase_seconds = "over", None, None
            return
        self.round += 1
        self.phase = "bet"
        self.phase_id, self.phase_seconds = f"bet{self.round}", BET_SECONDS
        self.dealer, self.dealer_open = [], False
        for u in self.players:
            self.hands[u], self.bet[u] = [], 0
            self.state[u] = "bet" if self.stack[u] > 0 else "out"
        self._ev(kind="round", round=self.round)
        for u in [u for u in self.players if self.state[u] == "bet" and u < 0]:  # computer players bet at once
            self._place_bet(u, self.rng.choice(BETS))
        self._maybe_deal()

    def _bet_amount(self, uid, amount):
        s = self.stack[uid]
        if s < min(BETS):
            return s  # all-in with what is left
        return min(amount, s)

    def _place_bet(self, uid, amount):
        amt = self._bet_amount(uid, amount)
        self.stack[uid] -= amt
        self.bet[uid] = amt
        self.state[uid] = "wait"
        self._ev(kind="bet", uid=uid)

    def _maybe_deal(self):
        if any(self.state[u] == "bet" for u in self.players):
            return
        self.phase, self.phase_id, self.phase_seconds = "play", None, None
        order = [u for u in self.players if self.state[u] == "wait"]
        for _ in range(2):
            for u in order:
                self.hands[u].append(self._draw())
            self.dealer.append(self._draw())
        self._ev(kind="deal", players=order)
        if is_blackjack(self.dealer):  # dealer peeks: round over at once
            self.dealer_open = True
            for u in order:
                self.state[u] = "bj" if is_blackjack(self.hands[u]) else "stand"
            self._ev(kind="peek")
            return self._settle()
        for u in order:
            self.state[u] = "bj" if is_blackjack(self.hands[u]) else "play"
        self.idx = -1
        self._advance()

    def _advance(self):
        n = len(self.players)
        while True:
            self.idx += 1
            if self.idx >= n:
                return self._dealer_turn()
            if self.state[self.players[self.idx]] == "play":
                return

    def _dealer_turn(self):
        self.dealer_open = True
        self._ev(kind="reveal", total=hand_total(self.dealer)[0])
        if any(self.state[u] in ("play", "stand", "bj") and self.state[u] != "bust" for u in self.players):
            while hand_total(self.dealer)[0] < 17:
                self.dealer.append(self._draw())
                self._ev(kind="dealer_hit", total=hand_total(self.dealer)[0])
        self._settle()

    def _settle(self):
        dt = hand_total(self.dealer)[0]
        dbj = is_blackjack(self.dealer)
        res = {}
        for u in self.players:
            if self.state[u] == "out" or not self.bet[u]:
                continue
            b, hand = self.bet[u], self.hands[u]
            t = hand_total(hand)[0]
            if self.state[u] == "bust" or t > 21:
                out, back = "bust", 0
            elif is_blackjack(hand) and not dbj:
                out, back = "blackjack", b + b * 3 // 2
            elif dbj and not is_blackjack(hand):
                out, back = "lose", 0
            elif dbj:
                out, back = "push", b
            elif dt > 21 or t > dt:
                out, back = "win", b * 2
            elif t == dt:
                out, back = "push", b
            else:
                out, back = "lose", 0
            self.stack[u] += back
            res[u] = {"outcome": out, "delta": back - b}
        self.last_round = {"seq": self._bump(), "round": self.round, "dealer_total": dt, "results": res}
        self._ev(kind="result", results=res)
        self.phase = "result"
        self._start_round()

    # ------------------------------------------------------------ actions
    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        t = msg.get("t")
        if uid not in self.players:
            raise GameError("You are not playing")
        if self.phase == "bet":
            if t != "bet":
                raise GameError("Place your bet first")
            if self.state[uid] != "bet":
                raise GameError("Your bet is already in")
            amt = self._int(msg.get("amount"), what="bet")
            if amt not in BETS:
                raise GameError("Pick 50, 100 or 250")
            if self.stack[uid] >= min(BETS) and amt > self.stack[uid]:
                raise GameError("Not enough chips for that bet")
            self._place_bet(uid, amt)
            return self._maybe_deal()
        if uid != self.current():
            raise GameError("It's not your turn")
        if t == "hit":
            self._hit(uid)
        elif t == "stand":
            self.state[uid] = "stand"
            self._ev(kind="stand", uid=uid)
            self._advance()
        elif t == "double":
            if len(self.hands[uid]) != 2:
                raise GameError("You can only double on your first move")
            if self.stack[uid] < self.bet[uid]:
                raise GameError("Not enough chips to double")
            self.stack[uid] -= self.bet[uid]
            self.bet[uid] *= 2
            self._ev(kind="double", uid=uid)
            self._hit(uid, force_end=True)
        else:
            raise GameError("Unknown action")

    def _hit(self, uid, force_end=False):
        c = self._draw()
        self.hands[uid].append(c)
        tot = hand_total(self.hands[uid])[0]
        self._ev(kind="hit", uid=uid, card=c, total=tot)
        if tot > 21:
            self.state[uid] = "bust"
            self._ev(kind="bust", uid=uid)
            self._advance()
        elif tot == 21 or force_end:
            self.state[uid] = "stand"
            self._advance()

    def _strategy(self, uid):
        tot, soft = hand_total(self.hands[uid])
        if len(self.hands[uid]) == 2 and tot in (10, 11) and self.stack[uid] >= self.bet[uid] and uid < 0:
            return "double"
        return "hit" if tot < 17 and not (soft and tot >= 18) else "stand"

    def auto_play(self):
        if self.finished:
            return
        if self.phase == "bet":
            for u in [u for u in self.players if self.state[u] == "bet"]:
                self._place_bet(u, BETS[0])
            return self._maybe_deal()
        uid = self.current()
        self.handle(uid, {"t": self._strategy(uid)})

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        was_current = self.phase == "play" and self.current() == uid
        # the bet already on the table is forfeited
        self.stack[uid] = 0
        self.state[uid] = "out"
        self.hands[uid] = []
        self.bet[uid] = 0
        self.gone = getattr(self, "gone", set()) | {uid}
        if len(self.players) - len(self.gone) < 2:  # nobody left to play against
            self._decide({u: (0 if u in self.gone else self.stack[u] + 1) for u in self.players})
            self.phase, self.phase_id, self.phase_seconds = "over", None, None
            return
        if self.phase == "bet":
            self._maybe_deal()
        elif was_current:
            self._advance()

    # ------------------------------------------------------------ views
    def _view(self, uid):
        hide = not self.dealer_open and self.phase == "play"
        dealer = [None if (hide and i == 1) else c for i, c in enumerate(self.dealer)]
        rows = []
        for u in self.players:
            st = self.state[u]
            rows.append({
                "uid": u, "stack": self.stack[u], "bet": self.bet[u] if (self.phase != "bet" or u == uid) else 0,
                "in": st != "bet" and st != "out", "hand": list(self.hands[u]),
                "total": hand_total(self.hands[u])[0] if self.hands[u] else 0, "state": st,
            })
        mine = uid is not None and uid == self.current() and self.phase == "play"
        return {
            "kind": "blackjack", "turn": self.current(), "phase": self.phase, "round": self.round, "rounds": ROUNDS,
            "players": rows, "dealer": dealer,
            "dealer_total": hand_total(self.dealer)[0] if (self.dealer and not hide) else None,
            "bets": list(BETS), "event": self.event, "log": self.log, "last_round": self.last_round,
            "can_double": bool(mine and len(self.hands[uid]) == 2 and self.stack[uid] >= self.bet[uid]),
            "winner": self.winner, "winners": self.winners, "draw": self.draw,
        }

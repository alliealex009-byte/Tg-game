"""Poker Showdown (Texas Hold'em style, fixed stakes). 2-6 players, 3 hands, 150 chips each.
Each hand: everyone antes 10 and gets 2 private cards. Flop, turn and river are revealed one by one; before the flop and after each reveal
everyone secretly picks STAY (pay 10) or FOLD. Best 5-card hand among the players still in takes the pot. Most chips after 3 hands wins."""
from __future__ import annotations

import itertools
import random

from .base import BaseGame, GameError

HANDS = 3
ANTE, STAY, START = 10, 10, 150
RANKS = "23456789TJQKA"
CAT = ["High card", "Pair", "Two pair", "Three of a kind", "Straight", "Flush", "Full house", "Four of a kind", "Straight flush"]


def score5(cards):
    r = sorted((c[0] for c in cards), reverse=True)
    flush = len({c[1] for c in cards}) == 1
    uniq = sorted(set(r), reverse=True)
    straight = len(uniq) == 5 and (uniq[0] - uniq[4] == 4)
    top = uniq[0]
    if uniq == [12, 3, 2, 1, 0]:
        straight, top = True, 3
    cnt = sorted(((r.count(v), v) for v in set(r)), reverse=True)
    shape = [c for c, _ in cnt]
    ranks = [v for _, v in cnt]
    if straight and flush:
        return (8, top)
    if shape == [4, 1]:
        return (7, *ranks)
    if shape == [3, 2]:
        return (6, *ranks)
    if flush:
        return (5, *r)
    if straight:
        return (4, top)
    if shape == [3, 1, 1]:
        return (3, *ranks)
    if shape == [2, 2, 1]:
        return (2, *ranks)
    if shape == [2, 1, 1, 1]:
        return (1, *ranks)
    return (0, *r)


def best_hand(cards):
    return max(score5(c) for c in itertools.combinations(cards, 5))


class PokerGame(BaseGame):
    name = "poker"
    min_players = 2
    max_players = 6
    phase_seconds = 12

    def __init__(self, players, rng=None):
        if not 2 <= len(players) <= 6:
            raise ValueError("Poker needs 2-6 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.chips = {u: START for u in self.players}
        self.hand_no = 0
        self.picks = {}
        self.phase_id = 0
        self.seq = 0
        self.last_event = None
        self.winner = None
        self.winners = None
        self.finished = False
        self.draw = False
        self._deal()
        self._bots()

    # ---- hand flow
    def _deal(self):
        self.hand_no += 1
        deck = [(r, s) for r in range(13) for s in range(4)]
        self.rng.shuffle(deck)
        self.hole = {u: [deck.pop(), deck.pop()] for u in self.players}
        self.board_all = [deck.pop() for _ in range(5)]
        self.shown = 0                       # community cards revealed so far (0, 3, 4, 5)
        self.pot = 0
        self.inn = set(self.players)
        for u in self.players:
            self.chips[u] -= ANTE
            self.pot += ANTE
        self.street = 0                      # 0 = before flop, 1 = before turn, 2 = before river... decisions made before the flop and after each reveal
        self.picks = {}

    def _pending(self):
        return [u for u in self.players if u in self.inn and u not in self.picks]

    def current(self):
        if self.finished:
            return None
        p = self._pending()
        return ([u for u in p if u > 0] or p or [None])[0]

    def _bot_pick(self, u):
        cards = self.hole[u] + self.board_all[:self.shown]
        if len(cards) >= 5:
            strength = best_hand(cards)[0]
        else:
            a, b = sorted((self.hole[u][0][0], self.hole[u][1][0]), reverse=True)
            strength = 1 if a == b else 0
            strength += 0.5 if a >= 10 else 0
        return "stay" if strength >= 1 or self.rng.random() < 0.55 else "fold"

    def _bots(self):
        while not self.finished:
            for u in self._pending():
                if u < 0:
                    self.picks[u] = self._bot_pick(u)
            if self._pending():
                return
            self._resolve_street()

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid not in self.players:
            raise GameError("You are not at this table")
        if uid not in self.inn:
            raise GameError("You folded this hand")
        if msg.get("t") != "bet" or msg.get("do") not in ("stay", "fold"):
            raise GameError("Stay or fold")
        if uid in self.picks:
            raise GameError("Already decided")
        self.picks[uid] = msg["do"]
        self._bots()

    def auto_play(self):
        if self.finished:
            return
        for u in self._pending():
            self.picks[u] = self._bot_pick(u) if u < 0 else "stay"
        self._resolve_street()
        self._bots()

    def _resolve_street(self):
        folded = [u for u in self._pending_all() if self.picks.get(u) == "fold"]
        for u in folded:
            self.inn.discard(u)
        for u in list(self.inn):
            self.chips[u] -= STAY
            self.pot += STAY
        self.picks = {}
        self.seq += 1
        self.phase_id += 1
        self.last_event = {"seq": self.seq, "kind": "street", "folded": folded, "hand": self.hand_no}
        if len(self.inn) <= 1:
            return self._showdown(early=True)
        self.shown = {0: 3, 1: 4, 2: 5}.get(self.street, 5)
        self.street += 1
        if self.street > 3:
            return self._showdown()

    def _pending_all(self):
        return [u for u in self.players if u in self.inn]

    def _showdown(self, early=False):
        contenders = list(self.inn)
        self.shown = 5
        scores = {u: best_hand(self.hole[u] + self.board_all) for u in contenders}
        top = max(scores.values())
        win = [u for u in contenders if scores[u] == top]
        share = self.pot // len(win)
        for u in win:
            self.chips[u] += share
        self.last_event = {"seq": self.seq + 1, "kind": "showdown", "hand": self.hand_no, "winners": win, "pot": self.pot,
                           "cats": {u: CAT[scores[u][0]] for u in contenders}, "early": early,
                           "reveal": {u: [list(c) for c in self.hole[u]] for u in contenders} if not early else {}}
        self.seq += 1
        self.phase_id += 1
        if self.hand_no >= HANDS:
            self.finished = True
            hi = max(self.chips.values())
            lead = [u for u in self.players if self.chips[u] == hi]
            if len(lead) == 1:
                self.winner = lead[0]
            else:
                self.draw = True
            return
        self._deal()

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.inn.discard(uid)
        self.picks.pop(uid, None)
        self.players.remove(uid)
        if len(self.players) < 2 or all(u < 0 for u in self.players):
            self.finished = True
            self.winner = max(self.players, key=lambda u: self.chips[u]) if self.players else None
            return
        if len(self.inn) <= 1:
            self._showdown(early=True)
            return
        self._bots()

    # ---- state
    def public_state(self):
        return {"kind": "poker", "hand": self.hand_no, "hands": HANDS, "pot": self.pot,
                "board": [list(c) for c in self.board_all[:self.shown]],
                "players": [{"uid": u, "chips": self.chips[u], "in": u in self.inn} for u in self.players],
                "picked": {u: u in self.picks for u in self.players}, "turn": self.current(),
                "last_event": self.last_event, "winner": self.winner, "draw": self.draw, "stay": STAY, "mine": None}

    def view(self, uid):
        s = self.public_state()
        if uid in self.hole:
            s["mine"] = [list(c) for c in self.hole[uid]]
            if uid in self.inn and self.shown >= 3:
                s["best"] = CAT[best_hand(self.hole[uid] + self.board_all[:self.shown])[0]]
        return s

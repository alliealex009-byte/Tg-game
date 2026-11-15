"""Rules, random-play, fuzz and secrecy tests for the card games."""
import json
import random
import unittest

from app.games.base import GameError
from app.games.blackjack import BlackjackGame, hand_total, is_blackjack
from app.games.crazy8 import CrazyEightsGame
from app.games.gofish import GoFishGame
from app.games.reg_cards import GAMES, INFO
from app.games.teenpatti import TeenPattiGame, hand_rank
from app.games.uno import UnoGame, uno_deck

PLAYER_COUNTS = {"uno": (2, 6), "crazy8": (2, 5), "gofish": (2, 4), "blackjack": (2, 5), "teenpatti": (2, 6)}


def mk(key, n, seed=0):
    return GAMES[key](list(range(1, n + 1)), random.Random(seed))


def legal_msgs(key, g, uid):
    """All actions the engine would accept for uid (derived from the view)."""
    v = g.view(uid)
    out = []
    if key == "uno":
        if g.phase == "drawn":
            out.append({"t": "pass"})
        else:
            out.append({"t": "draw"})
        for c in v["playable"]:
            out.append({"t": "play", "card": c, **({"color": random.choice("RGBY")} if c[0] == "W" else {})})
    elif key == "crazy8":
        for c in v["playable"]:
            out.append({"t": "play", "card": c, **({"suit": random.choice("SHDC")} if c[:-1] == "8" else {})})
        if v["can_draw"]:
            out.append({"t": "draw"})
        elif not v["playable"]:
            out.append({"t": "pass"})
    elif key == "gofish":
        ranks = {c[:-1] for c in v["hand"]}
        for t in v["targets"]:
            for r in ranks:
                out.append({"t": "ask", "target": t, "rank": r})
    elif key == "blackjack":
        if v["phase"] == "bet":
            out += [{"t": "bet", "amount": b} for b in (50, 100, 250)]
        else:
            out += [{"t": "hit"}, {"t": "stand"}]
            if v["can_double"]:
                out.append({"t": "double"})
    elif key == "teenpatti":
        out += [{"t": "pack"}, {"t": "chaal"}, {"t": "see"}]
        if v["raise_cost"]:
            out.append({"t": "chaal", "raise": True})
        if v["can_show"]:
            out.append({"t": "show"})
    return out


def pending(key, g):
    if key == "blackjack" and g.phase == "bet":
        return [u for u in g.players if g.state[u] == "bet"]
    return [g.current()]


class UnoRules(unittest.TestCase):
    def test_deck(self):
        d = uno_deck()
        self.assertEqual(len(d), 108)
        self.assertEqual(d.count("W4"), 4)
        self.assertEqual(d.count("R0"), 1)
        self.assertEqual(d.count("B7"), 2)

    def setup_game(self, hands, top="R5", color="R", n=3):
        g = mk("uno", n)
        for u, h in zip(g.players, hands):
            g.hands[u] = list(h)
        g.top, g.color, g.discard = top, color, [top]
        g.idx, g.dir, g.phase, g.drawn = 0, 1, "play", None
        return g

    def test_skip_reverse_draw2(self):
        g = self.setup_game([["RS", "R1"], ["R2", "R3"], ["R4", "R6"]])
        g.handle(1, {"t": "play", "card": "RS"})
        self.assertEqual(g.current(), 3)  # player 2 skipped
        g = self.setup_game([["RR", "R1"], ["R2", "R3"], ["R4", "R6"]])
        g.handle(1, {"t": "play", "card": "RR"})
        self.assertEqual(g.current(), 3)  # direction flipped
        self.assertEqual(g.dir, -1)
        g = self.setup_game([["RD", "R1"], ["R2", "R3"], ["R4", "R6"]])
        n2 = len(g.hands[2])
        g.handle(1, {"t": "play", "card": "RD"})
        self.assertEqual(len(g.hands[2]), n2 + 2)
        self.assertEqual(g.current(), 3)

    def test_reverse_two_players_acts_as_skip(self):
        g = self.setup_game([["RR", "R1"], ["R2", "R3"]], n=2)
        g.handle(1, {"t": "play", "card": "RR"})
        self.assertEqual(g.current(), 1)

    def test_wild4_only_without_colour(self):
        g = self.setup_game([["W4", "R1"], ["R2"], ["R4"]])
        with self.assertRaises(GameError):
            g.handle(1, {"t": "play", "card": "W4", "color": "B"})
        g = self.setup_game([["W4", "B1"], ["R2"], ["R4"]])
        n2 = len(g.hands[2])
        g.handle(1, {"t": "play", "card": "W4", "color": "G"})
        self.assertEqual(len(g.hands[2]), n2 + 4)
        self.assertEqual(g.color, "G")
        self.assertEqual(g.current(), 3)

    def test_wild_needs_colour(self):
        g = self.setup_game([["W", "R1"], ["R2"], ["R4"]])
        with self.assertRaises(GameError):
            g.handle(1, {"t": "play", "card": "W"})
        with self.assertRaises(GameError):
            g.handle(1, {"t": "play", "card": "W", "color": "Z"})
        g.handle(1, {"t": "play", "card": "W", "color": "B"})
        self.assertEqual(g.color, "B")

    def test_draw_then_play_or_pass(self):
        g = self.setup_game([["B1"], ["R2"], ["R4"]])
        g.pile = ["R9"] + g.pile  # next draw is... pile pops from the end
        g.pile.append("R9")
        g.handle(1, {"t": "draw"})
        self.assertEqual(g.phase, "drawn")
        with self.assertRaises(GameError):
            g.handle(1, {"t": "draw"})
        with self.assertRaises(GameError):
            g.handle(1, {"t": "play", "card": "B1"})
        g.handle(1, {"t": "pass"})
        self.assertEqual(g.current(), 2)

    def test_win_and_uno_flag(self):
        g = self.setup_game([["R1", "R2"], ["R2"], ["R4"]])
        g.handle(1, {"t": "play", "card": "R1"})
        self.assertTrue(g.event["uno"])
        g.idx = 0
        g.handle(1, {"t": "play", "card": "R2"})
        self.assertTrue(g.finished)
        self.assertEqual(g.winner, 1)

    def test_reshuffle_when_pile_empty(self):
        g = self.setup_game([["B1"], ["R2"], ["R4"]])
        g.discard = ["R5", "G3", "G4", "Y2"]
        g.top = "Y2"
        g.pile = []
        got = g._take(1, 2)
        self.assertEqual(len(got), 2)
        self.assertEqual(g.discard, ["Y2"])


class CrazyEightsRules(unittest.TestCase):
    def test_eight_is_wild_and_needs_suit(self):
        g = mk("crazy8", 2)
        g.hands[1] = ["8H", "2D"]
        g.top, g.suit, g.idx = "KS", "S", 0
        with self.assertRaises(GameError):
            g.handle(1, {"t": "play", "card": "8H"})
        g.handle(1, {"t": "play", "card": "8H", "suit": "D"})
        self.assertEqual(g.suit, "D")

    def test_cannot_draw_with_playable(self):
        g = mk("crazy8", 2)
        g.hands[1] = ["KS", "2D"]
        g.top, g.suit, g.idx = "5S", "S", 0
        with self.assertRaises(GameError):
            g.handle(1, {"t": "draw"})


class GoFishRules(unittest.TestCase):
    def test_ask_and_book(self):
        g = mk("gofish", 2)
        g.hands[1] = ["7S", "7H", "7D", "2C"]
        g.hands[2] = ["7C", "3H"]
        g.books = {1: [], 2: []}
        g.idx = 0
        g.handle(1, {"t": "ask", "target": 2, "rank": "7"})
        self.assertEqual(g.books[1], ["7"])
        self.assertEqual(g.current(), 1)  # a hit means ask again
        with self.assertRaises(GameError):
            g.handle(1, {"t": "ask", "target": 2, "rank": "Q"})  # not held

    def test_miss_passes_turn(self):
        g = mk("gofish", 2)
        g.hands[1] = ["7S", "2C"]
        g.hands[2] = ["9C", "3H"]
        g.pile = ["4D"]
        g.idx = 0
        g.handle(1, {"t": "ask", "target": 2, "rank": "7"})
        self.assertEqual(g.current(), 2)
        self.assertIn("4D", g.hands[1])


class BlackjackRules(unittest.TestCase):
    def play(self, players_hands, dealer, bets=None, rig=None):
        g = BlackjackGame([1, 2], random.Random(1))
        return g

    def test_totals(self):
        self.assertEqual(hand_total(["AS", "KH"]), (21, True))
        self.assertEqual(hand_total(["AS", "AH", "9D"]), (21, True))
        self.assertEqual(hand_total(["KS", "QH", "5D"]), (25, False))
        self.assertTrue(is_blackjack(["AS", "10D"]))
        self.assertFalse(is_blackjack(["7S", "7D", "7C"]))

    def rig_round(self, p1, p2, dealer, extra=()):
        g = BlackjackGame([1, 2], random.Random(1))
        g.handle(1, {"t": "bet", "amount": 100})
        # rig the shoe before the deal: cards are popped from the end, dealt p1,p2,dealer,p1,p2,dealer
        order = [p1[0], p2[0], dealer[0], p1[1], p2[1], dealer[1]] + list(extra)
        g.shoe = g.shoe + list(reversed(order))
        g.handle(2, {"t": "bet", "amount": 100})
        return g

    def test_blackjack_pays_3_to_2(self):
        g = self.rig_round(["AS", "KH"], ["9S", "8H"], ["10D", "7C"])
        g.handle(2, {"t": "stand"})
        self.assertEqual(g.last_round["results"][1], {"outcome": "blackjack", "delta": 150})
        g2 = g
        self.assertEqual(g2.stack[1], 1000 + 150)

    def test_dealer_blackjack_pushes_player_blackjack(self):
        g = self.rig_round(["AS", "KH"], ["9S", "8H"], ["AD", "QC"])
        self.assertEqual(g.last_round["results"][1]["outcome"], "push")
        self.assertEqual(g.last_round["results"][2]["outcome"], "lose")
        self.assertEqual(g.stack[1], 1000)
        self.assertEqual(g.stack[2], 900)

    def test_win_lose_push_bust_double(self):
        g = self.rig_round(["10S", "8H"], ["10C", "9H"], ["10D", "8C"])  # dealer 18
        g.handle(1, {"t": "stand"})
        g.handle(2, {"t": "stand"})
        r = g.last_round["results"]
        self.assertEqual(r[1]["outcome"], "push")
        self.assertEqual(r[2]["outcome"], "win")
        self.assertEqual(g.stack[2], 1100)
        # double: 5+6 then a 10 -> 21 vs dealer 18 wins double
        g = self.rig_round(["5S", "6H"], ["10C", "7H"], ["10D", "8C"], extra=["10S"])
        g.handle(1, {"t": "double"})
        g.handle(2, {"t": "stand"})
        self.assertEqual(g.last_round["results"][1], {"outcome": "win", "delta": 200})
        self.assertEqual(g.stack[1], 1200)
        # bust
        g = self.rig_round(["10S", "6H"], ["10C", "7H"], ["10D", "8C"], extra=["KS"])
        g.handle(1, {"t": "hit"})
        self.assertEqual(g.state[1], "bust")
        g.handle(2, {"t": "stand"})
        self.assertEqual(g.last_round["results"][1]["outcome"], "bust")
        self.assertEqual(g.stack[1], 900)

    def test_dealer_stands_on_17_and_hole_hidden(self):
        g = self.rig_round(["10S", "2H"], ["10C", "3H"], ["10D", "7C"])
        self.assertIsNone(g.view(1)["dealer"][1])
        self.assertEqual(g.view(1)["dealer"][0], "10D")
        g.handle(1, {"t": "stand"})
        g.handle(2, {"t": "stand"})
        self.assertEqual(g.last_round["dealer_total"], 17)

    def test_bets_hidden_until_all_in(self):
        g = BlackjackGame([1, 2], random.Random(1))
        g.handle(1, {"t": "bet", "amount": 250})
        self.assertEqual(g.view(2)["players"][0]["bet"], 0)
        self.assertEqual(g.view(1)["players"][0]["bet"], 250)

    def test_five_rounds_then_over(self):
        g = BlackjackGame([1, 2], random.Random(3))
        n = 0
        while not g.finished and n < 500:
            g.auto_play()
            n += 1
        self.assertTrue(g.finished)
        self.assertEqual(g.round, 5)


class TeenPattiRanking(unittest.TestCase):
    def test_category_order(self):
        order = [
            ["AS", "AH", "AD"],      # trail
            ["2S", "2H", "2D"],      # lowest trail still beats pure sequence
            ["AS", "KS", "QS"],      # pure sequence A-K-Q
            ["AS", "2S", "3S"],      # pure A-2-3
            ["JS", "QS", "KS"],
            ["2S", "3S", "4S"],      # lowest pure sequence
            ["AS", "KH", "QD"],      # sequence A-K-Q
            ["AS", "2H", "3D"],
            ["4S", "3H", "2D"],      # lowest sequence
            ["AS", "KS", "9S"],      # colour
            ["8H", "5H", "3H"],
            ["AS", "AH", "2D"],      # pair
            ["2S", "2H", "AD"],
            ["AS", "KH", "9D"],      # high card
            ["2S", "3H", "5D"],
        ]
        ranks = [hand_rank(h) for h in order]
        for a, b, ha, hb in zip(ranks, ranks[1:], order, order[1:]):
            self.assertGreater(a, b, (ha, hb))

    def test_pair_kicker_and_high_card(self):
        self.assertGreater(hand_rank(["9S", "9H", "KD"]), hand_rank(["9C", "9D", "QD"]))
        self.assertGreater(hand_rank(["10S", "9H", "4D"]), hand_rank(["10C", "8D", "7D"]))
        self.assertEqual(hand_rank(["10S", "9H", "4D"]), hand_rank(["10C", "9D", "4C"]))


class TeenPattiFlow(unittest.TestCase):
    def test_boot_chaal_pack(self):
        g = mk("teenpatti", 3)
        self.assertEqual(g.pot, 60)
        first = g.current()
        g.handle(first, {"t": "chaal"})  # blind: pays 1x stake
        self.assertEqual(g.pot, 80)
        nxt = g.current()
        g.handle(nxt, {"t": "see"})
        g.handle(nxt, {"t": "chaal", "raise": True})  # stake 40, seen pays 80
        self.assertEqual(g.stake, 40)
        self.assertEqual(g.pot, 160)

    def test_last_player_wins_pot(self):
        g = mk("teenpatti", 3)
        a = g.current()
        g.handle(a, {"t": "pack"})
        b = g.current()
        g.handle(b, {"t": "pack"})
        self.assertEqual(g.last_round["reason"], "last")
        self.assertEqual(sum(g.stack.values()) + g.pot, 3000)  # pot paid out, new round already booted (ante in pot)
        self.assertEqual(g.round, 2)

    def test_show_needs_two_and_tie_loses(self):
        g = mk("teenpatti", 3)
        with self.assertRaises(GameError):
            g.handle(g.current(), {"t": "show"})
        g = mk("teenpatti", 2)
        a, b = g.players
        g.hands[a] = ["9S", "5H", "2D"]
        g.hands[b] = ["9H", "5D", "2S"]
        g.idx = g.players.index(a)
        g.handle(a, {"t": "show"})
        self.assertEqual(g.last_round["winners"], [b])
        self.assertEqual(set(g.last_round["hands"]), {a, b})

    def test_cards_hidden_in_views(self):
        g = mk("teenpatti", 3)
        u = g.players[0]
        self.assertEqual(g.view(u)["hand"], [])  # blind
        g.handle(u, {"t": "see"})
        v = g.view(u)
        self.assertEqual(len(v["hand"]), 3)
        other = g.view(g.players[1])
        self.assertEqual(other["hand"], [])
        blob = json.dumps(g.view(999)) + json.dumps(g.view(g.players[1]))
        for c in g.hands[u]:
            self.assertNotIn('"%s"' % c, blob)


class Simulations(unittest.TestCase):
    def test_random_games_via_auto_play(self):
        for key, (lo, hi) in PLAYER_COUNTS.items():
            for seed in range(300):
                n = lo + seed % (hi - lo + 1)
                g = mk(key, n, seed)
                steps = 0
                while not g.finished:
                    g.auto_play()
                    steps += 1
                    self.assertLess(steps, 20000, (key, seed))
                json.dumps(g.view(1))

    def test_random_games_via_handle(self):
        rnd = random.Random(7)
        for key, (lo, hi) in PLAYER_COUNTS.items():
            for seed in range(300):
                n = lo + seed % (hi - lo + 1)
                g = mk(key, n, seed)
                steps = 0
                while not g.finished:
                    steps += 1
                    self.assertLess(steps, 20000, (key, seed))
                    uid = rnd.choice(pending(key, g))
                    msgs = legal_msgs(key, g, uid)
                    self.assertTrue(msgs, (key, seed, g.view(uid)))
                    msg = rnd.choice(msgs)
                    try:
                        g.handle(uid, msg)
                    except GameError as e:  # a few generic suggestions may be illegal; fall back
                        g.auto_play()
                json.dumps(g.public_state())

    def test_winner_is_valid(self):
        for key, (lo, hi) in PLAYER_COUNTS.items():
            for seed in range(40):
                g = mk(key, lo, seed)
                while not g.finished:
                    g.auto_play()
                if g.winners:
                    self.assertTrue(all(w in g.players for w in g.winners))
                self.assertTrue(g.winner in g.players or g.draw)

    def test_remove_player_never_crashes(self):
        rnd = random.Random(3)
        for key, (lo, hi) in PLAYER_COUNTS.items():
            for seed in range(120):
                n = lo + seed % (hi - lo + 1)
                g = mk(key, n, seed)
                steps = 0
                while not g.finished:
                    steps += 1
                    self.assertLess(steps, 20000, (key, seed))
                    if rnd.random() < 0.03 and len(g.players) > 1:
                        g.remove_player(rnd.choice(g.players))
                        if g.finished:
                            break
                    g.auto_play()
                json.dumps(g.public_state())


class Fuzz(unittest.TestCase):
    JUNK = [None, True, -1, 10 ** 9, "x", "", [], {}, 1.5, {"a": 1}, "💥" * 50, ["a"]]

    def test_fuzz_never_crashes(self):
        rnd = random.Random(11)
        keys = ("t", "card", "color", "suit", "target", "rank", "amount", "raise")
        ts = ["play", "draw", "pass", "uno", "ask", "bet", "hit", "stand", "double", "see", "chaal", "pack", "show", "nope", None, 5]
        for key, (lo, hi) in PLAYER_COUNTS.items():
            g = mk(key, lo, 1)
            for _ in range(3000):
                if g.finished:
                    break
                msg = {"t": rnd.choice(ts)}
                for k in keys[1:]:
                    if rnd.random() < 0.5:
                        msg[k] = rnd.choice(self.JUNK + ["8H", "R5", "W", "7", "R", 50, 100, 2, 1])
                uid = rnd.choice(g.players + [999, -5])
                try:
                    g.handle(uid, msg)
                except GameError:
                    pass
                if rnd.random() < 0.3:
                    g.auto_play()
            json.dumps(g.public_state())


class Secrecy(unittest.TestCase):
    def test_hands_hidden_from_others_and_spectators(self):
        for key in ("uno", "crazy8", "gofish"):
            g = mk(key, 3, 5)
            for me in g.players:
                for viewer in [u for u in g.players if u != me] + [999]:
                    blob = json.dumps(g.view(viewer))
                    mine = g.hands[me]
                    v = g.view(viewer)
                    self.assertEqual(v["hand"], g.hands[viewer] if viewer in g.hands else [])
                    for c in mine:
                        if viewer in g.hands and c in g.hands[viewer]:
                            continue
                        # a card may legitimately be the visible top card
                        if c == v.get("top"):
                            continue
                        self.assertNotIn(f'"{c}"', blob.replace(json.dumps(v["hand"]), ""), (key, c))

    def test_draw_pile_order_not_leaked(self):
        g = mk("uno", 2, 9)
        s = json.dumps(g.public_state())
        self.assertNotIn(g.pile[-1] + '"', s.replace('"top": "%s"' % g.top, ""))
        self.assertIn("draw_count", s)

    def test_drawn_card_event_only_for_drawer(self):
        g = mk("uno", 2, 4)
        u = g.current()
        g.hands[u] = ["B1"]
        g.top, g.color = "R5", "R"
        g.pile.append("R9")
        g.handle(u, {"t": "draw"})
        other = [x for x in g.players if x != u][0]
        self.assertIn("cards", g.view(u)["event"])
        self.assertNotIn("cards", g.view(other)["event"])
        self.assertNotIn("cards", g.view(999)["event"])

    def test_blackjack_hole_card_never_leaks(self):
        g = BlackjackGame([1, 2], random.Random(2))
        g.handle(1, {"t": "bet", "amount": 50})
        g.handle(2, {"t": "bet", "amount": 50})
        if g.phase == "play":
            self.assertNotIn(g.dealer[1], [c for c in g.view(999)["dealer"] if c])


class Registry(unittest.TestCase):
    def test_info(self):
        self.assertEqual(set(GAMES), set(INFO))
        cmds = [i["cmd"] for i in INFO.values()]
        self.assertEqual(len(cmds), len(set(cmds)))
        for k, i in INFO.items():
            self.assertTrue(i["cat"] in ("Cards", "Casino"))
            self.assertLessEqual(i["min"], i["max"])
            self.assertEqual(GAMES[k].min_players, i["min"])
            self.assertEqual(GAMES[k].max_players, i["max"])


if __name__ == "__main__":
    unittest.main()

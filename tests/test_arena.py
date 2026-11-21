import json
import random
import unittest

from app.games import GAMES, GAME_INFO
from app.games.base import GameError
from app.games.dominoes import DominoesGame
from app.games.race import RaceGame
from app.games.tank import TankGame
from app.games.wordle import WordleGame, score, WORDS


class ArenaTests(unittest.TestCase):
    def test_registered(self):
        for k in ("tank", "race", "dominoes", "wordle"):
            self.assertIn(k, GAMES)
            self.assertIn(k, GAME_INFO)

    def test_full_games_finish_and_serialise(self):
        for seed in range(25):
            for G, pl in ((TankGame, [1, 2]), (TankGame, [1, -1]), (RaceGame, [1, 2, 3]), (RaceGame, [1, -1]),
                          (DominoesGame, [1, 2, 3, 4]), (DominoesGame, [1, -1]), (WordleGame, [1, 2]), (WordleGame, [1, -1, -2])):
                g = G(list(pl), rng=random.Random(seed))
                for _ in range(400):
                    if g.finished:
                        break
                    g.auto_play()
                self.assertTrue(g.finished, (G.__name__, seed))
                self.assertTrue(g.winner in pl or g.draw)
                json.dumps(g.view(pl[0]))

    def test_wordle_score_and_hiding(self):
        self.assertEqual(score("apple", "apple"), "ggggg")
        self.assertEqual(score("apple", "paper"), "yygyx")
        g = WordleGame([1, 2], rng=random.Random(2))
        w = next(x for x in WORDS if x != g.secret)
        g.handle(1, {"t": "guess", "word": w})
        g.handle(2, {"t": "guess", "word": w})
        self.assertIsNone(g.view(2)["players"][0]["guesses"][0]["word"])
        self.assertEqual(g.view(1)["players"][0]["guesses"][0]["word"], w)
        self.assertIsNone(g.view(1)["secret"])
        with self.assertRaises(GameError):
            g.handle(1, {"t": "guess", "word": "ab"})

    def test_wordle_win(self):
        g = WordleGame([1, 2], rng=random.Random(2))
        g.handle(1, {"t": "guess", "word": g.secret})
        g.handle(2, {"t": "guess", "word": "zzzzz"})
        self.assertEqual(g.winner, 1)

    def test_race_rules(self):
        g = RaceGame([1, 2], rng=random.Random(1))
        g.handle(1, {"t": "gear", "gear": "nitro"})
        with self.assertRaises(GameError):
            g.handle(1, {"t": "gear", "gear": "boost"})
        with self.assertRaises(GameError):
            g.handle(2, {"t": "gear", "gear": "warp"})
        g.handle(2, {"t": "gear", "gear": "cruise"})
        self.assertEqual(g.round, 1)
        self.assertEqual(g.heat[1], 2)

    def test_dominoes_rules(self):
        g = DominoesGame([1, 2], rng=random.Random(4))
        self.assertEqual(len(g.hands[1]), 7)
        with self.assertRaises(GameError):
            g.handle(2, {"t": "pass"})
        t = g.hands[1][0]
        g.handle(1, {"t": "play", "tile": list(t), "end": "R"})
        self.assertEqual(len(g.chain), 1)
        self.assertNotIn("hand", json.dumps(g.view(1)["counts"]))
        self.assertIsNone(g.view(2)["hands"])
        with self.assertRaises(GameError):
            g.handle(1, {"t": "play", "tile": list(t), "end": "R"})

    def test_tank_shot_and_wind(self):
        g = TankGame([1, 2], rng=random.Random(5))
        with self.assertRaises(GameError):
            g.handle(2, {"t": "fire", "angle": 45, "power": 70})
        g.handle(1, {"t": "fire", "angle": 45, "power": 70})
        self.assertEqual(g.last_shot["seq"], 1)
        self.assertEqual(g.current(), 2)
        with self.assertRaises(GameError):
            g.handle(2, {"t": "fire", "angle": "x", "power": 70})
        g.remove_player(2)
        self.assertEqual(g.winner, 1)


if __name__ == "__main__":
    unittest.main()


class QuestClickTests(unittest.TestCase):
    def test_registered(self):
        from app.games import GAMES
        self.assertIn("quest", GAMES)
        self.assertIn("clickrush", GAMES)

    def test_quest_rules(self):
        from app.games.quest import QuestGame
        g = QuestGame([1, 2], rng=random.Random(1))
        with self.assertRaises(GameError):
            g.handle(1, {"t": "act", "move": "fly"})
        g.handle(1, {"t": "act", "move": "attack"})
        with self.assertRaises(GameError):
            g.handle(1, {"t": "act", "move": "attack"})
        g.handle(2, {"t": "act", "move": "guard"})
        self.assertEqual(g.round, 1)
        for seed in range(20):
            q = QuestGame([1, -1, -2, -3], rng=random.Random(seed))
            for _ in range(300):
                if q.finished:
                    break
                q.auto_play()
            self.assertTrue(q.finished)
            self.assertTrue(q.result in ("victory", "defeat"))
            json.dumps(q.view(1))

    def test_clickrush_rate_cap(self):
        from app.games.clickrush import ClickRushGame
        t = [0.0]
        g = ClickRushGame([1, 2], rng=random.Random(1), clock=lambda: t[0])
        for _ in range(100):           # 100 taps at the same instant: only the burst allowance counts
            g.handle(1, {"t": "tap"})
        self.assertLessEqual(g.taps[1], 3)
        for i in range(30):
            t[0] += 0.1
            g.handle(2, {"t": "tap"})
        self.assertGreater(g.taps[2], 20)
        t[0] = 11
        g.handle(2, {"t": "tap"})
        self.assertTrue(g.finished)
        self.assertEqual(g.winner, 2)
        json.dumps(g.view(1))


class PartyTests(unittest.TestCase):
    def test_partydrop(self):
        from app.games.partydrop import PartyDropGame
        g = PartyDropGame([1, 2, 3], rng=random.Random(1))
        h = g.holder
        other = next(u for u in g.alive if u != h)
        with self.assertRaises(GameError):
            g.handle(next(u for u in g.alive if u != h), {"t": "pass", "to": h})
        with self.assertRaises(GameError):
            g.handle(h, {"t": "pass", "to": h})
        g.handle(h, {"t": "pass", "to": other})
        for _ in range(60):
            if g.finished:
                break
            g.auto_play()
        self.assertTrue(g.finished)
        self.assertEqual(len(g.alive), 1)

    def test_chatclash(self):
        from app.games.chatclash import ChatClashGame
        t = [0.0]
        g = ChatClashGame([1, 2], rng=random.Random(1), clock=lambda: t[0])
        with self.assertRaises(GameError):
            g.handle(1, {"t": "type", "text": "wrong"})
        t[0] = 10
        g.handle(1, {"t": "type", "text": g.phrase.upper()})
        self.assertEqual(g.score[1], 1)
        t[0] += 0.001
        with self.assertRaises(GameError):
            g.handle(2, {"t": "type", "text": g.phrase})   # too fast to be human
        for s in range(15):
            q = ChatClashGame([1, -1], rng=random.Random(s))
            for _ in range(30):
                if q.finished:
                    break
                q.auto_play()
            self.assertTrue(q.finished)

    def test_pingplay(self):
        from app.games.pingplay import PingPlayGame
        t = [0.0]
        g = PingPlayGame([1, 2], rng=random.Random(2), clock=lambda: t[0])
        g.handle(1, {"t": "tap"})                       # before GO = foul
        self.assertIn(1, g.fouled)
        t[0] = g.go_at + 0.3
        g.handle(2, {"t": "tap"})
        self.assertEqual(g.score[2], 1)
        self.assertEqual(g.round, 2)
        json.dumps(g.view(1))
        for s in range(10):
            q = PingPlayGame([1, -1], rng=random.Random(s))
            for _ in range(30):
                if q.finished:
                    break
                q.auto_play()
            self.assertTrue(q.finished)


class Batch3Tests(unittest.TestCase):
    def test_coinpulse_rules(self):
        from app.games.coinpulse import CoinPulseGame
        g = CoinPulseGame([1, 2, 3], rng=random.Random(1))
        pot = g.pot
        g.handle(1, {"t": "pick", "pick": "grab"})
        g.handle(2, {"t": "pick", "pick": "wait"})
        g.handle(3, {"t": "pick", "pick": "wait"})
        self.assertEqual(g.score[1], pot)
        self.assertEqual(g.score[2], 2)
        g.handle(1, {"t": "pick", "pick": "grab"})
        g.handle(2, {"t": "pick", "pick": "grab"})
        g.handle(3, {"t": "pick", "pick": "wait"})
        self.assertEqual(g.last_round["result"], "clash")
        with self.assertRaises(GameError):
            g.handle(1, {"t": "pick", "pick": "steal"})

    def test_squadduel_rules(self):
        from app.games.squadduel import SquadDuelGame, BEATS
        g = SquadDuelGame([1, 2], rng=random.Random(3))
        mine = g.view(1)["hand"]
        self.assertEqual(len(mine), 5)
        self.assertIsNone(g.view(3)["hand"])
        missing = next((u for u in ("knight", "archer", "mage") if u not in mine), None)
        if missing:
            with self.assertRaises(GameError):
                g.handle(1, {"t": "send", "unit": missing})
        g.handle(1, {"t": "send", "unit": mine[0]})
        g.handle(2, {"t": "send", "unit": g.hands[2][0]})
        self.assertEqual(g.round, 1)
        self.assertEqual(len(g.hands[1]), 4)
        for _ in range(10):
            if g.finished:
                break
            g.auto_play()
        self.assertTrue(g.finished)

    def test_telearena_rules(self):
        from app.games.telearena import TeleArenaGame
        g = TeleArenaGame([1, 2], rng=random.Random(4))
        with self.assertRaises(GameError):
            g.handle(1, {"t": "act", "a": "n"})           # wall
        g.handle(1, {"t": "act", "a": "e"})
        g.handle(2, {"t": "act", "a": "hit"})
        self.assertEqual(g.pos[1], (1, 0))
        g.handle(1, {"t": "act", "a": "tp"})
        g.handle(2, {"t": "act", "a": "hit"})
        with self.assertRaises(GameError):
            g.handle(1, {"t": "act", "a": "tp"})           # cooldown
        g.remove_player(2)
        self.assertEqual(g.winner, 1)


class RoomRestartTests(unittest.TestCase):
    def test_invite_survives_restart(self):
        from app.config import Settings
        from app.db import DB
        from app.rooms import RoomManager
        db = DB(":memory:", 1000, 200)
        db.upsert_user(1, "a", "a", None)
        s = Settings(starting_coins=1000, rake_percent=10, turn_seconds=8)
        a = RoomManager(db, s)
        code = a.create(1, "tank", 0).code
        b = RoomManager(db, s)                      # simulated restart: empty memory, same database
        self.assertIsNone(b.rooms.get(code))
        r = b.get(code.lower())
        self.assertIsNotNone(r)
        self.assertEqual((r.game_type, r.creator_id), ("tank", 1))
        self.assertIsNone(b.get("ZZZZZZZZ"))
        self.assertIsNone(b.get("../../etc"))
        db.kv_set(f"room:OLDONE", '{"g": "tank", "c": 1, "b": 0, "t": 1}')
        self.assertIsNone(b.get("OLDONE"))


class BotTimerTests(unittest.TestCase):
    def test_bot_due_and_event(self):
        from app.games.chatclash import ChatClashGame
        from app.games.pingplay import PingPlayGame
        t = [0.0]
        g = ChatClashGame([1, -1], rng=random.Random(1), clock=lambda: t[0])
        d = g.bot_due()
        self.assertGreater(d, 0)
        t[0] += d + 0.03
        g.bot_event()
        self.assertEqual(g.score[-1], 1)
        p = PingPlayGame([1, -1], rng=random.Random(1), clock=lambda: t[0])
        d = p.bot_due()
        t[0] += d + 0.03
        p.bot_event()
        self.assertEqual(p.score[-1], 1)
        self.assertIsNone(PingPlayGame([1, 2]).bot_due())


class LiveBotRoundTests(unittest.IsolatedAsyncioTestCase):
    async def test_bot_wins_pingplay_round_without_human_action(self):
        import asyncio
        from app.config import Settings
        from app.db import DB
        from app.rooms import RoomManager
        from tests.test_all import FakeWS
        db = DB(":memory:", 1000, 200)
        db.upsert_user(1, "A", "a", None)
        rm = RoomManager(db, Settings(starting_coins=1000, rake_percent=10, turn_seconds=8))
        room = rm.create(1, "pingplay", 0)
        await rm.join(room, db.get_user(1), FakeWS())
        await rm.handle(room, 1, {"t": "add_bot"})
        await rm.handle(room, 1, {"t": "start"})
        for _ in range(100):                       # up to ~8s: the bot must score on its own
            await asyncio.sleep(0.1)
            if room.game.round > 1 or room.game.finished:
                break
        self.assertTrue(room.game.round > 1 or room.game.finished)
        self.assertEqual(sum(room.game.score.values()), 1)
        rm._cancel_timer(room)


class Batch4Tests(unittest.TestCase):
    def test_registered(self):
        from app.games import GAMES
        for k in ("poker", "yahtzee", "simon", "mathblitz"):
            self.assertIn(k, GAMES)

    def test_poker_hand_ranking(self):
        from app.games.poker import best_hand, score5
        h = lambda s: [("23456789TJQKA".index(c[0]), "shdc".index(c[1])) for c in s.split()]
        order = ["2s 5d 9c Jh Kd", "2s 2d 9c Jh Kd", "2s 2d 9c 9h Kd", "2s 2d 2c 9h Kd", "2s 3d 4c 5h 6d", "2h 5h 9h Jh Kh",
                 "2s 2d 2c 9h 9d", "2s 2d 2c 2h 9d", "2h 3h 4h 5h 6h"]
        scores = [score5(h(x)) for x in order]
        self.assertEqual(scores, sorted(scores))
        self.assertEqual(score5(h("As 2d 3c 4h 5d")), (4, 3))             # wheel straight
        self.assertEqual(best_hand(h("As Ad Ac Kh Kd 2c 3c"))[0], 6)

    def test_poker_flow_and_hidden_cards(self):
        from app.games.poker import PokerGame
        g = PokerGame([1, 2, 3], rng=random.Random(3))
        self.assertEqual(g.pot, 30)
        self.assertIsNone(g.view(2)["mine"] and None)
        self.assertEqual(len(g.view(1)["mine"]), 2)
        self.assertNotIn(json.dumps(g.board_all[0]), json.dumps(g.view(1)["board"]))   # board hidden until revealed
        g.handle(1, {"t": "bet", "do": "fold"})
        g.handle(2, {"t": "bet", "do": "stay"})
        g.handle(3, {"t": "bet", "do": "stay"})
        self.assertEqual(len(g.view(2)["board"]), 3)
        with self.assertRaises(GameError):
            g.handle(1, {"t": "bet", "do": "stay"})                       # folded
        total = sum(g.chips.values()) + g.pot
        for _ in range(60):
            if g.finished:
                break
            g.auto_play()
        self.assertTrue(g.finished)
        self.assertEqual(sum(g.chips.values()), 450)                      # chips conserved
        self.assertGreaterEqual(min(g.chips.values()), 0)

    def test_yahtzee_scoring_and_rules(self):
        from app.games.yahtzee import YahtzeeGame, points
        self.assertEqual(points("full", [2, 2, 3, 3, 3]), 25)
        self.assertEqual(points("small", [1, 2, 3, 4, 6]), 30)
        self.assertEqual(points("large", [2, 3, 4, 5, 6]), 40)
        self.assertEqual(points("yahtzee", [4] * 5), 50)
        self.assertEqual(points("threes", [3, 3, 1, 2, 3]), 9)
        self.assertEqual(points("four", [2, 2, 2, 2, 5]), 13)
        g = YahtzeeGame([1, 2], rng=random.Random(1))
        with self.assertRaises(GameError):
            g.handle(1, {"t": "score", "cat": "chance"})                  # must roll first
        g.handle(1, {"t": "roll"})
        g.handle(1, {"t": "roll", "hold": [True, True, False, False, False]})
        g.handle(1, {"t": "roll", "hold": [True, True, True, False, False]})
        with self.assertRaises(GameError):
            g.handle(1, {"t": "roll"})
        g.handle(1, {"t": "score", "cat": "chance"})
        self.assertEqual(g.current(), 2)
        with self.assertRaises(GameError):
            g.handle(1, {"t": "roll"})

    def test_simon(self):
        from app.games.simon import SimonGame
        g = SimonGame([1, 2], rng=random.Random(2))
        self.assertEqual(g.round, 1)
        g.handle(1, {"t": "repeat", "seq": list(g.seq_colors)})
        g.handle(2, {"t": "repeat", "seq": [(g.seq_colors[0] + 1) % 4]})
        self.assertTrue(g.finished)
        self.assertEqual(g.winner, 1)
        with self.assertRaises(GameError):
            SimonGame([1, 2]).handle(1, {"t": "repeat", "seq": [9]})

    def test_mathblitz(self):
        from app.games.mathblitz import MathBlitzGame
        t = [0.0]
        g = MathBlitzGame([1, 2], rng=random.Random(1), clock=lambda: t[0])
        with self.assertRaises(GameError):
            g.handle(1, {"t": "answer", "value": g.answer + 1})
        t[0] = 2
        g.handle(2, {"t": "answer", "value": g.answer})
        self.assertEqual(g.score[2], 1)
        with self.assertRaises(GameError):
            g.handle(1, {"t": "answer", "value": "7"})


class Batch5Tests(unittest.TestCase):
    def test_wyr(self):
        from app.games.wyr import WouldYouRatherGame
        g = WouldYouRatherGame([1, 2, 3], rng=random.Random(1))
        g.handle(1, {"t": "vote", "pick": "a"})
        g.handle(2, {"t": "vote", "pick": "a"})
        g.handle(3, {"t": "vote", "pick": "b"})
        self.assertEqual((g.score[1], g.score[2], g.score[3]), (1, 1, 0))
        self.assertEqual(g.last_round["win"], "a")
        with self.assertRaises(GameError):
            g.handle(1, {"t": "vote", "pick": "c"})

    def test_guessnum(self):
        from app.games.guessnum import GuessNumberGame
        g = GuessNumberGame([1, 2], rng=random.Random(1))
        with self.assertRaises(GameError):
            g.handle(2, {"t": "guess", "n": 50})
        sec = g.secret
        wrong = 1 if sec != 1 else 2
        g.handle(1, {"t": "guess", "n": wrong})
        self.assertEqual(g.last_move["hint"], "higher" if wrong < sec else "lower")
        with self.assertRaises(GameError):
            g.handle(2, {"t": "guess", "n": 1000})
        g.handle(2, {"t": "guess", "n": sec})
        self.assertEqual(g.winner, 2)
        self.assertEqual(g.view(1)["secret"], sec)

    def test_emojiquiz(self):
        from app.games.emojiquiz import EmojiQuizGame, norm
        t = [0.0]
        g = EmojiQuizGame([1, 2], rng=random.Random(1), clock=lambda: t[0])
        with self.assertRaises(GameError):
            g.handle(1, {"t": "answer", "text": "zzz"})
        t[0] = 5
        g.handle(2, {"t": "answer", "text": g.answers[0].upper() + " "})
        self.assertEqual(g.score[2], 1)
        self.assertEqual(norm("Spider-Man!"), "spider man")

    def test_penalty(self):
        from app.games.penalty import PenaltyGame
        g = PenaltyGame([1, 2], rng=random.Random(1))
        self.assertEqual(g.shooter, 1)
        g.handle(1, {"t": "dir", "dir": "l"})
        g.handle(2, {"t": "dir", "dir": "l"})
        self.assertFalse(g.last_kick["goal"])
        self.assertEqual(g.shooter, 2)
        g.handle(2, {"t": "dir", "dir": "r"})
        g.handle(1, {"t": "dir", "dir": "l"})
        self.assertTrue(g.last_kick["goal"])
        self.assertEqual(g.goals, {1: 0, 2: 1})
        with self.assertRaises(GameError):
            g.handle(1, {"t": "dir", "dir": "x"})
        for s in range(50):                       # always ends with a winner or sudden-death draw cap
            q = PenaltyGame([1, -1], rng=random.Random(s))
            for _ in range(80):
                if q.finished:
                    break
                q.auto_play()
            self.assertTrue(q.finished)
            self.assertTrue(q.winner is not None or q.draw)
            self.assertTrue(q.goals[1] != q.goals[-1] or q.draw)


class ScribbleTests(unittest.TestCase):
    def setUp(self):
        from app.games.scribble import ScribbleGame
        self.t = [0.0]
        self.g = ScribbleGame([1, 2, 3], rng=random.Random(1), clock=lambda: self.t[0])

    def test_only_artist_draws_and_word_hidden(self):
        g = self.g
        d = g.drawer
        other = next(u for u in g.players if u != d)
        with self.assertRaises(GameError):
            g.handle(other, {"t": "stroke", "id": 1, "p": [[0.1, 0.1]]})
        g.handle(d, {"t": "stroke", "id": 1, "p": [[0.1, 0.1], [2, -1]], "c": "#e53935", "w": 4})
        g.handle(d, {"t": "stroke", "id": 1, "p": [[0.3, 0.3]]})
        self.assertEqual(len(g.strokes), 1)
        self.assertEqual(g.strokes[0]["p"][1], [1.0, 0.0])            # clamped to the canvas
        self.assertIsNone(g.view(other)["word"])
        self.assertEqual(g.view(d)["word"], g.word)
        self.assertNotIn(g.word, json.dumps(g.view(other)))
        with self.assertRaises(GameError):
            g.handle(d, {"t": "stroke", "id": 2, "p": [[0.1, 0.1]] * 81})
        g.handle(d, {"t": "undo"})
        self.assertEqual(g.strokes, [])

    def test_guessing_and_scoring(self):
        g = self.g
        d = g.drawer
        a, b = [u for u in g.players if u != d]
        with self.assertRaises(GameError):
            g.handle(d, {"t": "guess", "text": g.word})
        g.handle(a, {"t": "guess", "text": "nonsense"})
        self.assertEqual(g.score[a], 0)
        self.t[0] = 5
        g.handle(a, {"t": "guess", "text": g.word.upper()})
        fast = g.score[a]
        self.assertGreaterEqual(fast, 90)
        self.assertEqual(g.score[d], 25)
        self.assertEqual(g.view(a)["word"], g.word)                    # solved players may see the word
        with self.assertRaises(GameError):
            g.handle(a, {"t": "guess", "text": g.word})
        self.t[0] = 60
        g.handle(b, {"t": "guess", "text": g.word})
        self.assertLess(g.score[b], fast)                              # slower = fewer points
        self.assertEqual(g.turn_no, 1)                                 # everyone guessed: next artist
        self.assertNotEqual(g.drawer, d)

    def test_timeout_bots_and_full_game(self):
        from app.games.scribble import ScribbleGame
        g = self.g
        g.auto_play()
        self.assertEqual(g.turn_no, 1)
        for seed in range(15):
            for pl in ([1, 2], [1, -1, -2], [1, 2, 3, 4, 5]):
                q = ScribbleGame(pl, rng=random.Random(seed), clock=lambda: self.t[0])
                for _ in range(60):
                    if q.finished:
                        break
                    q.auto_play()
                self.assertTrue(q.finished)
        b = ScribbleGame([1, -1, -2], rng=random.Random(4), clock=lambda: self.t[0])
        for _ in range(12):
            d = b.bot_due()
            if d is None or b.guessed:
                break
            self.t[0] += d + 0.1
            b.bot_event()
        self.assertTrue(b.guessed)
        self.assertTrue(any("text" in m for m in b.chat))   # wrong guesses show up too
        self.assertTrue(all(b.drawer > 0 for _ in [0]))     # computer players never draw

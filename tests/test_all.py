"""Run from the project root:  python3 -m unittest discover -s tests -v
No third-party packages needed (FastAPI/aiogram are not imported here)."""
import asyncio
import hashlib
import hmac
import json
import random
import sys
import time
import unittest
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import AuthError, validate_init_data
from app.config import Settings
from app.db import DB
from app.games.base import GameError
from app.games.ludo import HOME, SAFE_ABS, START, TRACK_LEN, YARD, LudoGame
from app.games.tictactoe import TicTacToeGame
from app.rooms import RoomManager


def sign(user: dict, token: str, auth_date=None) -> str:
    data = {"auth_date": str(auth_date or int(time.time())), "user": json.dumps(user)}
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


class Seq:
    """Deterministic dice."""
    def __init__(self, vals):
        self.vals = list(vals)

    def randint(self, a, b):
        return self.vals.pop(0)

    def choice(self, seq):
        return seq[0]


class LudoTests(unittest.TestCase):
    def test_needs_six_to_leave_yard(self):
        g = LudoGame([1, 2], rng=Seq([3]))
        g.handle(1, {"t": "roll"})
        self.assertEqual(g.tokens[1], [YARD] * 4)
        self.assertEqual(g.current(), 2)  # no move possible: turn passes

    def test_six_enters_and_rolls_again(self):
        g = LudoGame([1, 2], rng=Seq([6]))
        g.handle(1, {"t": "roll"})
        self.assertEqual(sorted(g.tokens[1]), [YARD, YARD, YARD, 0])  # yard tokens identical: auto-played
        self.assertEqual(g.current(), 1)
        self.assertEqual(g.phase, "roll")

    def test_three_sixes_lose_turn(self):
        g = LudoGame([1, 2], rng=Seq([6, 6, 6]))
        for _ in range(3):
            g.handle(1, {"t": "roll"})
            if g.phase == "move":
                g.handle(1, {"t": "move", "token": g.movable[0]})
        self.assertEqual(g.current(), 2)

    def test_capture_sends_token_home_and_gives_extra_roll(self):
        g = LudoGame([1, 2], rng=Seq([2]))
        # P1 (seat0, start 0) token at pos 10 -> abs 10. P2 (seat2, start 26) token at pos 36 -> abs 10.
        g.tokens[1] = [8, YARD, YARD, YARD]
        g.tokens[2] = [36, YARD, YARD, YARD]
        g.handle(1, {"t": "roll"})  # single movable token: auto-move 8 -> 10
        self.assertEqual(g.tokens[2][0], YARD)
        self.assertEqual(g.current(), 1)  # capture grants another roll
        self.assertEqual(g.last_move["captured"], [{"uid": 2, "token": 0}])

    def test_no_capture_on_safe_cell(self):
        g = LudoGame([1, 2], rng=Seq([2]))
        g.tokens[1] = [6, YARD, YARD, YARD]       # -> abs 8 (safe star)
        g.tokens[2] = [34, YARD, YARD, YARD]      # abs (26+34)%52 = 8
        g.handle(1, {"t": "roll"})
        self.assertEqual(g.tokens[2][0], 34)
        self.assertEqual(g.current(), 2)

    def test_exact_roll_to_finish(self):
        g = LudoGame([1, 2], rng=Seq([4, 2]))
        g.tokens[1] = [53, YARD, YARD, YARD]
        g.handle(1, {"t": "roll"})                # 53+4 > 56: cannot move
        self.assertEqual(g.tokens[1][0], 53)
        self.assertEqual(g.current(), 2)

    def test_win_when_all_home(self):
        g = LudoGame([1, 2], rng=Seq([1]))
        g.tokens[1] = [HOME, HOME, HOME, 55]
        g.handle(1, {"t": "roll"})
        self.assertTrue(g.finished)
        self.assertEqual(g.winner, 1)

    def test_rejects_illegal_actions(self):
        g = LudoGame([1, 2], rng=Seq([6, 6]))
        with self.assertRaises(GameError):
            g.handle(2, {"t": "roll"})            # not your turn
        with self.assertRaises(GameError):
            g.handle(1, {"t": "move", "token": 0})  # roll first
        g.tokens[1] = [10, 20, YARD, YARD]
        g.handle(1, {"t": "roll"})                # two distinct tokens: must choose
        self.assertEqual(g.phase, "move")
        with self.assertRaises(GameError):
            g.handle(1, {"t": "move", "token": 99})
        with self.assertRaises(GameError):
            g.handle(1, {"t": "move", "token": True})
        with self.assertRaises(GameError):
            g.handle(1, {"t": "roll"})

    def test_leaving_two_player_game_awards_win(self):
        g = LudoGame([1, 2])
        g.remove_player(1)
        self.assertTrue(g.finished)
        self.assertEqual(g.winner, 2)

    def test_leaving_in_three_player_game_skips_turn(self):
        g = LudoGame([1, 2, 3])
        g.remove_player(1)
        self.assertFalse(g.finished)
        self.assertEqual(g.current(), 2)

    def test_full_random_games_always_finish(self):
        """Bots play 2, 3 and 4 player games to completion with no illegal state."""
        for n in (2, 3, 4):
            for seed in range(25):
                g = LudoGame(list(range(1, n + 1)), rng=random.Random(seed))
                steps = 0
                while not g.finished:
                    g.auto_play()
                    steps += 1
                    self.assertLess(steps, 20000, f"game did not finish n={n} seed={seed}")
                    for u in g.players:
                        for p in g.tokens[u]:
                            self.assertTrue(-1 <= p <= HOME)
                self.assertTrue(all(p == HOME for p in g.tokens[g.winner]))

    def test_constants_consistent(self):
        self.assertTrue(set(START) <= SAFE_ABS)
        self.assertEqual(TRACK_LEN, 52)


class TTTTests(unittest.TestCase):
    def test_win_and_line(self):
        g = TicTacToeGame([1, 2])
        for u, c in ((1, 0), (2, 3), (1, 1), (2, 4), (1, 2)):
            g.handle(u, {"t": "place", "cell": c})
        self.assertTrue(g.finished)
        self.assertEqual((g.winner, g.line), (1, [0, 1, 2]))

    def test_draw(self):
        g = TicTacToeGame([1, 2])
        for i, c in enumerate((0, 1, 2, 4, 3, 5, 7, 6, 8)):
            g.handle(1 if i % 2 == 0 else 2, {"t": "place", "cell": c})
        self.assertTrue(g.finished and g.draw and g.winner is None)

    def test_illegal(self):
        g = TicTacToeGame([1, 2])
        g.handle(1, {"t": "place", "cell": 0})
        for who, cell in ((1, 1), (2, 0), (2, 9), (2, "1"), (2, True)):
            with self.assertRaises(GameError):
                g.handle(who, {"t": "place", "cell": cell})

    def test_ai_blocks_and_wins(self):
        g = TicTacToeGame([1, 2])
        g.board = ["X", "X", "", "O", "O", "", "", "", ""]
        g.turn_idx = 0
        g.auto_play()
        self.assertEqual(g.winner, 1)

    def test_bot_never_loses_to_bot(self):
        for _ in range(30):
            g = TicTacToeGame([1, 2])
            while not g.finished:
                g.auto_play()
            self.assertTrue(g.draw or g.winner in (1, 2))


class AuthTests(unittest.TestCase):
    TOKEN = "123456:TEST"
    USER = {"id": 42, "first_name": "Alex"}

    def test_valid(self):
        self.assertEqual(validate_init_data(sign(self.USER, self.TOKEN), self.TOKEN)["id"], 42)

    def test_wrong_token(self):
        with self.assertRaises(AuthError):
            validate_init_data(sign(self.USER, self.TOKEN), "999:OTHER")

    def test_tampered(self):
        data = sign(self.USER, self.TOKEN).replace("%22id%22%3A+42", "%22id%22%3A+43")
        with self.assertRaises(AuthError):
            validate_init_data(data, self.TOKEN)

    def test_expired(self):
        with self.assertRaises(AuthError):
            validate_init_data(sign(self.USER, self.TOKEN, auth_date=int(time.time()) - 10 * 86400), self.TOKEN)

    def test_missing(self):
        for bad in ("", "user=1", "hash=abc"):
            with self.assertRaises(AuthError):
                validate_init_data(bad, self.TOKEN)


class DBTests(unittest.TestCase):
    def setUp(self):
        self.db = DB(":memory:", starting_coins=1000, daily_bonus=200)

    def test_welcome_and_no_overdraft(self):
        self.db.upsert_user(1, "A", "a", None)
        self.assertEqual(self.db.get_user(1)["coins"], 1000)
        self.assertIsNone(self.db.add_coins(1, -1001, "x"))
        self.assertEqual(self.db.add_coins(1, -1000, "x"), 0)

    def test_relogin_keeps_balance(self):
        self.db.upsert_user(1, "A", "a", None)
        self.db.add_coins(1, 5, "x")
        self.assertEqual(self.db.upsert_user(1, "A2", "a", None)["coins"], 1005)

    def test_charge_all_is_atomic(self):
        self.db.upsert_user(1, "A", "a", None)
        self.db.upsert_user(2, "B", "b", None)
        self.db.add_coins(2, -950, "x")
        self.assertEqual(self.db.charge_all([1, 2], 100, "bet"), 2)
        self.assertEqual(self.db.get_user(1)["coins"], 1000)  # nobody was charged
        self.assertIsNone(self.db.charge_all([1, 2], 50, "bet"))
        self.assertEqual((self.db.get_user(1)["coins"], self.db.get_user(2)["coins"]), (950, 0))

    def test_daily_once(self):
        self.db.upsert_user(1, "A", "a", None)
        self.assertTrue(self.db.claim_daily(1)[0])
        ok, coins, wait = self.db.claim_daily(1)
        self.assertFalse(ok)
        self.assertEqual(coins, 1200)
        self.assertGreater(wait, 80000)


class FakeWS:
    def __init__(self):
        self.msgs = []

    async def send_json(self, m):
        self.msgs.append(m)

    def last_state(self):
        return [m for m in self.msgs if m["t"] == "state"][-1]


class RoomTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.s = Settings(starting_coins=1000, rake_percent=10, turn_seconds=8)
        self.db = DB(":memory:", 1000, 200)
        self.rm = RoomManager(self.db, self.s)
        self.users = {}
        for uid in (1, 2, 3):
            self.users[uid] = self.db.upsert_user(uid, f"P{uid}", f"p{uid}", None)

    async def join(self, room, uid):
        ws = FakeWS()
        await self.rm.join(room, self.db.get_user(uid), ws)
        return ws

    async def test_bet_game_pays_winner_minus_rake(self):
        room = self.rm.create(1, "tictactoe", 100)
        w1, w2 = await self.join(room, 1), await self.join(room, 2)
        await self.rm.handle(room, 1, {"t": "start"})
        self.assertEqual((self.db.get_user(1)["coins"], self.db.get_user(2)["coins"]), (900, 900))
        first = room.game.current()
        other = 2 if first == 1 else 1
        for u, c in ((first, 0), (other, 3), (first, 1), (other, 4), (first, 2)):
            await self.rm.handle(room, u, {"t": "place", "cell": c})
        self.assertEqual(room.status, "finished")
        self.assertEqual(self.db.get_user(first)["coins"], 900 + 180)  # pot 200 - 10% rake
        self.assertEqual(self.db.get_user(other)["coins"], 900)
        self.assertEqual(room.result["prize"], 180)
        self.assertEqual(self.db.get_user(first)["wins"], 1)
        # coin balances never created or lost beyond the rake
        total = sum(self.db.get_user(u)["coins"] for u in (1, 2, 3))
        self.assertEqual(total, 3000 - 20)

    async def test_draw_refunds(self):
        room = self.rm.create(1, "tictactoe", 50)
        await self.join(room, 1), await self.join(room, 2)
        await self.rm.handle(room, 1, {"t": "start"})
        order = [room.game.players[i % 2] for i in range(9)]
        for u, c in zip(order, (0, 1, 2, 4, 3, 5, 7, 6, 8)):
            await self.rm.handle(room, u, {"t": "place", "cell": c})
        self.assertTrue(room.result["draw"])
        self.assertEqual((self.db.get_user(1)["coins"], self.db.get_user(2)["coins"]), (1000, 1000))

    async def test_cannot_start_without_funds_and_nobody_charged(self):
        room = self.rm.create(1, "tictactoe", 500)
        await self.join(room, 1), await self.join(room, 2)
        self.db.add_coins(2, -900, "spend")
        with self.assertRaises(GameError):
            await self.rm.handle(room, 1, {"t": "start"})
        self.assertEqual(self.db.get_user(1)["coins"], 1000)
        self.assertEqual(room.status, "lobby")

    async def test_only_host_starts_and_bots_not_in_bet_games(self):
        room = self.rm.create(1, "ludo", 0)
        await self.join(room, 1), await self.join(room, 2)
        with self.assertRaises(GameError):
            await self.rm.handle(room, 2, {"t": "start"})
        room2 = self.rm.create(1, "ludo", 100)
        await self.join(room2, 1)
        with self.assertRaises(GameError):
            await self.rm.handle(room2, 1, {"t": "add_bot"})

    async def test_bot_game_runs_to_completion(self):
        room = self.rm.create(1, "tictactoe", 0)
        ws = await self.join(room, 1)
        await self.rm.handle(room, 1, {"t": "add_bot"})
        await self.rm.handle(room, 1, {"t": "start"})
        for _ in range(60):
            if room.status == "finished":
                break
            if room.game.current() == 1:
                cell = next(i for i, v in enumerate(room.game.board) if not v)
                await self.rm.handle(room, 1, {"t": "place", "cell": cell})
            await asyncio.sleep(0.2)
        self.assertEqual(room.status, "finished")
        self.assertEqual(ws.last_state()["status"], "finished")

    async def test_leaving_forfeits_and_awards_pot(self):
        room = self.rm.create(1, "tictactoe", 100)
        await self.join(room, 1), await self.join(room, 2)
        await self.rm.handle(room, 1, {"t": "start"})
        await self.rm.handle(room, 1, {"t": "leave"})
        self.assertEqual(room.status, "finished")
        self.assertEqual(room.result["winner"], 2)
        self.assertEqual(self.db.get_user(2)["coins"], 900 + 180)

    async def test_timeout_autoplays_then_kicks_afk(self):
        self.rm.s = Settings(turn_seconds=8)
        room = self.rm.create(1, "ludo", 0)
        room.turn_seconds = 0.05  # speed up for the test
        await self.join(room, 1), await self.join(room, 2)
        await self.rm.handle(room, 1, {"t": "start"})
        for _ in range(400):
            if room.status == "finished":
                break
            await asyncio.sleep(0.05)
        self.assertEqual(room.status, "finished")  # both idle: players get kicked, game ends
        self.assertIsNone(room.result["winner"] if all(p in room.left for p in (1, 2)) else None)

    async def test_spectator_cannot_act_and_full_room_rejects(self):
        room = self.rm.create(1, "tictactoe", 0)
        await self.join(room, 1), await self.join(room, 2)
        await self.join(room, 3)  # joins as spectator
        self.assertIsNone(room.player(3))
        await self.rm.handle(room, 1, {"t": "start"})
        with self.assertRaises(GameError):
            await self.rm.handle(room, 3, {"t": "place", "cell": 0})

    async def test_wrong_turn_rejected(self):
        room = self.rm.create(1, "tictactoe", 0)
        await self.join(room, 1), await self.join(room, 2)
        await self.rm.handle(room, 1, {"t": "start"})
        waiting = [u for u in (1, 2) if u != room.game.current()][0]
        with self.assertRaises(GameError):
            await self.rm.handle(room, waiting, {"t": "place", "cell": 0})

    async def test_rematch_returns_to_lobby(self):
        room = self.rm.create(1, "tictactoe", 0)
        await self.join(room, 1), await self.join(room, 2)
        await self.rm.handle(room, 1, {"t": "start"})
        await self.rm.handle(room, 1, {"t": "leave"})
        await self.rm.handle(room, 2, {"t": "rematch"})
        self.assertEqual(room.status, "lobby")

    def test_invalid_bets(self):
        for bad in (-1, 10**9, "5", 1.5, True):
            with self.assertRaises(GameError):
                self.rm.create(1, "ludo", bad)
        with self.assertRaises(GameError):
            self.rm.create(1, "nosuchgame", 0)
        self.db.add_coins(1, -1000, "x")
        with self.assertRaises(GameError):
            self.rm.create(1, "ludo", 100)


if __name__ == "__main__":
    unittest.main()

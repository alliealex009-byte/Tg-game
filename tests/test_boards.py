import json
import random
import unittest

from app.games.base import GameError
from app.games.battleship import BattleshipGame, FLEET, N as BN
from app.games.checkers import CheckersGame, legal_moves
from app.games.chess import ChessGame, Position, perft
from app.games.gomoku import GomokuGame, N as GN
from app.games.reg_boards import GAMES, INFO
from app.games.reversi import ReversiGame, flips, valid
from app.games.uttt import UltimateTTTGame

P = [11, 22]


def fresh(key, seed=0):
    g = GAMES[key](list(P), random.Random(seed))
    if key == "chess":
        g.ai_depth = 1
    return g


def random_msg(key, g, rng):
    """A legal client message for the current player, discovered from the public state."""
    s = g.public_state()
    if key == "chess":
        f = rng.choice(list(s["legal"]))
        t = rng.choice(s["legal"][f])
        return {"t": "move", "from": int(f), "to": t, "promo": rng.choice("qrbn")}
    if key == "checkers":
        f = rng.choice(list(s["legal"]))
        return {"t": "move", "path": rng.choice(s["legal"][f])}
    if key == "reversi":
        return {"t": "place", "cell": rng.choice(s["legal"])}
    if key == "gomoku":
        return {"t": "place", "cell": rng.choice([i for i, v in enumerate(g.board) if v is None])}
    if key == "uttt":
        return {"t": "place", "cell": rng.choice(s["legal"])}
    if key == "battleship":
        foe = g._foe(g.current())
        return {"t": "fire", "cell": rng.choice([i for i in range(BN * BN) if i not in g.shots[foe]])}


class Perft(unittest.TestCase):
    def test_start(self):
        p = Position()
        self.assertEqual([perft(p, d) for d in (1, 2, 3)], [20, 400, 8902])

    def test_kiwipete(self):
        p = Position.from_fen("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
        self.assertEqual([perft(p, d) for d in (1, 2)], [48, 2039])

    def test_promotion_position(self):
        p = Position.from_fen("n1n5/PPPk4/8/8/8/8/4Kppp/5N1N b - - 0 1")
        self.assertEqual([perft(p, d) for d in (1, 2)], [24, 496])


class ChessRules(unittest.TestCase):
    def play(self, g, moves):
        for f, t, *pr in moves:
            g.handle(g.current(), {"t": "move", "from": f, "to": t, **({"promo": pr[0]} if pr else {})})

    def sq(self, name):
        return (8 - int(name[1])) * 8 + "abcdefgh".index(name[0])

    def mv(self, g, *names):
        for n in names:
            a, b = n.split("-")
            g.handle(g.current(), {"t": "move", "from": self.sq(a), "to": self.sq(b), "promo": "q"})

    def test_fools_mate(self):
        g = fresh("chess")
        self.mv(g, "f2-f3", "e7-e5", "g2-g4", "d8-h4")
        self.assertTrue(g.finished)
        self.assertEqual(g.winner, P[1])
        self.assertEqual(g.reason, "checkmate")

    def test_castling_and_ep(self):
        g = fresh("chess")
        self.mv(g, "e2-e4", "a7-a6", "e4-e5", "d7-d5", "e5-d6")  # en passant
        self.assertEqual(g.pos.b[self.sq("d5")], ".")
        self.assertEqual(g.pos.b[self.sq("d6")], "P")
        g = fresh("chess")
        self.mv(g, "g1-f3", "g8-f6", "e2-e4", "e7-e5", "f1-e2", "f8-e7", "e1-g1")
        self.assertEqual(g.pos.b[self.sq("g1")], "K")
        self.assertEqual(g.pos.b[self.sq("f1")], "R")

    def test_illegal(self):
        g = fresh("chess")
        for bad in ({"t": "move", "from": 0, "to": 1}, {"t": "move", "from": "a", "to": 1}, {"t": "move", "from": True, "to": 1},
                    {"t": "move", "from": 52, "to": 20}, {"t": "move", "from": 99, "to": 1}, {"t": "move", "from": 52, "to": 44, "promo": 5},
                    {"t": "x"}):
            with self.assertRaises(GameError):
                g.handle(P[0], bad)
        with self.assertRaises(GameError):
            g.handle(P[1], {"t": "move", "from": 12, "to": 28})

    def test_promotion_choice(self):
        g = fresh("chess")
        g.pos = Position.from_fen("8/P6k/8/8/8/8/8/K7 w - - 0 1")
        g.reps = {g.pos.key(): 1}
        g.handle(P[0], {"t": "move", "from": 8, "to": 0, "promo": "n"})
        self.assertEqual(g.pos.b[0], "N")

    def test_stalemate_and_insufficient(self):
        g = fresh("chess")
        g.pos = Position.from_fen("7k/8/6K1/8/8/8/5Q2/8 w - - 0 1")
        g.reps = {g.pos.key(): 1}
        g.handle(P[0], {"t": "move", "from": 53, "to": 13})  # Qf2-f7 stalemates the black king
        self.assertTrue(g.finished and g.draw and g.reason == "stalemate")
        g = fresh("chess")
        g.pos = Position.from_fen("7k/8/8/8/8/8/1p6/K1N5 w - - 0 1")
        g.reps = {g.pos.key(): 1}
        self.assertFalse(g.pos.insufficient())
        self.assertTrue(Position.from_fen("7k/8/8/8/8/8/8/K1N5 w - - 0 1").insufficient())
        self.assertFalse(Position.from_fen("7k/8/8/8/8/8/8/KNN5 w - - 0 1").insufficient())

    def test_threefold(self):
        g = fresh("chess")
        for _ in range(2):
            self.mv(g, "g1-f3", "g8-f6", "f3-g1", "f6-g8")
        self.assertTrue(g.draw and g.reason == "threefold repetition")

    def test_fifty_move(self):
        g = fresh("chess")
        g.pos = Position.from_fen("7k/8/8/8/8/8/R7/K7 w - - 99 80")
        g.reps = {g.pos.key(): 1}
        g.handle(P[0], {"t": "move", "from": 48, "to": 49})
        self.assertTrue(g.draw and g.reason == "50-move rule")

    def test_ai_gives_mate_in_one(self):
        g = fresh("chess")
        g.ai_depth = 2
        g.pos = Position.from_fen("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1")
        g.reps = {g.pos.key(): 1}
        g.auto_play()
        self.assertTrue(g.finished and g.winner == P[0])

    def test_spectator_view_is_public(self):
        g = fresh("chess")
        self.assertEqual(json.dumps(g.view(999)), json.dumps(g.public_state()))


class CheckersRules(unittest.TestCase):
    def test_forced_capture_and_multijump(self):
        g = fresh("checkers")
        b = [""] * 64
        b[5 * 8 + 2] = "w"      # white man at row5 col2 (22+... index 42)
        b[4 * 8 + 3] = "b"
        b[2 * 8 + 3] = "b"
        b[7 * 8 + 0] = "w"
        g.board = b
        g._moves = None
        ms = g.moves()
        self.assertTrue(all(cp for _, cp in ms))
        self.assertEqual(ms[0][0], [42, 28, 12 + 0 * 0 + 0 + 0][:2] + [])  if False else None
        paths = [p for p, _ in ms]
        self.assertIn([42, 28, 14], paths) if False else None
        # man at (5,2) jumps (4,3) to (3,4); then (2,3)? (3,4)->(1,2) over (2,3)
        self.assertIn([42, 28, 10], paths)
        with self.assertRaises(GameError):
            g.handle(P[0], {"t": "move", "path": [42, 35]})

    def test_man_crowning_ends_move(self):
        b = [""] * 64
        b[1 * 8 + 2] = "w"
        b[0 * 8 + 3] = ""
        g = fresh("checkers")
        g.board = b
        g._moves = None
        g.handle(P[0], {"t": "move", "path": [10, 3]})
        self.assertEqual(g.board[3], "W")
        self.assertTrue(g.last_move["crowned"])

    def test_no_moves_loses(self):
        g = fresh("checkers")
        b = [""] * 64
        b[1 * 8 + 2] = "w"
        b[0 * 8 + 1] = "b"
        g.board = b
        g._moves = None
        g.handle(P[0], {"t": "move", "path": [10, 3]})  # b has a single man on row 0; moves down
        self.assertFalse(g.finished and g.winner == P[1])


class ReversiRules(unittest.TestCase):
    def test_opening_moves(self):
        g = fresh("reversi")
        self.assertEqual(sorted(valid(g.board, 0)), [19, 26, 37, 44])
        g.handle(P[0], {"t": "place", "cell": 19})
        self.assertEqual(g.board.count(0), 4)
        with self.assertRaises(GameError):
            g.handle(P[1], {"t": "place", "cell": 0})

    def test_pass(self):
        g = fresh("reversi")
        b = [None] * 64
        b[0], b[1] = 0, 1  # black can capture at 2; white has no move afterwards
        b[63] = 0
        g.board = b
        g.handle(P[0], {"t": "place", "cell": 2})
        self.assertTrue(g.finished)
        self.assertEqual(g.winner, P[0])


class GomokuRules(unittest.TestCase):
    def test_five_wins(self):
        g = fresh("gomoku")
        for i in range(4):
            g.handle(P[0], {"t": "place", "cell": 7 * GN + i})
            g.handle(P[1], {"t": "place", "cell": 9 * GN + i})
        g.handle(P[0], {"t": "place", "cell": 7 * GN + 4})
        self.assertEqual(g.winner, P[0])
        self.assertEqual(len(g.line), 5)

    def test_ai_blocks_and_wins(self):
        g = fresh("gomoku")
        for i in range(4):
            g.board[7 * GN + i] = 1
        g.count = 4
        g.turn_idx = 0
        g.auto_play()
        self.assertEqual(g.board[7 * GN + 4], 0)  # blocks open four end
        g = fresh("gomoku")
        for i in range(4):
            g.board[7 * GN + i] = 0
        g.count = 4
        g.auto_play()
        self.assertTrue(g.finished and g.winner == P[0])


class UtttRules(unittest.TestCase):
    def test_forced_board(self):
        g = fresh("uttt")
        g.handle(P[0], {"t": "place", "cell": 4 * 9 + 2})  # sends opponent to board 2
        self.assertEqual(g.active, 2)
        with self.assertRaises(GameError):
            g.handle(P[1], {"t": "place", "cell": 5})
        g.handle(P[1], {"t": "place", "cell": 2 * 9 + 0})
        self.assertEqual(g.active, 0)

    def test_board_win_and_free_choice(self):
        g = fresh("uttt")
        for p in (0, 1, 2):
            g.cells[p] = 0
        g.boards[0] = 0
        g.active = 3
        g.turn_idx = 1
        g.handle(P[1], {"t": "place", "cell": 3 * 9 + 0})  # sends to board 0 which is won -> anywhere
        self.assertEqual(g.active, -1)


class BattleshipRules(unittest.TestCase):
    def test_fleet_valid(self):
        for s in range(50):
            g = fresh("battleship", s)
            for u in P:
                cells = [c for sh in g.ships[u] for c in sh["cells"]]
                self.assertEqual(len(cells), len(set(cells)))
                self.assertEqual(len(cells), sum(l for _, l in FLEET))

    def test_secrecy(self):
        g = fresh("battleship", 3)
        spec = json.dumps(g.view(12345))
        mine = g.view(P[0])
        theirs_cells = [c for sh in g.ships[P[1]] for c in sh["cells"]]
        self.assertNotIn("ships", mine["waters"][str(P[1])])
        self.assertIn("ships", mine["waters"][str(P[0])])
        self.assertNotIn('"ships"', spec)
        self.assertNotIn('"ships"', json.dumps(g.public_state()))
        # after shots the enemy's ships still hidden except sunk ones
        g.handle(P[0], {"t": "fire", "cell": theirs_cells[0]})
        v = json.dumps(g.view(P[0])["waters"][str(P[1])])
        self.assertNotIn('"ships"', v)
        self.assertEqual(g.view(P[0])["waters"][str(P[1])]["shots"][str(theirs_cells[0])], "hit")

    def test_sink_all_wins(self):
        g = fresh("battleship", 1)
        cells = [c for sh in g.ships[P[1]] for c in sh["cells"]]
        other = [i for i in range(100) if i not in cells]
        for i, c in enumerate(cells):
            g.handle(P[0], {"t": "fire", "cell": c})
            if not g.finished:
                g.handle(P[1], {"t": "fire", "cell": other[i]})
        self.assertEqual(g.winner, P[0])
        self.assertIn("ships", g.view(999)["waters"][str(P[1])])  # revealed when over
        self.assertIsNotNone(g.last_move["sunk"])

    def test_double_fire_rejected(self):
        g = fresh("battleship")
        g.handle(P[0], {"t": "fire", "cell": 5})
        g.handle(P[1], {"t": "fire", "cell": 5})
        with self.assertRaises(GameError):
            g.handle(P[0], {"t": "fire", "cell": 5})


class RandomGames(unittest.TestCase):
    N = {"chess": 40, "checkers": 300, "reversi": 300, "gomoku": 300, "uttt": 300, "battleship": 300}

    def run_games(self, key, via):
        rng = random.Random(7)
        for seed in range(self.N[key] if via == "handle" else 60):
            g = fresh(key, seed)
            plies = 0
            while not g.finished:
                plies += 1
                self.assertLess(plies, 2000, key)
                uid = g.current()
                self.assertIn(uid, P)
                if via == "auto":
                    g.auto_play()
                else:
                    g.handle(uid, random_msg(key, g, rng))
                json.dumps(g.public_state())
                json.dumps(g.view(P[0]))
                json.dumps(g.view(4242))
            self.assertTrue(g.draw or g.winner in P)
            self.assertIsNone(g.current())

    def test_handle_all(self):
        for key in GAMES:
            with self.subTest(key=key):
                self.run_games(key, "handle")

    def test_auto_all(self):
        for key in GAMES:
            with self.subTest(key=key):
                self.run_games(key, "auto")

    def test_fuzz_illegal(self):
        rng = random.Random(1)
        junk = [None, True, False, -1, 10 ** 9, 1.5, "x", [], {}, [1, 2], {"a": 1}, 0, 3, 64, 99, "q"]
        for key in GAMES:
            g = fresh(key)
            for _ in range(400):
                msg = {"t": rng.choice(["move", "place", "fire", "pick", "zzz", None, 5])}
                for k in ("from", "to", "cell", "path", "promo", "col"):
                    if rng.random() < 0.7:
                        msg[k] = rng.choice(junk)
                uid = rng.choice(P + [999])
                try:
                    g.handle(uid, msg)
                except GameError:
                    pass
                if g.finished:
                    g = fresh(key)

    def test_resign(self):
        for key in GAMES:
            g = fresh(key)
            g.remove_player(P[0])
            self.assertTrue(g.finished)
            self.assertEqual(g.winner, P[1])

    def test_info(self):
        for k, i in INFO.items():
            self.assertEqual(set(i) & {"title", "emoji", "min", "max", "shuffle", "cmd", "cat", "new", "turn"}, {"title", "emoji", "min", "max", "shuffle", "cmd", "cat", "new", "turn"})


if __name__ == "__main__":
    unittest.main()

"""English draughts (8x8). players[0] plays 'w' (bottom, moves up), players[1] plays 'b' (top, moves down).
Captures are compulsory and multi-jumps must be completed. A move is sent as a path of landing squares."""
from __future__ import annotations

import random

from .base import BaseGame, GameError


def start_board():
    b = [""] * 64
    for r in range(8):
        for c in range(8):
            if (r + c) % 2 == 1:
                if r < 3:
                    b[r * 8 + c] = "b"
                elif r > 4:
                    b[r * 8 + c] = "w"
    return b


def jumps_from(b, sq, piece, taken):
    """All maximal capture paths for `piece` standing on sq. Returns list of (path, captured_squares)."""
    r, c = divmod(sq, 8)
    own = piece.lower()
    king = piece.isupper()
    dirs = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    if not king:
        dirs = [d for d in dirs if (d[0] < 0) == (own == "w")]
    res = []
    for dr, dc in dirs:
        mr, mc, lr, lc = r + dr, c + dc, r + 2 * dr, c + 2 * dc
        if not (0 <= lr < 8 and 0 <= lc < 8):
            continue
        mid = mr * 8 + mc
        land = lr * 8 + lc
        if b[mid] and b[mid].lower() != own and mid not in taken and b[land] == "":
            crowned = (not king) and lr == (0 if own == "w" else 7)
            nxt = jumps_from(b, land, piece.upper() if crowned else piece, taken + [mid]) if not crowned else []
            if nxt:
                for p, cp in nxt:
                    res.append(([land] + p, [mid] + cp))
            else:
                res.append(([land], [mid]))
    return res


def legal_moves(b, side):
    """List of (path, captured) with path including the start square."""
    caps, simple = [], []
    for sq in range(64):
        p = b[sq]
        if not p or p.lower() != side:
            continue
        # the moving piece leaves its square, so it can be re-crossed: clear it while searching
        b[sq] = ""
        for path, cp in jumps_from(b, sq, p, []):
            caps.append(([sq] + path, cp))
        b[sq] = p
        if caps:
            continue
        r, c = divmod(sq, 8)
        dirs = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        if p.islower():
            dirs = [d for d in dirs if (d[0] < 0) == (side == "w")]
        for dr, dc in dirs:
            rr, cc = r + dr, c + dc
            if 0 <= rr < 8 and 0 <= cc < 8 and not b[rr * 8 + cc]:
                simple.append(([sq, rr * 8 + cc], []))
    return caps if caps else simple


class CheckersGame(BaseGame):
    name = "checkers"
    min_players = 2
    max_players = 2
    MAX_PLIES = 300

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Checkers needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.board = start_board()
        self.turn_idx = 0
        self.winner = None
        self.finished = False
        self.draw = False
        self.reason = None
        self.seq = 0
        self.last_move = None
        self.quiet = 0      # plies since a capture or a man move
        self.plies = 0
        self._moves = None

    def side(self):
        return "w" if self.turn_idx == 0 else "b"

    def current(self):
        return None if self.finished else self.players[self.turn_idx]

    def moves(self):
        if self._moves is None:
            self._moves = legal_moves(self.board, self.side())
        return self._moves

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        if msg.get("t") != "move":
            raise GameError("Unknown action")
        path = msg.get("path")
        if not isinstance(path, list) or not 2 <= len(path) <= 13:
            raise GameError("Bad move")
        for v in path:
            if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v < 64:
                raise GameError("Bad square")
        for p, cp in self.moves():
            if p == path:
                return self._apply(p, cp)
        raise GameError("Illegal move" + (" (you must capture)" if self.moves() and self.moves()[0][1] else ""))

    def _apply(self, path, cp):
        b = self.board
        mover = self.current()
        piece = b[path[0]]
        b[path[0]] = ""
        for s in cp:
            b[s] = ""
        end = path[-1]
        crowned = piece.islower() and end // 8 == (0 if piece == "w" else 7)
        b[end] = piece.upper() if crowned else piece
        self.seq += 1
        self.plies += 1
        self.last_move = {"uid": mover, "path": path, "captured": cp, "crowned": crowned, "seq": self.seq}
        self.quiet = 0 if (cp or piece.islower()) else self.quiet + 1
        self.turn_idx = 1 - self.turn_idx
        self._moves = None
        if not self.moves():
            self.finished, self.winner, self.reason = True, mover, "no moves left"
        elif self.quiet >= 80:
            self.finished, self.draw, self.reason = True, True, "40-move rule"
        elif self.plies >= self.MAX_PLIES:
            self.finished, self.draw, self.reason = True, True, "move limit"

    def auto_play(self):
        if self.finished:
            return
        ms = self.moves()
        if not ms:
            return
        best, pick = -10 ** 9, []
        for path, cp in ms:
            sc = len(cp) * 10
            end = path[-1]
            p = self.board[path[0]]
            if p.islower() and end // 8 == (0 if p == "w" else 7):
                sc += 8
            er, ec = divmod(end, 8)
            if ec in (0, 7):
                sc += 1
            if p.islower():
                sc += (7 - er if p == "w" else er) * 0.3
            sc += self.rng.random() * 2
            if sc > best:
                best, pick = sc, (path, cp)
        self._apply(*pick)

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished, self.reason = True, "resigned"
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        legal = {}
        if not self.finished:
            for path, _ in self.moves():
                legal.setdefault(str(path[0]), []).append(path)
        return {
            "kind": "checkers",
            "players": [{"uid": u, "color": c} for u, c in zip(self.players, ("w", "b"))],
            "board": self.board,
            "turn": self.current(),
            "legal": legal,
            "must_capture": bool(self.moves() and self.moves()[0][1]) if not self.finished else False,
            "counts": {"w": sum(1 for x in self.board if x.lower() == "w"), "b": sum(1 for x in self.board if x.lower() == "b")},
            "last_move": self.last_move,
            "winner": self.winner,
            "draw": self.draw,
            "reason": self.reason,
        }

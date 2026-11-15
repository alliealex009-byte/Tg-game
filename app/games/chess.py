"""Chess with full rules: check, checkmate, stalemate, castling, en passant, promotion, repetition, 50-move rule."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

START = ["bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR"] + ["bP"] * 8 + [""] * 32 + ["wP"] * 8 + ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR"]
VAL = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 0}
KN = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
KG = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
DIAG = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
ORTH = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _on(r, c):
    return 0 <= r < 8 and 0 <= c < 8


def attacked(b, sq, by):
    r, c = divmod(sq, 8)
    d = -1 if by == "w" else 1  # direction a pawn of colour `by` moves (towards rank decreasing for white)
    for dc in (-1, 1):
        rr, cc = r - d, c + dc
        if _on(rr, cc) and b[rr * 8 + cc] == by + "P":
            return True
    for dr, dc in KN:
        rr, cc = r + dr, c + dc
        if _on(rr, cc) and b[rr * 8 + cc] == by + "N":
            return True
    for dr, dc in KG:
        rr, cc = r + dr, c + dc
        if _on(rr, cc) and b[rr * 8 + cc] == by + "K":
            return True
    for dirs, kinds in ((DIAG, "BQ"), (ORTH, "RQ")):
        for dr, dc in dirs:
            rr, cc = r + dr, c + dc
            while _on(rr, cc):
                p = b[rr * 8 + cc]
                if p:
                    if p[0] == by and p[1] in kinds:
                        return True
                    break
                rr, cc = rr + dr, cc + dc
    return False


def king_sq(b, col):
    return b.index(col + "K")


def pseudo(b, col, ep, castle):
    """Yield (from, to, promo|None) pseudo-legal moves."""
    out = []
    opp = "b" if col == "w" else "w"
    for sq in range(64):
        p = b[sq]
        if not p or p[0] != col:
            continue
        r, c = divmod(sq, 8)
        k = p[1]
        if k == "P":
            d = -1 if col == "w" else 1
            start = 6 if col == "w" else 1
            last = 0 if col == "w" else 7
            rr = r + d
            if _on(rr, c) and not b[rr * 8 + c]:
                if rr == last:
                    out += [(sq, rr * 8 + c, q) for q in "QRBN"]
                else:
                    out.append((sq, rr * 8 + c, None))
                    if r == start and not b[(r + 2 * d) * 8 + c]:
                        out.append((sq, (r + 2 * d) * 8 + c, None))
            for dc in (-1, 1):
                cc = c + dc
                if not _on(rr, cc):
                    continue
                t = rr * 8 + cc
                if b[t] and b[t][0] == opp or t == ep:
                    if rr == last:
                        out += [(sq, t, q) for q in "QRBN"]
                    else:
                        out.append((sq, t, None))
        elif k in "NK":
            for dr, dc in (KN if k == "N" else KG):
                rr, cc = r + dr, c + dc
                if _on(rr, cc) and (not b[rr * 8 + cc] or b[rr * 8 + cc][0] == opp):
                    out.append((sq, rr * 8 + cc, None))
            if k == "K":
                home = 60 if col == "w" else 4
                if sq == home and not attacked(b, home, opp):
                    if castle.get(col + "K") and not b[home + 1] and not b[home + 2] and b[home + 3] == col + "R" \
                            and not attacked(b, home + 1, opp) and not attacked(b, home + 2, opp):
                        out.append((sq, home + 2, None))
                    if castle.get(col + "Q") and not b[home - 1] and not b[home - 2] and not b[home - 3] and b[home - 4] == col + "R" \
                            and not attacked(b, home - 1, opp) and not attacked(b, home - 2, opp):
                        out.append((sq, home - 2, None))
        else:
            dirs = DIAG if k == "B" else ORTH if k == "R" else DIAG + ORTH
            for dr, dc in dirs:
                rr, cc = r + dr, c + dc
                while _on(rr, cc):
                    t = b[rr * 8 + cc]
                    if not t:
                        out.append((sq, rr * 8 + cc, None))
                    else:
                        if t[0] == opp:
                            out.append((sq, rr * 8 + cc, None))
                        break
                    rr, cc = rr + dr, cc + dc
    return out


def make(b, mv, ep, castle):
    """Return (new_board, new_ep, new_castle, captured_piece, flags)."""
    frm, to, promo = mv
    nb = b[:]
    p = nb[frm]
    col, kind = p[0], p[1]
    cap = nb[to]
    flags = []
    if kind == "P" and to == ep and not cap:
        capsq = to + (8 if col == "w" else -8)
        cap = nb[capsq]
        nb[capsq] = ""
        flags.append("ep")
    nb[to], nb[frm] = p, ""
    if promo:
        nb[to] = col + promo
        flags.append("promo")
    if kind == "K" and abs(to - frm) == 2:
        if to > frm:
            nb[frm + 1], nb[frm + 3] = nb[frm + 3], ""
        else:
            nb[frm - 1], nb[frm - 4] = nb[frm - 4], ""
        flags.append("castle")
    nep = (frm + to) // 2 if kind == "P" and abs(to - frm) == 16 else None
    nc = dict(castle)
    if kind == "K":
        nc[col + "K"] = nc[col + "Q"] = False
    for sq, key in ((56, "wQ"), (63, "wK"), (0, "bQ"), (7, "bK")):
        if frm == sq or to == sq:
            nc[key] = False
    return nb, nep, nc, cap, flags


class ChessGame(BaseGame):
    name = "chess"
    min_players = max_players = 2

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Chess needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.color = {self.players[0]: "w", self.players[1]: "b"}
        self.board = START[:]
        self.turn_col = "w"
        self.ep = None
        self.castle = {"wK": True, "wQ": True, "bK": True, "bQ": True}
        self.half = 0
        self.seen = {}
        self.captured = {"w": [], "b": []}  # pieces captured BY that colour
        self.seq = 0
        self.last_move = None
        self.reason = ""
        self.winner, self.finished, self.draw = None, False, False
        self._note()

    def _uid(self, col):
        return next(u for u in self.players if self.color[u] == col)

    def current(self):
        return None if self.finished else self._uid(self.turn_col)

    def legal(self, col=None):
        col = col or self.turn_col
        opp = "b" if col == "w" else "w"
        res = []
        for mv in pseudo(self.board, col, self.ep, self.castle):
            nb, *_ = make(self.board, mv, self.ep, self.castle)
            if not attacked(nb, king_sq(nb, col), opp):
                res.append(mv)
        return res

    def _key(self):
        return (tuple(self.board), self.turn_col, self.ep, tuple(sorted(self.castle.items())))

    def _note(self):
        k = self._key()
        self.seen[k] = self.seen.get(k, 0) + 1

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        if msg.get("t") != "move":
            raise GameError("Unknown action")
        f, t, pr = msg.get("from"), msg.get("to"), msg.get("promo") or None
        if any(isinstance(x, bool) or not isinstance(x, int) for x in (f, t)):
            raise GameError("Bad move")
        cands = [m for m in self.legal() if m[0] == f and m[1] == t]
        if not cands:
            raise GameError("Illegal move")
        if len(cands) > 1:  # promotion
            pr = pr if pr in ("Q", "R", "B", "N") else "Q"
            cands = [m for m in cands if m[2] == pr]
        self._play(cands[0])

    def _play(self, mv):
        col = self.turn_col
        opp = "b" if col == "w" else "w"
        piece = self.board[mv[0]]
        nb, nep, nc, cap, flags = make(self.board, mv, self.ep, self.castle)
        self.half = 0 if (cap or piece[1] == "P") else self.half + 1
        self.board, self.ep, self.castle = nb, nep, nc
        if cap:
            self.captured[col].append(cap)
        self.turn_col = opp
        self.seq += 1
        legal = self.legal()
        chk = attacked(self.board, king_sq(self.board, opp), col)
        self.last_move = {"seq": self.seq, "uid": self._uid(col), "from": mv[0], "to": mv[1], "piece": piece,
                          "captured": cap or None, "promo": mv[2], "flags": flags, "check": chk}
        self._note()
        if not legal:
            self.finished = True
            if chk:
                self.winner, self.reason = self._uid(col), "checkmate"
            else:
                self.draw, self.reason = True, "stalemate"
        elif self.half >= 100:
            self.finished, self.draw, self.reason = True, True, "50-move rule"
        elif self.seen[self._key()] >= 3:
            self.finished, self.draw, self.reason = True, True, "threefold repetition"
        elif self._insufficient():
            self.finished, self.draw, self.reason = True, True, "insufficient material"

    def _insufficient(self):
        rest = [p for p in self.board if p and p[1] != "K"]
        if not rest:
            return True
        return len(rest) == 1 and rest[0][1] in "BN"

    def _score(self, mv):
        b = self.board
        s = self.rng.random() * 30
        tgt = b[mv[1]]
        if tgt:
            s += VAL[tgt[1]] * 10 - VAL[b[mv[0]][1]]
        if mv[2]:
            s += 800
        nb, nep, nc, cap, fl = make(b, mv, self.ep, self.castle)
        col = self.turn_col
        opp = "b" if col == "w" else "w"
        if attacked(nb, king_sq(nb, opp), col):
            s += 60
        if attacked(nb, mv[1], opp):  # moving onto an attacked square
            s -= VAL[b[mv[0]][1]] * 0.9
        r, c = divmod(mv[1], 8)
        s += (3.5 - abs(3.5 - r)) * 4 + (3.5 - abs(3.5 - c)) * 4 if b[mv[0]][1] in "NBP" else 0
        return s

    def auto_play(self):
        if self.finished:
            return
        mvs = self.legal()
        self._play(max(mvs, key=self._score))

    def remove_player(self, uid):
        if uid not in self.color or self.finished:
            return
        self.finished, self.winner, self.reason = True, next(u for u in self.players if u != uid), "resigned"

    def public_state(self):
        cur = self.current()
        dests = {}
        if not self.finished:
            for f, t, p in self.legal():
                dests.setdefault(f, [])
                if t not in dests[f]:
                    dests[f].append(t)
        return {
            "kind": "chess", "players": [{"uid": u, "color": self.color[u]} for u in self.players],
            "board": self.board, "turn": cur, "dests": dests, "last_move": self.last_move,
            "in_check": (not self.finished or self.reason == "checkmate") and attacked(self.board, king_sq(self.board, self.turn_col), "b" if self.turn_col == "w" else "w"),
            "captured": self.captured, "reason": self.reason, "winner": self.winner, "draw": self.draw,
        }

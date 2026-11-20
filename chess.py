"""Chess: full legal rules (castling, en passant, promotion, check/mate/stalemate, 50-move, repetition, dead position).
Squares are 0..63, index = row*8 + col, row 0 is rank 8 (black's back rank). White is players[0]."""
from __future__ import annotations

import random

from .base import BaseGame, GameError

START = "rnbqkbnrpppppppp" + "." * 32 + "PPPPPPPPRNBQKBNR"
KN = ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1))
KG = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
DIAG = ((-1, -1), (-1, 1), (1, -1), (1, 1))
ORTH = ((-1, 0), (1, 0), (0, -1), (0, 1))
VAL = {"p": 100, "n": 320, "b": 330, "r": 500, "q": 900, "k": 0}
PROMO = "qrbn"


def is_white(p):
    return p.isupper()


class Position:
    __slots__ = ("b", "turn", "castle", "ep", "half", "full")

    def __init__(self, b=None, turn="w", castle="KQkq", ep=-1, half=0, full=1):
        self.b = list(b if b is not None else START)
        self.turn, self.castle, self.ep, self.half, self.full = turn, castle, ep, half, full

    def copy(self):
        return Position(self.b, self.turn, self.castle, self.ep, self.half, self.full)

    @staticmethod
    def from_fen(fen):
        parts = fen.split()
        rows = parts[0].split("/")
        b = []
        for row in rows:
            for ch in row:
                b += ["."] * int(ch) if ch.isdigit() else [ch]
        ep = -1
        if parts[3] != "-":
            ep = (8 - int(parts[3][1])) * 8 + "abcdefgh".index(parts[3][0])
        return Position("".join(b), parts[1], parts[2] if parts[2] != "-" else "", ep,
                        int(parts[4]) if len(parts) > 4 else 0, int(parts[5]) if len(parts) > 5 else 1)

    # ---- attack detection
    def attacked(self, sq, by_white):
        b = self.b
        r, c = divmod(sq, 8)
        pawn, knight, king, bish, rook, queen = (("P", "N", "K", "B", "R", "Q") if by_white else ("p", "n", "k", "b", "r", "q"))
        pr = r + 1 if by_white else r - 1  # row where an attacking pawn would stand
        if 0 <= pr < 8:
            for dc in (-1, 1):
                if 0 <= c + dc < 8 and b[pr * 8 + c + dc] == pawn:
                    return True
        for dr, dc in KN:
            rr, cc = r + dr, c + dc
            if 0 <= rr < 8 and 0 <= cc < 8 and b[rr * 8 + cc] == knight:
                return True
        for dr, dc in KG:
            rr, cc = r + dr, c + dc
            if 0 <= rr < 8 and 0 <= cc < 8 and b[rr * 8 + cc] == king:
                return True
        for dirs, pieces in ((DIAG, (bish, queen)), (ORTH, (rook, queen))):
            for dr, dc in dirs:
                rr, cc = r + dr, c + dc
                while 0 <= rr < 8 and 0 <= cc < 8:
                    p = b[rr * 8 + cc]
                    if p != ".":
                        if p in pieces:
                            return True
                        break
                    rr += dr
                    cc += dc
        return False

    def king_sq(self, white):
        return self.b.index("K" if white else "k")

    def in_check(self, white=None):
        w = (self.turn == "w") if white is None else white
        return self.attacked(self.king_sq(w), not w)

    # ---- generation
    def pseudo(self):
        b, w = self.b, self.turn == "w"
        out = []
        for sq in range(64):
            p = b[sq]
            if p == "." or is_white(p) != w:
                continue
            r, c = divmod(sq, 8)
            k = p.lower()
            if k == "p":
                d = -1 if w else 1
                start, last = (6, 0) if w else (1, 7)
                r1 = r + d
                if 0 <= r1 < 8:
                    if b[r1 * 8 + c] == ".":
                        self._pawn_add(out, sq, r1 * 8 + c, r1 == last)
                        if r == start and b[(r + 2 * d) * 8 + c] == ".":
                            out.append((sq, (r + 2 * d) * 8 + c, ""))
                    for dc in (-1, 1):
                        cc = c + dc
                        if 0 <= cc < 8:
                            t = r1 * 8 + cc
                            if b[t] != "." and is_white(b[t]) != w:
                                self._pawn_add(out, sq, t, r1 == last)
                            elif t == self.ep:
                                out.append((sq, t, ""))
            elif k in "nk":
                for dr, dc in (KN if k == "n" else KG):
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < 8 and 0 <= cc < 8:
                        t = rr * 8 + cc
                        if b[t] == "." or is_white(b[t]) != w:
                            out.append((sq, t, ""))
                if k == "k":
                    self._castles(out, sq, w)
            else:
                dirs = DIAG if k == "b" else ORTH if k == "r" else DIAG + ORTH
                for dr, dc in dirs:
                    rr, cc = r + dr, c + dc
                    while 0 <= rr < 8 and 0 <= cc < 8:
                        t = rr * 8 + cc
                        if b[t] == ".":
                            out.append((sq, t, ""))
                        else:
                            if is_white(b[t]) != w:
                                out.append((sq, t, ""))
                            break
                        rr += dr
                        cc += dc
        return out

    @staticmethod
    def _pawn_add(out, f, t, promo):
        if promo:
            out += [(f, t, x) for x in PROMO]
        else:
            out.append((f, t, ""))

    def _castles(self, out, sq, w):
        b = self.b
        home = 60 if w else 4
        if sq != home or self.in_check(w):
            return
        rk = "R" if w else "r"
        if ("K" if w else "k") in self.castle and b[home + 1] == "." and b[home + 2] == "." and b[home + 3] == rk \
                and not self.attacked(home + 1, not w) and not self.attacked(home + 2, not w):
            out.append((sq, home + 2, ""))
        if ("Q" if w else "q") in self.castle and b[home - 1] == "." and b[home - 2] == "." and b[home - 3] == "." \
                and b[home - 4] == rk and not self.attacked(home - 1, not w) and not self.attacked(home - 2, not w):
            out.append((sq, home - 2, ""))

    def make(self, m):
        f, t, promo = m
        n = self.copy()
        b = n.b
        p = b[f]
        k = p.lower()
        w = p.isupper()
        cap = b[t] != "."
        b[t], b[f] = p, "."
        if k == "p":
            if t == self.ep and not cap:
                b[t + (8 if w else -8)] = "."
                cap = True
            if promo:
                b[t] = promo.upper() if w else promo
        if k == "k" and abs(t - f) == 2:
            if t > f:
                b[f + 1], b[f + 3] = b[f + 3], "."
            else:
                b[f - 1], b[f - 4] = b[f - 4], "."
        cr = n.castle
        for sq, ch in ((60, "KQ"), (4, "kq"), (63, "K"), (56, "Q"), (7, "k"), (0, "q")):
            if f == sq or t == sq:
                for x in ch:
                    cr = cr.replace(x, "")
        n.castle = cr
        n.ep = -1
        if k == "p" and abs(t - f) == 16:
            mid = (t + f) // 2
            enemy = "p" if w else "P"
            r, c = divmod(t, 8)
            if any(0 <= c + dc < 8 and b[r * 8 + c + dc] == enemy for dc in (-1, 1)):
                n.ep = mid
        n.half = 0 if (k == "p" or cap) else self.half + 1
        if self.turn == "b":
            n.full += 1
        n.turn = "b" if self.turn == "w" else "w"
        return n

    def legal(self):
        w = self.turn == "w"
        out = []
        for m in self.pseudo():
            n = self.make(m)
            if not n.attacked(n.king_sq(w), not w):
                out.append(m)
        return out

    def key(self):
        return ("".join(self.b), self.turn, self.castle, self.ep)

    def insufficient(self):
        pcs = [p for p in self.b if p != "." and p.lower() != "k"]
        if not pcs:
            return True
        if any(p.lower() in "prq" for p in pcs):
            return False
        if len(pcs) == 1:
            return True
        if all(p.lower() == "b" for p in pcs):  # only bishops: dead if all on one colour
            cols = {(i // 8 + i % 8) % 2 for i, p in enumerate(self.b) if p.lower() == "b"}
            return len(cols) == 1
        return False


def perft(pos, depth):
    if depth == 0:
        return 1
    ms = pos.legal()
    if depth == 1:
        return len(ms)
    return sum(perft(pos.make(m), depth - 1) for m in ms)


def sq_name(i):
    return "abcdefgh"[i % 8] + str(8 - i // 8)


# ---- tiny evaluation for the computer player
CENTER = [0, 0, 0, 0, 0, 0, 0, 0,
          0, 1, 1, 1, 1, 1, 1, 0,
          0, 1, 2, 2, 2, 2, 1, 0,
          0, 1, 2, 3, 3, 2, 1, 0,
          0, 1, 2, 3, 3, 2, 1, 0,
          0, 1, 2, 2, 2, 2, 1, 0,
          0, 1, 1, 1, 1, 1, 1, 0,
          0, 0, 0, 0, 0, 0, 0, 0]


def evaluate(pos):
    """Score from the side-to-move's point of view."""
    s = 0
    for i, p in enumerate(pos.b):
        if p == ".":
            continue
        k = p.lower()
        v = VAL[k] + (CENTER[i] * 6 if k in "nbpq" else 0)
        if k == "p":
            r = i // 8
            v += (6 - r if p == "P" else r - 1) * 4
        s += v if p.isupper() else -v
    return s if pos.turn == "w" else -s


def search(pos, depth, alpha, beta):
    ms = pos.legal()
    if not ms:
        return (-100000 - depth) if pos.in_check() else 0
    if depth == 0:
        return evaluate(pos)
    best = -10 ** 9
    # captures first for better pruning
    ms.sort(key=lambda m: pos.b[m[1]] != ".", reverse=True)
    for m in ms:
        v = -search(pos.make(m), depth - 1, -beta, -alpha)
        if v > best:
            best = v
        alpha = max(alpha, v)
        if alpha >= beta:
            break
    return best


class ChessGame(BaseGame):
    name = "chess"
    min_players = 2
    max_players = 2
    ai_depth = 2
    MAX_PLIES = 400

    def __init__(self, players, rng=None):
        if len(players) != 2:
            raise ValueError("Chess needs exactly 2 players")
        self.rng = rng or random.SystemRandom()
        self.players = list(players)
        self.pos = Position()
        self.winner = None
        self.finished = False
        self.draw = False
        self.reason = None
        self.seq = 0
        self.last_move = None
        self.plies = 0
        self.reps = {self.pos.key(): 1}
        self.captured = {"w": [], "b": []}  # pieces captured BY that colour

    def current(self):
        return None if self.finished else self.players[0 if self.pos.turn == "w" else 1]

    def legal_moves(self):
        return [] if self.finished else self.pos.legal()

    def handle(self, uid, msg):
        if self.finished:
            raise GameError("The game is over")
        if uid != self.current():
            raise GameError("It's not your turn")
        if msg.get("t") != "move":
            raise GameError("Unknown action")
        f, t, promo = msg.get("from"), msg.get("to"), msg.get("promo", "q")
        for v in (f, t):
            if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v < 64:
                raise GameError("Bad square")
        if not isinstance(promo, str):
            raise GameError("Bad promotion")
        promo = promo.lower() or "q"
        if promo not in PROMO:
            raise GameError("Bad promotion piece")
        p = self.pos.b[f]
        is_promo = p != "." and p.lower() == "p" and (t < 8 or t >= 56)
        m = (f, t, promo if is_promo else "")
        if m not in self.pos.legal():
            raise GameError("Illegal move")
        self._apply(m)

    def _apply(self, m):
        pos = self.pos
        mover = self.current()
        f, t, promo = m
        piece = pos.b[f]
        target = pos.b[t]
        ep_cap = piece.lower() == "p" and t == pos.ep and target == "."
        captured = target if target != "." else ("p" if piece == "P" else "P") if ep_cap else None
        castle = piece.lower() == "k" and abs(t - f) == 2
        side = pos.turn
        if captured:
            self.captured[side].append(captured)
        self.pos = pos.make(m)
        self.plies += 1
        self.seq += 1
        n = self.pos
        check = n.in_check()
        legal = n.legal()
        self.last_move = {"uid": mover, "from": f, "to": t, "promo": promo, "piece": piece, "capture": captured,
                          "ep": ep_cap, "castle": castle, "check": check, "san": self._san(pos, m, check, not legal), "seq": self.seq}
        k = n.key()
        self.reps[k] = self.reps.get(k, 0) + 1
        if not legal:
            self.finished = True
            if check:
                self.winner, self.reason = mover, "checkmate"
            else:
                self.draw, self.reason = True, "stalemate"
        elif n.insufficient():
            self.finished, self.draw, self.reason = True, True, "insufficient material"
        elif n.half >= 100:
            self.finished, self.draw, self.reason = True, True, "50-move rule"
        elif self.reps[k] >= 3:
            self.finished, self.draw, self.reason = True, True, "threefold repetition"
        elif self.plies >= self.MAX_PLIES:
            self.finished, self.draw, self.reason = True, True, "move limit"

    @staticmethod
    def _san(pos, m, check, mate):
        f, t, promo = m
        p = pos.b[f]
        if p.lower() == "k" and abs(t - f) == 2:
            s = "O-O" if t > f else "O-O-O"
        else:
            cap = pos.b[t] != "." or (p.lower() == "p" and t == pos.ep)
            s = ("" if p.lower() == "p" else p.upper()) + (sq_name(f)[0] if p.lower() == "p" and cap else "") + ("x" if cap else "") + sq_name(t)
            if promo:
                s += "=" + promo.upper()
        return s + ("#" if mate else "+" if check else "")

    # ---- computer player
    def pick(self):
        ms = self.pos.legal()
        if not ms:
            return None
        if self.ai_depth <= 0:
            return self.rng.choice(ms)
        best, scored = -10 ** 9, []
        for m in ms:
            v = -search(self.pos.make(m), self.ai_depth - 1, -10 ** 9, 10 ** 9)
            v += self.rng.random() * 6  # variety
            scored.append((v, m))
            best = max(best, v)
        return max(scored)[1]

    def auto_play(self):
        if self.finished:
            return
        m = self.pick()
        if m is None:
            return
        self._apply(m)

    def remove_player(self, uid):
        if uid not in self.players or self.finished:
            return
        self.finished = True
        self.reason = "resigned"
        self.winner = next(u for u in self.players if u != uid)

    def public_state(self):
        pos = self.pos
        legal = {}
        if not self.finished:
            for f, t, p in pos.legal():
                legal.setdefault(f, [])
                if t not in legal[f]:
                    legal[f].append(t)
        return {
            "kind": "chess",
            "players": [{"uid": u, "color": c} for u, c in zip(self.players, ("w", "b"))],
            "board": "".join(pos.b),
            "turn": self.current(),
            "side": pos.turn,
            "legal": {str(k): v for k, v in legal.items()},
            "in_check": (pos.king_sq(pos.turn == "w") if (not self.finished or self.reason == "checkmate") and pos.in_check() else None),
            "captured": self.captured,
            "last_move": self.last_move,
            "winner": self.winner,
            "draw": self.draw,
            "reason": self.reason,
            "plies": self.plies,
        }

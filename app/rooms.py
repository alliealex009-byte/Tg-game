"""Room manager: lobbies, entry fees and payouts, turn timers, AFK handling, bots, broadcasting.

Deliberately free of web-framework imports. A "websocket" is any object with `async send_json(dict)`.
All state lives in memory, so run a single server process.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import secrets
import time

from .games import GAME_INFO, GAMES
from .games.base import GameError

log = logging.getLogger("rooms")
ROOM_MEMORY_H = 24

BOT_NAMES = ["Bot Ravi", "Bot Mia", "Bot Zed", "Bot Luna", "Bot Kai", "Bot Nova"]
KICK_AFTER = 4   # consecutive turn timeouts before a human is removed from a running game
AFK_AFTER = 2    # timeouts before a player is flagged AFK (their turns then play out quickly)
CHAT_KEEP = 40


class Player:
    def __init__(self, uid, name, username=None, photo=None, is_bot=False, coins=0):
        self.uid, self.name, self.username, self.photo = uid, name, username, photo
        self.is_bot, self.coins = is_bot, coins
        self.afk_count, self.afk = 0, False

    def public(self, online: bool, left: bool):
        return {
            "uid": self.uid, "name": self.name, "username": self.username, "photo": self.photo,
            "is_bot": self.is_bot, "coins": self.coins, "online": online or self.is_bot,
            "afk": self.afk, "left": left,
        }


class Room:
    def __init__(self, code, game_type, creator_id, bet, turn_seconds):
        info = GAME_INFO[game_type]
        self.code, self.game_type, self.creator_id, self.bet = code, game_type, creator_id, bet
        self.min_players, self.max_players = info["min"], info["max"]
        self.turn_seconds = turn_seconds
        self.phase_id = None
        self.players: list[Player] = []
        self.status = "lobby"  # lobby | playing | finished
        self.game = None
        self.conns: dict[int, set] = {}
        self.left: set[int] = set()
        self.result = None
        self.pot = 0
        self.version = 0
        self.deadline = None
        self.timer_task = None
        self.timer_token = 0
        self.chat: list[dict] = []
        self.last_chat: dict[int, float] = {}
        self.watchers: dict[int, str] = {}   # spectators: uid -> name
        self.last_react: dict[int, float] = {}
        self.host_away_since = None
        self.touched = time.time()

    def player(self, uid):
        return next((p for p in self.players if p.uid == uid), None)

    def humans(self):
        return [p for p in self.players if not p.is_bot]

    def host_id(self):
        if self.player(self.creator_id):
            return self.creator_id
        h = self.humans()
        return h[0].uid if h else None

    def snapshot(self, you):
        tl = None
        if self.status == "playing" and self.deadline is not None:
            tl = max(0.0, self.deadline - time.monotonic())
        info = GAME_INFO[self.game_type]
        return {
            "t": "state", "v": self.version, "you": you, "code": self.code,
            "game_type": self.game_type, "title": info["title"], "emoji": info["emoji"],
            "status": self.status, "bet": self.bet, "host": self.host_id(),
            "min_players": self.min_players, "max_players": self.max_players,
            "players": [p.public(bool(self.conns.get(p.uid)), p.uid in self.left) for p in self.players],
            "game": self.game.view(you) if self.game else None,
            "watching": sum(1 for u in self.watchers if self.conns.get(u)),
            "watchers": [{"uid": u, "name": n} for u, n in list(self.watchers.items()) if self.conns.get(u)][:12],
            "spectator": self.player(you) is None,
            "time_left": tl, "turn_seconds": (getattr(self.game, "phase_seconds", None) or self.turn_seconds), "result": self.result,
        }


class RoomManager:
    def __init__(self, db, settings):
        self.db, self.s = db, settings
        self.rooms: dict[str, Room] = {}

    # ---------- lifecycle ----------
    def create(self, creator_id: int, game_type: str, bet: int) -> Room:
        if game_type not in GAMES:
            raise GameError("Unknown game")
        if not isinstance(bet, int) or isinstance(bet, bool) or not 0 <= bet <= 100000:
            raise GameError("Invalid bet")
        u = self.db.get_user(creator_id)
        if bet and (u is None or u["coins"] < bet):
            raise GameError("You don't have enough coins for that bet")
        if len(self.rooms) >= 5000:
            raise GameError("Server is busy, try again later")
        code = secrets.token_hex(4).upper()
        while code in self.rooms:
            code = secrets.token_hex(4).upper()
        room = Room(code, game_type, creator_id, bet, GAME_INFO[game_type].get("turn", self.s.turn_seconds))
        self.rooms[code] = room
        try:   # remember the room so an invite link still works after a server restart
            self.db.kv_set(f"room:{code}", json.dumps({"g": game_type, "c": creator_id, "b": bet, "t": time.time()}))
        except Exception:
            log.exception("could not persist room")
        return room

    def get(self, code):
        code = (code or "").strip().upper()
        room = self.rooms.get(code)
        return room if room is not None else self._revive(code)

    def _revive(self, code):
        """Bring back an empty lobby for a room that vanished (restart / idle cleanup) so shared invites keep working."""
        if not (3 <= len(code) <= 16) or not code.isalnum():
            return None
        try:
            rec = json.loads(self.db.kv_get(f"room:{code}") or "null")
            if not isinstance(rec, dict) or time.time() - float(rec["t"]) > ROOM_MEMORY_H * 3600 or rec["g"] not in GAMES:
                return None
            room = Room(code, rec["g"], int(rec["c"]), int(rec["b"]), GAME_INFO[rec["g"]].get("turn", self.s.turn_seconds))
        except (ValueError, KeyError, TypeError):
            return None
        self.rooms[code] = room
        return room

    def _forget_old_rooms(self):
        try:
            for r in self.db.c.execute("SELECT k, v FROM kv WHERE k LIKE 'room:%'").fetchall():
                try:
                    old = time.time() - float(json.loads(r["v"])["t"]) > ROOM_MEMORY_H * 3600
                except (ValueError, KeyError, TypeError):
                    old = True
                if old:
                    self.db.c.execute("DELETE FROM kv WHERE k=?", (r["k"],))
        except Exception:
            log.exception("room memory cleanup failed")

    def _destroy(self, room: Room):
        self._cancel_timer(room)
        self.rooms.pop(room.code, None)

    async def janitor(self):
        while True:
            await asyncio.sleep(60)
            now = time.time()
            if int(now // 60) % 60 == 0:
                self._forget_old_rooms()
            for room in list(self.rooms.values()):
                idle = now - room.touched
                if (not room.conns and idle > 4 * 3600) or idle > 8 * 3600:
                    self._destroy(room)

    # ---------- connections ----------
    async def join(self, room: Room, user: dict, ws):
        uid = user["id"]
        room.touched = time.time()
        p = room.player(uid)
        if p is None and room.status == "lobby" and len(room.players) < room.max_players:
            if room.bet and user["coins"] < room.bet:
                raise GameError(f"You need {room.bet} coins to join this room")
            room.players.append(Player(uid, user["name"], user.get("username"), user.get("photo"), coins=user["coins"]))
        elif p is not None:
            p.name, p.photo, p.coins = user["name"], user.get("photo") or p.photo, user["coins"]
            room.watchers.pop(uid, None)
        else:  # game running or room full: watch instead of being turned away
            room.watchers[uid] = user["name"]
        room.conns.setdefault(uid, set()).add(ws)
        await self.broadcast(room)

    async def disconnect(self, room: Room, uid: int, ws):
        s = room.conns.get(uid)
        if s is not None:
            s.discard(ws)
            if not s:
                room.conns.pop(uid, None)
                room.watchers.pop(uid, None)
        room.touched = time.time()
        if room.code in self.rooms:
            await self.broadcast(room)

    async def _send(self, ws, payload):
        try:
            await asyncio.wait_for(ws.send_json(payload), 5)
            return None
        except Exception:
            return ws

    async def broadcast(self, room: Room):
        room.version += 1
        jobs = []
        for uid, sockets in list(room.conns.items()):
            snap = room.snapshot(uid)
            jobs += [self._send(ws, snap) for ws in list(sockets)]
        if jobs:
            await asyncio.gather(*jobs)

    async def _broadcast_raw(self, room: Room, payload: dict):
        jobs = [self._send(ws, payload) for s in list(room.conns.values()) for ws in list(s)]
        if jobs:
            await asyncio.gather(*jobs)

    # ---------- messages ----------
    async def handle(self, room: Room, uid: int, msg: dict):
        t = msg.get("t")
        room.touched = time.time()
        if t == "start":
            await self.start(room, uid)
        elif t == "add_bot":
            await self.add_bot(room, uid)
        elif t == "remove_bot":
            await self.remove_bot(room, uid, msg.get("uid"))
        elif t == "leave":
            await self.leave(room, uid)
        elif t == "rematch":
            await self.rematch(room, uid)
        elif t == "chat":
            await self.chat(room, uid, msg.get("text"))
        elif t == "react":
            await self.react(room, uid, msg.get("e"))
        elif t == "sit":
            await self.sit(room, uid)
        elif isinstance(t, str):  # anything else is a game action; the engine validates it
            await self.action(room, uid, msg)
        else:
            raise GameError("Unknown message")

    async def add_bot(self, room, uid):
        if room.status != "lobby":
            raise GameError("The game already started")
        if uid != room.host_id():
            raise GameError("Only the host can add bots")
        if room.bet:
            raise GameError("Bots can only join free games")
        if len(room.players) >= room.max_players:
            raise GameError("The room is full")
        used = {p.name for p in room.players}
        name = next((n for n in BOT_NAMES if n not in used), f"Bot {secrets.token_hex(1).upper()}")
        bot_uid = -1
        while room.player(bot_uid):
            bot_uid -= 1
        room.players.append(Player(bot_uid, name, None, None, is_bot=True))
        await self.broadcast(room)

    async def remove_bot(self, room, uid, bot_uid):
        if room.status != "lobby" or uid != room.host_id():
            raise GameError("Only the host can do that in the lobby")
        p = room.player(bot_uid) if isinstance(bot_uid, int) else None
        if p is None or not p.is_bot:
            raise GameError("No such bot")
        room.players.remove(p)
        await self.broadcast(room)

    async def start(self, room, uid):
        if room.status != "lobby":
            raise GameError("The game already started")
        if uid != room.host_id():
            raise GameError("Only the host can start the game")
        n = len(room.players)
        if n < room.min_players:
            raise GameError(f"Need at least {room.min_players} players")
        humans = [p.uid for p in room.humans()]
        room.pot = 0
        if room.bet:
            bad = self.db.charge_all(humans, room.bet, f"bet:{room.code}")
            if bad is not None:
                who = room.player(bad)
                raise GameError(f"{who.name if who else 'A player'} doesn't have enough coins")
            room.pot = room.bet * len(humans)
        for p in room.humans():
            u = self.db.get_user(p.uid)
            if u:
                p.coins = u["coins"]
            p.afk_count, p.afk = 0, False
        order = [p.uid for p in room.players]
        if GAME_INFO[room.game_type]["shuffle"]:
            random.SystemRandom().shuffle(order)
        room.game = GAMES[room.game_type](order)
        room.status, room.result, room.left = "playing", None, set()
        await self._after(room)

    async def action(self, room, uid, msg):
        if room.status != "playing" or room.game is None:
            raise GameError("The game isn't running")
        p = room.player(uid)
        if p is None or uid in room.left:
            raise GameError("You are not playing")
        room.game.handle(uid, msg)
        p.afk_count, p.afk = 0, False
        await self._after(room)

    async def leave(self, room, uid):
        p = room.player(uid)
        if p is None:
            return
        if room.status == "lobby" or room.status == "finished":
            room.players.remove(p)
            if room.status == "lobby" and not room.humans() and not room.conns:
                self._destroy(room)
                return
            await self.broadcast(room)
        else:
            await self._remove_from_game(room, uid)

    async def rematch(self, room, uid):
        if room.status != "finished":
            raise GameError("The game is still running")
        if room.player(uid) is None:
            raise GameError("You are not in this game")
        room.players = [p for p in room.players if p.uid not in room.left]
        room.status, room.game, room.result, room.left = "lobby", None, None, set()
        for p in room.players:
            p.afk_count, p.afk = 0, False
        await self.broadcast(room)

    REACTIONS = ("😂", "🔥", "👏", "😮", "😡", "❤️", "👍", "😭", "🎉", "🤯", "💀", "🙏")

    async def react(self, room, uid, e):
        if e not in self.REACTIONS:
            return
        now = time.time()
        if now - room.last_react.get(uid, 0) < 0.35:
            return
        room.last_react[uid] = now
        p = room.player(uid)
        name = p.name if p else room.watchers.get(uid, "Viewer")
        await self._broadcast_raw(room, {"t": "react", "uid": uid, "name": name, "e": e})

    async def sit(self, room, uid):
        """A spectator takes a free seat while the room is in the lobby."""
        if room.player(uid) is not None:
            return
        if room.status != "lobby":
            raise GameError("Wait for the next round to take a seat")
        if len(room.players) >= room.max_players:
            raise GameError("The room is full")
        u = self.db.get_user(uid)
        if room.bet and u["coins"] < room.bet:
            raise GameError(f"You need {room.bet} coins to join this room")
        room.players.append(Player(uid, u["name"], u.get("username"), u.get("photo"), coins=u["coins"]))
        room.watchers.pop(uid, None)
        await self.broadcast(room)

    async def host_watch(self):
        """If the host has been offline for 70 s, hand the room to another connected player."""
        while True:
            await asyncio.sleep(5)
            now = time.time()
            for room in list(self.rooms.values()):
                if room.status == "playing":
                    room.host_away_since = None
                    continue
                h = room.host_id()
                if h is None or room.conns.get(h) or not any(not p.is_bot and room.conns.get(p.uid) for p in room.players):
                    room.host_away_since = None
                    continue
                room.host_away_since = room.host_away_since or now
                if now - room.host_away_since >= 70:
                    new = next((p for p in room.players if not p.is_bot and p.uid != h and room.conns.get(p.uid)), None)
                    if new:
                        room.creator_id, room.host_away_since = new.uid, None
                        await self.broadcast(room)
                        await self._broadcast_raw(room, {"t": "toast", "msg": f"👑 {new.name} is the new host (old host was away)"})

    async def chat(self, room, uid, text):
        if not isinstance(text, str):
            return
        text = " ".join(text.split())[:80]
        now = time.time()
        if not text or now - room.last_chat.get(uid, 0) < 0.8:
            return
        room.last_chat[uid] = now
        p = room.player(uid)
        u = None if p else self.db.get_user(uid)
        name = p.name if p else (u["name"] if u else "Viewer")
        entry = {"t": "chat", "uid": uid, "name": name, "text": text, "ts": int(now)}
        room.chat = (room.chat + [entry])[-CHAT_KEEP:]
        await self._broadcast_raw(room, entry)

    # ---------- game flow ----------
    async def _after(self, room):
        if room.game.finished:
            self._finish(room)
        else:
            self._schedule(room)
        await self.broadcast(room)

    async def _remove_from_game(self, room, uid):
        if room.status != "playing" or room.game is None:
            return
        room.left.add(uid)
        room.game.remove_player(uid)
        still_in = [p for p in room.humans() if p.uid not in room.left]
        if not still_in and not room.game.finished:  # only bots left: nobody to play for
            room.game.finished, room.game.winner = True, None
        await self._after(room)

    def _finish(self, room):
        if room.status == "finished":
            return
        g = room.game
        room.status = "finished"
        self._cancel_timer(room)
        room.deadline = None
        humans = [p.uid for p in room.humans()]
        winner = g.winner if (g.winner is not None and g.winner > 0) else None
        wl = [w for w in (g.winners or []) if w in humans]
        if wl:
            winner = wl[0]
        elif winner is not None:
            wl = [winner]
        pot, rake, prize, share = room.pot, 0, 0, 0
        if room.bet and pot:
            if not wl:  # draw / nobody to pay: refund everyone
                for u in humans:
                    self.db.add_coins(u, room.bet, f"refund:{room.code}")
            else:
                rake = pot * self.s.rake_percent // 100
                prize = pot - rake
                share = prize // len(wl)
                for w in wl:
                    self.db.add_coins(w, share, f"win:{room.code}")
                prize = share * len(wl)
        room.pot = 0
        self.db.record_result(room.game_type, room.code, room.bet, humans, winner, prize, wl if len(wl) > 1 else None)
        for p in room.humans():
            u = self.db.get_user(p.uid)
            if u:
                p.coins = u["coins"]
        room.result = {"winner": g.winner, "draw": bool(g.draw), "pot": pot, "rake": rake, "prize": share or prize,
                       "winners": wl if len(wl) > 1 else None, "share": share}

    # ---------- timers ----------
    def _cancel_timer(self, room):
        t = room.timer_task
        room.timer_task = None
        if t is not None and t is not asyncio.current_task():
            t.cancel()

    def _schedule(self, room):
        self._cancel_timer(room)
        g = room.game
        if room.status != "playing" or g is None or g.finished:
            room.deadline = None
            return
        p = room.player(g.current())
        if p is None:
            return
        if p.is_bot:
            delay, room.deadline = random.uniform(*self.s.bot_delay), None
        elif p.afk:
            delay, room.deadline = 1.0, None
        else:
            delay = getattr(g, "phase_seconds", None) or room.turn_seconds
            pid = getattr(g, "phase_id", None)  # simultaneous-action games: keep one deadline per phase
            if pid is not None and getattr(room, "phase_id", None) == pid and room.deadline is not None:
                delay = max(0.3, room.deadline - time.monotonic())
            else:
                room.deadline = time.monotonic() + delay
            room.phase_id = pid
            room.deadline = time.monotonic() + delay
        kind = "phase"
        due = g.bot_due() if hasattr(g, "bot_due") and not p.is_bot and not p.afk else None
        if due is not None and due < delay:       # a bot has something to do before the phase deadline
            delay, kind = max(0.05, due + 0.02), "bot"
        room.timer_token += 1
        room.timer_task = asyncio.create_task(self._timer(room, delay, room.timer_token, kind))

    async def _timer(self, room, delay, token, kind="phase"):
        try:
            await asyncio.sleep(delay)
            if room.timer_token != token or room.status != "playing":
                return
            room.timer_task = None  # we are the running task; don't let _schedule cancel us
            if kind == "bot":
                room.game.bot_event()
                await self._after(room)
                return
            uid = room.game.current()
            p = room.player(uid)
            if p is not None and not p.is_bot and not getattr(room.game, "ticker", False):
                p.afk_count += 1
                p.afk = p.afk_count >= AFK_AFTER
                if p.afk_count >= KICK_AFTER:
                    await self._remove_from_game(room, uid)
                    return
            try:
                room.game.auto_play()
            except GameError:
                log.exception("auto_play failed in room %s", room.code)
                return
            await self._after(room)
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("timer crashed in room %s", room.code)

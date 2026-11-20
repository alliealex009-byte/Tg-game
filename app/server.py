"""FastAPI app: REST for profile/coins, a WebSocket for live rooms, static mini app, and the bot (polling).

Run with ONE worker (rooms live in memory):  uvicorn app.server:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import time

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .auth import AuthError, user_from_init_data
from .config import load_settings
from .db import DB
from . import broadcast as bcast
from .arcade import Arcade
from .idle import Idle
from .games import GAME_INFO, GAMES
from .howto import ARCADE_TIPS, HOWTO
from .games.base import GameError
from .rooms import RoomManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("server")

settings = load_settings()
db = DB(settings.db_path, settings.starting_coins, settings.daily_bonus)
rooms = RoomManager(db, settings)
arcade = Arcade(db)
idle = Idle(arcade)
WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webapp")
BETS = [0, 50, 100, 500, 1000]


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bot_username = ""
    app.state.bot = None
    tasks = [asyncio.create_task(rooms.janitor()), asyncio.create_task(rooms.host_watch())]
    mongo = None
    if settings.mongo_uri:
        try:
            from .mongo_sync import MongoSync, connect

            mongo = MongoSync(db, await asyncio.to_thread(connect, settings.mongo_uri, settings.mongo_db))
            await asyncio.to_thread(mongo.restore)
            await asyncio.to_thread(mongo.flush)
            tasks.append(asyncio.create_task(mongo.run()))
            log.info("MongoDB sync on (database %s)", settings.mongo_db)
        except Exception:
            log.exception("MongoDB unavailable, continuing with SQLite only (check MONGO_URI)")
            mongo = None
    bot = None
    if settings.bot_token:
        try:
            from .bot import build, prepare

            bot, dp, ctx = build(settings, db, rooms)
            await prepare(bot, settings, ctx)
            app.state.bot_username = ctx["username"]
            app.state.bot = bot
            tasks.append(
                asyncio.create_task(
                    dp.start_polling(bot, handle_signals=False, allowed_updates=dp.resolve_used_update_types())
                )
            )
            log.info("Bot @%s started", ctx["username"])
        except Exception:
            log.exception("Bot failed to start (check BOT_TOKEN). The web server keeps running.")
    else:
        log.warning("BOT_TOKEN is empty: running web server only")
    if settings.dev_mode:
        log.warning("DEV_MODE is ON: anyone can log in as any user. Never use this in production.")
    yield
    for t in tasks:
        t.cancel()
    if mongo:
        with contextlib.suppress(Exception):
            await asyncio.to_thread(mongo.flush)
    if bot:
        with contextlib.suppress(Exception):
            await bot.session.close()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def no_cache(request: Request, call_next):
    resp = await call_next(request)
    if not request.url.path.startswith("/api"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


def public_user(u: dict) -> dict:
    return {k: u[k] for k in ("id", "name", "username", "photo", "coins", "games", "wins")}


def auth_user(request: Request) -> dict:
    try:
        tg = user_from_init_data(request.headers.get("x-init-data", ""), settings)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    u = db.upsert_user(tg["id"], tg["name"], tg["username"], tg["photo"])
    if u.get("banned"):
        raise HTTPException(status_code=403, detail="Your account is banned")
    return u


@app.get("/healthz")
async def healthz():
    return {"ok": True, "rooms": len(rooms.rooms)}


@app.get("/api/config")
async def config():
    return {
        "bot": app.state.bot_username,
        "app": settings.app_short_name,
        "games": GAME_INFO,
        "bets": BETS,
        "daily": settings.daily_bonus,
        "rake": settings.rake_percent,
        "dev": settings.dev_mode,
        "owner": {"name": settings.owner_name, "username": settings.owner_username},
        "sister": settings.sister_bot,
        "howto": HOWTO,
        "arcade_tips": ARCADE_TIPS,
        "version": "2.1",
    }


@app.post("/api/me")
async def me(request: Request):
    u = auth_user(request)
    return {"user": public_user(u), "daily_wait": db.daily_wait(u["id"]), "is_admin": u["id"] in settings.admin_ids}


@app.post("/api/daily")
async def daily(request: Request):
    u = auth_user(request)
    ok, coins, wait = db.claim_daily(u["id"])
    return {"claimed": ok, "coins": coins, "wait": wait, "bonus": getattr(db, "last_bonus", settings.daily_bonus) if ok else settings.daily_bonus}


@app.get("/api/leaderboard")
async def leaderboard():
    return {"rows": [{k: r[k] for k in ("id", "name", "username", "photo", "wins", "games")} for r in db.leaderboard(15)]}


@app.post("/api/room")
async def create_room(request: Request):
    u = auth_user(request)
    try:
        data = await request.json()
        game, bet = data.get("game"), data.get("bet", 0)
    except Exception:
        raise HTTPException(400, "Bad request")
    try:
        room = rooms.create(u["id"], game, bet)
    except GameError as e:
        raise HTTPException(400, str(e))
    return {"code": room.code}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    room, uid = None, None
    window = []  # recent message timestamps for a basic flood guard
    try:
        while True:
            raw = await ws.receive_text()
            now = time.monotonic()
            window = [x for x in window if now - x < 5] + [now]
            if len(window) > 120:
                await ws.send_json({"t": "error", "fatal": True, "msg": "Too many requests"})
                break
            if len(raw) > 2000:
                continue
            try:
                msg = json.loads(raw)
                if not isinstance(msg, dict):
                    raise ValueError
            except ValueError:
                await ws.send_json({"t": "error", "msg": "Bad message"})
                continue
            t = msg.get("t")
            if t == "ping":
                await ws.send_json({"t": "pong"})
                continue
            try:
                if room is None:
                    if t != "join":
                        continue
                    try:
                        tg = user_from_init_data(str(msg.get("initData", "")), settings)
                    except AuthError as e:
                        await ws.send_json({"t": "error", "fatal": True, "msg": str(e)})
                        break
                    r = rooms.get(str(msg.get("room", "")))
                    if r is None:
                        await ws.send_json({"t": "error", "fatal": True, "msg": "Room not found or expired"})
                        break
                    user = db.upsert_user(tg["id"], tg["name"], tg["username"], tg["photo"])
                    if user.get("banned"):
                        await ws.send_json({"t": "error", "fatal": True, "msg": "Your account is banned"})
                        break
                    await rooms.join(r, user, ws)
                    room, uid = r, user["id"]
                    for entry in r.chat[-15:]:
                        await ws.send_json(entry)
                else:
                    await rooms.handle(room, uid, msg)
            except GameError as e:
                fatal = room is None
                await ws.send_json({"t": "error", "msg": str(e), "fatal": fatal})
                if fatal:
                    break
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("websocket crashed")
    finally:
        if room is not None:
            await rooms.disconnect(room, uid, ws)
        with contextlib.suppress(Exception):
            await ws.close()


async def body(request: Request) -> dict:
    try:
        d = await request.json()
    except Exception:
        raise HTTPException(400, "Bad request")
    if not isinstance(d, dict):
        raise HTTPException(400, "Bad request")
    return d


def arc_call(fn, *a):
    try:
        return fn(*a)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/arcade/start")
async def arcade_start(request: Request):
    u, d = auth_user(request), await body(request)
    arc_call(arcade.start, u["id"], d.get("game"))
    return {"ok": True, "left": arcade.left_today(u["id"])}


@app.post("/api/arcade/claim")
async def arcade_claim(request: Request):
    u, d = auth_user(request), await body(request)
    return arc_call(arcade.claim, u["id"], d.get("game"), d.get("score"))


@app.post("/api/tap")
async def tap(request: Request):
    u, d = auth_user(request), await body(request)
    if d.get("n") is None:
        return arcade.tap_state(u["id"])
    return arc_call(arcade.tap, u["id"], d.get("n"))


@app.post("/api/tap/upgrade")
async def tap_upgrade(request: Request):
    u = auth_user(request)
    return arc_call(arcade.tap_upgrade, u["id"])


@app.post("/api/farm")
async def farm(request: Request):
    u, d = auth_user(request), await body(request)
    if not d.get("action"):
        return arcade.farm_state(u["id"])
    return arc_call(arcade.farm_act, u["id"], d.get("idx"), d.get("action"))


@app.post("/api/idle/{kind}")
async def idle_api(kind: str, request: Request):
    u, d = auth_user(request), await body(request)
    if not d.get("action"):
        return arc_call(idle.state, kind, u["id"])
    return arc_call(idle.act, kind, u["id"], d.get("action"), d.get("arg"))


def owner_user(request: Request) -> dict:
    u = auth_user(request)
    if u["id"] not in settings.admin_ids:
        raise HTTPException(403, "Owner only")
    return u


@app.post("/api/owner/stats")
async def owner_stats(request: Request):
    owner_user(request)
    st = db.stats()
    st["live_rooms"] = len(rooms.rooms)
    st["online"] = sum(len(r.conns) for r in rooms.rooms.values())
    return st


@app.post("/api/owner/user")
async def owner_user_action(request: Request):
    owner_user(request)
    d = await body(request)
    uid, act = d.get("uid"), d.get("action")
    if isinstance(uid, bool) or not isinstance(uid, int) or uid in settings.admin_ids and act == "ban":
        raise HTTPException(400, "Bad user id")
    if db.get_user(uid) is None:
        raise HTTPException(404, "Unknown user id")
    if act in ("ban", "unban"):
        db.set_ban(uid, act == "ban")
    elif act == "coins":
        amt = d.get("amount")
        if isinstance(amt, bool) or not isinstance(amt, int) or abs(amt) > 10**7 or db.add_coins(uid, amt, "owner") is None:
            raise HTTPException(400, "Bad amount")
    elif act != "info":
        raise HTTPException(400, "Bad action")
    u = db.get_user(uid)
    return {"id": uid, "name": u["name"], "username": u["username"], "coins": u["coins"], "games": u["games"], "wins": u["wins"], "banned": bool(u["banned"])}


@app.post("/api/owner/broadcast")
async def owner_broadcast(request: Request):
    owner_user(request)
    d = await body(request)
    text, kind = d.get("text"), d.get("target", "users")
    if not isinstance(text, str) or not text.strip() or len(text) > 3500 or kind not in ("users", "groups", "all"):
        raise HTTPException(400, "Bad broadcast")
    bot = app.state.bot
    if bot is None:
        raise HTTPException(503, "Bot is not running")
    targets = (db.user_ids() if kind in ("users", "all") else []) + (db.chat_ids() if kind in ("groups", "all") else [])

    async def send(t):
        try:
            await bot.send_message(t, text)
            return "ok"
        except Exception as e:  # classify by name so we don't import aiogram here
            n = type(e).__name__
            if n == "TelegramRetryAfter":
                return ("retry", getattr(e, "retry_after", 3))
            return "blocked" if n == "TelegramForbiddenError" else ("gone" if n == "TelegramBadRequest" else "fail")

    async def job():
        res = await bcast.run(targets, send, 0.05)
        for t in res["blocked_ids"] + res["gone_ids"]:
            db.mark_dm(t, False) if t > 0 else db.set_chat_active(t, False)
        log.info("broadcast finished: %s", {k: v for k, v in res.items() if not k.endswith("_ids")})

    asyncio.create_task(job())
    return {"queued": len(targets)}


# Mounted last so the API routes above win.
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

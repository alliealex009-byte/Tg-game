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
from .store import make_db
from .games import GAME_INFO, GAMES
from .games.base import GameError
from .rooms import RoomManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("server")

settings = load_settings()
db = make_db(settings)
rooms = RoomManager(db, settings)
WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "webapp")
BETS = [0, 50, 100, 500, 1000]


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bot_username = ""
    tasks = [asyncio.create_task(rooms.janitor()), asyncio.create_task(rooms.host_loop())]
    bot = None
    if settings.bot_token:
        try:
            from .bot import build, prepare

            bot, dp, ctx = build(settings, db, rooms)
            await prepare(bot, settings, ctx)
            app.state.bot_username = ctx["username"]
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
    }


@app.post("/api/me")
async def me(request: Request):
    u = auth_user(request)
    return {"user": public_user(u), "daily_wait": db.daily_wait(u["id"])}


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
            weight = 0.3 if raw.startswith('{"t":"tap"') or raw.startswith('{"t": "tap"') else 1.0
            window = [x for x in window if now - x[0] < 5] + [(now, weight)]
            if sum(w for _, w in window) > 40:
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


# Mounted last so the API routes above win.
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

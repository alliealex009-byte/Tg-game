"""End-to-end run WITHOUT Telegram or FastAPI.

The real RoomManager + game engines + coin database run in-process; Playwright serves the real mini app
(webapp/) and bridges its WebSocket/REST calls to them. A scripted player clicks through each game in
headless Chromium exactly like a person would, while "Rhea" (another human) and computer players answer.

    python3 tests/e2e_shots.py [game ...]        # default: every game
Screenshots go to ./shots/<game>_{lobby,play,result}.png and a combined <game>_overview.png.
Some results are fast-forwarded by editing the engine state (marked below) so a run takes seconds.
"""
import asyncio
import copy
import json
import math
import os
import random
import subprocess
import sys
import time
import traceback
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright  # noqa: E402

from app.auth import user_from_init_data  # noqa: E402
from app.config import Settings  # noqa: E402
from app.db import DB  # noqa: E402
from app.games import GAME_INFO  # noqa: E402
from app.games import carrom  # noqa: E402
from app.games.base import GameError  # noqa: E402
from app.rooms import RoomManager  # noqa: E402

PORT = 8766
BASE = f"http://127.0.0.1:{PORT}"
OUT = Path(os.environ.get("SHOTS_DIR", ROOT / "shots"))
VIEW = {"width": 390, "height": 844}


def dev_uid(name):  # same hash as getInitData() in app.js
    h = 0
    for ch in name:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h % 900000 + 100000


class Script:
    """Dice that return scripted values first, then real randomness."""
    def __init__(self, vals):
        self.vals = list(vals)

    def randint(self, a, b):
        return self.vals.pop(0) if self.vals else random.randint(a, b)

    def __getattr__(self, name):
        return getattr(random, name)


def clone(g):
    rng = g.rng
    g.rng = random.Random()
    try:
        return copy.deepcopy(g)
    finally:
        g.rng = rng


def bot_choice(game_key, g):
    """What the built-in computer would do for the current player, as a client message."""
    g2 = clone(g)
    if game_key == "carrom":
        cap = {}
        g2._shoot = lambda x, a, p: cap.update(x=x, angle=a, power=p)
        g2.auto_play()
        return {"t": "shoot", **cap} if cap else {"t": "shoot", "x": 400, "angle": -math.pi / 2, "power": 0.5}
    g2.auto_play()
    if game_key == "tictactoe":
        return {"t": "place", "cell": g2.last_move["cell"]}
    if game_key == "connect4":
        return {"t": "drop", "col": g2.last_move["col"]}
    if game_key == "memory":
        return {"t": "flip", "i": g2.last_flip["i"]}
    raise ValueError(game_key)


def remote_action(game_key, g, uid):
    if game_key == "snakes":
        return {"t": "roll"}
    if game_key == "ludo":
        return {"t": "roll"} if g.phase == "roll" else {"t": "move", "token": g.choose_token(uid)}
    if game_key == "rps":
        return {"t": "pick", "choice": random.choice(["rock", "paper", "scissors"])}
    return bot_choice(game_key, g)


class Link:
    def __init__(self, route=None):
        self.route = route

    async def send_json(self, m):
        if self.route is not None:
            try:
                self.route.send(json.dumps(m))
            except Exception:
                pass


class Harness:
    def __init__(self):
        self.settings = Settings(dev_mode=True, turn_seconds=30, bot_token="")
        self.db = DB(":memory:", 1000, 200)
        self.rm = RoomManager(self.db, self.settings)
        self.errors = []

    def user(self, name):
        uid = dev_uid(name)
        return self.db.upsert_user(uid, name, f"user_{uid}", None)

    async def add_remote(self, room, name):
        u = self.user(name)
        await self.rm.join(room, u, Link())
        return u["id"]

    async def remote_loop(self, game_key, room, uid):
        while room.status != "finished":
            await asyncio.sleep(0.4)
            g = room.game
            if room.status == "playing" and g is not None and g.current() == uid:
                await asyncio.sleep(1.0)
                if room.status == "playing" and g.current() == uid:
                    try:
                        await self.rm.handle(room, uid, remote_action(game_key, g, uid))
                    except GameError as e:
                        print("   remote player error:", e)

    # ---- bridge the page's network calls to the real server logic ----
    async def attach(self, page):
        await page.route("https://telegram.org/**", lambda r: r.abort())
        await page.route("**/api/**", self._api)
        await page.route_web_socket("**/ws", self._ws)
        page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e} | {(getattr(e, 'stack', '') or '').splitlines()[1:3]}"))
        page.on("console", lambda m: self.errors.append(f"console: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)

    async def _api(self, route, request):
        path = urlparse(request.url).path
        init = request.headers.get("x-init-data", "")
        try:
            if path == "/api/config":
                return await route.fulfill(json={"bot": "LudoKingProbot", "app": "LudoGame", "games": GAME_INFO,
                                                 "bets": [0, 50, 100, 500, 1000], "daily": 200, "rake": 10, "dev": True})
            if path == "/api/leaderboard":
                rows = self.db.leaderboard(15)
                return await route.fulfill(json={"rows": [{k: r[k] for k in ("id", "name", "username", "photo", "wins", "games")} for r in rows]})
            tg = user_from_init_data(init, self.settings)
            u = self.db.upsert_user(tg["id"], tg["name"], tg["username"], tg["photo"])
            if path == "/api/me":
                pu = {k: u[k] for k in ("id", "name", "username", "photo", "coins", "games", "wins")}
                return await route.fulfill(json={"user": pu, "daily_wait": self.db.daily_wait(u["id"])})
            if path == "/api/daily":
                ok, coins, wait = self.db.claim_daily(u["id"])
                return await route.fulfill(json={"claimed": ok, "coins": coins, "wait": wait, "bonus": 200})
            if path == "/api/room":
                d = request.post_data_json
                room = self.rm.create(u["id"], d.get("game"), d.get("bet", 0))
                return await route.fulfill(json={"code": room.code})
        except GameError as e:
            return await route.fulfill(status=400, json={"detail": str(e)})
        await route.fulfill(status=404, json={"detail": "not found"})

    def _ws(self, ws):
        link, st = Link(ws), {"room": None, "uid": None}
        ws.on_message(lambda m: asyncio.ensure_future(self._on_msg(link, st, m)))
        ws.on_close(lambda *a: asyncio.ensure_future(self._on_close(link, st)))

    async def _on_msg(self, link, st, raw):
        msg = json.loads(raw)
        t = msg.get("t")
        if t == "ping":
            return await link.send_json({"t": "pong"})
        try:
            if st["room"] is None:
                if t != "join":
                    return
                tg = user_from_init_data(str(msg.get("initData", "")), self.settings)
                r = self.rm.get(str(msg.get("room", "")))
                if r is None:
                    return await link.send_json({"t": "error", "fatal": True, "msg": "Room not found or expired"})
                u = self.db.upsert_user(tg["id"], tg["name"], tg["username"], tg["photo"])
                await self.rm.join(r, u, link)
                st["room"], st["uid"] = r, u["id"]
            else:
                await self.rm.handle(st["room"], st["uid"], msg)
        except GameError as e:
            await link.send_json({"t": "error", "msg": str(e), "fatal": st["room"] is None})

    async def _on_close(self, link, st):
        if st["room"] is not None:
            await self.rm.disconnect(st["room"], st["uid"], link)


# ------------------------------------------------------------------ play scripts
async def wf(page, js, arg=None, timeout=120000):
    await page.wait_for_function(js, arg=arg, timeout=timeout)


async def play_snakes(page, room, me, shot, h):
    ready = "() => { const b = document.querySelector('#slroll'); return b && !b.disabled; }"
    for _ in range(4):
        await wf(page, ready)
        await page.click("#slroll")
        await asyncio.sleep(1.0)
    await wf(page, ready)
    await shot("play")
    g = room.game  # fast-forward (engine state edited): everyone near the end, my next roll is a 6 from 94
    for u in g.players:
        g.pos[u] = 40
    g.pos[me] = 94
    g.rng = Script([6])
    await h.rm.broadcast(room)
    await asyncio.sleep(1.0)
    await page.click("#slroll")


async def play_ludo(page, room, me, shot, h):
    sel = "() => document.querySelector('.dicebox.rollable') || document.querySelector('.token.movable') || document.querySelector('#result:not(.hidden)')"
    actions = 0
    while actions < 10:
        await wf(page, sel)
        if await page.query_selector(".dicebox.rollable"):
            await page.click(".dicebox.rollable")
        elif await page.query_selector(".token.movable"):
            await page.click(".token.movable")
        actions += 1
        await asyncio.sleep(0.9)
    await wf(page, "() => document.querySelector('.dicebox.rollable')")
    await shot("play")
    g = room.game  # fast-forward (engine state edited): three tokens home, one a single step away
    g.tokens[me] = [56, 56, 56, 55]
    g.rng = Script([1])
    await h.rm.broadcast(room)
    await asyncio.sleep(1.0)
    await page.click(".dicebox.rollable")


async def play_ttt(page, room, me, shot, h):
    moves = 0
    while room.status == "playing":
        await wf(page, "() => document.querySelector('.tcell.can') || document.querySelector('#result:not(.hidden)')")
        if room.status != "playing":
            break
        g = room.game
        cell = next(i for i in (4, 0, 2, 6, 8, 1, 3, 5, 7) if not g.board[i])
        await page.click(f'.tcell[data-i="{cell}"]')
        moves += 1
        await wf(page, "() => !document.querySelector('.tcell.can')")
        if moves == 2:
            await wf(page, "() => document.querySelector('.tcell.can')")
            await shot("play")


async def play_c4(page, room, me, shot, h):
    moves = 0
    while room.status == "playing":
        await wf(page, "() => document.querySelector('#c4.can') || document.querySelector('#result:not(.hidden)')")
        if room.status != "playing":
            break
        g = room.game
        col = bot_choice("connect4", g)["col"]  # sensible play for Alex, so the game lasts
        if moves == 4:
            await shot("play")
        await page.click(f'.c4col[data-c="{col}"]')
        moves += 1
        await wf(page, "() => !document.querySelector('#c4.can')")


async def play_rps(page, room, me, shot, h):
    shot_done = False
    while room.status == "playing":
        await wf(page, "() => (document.querySelector('#rbtns') && !document.querySelector('#rbtns').classList.contains('off')) || document.querySelector('#result:not(.hidden)')")
        if room.status != "playing":
            break
        await page.click(f'.rbtn[data-c="{random.choice(["rock", "paper", "scissors"])}"]')
        await wf(page, "() => document.querySelector('#rbtns').classList.contains('off')")
        if not shot_done:
            await wf(page, "() => document.querySelector('.reveal .pop')", timeout=30000)
            await asyncio.sleep(0.7)
            await shot("play")
            shot_done = True
    if not shot_done:
        await shot("play")


async def play_memory(page, room, me, shot, h):
    clicks = 0
    play_memory.shot_taken = False
    while room.status == "playing":
        await wf(page, "() => document.querySelector('#mg.can') || document.querySelector('#result:not(.hidden)')")
        if room.status != "playing":
            break
        g = room.game
        free = [i for i in range(16) if i not in g.owner and (i not in g.up or len(g.up) == 2)]
        i = random.choice(free)
        if clicks >= 2 and len(g.up) in (0, 2) and not getattr(play_memory, "shot_taken", False):
            play_memory.shot_taken = True
            await shot("play")
        await page.click(f'.mcard[data-i="{i}"]')
        clicks += 1
        await wf(page, "i => document.querySelector('.mcard[data-i=\"' + i + '\"]').classList.contains('up')", arg=i)
        await asyncio.sleep(0.5)


async def carrom_shoot(page, room, me):
    g = room.game
    cap = bot_choice("carrom", g)
    idx = g.players.index(me)
    flip = idx == 1
    sy = carrom.BASE_Y[idx]
    vx = 800 - cap["x"] if flip else cap["x"]
    await page.evaluate("v => { const s = document.querySelector('#cx'); s.value = v; s.dispatchEvent(new Event('input')); }", vx)
    length = cap["power"] * 220
    px, py = cap["x"] - math.cos(cap["angle"]) * length, sy - math.sin(cap["angle"]) * length
    rect = await page.evaluate("() => { const r = document.querySelector('#cv').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")

    def to_client(bx, by):
        x, y = (800 - bx, 800 - by) if flip else (bx, by)
        return rect[0] + x / 800 * rect[2], rect[1] + y / 800 * rect[3]

    sx0, sy0 = to_client(cap["x"], sy)
    tx, ty = to_client(px, py)
    await page.mouse.move(sx0, sy0)
    await page.mouse.down()
    for k in range(1, 7):
        await page.mouse.move(sx0 + (tx - sx0) * k / 6, sy0 + (ty - sy0) * k / 6)
    await page.screenshot(path=str(OUT / "_aim.png"))
    await page.mouse.up()


async def play_carrom(page, room, me, shot, h):
    turns = 0
    while room.status == "playing":
        await wf(page, "() => (document.querySelector('#cx') && !document.querySelector('#cx').disabled) || document.querySelector('#result:not(.hidden)')")
        if room.status != "playing":
            break
        if turns == 3:  # fast-forward (engine state edited): my score is one shot from winning
            room.game.scores[me] = 11
            await h.rm.broadcast(room)
            await asyncio.sleep(0.6)
        await carrom_shoot(page, room, me)
        turns += 1
        if turns == 2:
            await asyncio.sleep(0.9)
            await shot("play")  # captured while the coins are still moving
        await wf(page, "() => document.querySelector('#cx') && document.querySelector('#cx').disabled || document.querySelector('#result:not(.hidden)')")


SCEN = {
    "ludo": dict(bet=0, bots=2, play=play_ludo),
    "snakes": dict(bet=0, bots=2, play=play_snakes),
    "carrom": dict(bet=100, bots=0, play=play_carrom),
    "connect4": dict(bet=100, bots=0, play=play_c4),
    "tictactoe": dict(bet=100, bots=0, play=play_ttt),
    "rps": dict(bet=100, bots=0, play=play_rps),
    "memory": dict(bet=100, bots=0, play=play_memory),
}


async def run_game(h, browser, key):
    cfg = SCEN[key]
    OUT.mkdir(parents=True, exist_ok=True)
    ctx = await browser.new_context(viewport=VIEW, device_scale_factor=2)
    page = await ctx.new_page()
    await h.attach(page)
    me = h.user("Alex")["id"]
    room = h.rm.create(me, key, cfg["bet"])
    rhea = await h.add_remote(room, "Rhea")
    await page.goto(f"{BASE}/?room={room.code}&dev=Alex")
    await page.wait_for_selector(".lobby .plist", timeout=15000)
    for _ in range(cfg["bots"]):
        await h.rm.handle(room, me, {"t": "add_bot"})
    want = 2 + cfg["bots"]
    await wf(page, "n => document.querySelectorAll('.plist .prow2:not(.empty)').length >= n", arg=want, timeout=15000)
    await asyncio.sleep(0.4)

    async def shot(name):
        await page.screenshot(path=str(OUT / f"{key}_{name}.png"))
        print(f"   saved {key}_{name}.png")

    await shot("lobby")
    await page.click("#start")
    await page.wait_for_selector("#screen-game.active", timeout=15000)
    remote = asyncio.ensure_future(h.remote_loop(key, room, rhea))
    try:
        await asyncio.wait_for(cfg["play"](page, room, me, shot, h), timeout=240)
        await page.wait_for_selector("#result .rbox", timeout=60000)
        await asyncio.sleep(0.8)
        await shot("result")
    except Exception:
        traceback.print_exc()
        await shot("error")
        raise
    finally:
        remote.cancel()
        await ctx.close()
    res = room.result or {}
    me_coins = h.db.get_user(me)["coins"]
    print(f"   result: winner={res.get('winner')} (Alex={me}) prize={res.get('prize')} Alex coins={me_coins}")


async def run_home(h, browser):
    ctx = await browser.new_context(viewport=VIEW, device_scale_factor=2)
    page = await ctx.new_page()
    await h.attach(page)
    await page.goto(f"{BASE}/?dev=Alex")
    await page.wait_for_selector(".games .gcard", timeout=15000)
    await asyncio.sleep(0.5)
    await page.screenshot(path=str(OUT / "home.png"), full_page=False)
    n = await page.evaluate("() => document.querySelectorAll('.gcard').length")
    print(f"   home shows {n} games")
    await ctx.close()


async def main(keys):
    server = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--directory", str(ROOT / "webapp")],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    h = Harness()
    failures = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            if "home" in keys:
                print("home")
                await run_home(h, browser)
            for key in [k for k in keys if k in SCEN]:
                print(key)
                try:
                    await run_game(h, browser, key)
                except Exception as e:
                    failures.append((key, repr(e)))
            await browser.close()
    finally:
        server.terminate()
    print("JS errors:", h.errors or "none")
    print("FAILED:", failures or "none")
    return 1 if (failures or h.errors) else 0


if __name__ == "__main__":
    args = sys.argv[1:] or ["home"] + list(SCEN)
    sys.exit(asyncio.run(main(args)))

"""Browser test for the card games. E2E_PORT=8772 SHOTS_DIR=shots python3 tests/e2e_cards.py [game ...]"""
import asyncio
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault("E2E_PORT", "8772")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import e2e_shots as E  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

from app.config import Settings  # noqa: E402

GAMES = ["uno", "crazy8", "gofish", "blackjack", "teenpatti"]


async def alex_action(page, room, key):
    """One real UI action by Alex; returns once the server accepted it (game seq moved)."""
    g0 = room.game.seq
    if key in ("uno", "crazy8"):
        await page.wait_for_selector("#gch .gc-slot.can, #gca button[data-t=draw], #gca button[data-t=pass]", timeout=60000)
        if await page.query_selector("#gch .gc-slot.can"):
            await page.click("#gch .gc-slot.can >> nth=0")
            if await page.query_selector(".gc-modal .gc-pb"):
                await page.click(".gc-modal .gc-pb >> nth=0")
        else:
            await page.click("#gca button >> nth=0")
    elif key == "gofish":
        await page.wait_for_selector("#gca [data-rank]", timeout=60000)
        await page.click("#gca [data-rank] >> nth=0")
        await page.click("#gca [data-target]:not([disabled]) >> nth=0")
    elif key == "blackjack":
        await page.wait_for_selector(".gc-chipbtn", timeout=30000)
        await page.click(".gc-chipbtn >> nth=0")
        await page.wait_for_selector("#gca button[data-t=stand]", timeout=30000)
        await page.click("#gca button[data-t=stand]")
    elif key == "teenpatti":
        await page.wait_for_selector("#gca button[data-t=see]", timeout=30000)
        await page.click("#gca button[data-t=see]")
        await page.wait_for_selector("#gca button[data-t=chaal]", timeout=60000)
        await page.click("#gca button[data-t=chaal]")
    for _ in range(40):
        if room.game.seq > g0:
            return
        await asyncio.sleep(0.15)
    raise AssertionError(f"{key}: server did not accept the UI action")


async def run(h, browser, key):
    info = E.GAME_INFO[key]
    ctx = await browser.new_context(viewport=E.VIEW, device_scale_factor=2)
    page = await ctx.new_page()
    await h.attach(page)
    me = h.user("Alex")["id"]
    room = h.rm.create(me, key, 0)
    room.turn_seconds = 30
    await page.goto(f"{E.BASE}/?room={room.code}&dev=Alex")
    await page.wait_for_selector(".lobby .plist", timeout=15000)
    n_bots = 2 if info["max"] >= 3 else 1
    for _ in range(n_bots):
        await h.rm.handle(room, me, {"t": "add_bot"})
    await page.wait_for_function("n => document.querySelectorAll('.plist .prow2:not(.empty)').length >= n", arg=1 + n_bots, timeout=15000)
    await asyncio.sleep(0.4)
    await page.screenshot(path=str(E.OUT / f"{key}_lobby.png"))
    await page.click("#start")
    await page.wait_for_selector("#screen-game.active .gc-table", timeout=15000)
    await alex_action(page, room, key)
    await asyncio.sleep(1.5)
    await page.screenshot(path=str(E.OUT / f"{key}_play.png"))
    for p in [p for p in room.players if p.is_bot]:  # bots forfeit -> Alex wins
        await h.rm._remove_from_game(room, p.uid)
    await page.wait_for_selector("#result .rbox", timeout=15000)
    await asyncio.sleep(0.8)
    await page.screenshot(path=str(E.OUT / f"{key}_result.png"))
    await ctx.close()
    print(f"   {key}: ok, status={room.status}")


async def main(keys):
    E.OUT.mkdir(parents=True, exist_ok=True)
    server = subprocess.Popen([sys.executable, "-m", "http.server", str(E.PORT), "--directory", str(E.ROOT / "webapp")],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    h = E.Harness()
    h.rm.s = Settings(dev_mode=True, turn_seconds=30, bot_token="", bot_delay=(0.3, 0.6))
    fails = []
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch()
            for k in keys:
                print(k)
                try:
                    await asyncio.wait_for(run(h, b, k), 120)
                except Exception:
                    traceback.print_exc()
                    fails.append(k)
            await b.close()
    finally:
        server.terminate()
    print("JS errors:", h.errors or "none")
    print("FAILED:", fails or "none")
    return 1 if fails or h.errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:] or GAMES)))

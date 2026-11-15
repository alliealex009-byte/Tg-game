"""Browser test for the board games (chess, checkers, reversi, gomoku, uttt, battleship).
   E2E_PORT=8771 SHOTS_DIR=shots python3 tests/e2e_boards.py [game ...]"""
import asyncio
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault("E2E_PORT", "8771")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import e2e_shots as E  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

KEYS = ["chess", "checkers", "reversi", "gomoku", "uttt", "battleship"]


async def ui_move(page, key, g):
    """One real click-driven move for Alex, derived from the engine's current legal moves."""
    s = g.public_state() if key != "battleship" else None
    if key == "chess":
        f = next(iter(s["legal"]))
        t = s["legal"][f][0]
        await page.click(f'#gbb .gb-sq[data-sq="{f}"]')
        await page.click(f'#gbb .gb-sq[data-sq="{t}"]')
    elif key == "checkers":
        f = next(iter(s["legal"]))
        path = s["legal"][f][0]
        await page.click(f'#gbb .gb-sq[data-sq="{f}"]')
        await page.click(f'#gbb .gb-sq[data-sq="{path[-1]}"]')
    elif key == "reversi":
        await page.click(f'#gbb .gb-sq[data-sq="{s["legal"][0]}"]')
    elif key == "gomoku":
        i = next(i for i, v in enumerate(g.board) if v is None and abs(i - 112) < 40)
        await page.click(f'#gbb .gb-gp[data-i="{i}"]')
    elif key == "uttt":
        await page.click(f'#gbb .gb-uc[data-i="{s["legal"][0]}"]')
    elif key == "battleship":
        foe = next(u for u in g.players if u != g.current())
        i = next(i for i in range(100) if i not in g.shots[foe])
        await page.click(f'#gbe .gb-wc[data-i="{i}"]')


async def run(h, browser, key):
    ctx = await browser.new_context(viewport=E.VIEW, device_scale_factor=2)
    page = await ctx.new_page()
    await h.attach(page)
    me = h.user("Alex")["id"]
    room = h.rm.create(me, key, 0)
    room.turn_seconds = 60
    rhea = await h.add_remote(room, "Rhea")
    await page.goto(f"{E.BASE}/?room={room.code}&dev=Alex")
    await page.wait_for_selector(".lobby .plist", timeout=15000)
    await E.wf(page, "() => document.querySelectorAll('.plist .prow2:not(.empty)').length >= 2", timeout=15000)

    async def shot(name):
        E.OUT.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(E.OUT / f"{key}_{name}.png"))

    await shot("lobby")
    await page.click("#start")
    await page.wait_for_selector("#screen-game.active", timeout=15000)
    g = room.game
    moves_by_alex, plies = 0, 0
    t0 = time.time()
    while plies < 7 and not g.finished and time.time() - t0 < 60:
        await asyncio.sleep(0.5)
        cur = g.current()
        if cur == rhea:
            g.auto_play()
            await h.rm._after(room)
            plies += 1
        elif cur == me:
            before = (g.last_move or {}).get("seq", 0)
            await asyncio.sleep(0.5)
            await ui_move(page, key, g)
            await asyncio.sleep(0.6)
            after = (g.last_move or {}).get("seq", 0)
            assert after > before and g.last_move["uid"] == me, f"{key}: UI move was not accepted"
            moves_by_alex += 1
            plies += 1
    assert moves_by_alex >= 1, f"{key}: Alex never moved"
    await asyncio.sleep(0.8)
    await shot("play")
    # spectator rendering: same state, a uid that is not a player
    err = await page.evaluate("""() => { try { const s = JSON.parse(JSON.stringify(HUB.S.room)); s.you = 424242;
        HUB.UI[s.game_type].build(s); HUB.UI[s.game_type].apply(s); return ''; } catch (e) { return String(e); } }""")
    assert not err, f"{key}: spectator render failed: {err}"
    await page.reload()
    await page.wait_for_selector("#screen-game.active", timeout=15000)
    await asyncio.sleep(0.8)
    await h.rm._remove_from_game(room, rhea)
    await page.wait_for_selector("#result .rbox", timeout=15000)
    await asyncio.sleep(0.8)
    await shot("result")
    print(f"   {key}: ok (Alex UI moves: {moves_by_alex}, winner={room.result and room.result.get('winner')})")
    await ctx.close()


async def main(keys):
    server = subprocess.Popen([sys.executable, "-m", "http.server", str(E.PORT), "--directory", str(E.ROOT / "webapp")],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    h = E.Harness()
    failures = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            for key in keys:
                print(key)
                try:
                    await run(h, browser, key)
                except Exception as e:
                    traceback.print_exc()
                    failures.append((key, repr(e)))
            await browser.close()
    finally:
        server.terminate()
    print("JS errors:", h.errors or "none")
    print("FAILED:", failures or "none")
    return 1 if (failures or h.errors) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:] or KEYS)))

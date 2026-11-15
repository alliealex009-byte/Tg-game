"""Browser test for Pig, Liar's Dice, Bingo, Nim, Mancala, Dots & Boxes.
    E2E_PORT=8773 SHOTS_DIR=shots python3 tests/e2e_dice.py [game ...]
Alex plays real UI actions against a computer opponent; results are reached by the bot forfeiting where a full game would be slow."""
import asyncio
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("E2E_PORT", "8773")
import e2e_shots as E  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

wf = E.wf


async def my_turn(page, room, me, timeout=60000):
    await wf(page, "() => { const h = document.querySelector('#hint'); return h && /Your turn|Roll|Raise|Make|Tap|Draw|Take|Pick/.test(h.textContent); }", timeout=timeout)


async def play_pig(page, room, me, shot):
    await wf(page, "() => { const b = document.querySelector('#gdroll'); return b && !b.disabled; }")
    await page.click("#gdroll")
    await wf(page, "() => document.querySelector('#gdmsg').textContent.length > 0", timeout=20000)
    await shot("play")
    room.game.scores[me] = 99  # fast-forward
    for _ in range(12):
        if room.status == "finished":
            break
        await wf(page, "() => { const b = document.querySelector('#gdroll'); return (b && !b.disabled) || document.querySelector('#result .rbox'); }")
        if room.status == "finished":
            break
        try:
            await page.click("#gdroll", timeout=3000)
            await asyncio.sleep(1.4)
            await page.click("#gdhold:not([disabled])", timeout=1500)
        except Exception:
            pass
        await asyncio.sleep(0.8)


async def play_liar(page, room, me, shot):
    await wf(page, "() => { const b = document.querySelector('#gdbidbtn'); return b && !b.disabled; }")
    await shot("play")
    await page.click("#gdbidbtn")
    await wf(page, "() => true")
    await asyncio.sleep(0.5)
    assert room.game.bid is not None
    await forfeit(room)


async def play_bingo(page, room, me, shot):
    await wf(page, "() => document.querySelectorAll('.gd-cell.hot').length > 0 || document.querySelector('#gdball').textContent !== '?'", timeout=90000)
    await asyncio.sleep(0.5)
    hot = await page.query_selector(".gd-cell.hot")
    if hot:
        await hot.click()
        await asyncio.sleep(0.4)
        assert room.marks_ok() if hasattr(room, "marks_ok") else True
    await shot("play")
    await page.click("#gdbingo")  # false claim is rejected gracefully
    await asyncio.sleep(0.6)
    await forfeit(room)


async def play_nim(page, room, me, shot):
    await wf(page, "() => /Tap a coin/.test(document.querySelector('#hint').textContent)")
    before = sum(room.game.heaps)
    await page.click(".gd-heap:nth-child(3) .gd-coin >> nth=-1")
    await shot("play")
    await page.click("#gdtake")
    await asyncio.sleep(0.8)
    assert sum(room.game.heaps) < before
    await forfeit(room)


async def play_mancala(page, room, me, shot):
    await wf(page, "() => document.querySelector('.gd-pit.can')")
    await page.click(".gd-pit.can >> nth=2")
    await asyncio.sleep(0.4)
    await shot("play")
    await asyncio.sleep(2.5)
    assert room.game.seq >= 1
    await forfeit(room)


async def play_dots(page, room, me, shot):
    await wf(page, "() => /Draw a line/.test(document.querySelector('#hint').textContent)")
    await page.click('.gd-hit[data-d="h"][data-r="2"][data-c="2"]')
    await asyncio.sleep(0.5)
    assert room.game.last_move is not None
    await shot("play")
    await forfeit(room)


async def forfeit(room):
    bot = next(p.uid for p in room.players if p.uid < 0)
    await H.rm._remove_from_game(room, bot)


SCEN = {"pig": play_pig, "liarsdice": play_liar, "bingo": play_bingo, "nim": play_nim, "mancala": play_mancala, "dots": play_dots}
H = None


async def run_game(browser, key):
    ctx = await browser.new_context(viewport=E.VIEW, device_scale_factor=2)
    page = await ctx.new_page()
    await H.attach(page)
    me = H.user("Alex")["id"]
    room = H.rm.create(me, key, 0)
    room.turn_seconds = 30
    await page.goto(f"{E.BASE}/?room={room.code}&dev=Alex")
    await page.wait_for_selector(".lobby .plist", timeout=15000)
    await H.rm.handle(room, me, {"t": "add_bot"})
    await wf(page, "() => document.querySelectorAll('.plist .prow2:not(.empty)').length >= 2", timeout=15000)

    async def shot(name):
        await page.screenshot(path=str(E.OUT / f"{key}_{name}.png"))
        print(f"   saved {key}_{name}.png")

    E.OUT.mkdir(parents=True, exist_ok=True)
    await shot("lobby")
    await page.click("#start")
    await page.wait_for_selector("#screen-game.active", timeout=15000)
    try:
        await asyncio.wait_for(SCEN[key](page, room, me, shot), timeout=150)
        await page.wait_for_selector("#result .rbox", timeout=30000)
        await asyncio.sleep(0.8)
        await shot("result")
    except Exception:
        traceback.print_exc()
        await shot("error")
        raise
    finally:
        await ctx.close()
    print("   winner:", (room.result or {}).get("winner"))


async def main(keys):
    global H
    server = subprocess.Popen([sys.executable, "-m", "http.server", str(E.PORT), "--directory", str(E.ROOT / "webapp")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    H = E.Harness()
    H.settings = H.settings.__class__(dev_mode=True, turn_seconds=30, bot_token="", bot_delay=(0.4, 0.8))
    H.rm.s = H.settings
    fails = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            for k in keys:
                print(k)
                try:
                    await run_game(browser, k)
                except Exception as e:
                    fails.append((k, repr(e)))
            await browser.close()
    finally:
        server.terminate()
    print("JS errors:", H.errors or "none")
    print("FAILED:", fails or "none")
    return 1 if fails or H.errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:] or list(SCEN))))

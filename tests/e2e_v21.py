"""v2.1 browser test: home (categories, credits), arcade games, tap-to-earn, farm, owner panel,
spectator + emoji reactions + dock, how-to overlay, host-less lobby."""
import asyncio
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e2e_shots as E  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

OUT = E.OUT


async def main():
    server = subprocess.Popen([sys.executable, "-m", "http.server", str(E.PORT), "--directory", str(E.ROOT / "webapp")],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(0.8)
    h = E.Harness()
    fails = []
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch()
            ctx = await b.new_context(viewport=E.VIEW, device_scale_factor=2)
            page = await ctx.new_page()
            await h.attach(page)
            await page.goto(f"{E.BASE}/?dev=Alex")
            await page.wait_for_selector(".home .gcard", timeout=15000)
            await page.screenshot(path=str(OUT / "v21_home.png"))
            n_games = await page.evaluate("document.querySelectorAll('.gcard').length")
            print("games on home:", n_games)

            async def check(name, cond):
                if not cond:
                    fails.append(name); print("FAIL", name)
                else:
                    print("ok  ", name)

            await check("credits shown", "Advik_prakashh" in await page.inner_text(".credits"))
            await page.click("[data-cat='Board']")
            await check("category filter", await page.evaluate("document.querySelectorAll('.gcard').length") < n_games)
            await page.click("[data-info='chess']")
            await check("how-to overlay", "how to play" in (await page.inner_text(".xcard")).lower())
            await page.click(".xcard button")

            # arcade
            await page.click("#h-arcade")
            await page.wait_for_selector(".atile")
            await page.screenshot(path=str(OUT / "v21_arcade.png"))
            await page.click("[data-k='bricks']")
            await page.wait_for_selector("#xc")
            await page.mouse.click(200, 400)
            await asyncio.sleep(2.0)
            await page.screenshot(path=str(OUT / "v21_bricks.png"))
            await page.click("#xback")
            # tapverse
            await page.wait_for_selector("[data-k='tapverse']")
            await page.click("[data-k='tapverse']")
            await page.wait_for_selector("#tvbtn")
            for _ in range(12):
                await page.click("#tvbtn"); await asyncio.sleep(0.05)
            await asyncio.sleep(1.6)
            await page.screenshot(path=str(OUT / "v21_tap.png"))
            coins = h.db.get_user(h.user("Alex")["id"])["coins"]
            await check("tap earned coins server-side", coins > 1000)
            await page.click("#xback")
            await page.wait_for_selector("[data-k='pocketfarm']")
            await page.click("[data-k='pocketfarm']")
            await page.wait_for_selector(".pfp")
            await page.click(".pfp >> nth=0")
            await asyncio.sleep(0.5)
            await check("farm planted", await page.evaluate("!!document.querySelector('.pfp.grow')"))
            await page.screenshot(path=str(OUT / "v21_farm.png"))
            await page.click("#xback")
            await page.wait_for_selector("[data-k='gridpop']")
            await page.click("[data-k='gridpop']")
            await page.wait_for_selector(".gpc")
            await page.screenshot(path=str(OUT / "v21_gridpop.png"))
            await page.click("#xback")
            await page.wait_for_selector("[data-k='quickdrop']")
            await page.click("[data-k='quickdrop']")
            await page.wait_for_selector("#xc")
            await asyncio.sleep(2)
            await page.screenshot(path=str(OUT / "v21_quickdrop.png"))
            await page.click("#xback")
            await page.click("#xback")  # menu -> home
            # owner
            await page.wait_for_selector("#h-owner")
            await page.click("#h-owner")
            await page.wait_for_selector("#ow-send")
            await page.screenshot(path=str(OUT / "v21_owner.png"))
            await check("owner stats", "users" in await page.inner_text(".xgrid"))
            await page.click("#xback")

            # room with a spectator + reactions
            me = h.user("Alex")["id"]
            room = h.rm.create(me, "tictactoe", 0)
            await h.add_remote(room, "Rhea")
            await page.goto(f"{E.BASE}/?room={room.code}&dev=Alex")
            await page.wait_for_selector(".lobby .plist")
            await page.click("#start")
            await page.wait_for_selector("#screen-game.active")
            ctx2 = await b.new_context(viewport=E.VIEW, device_scale_factor=2)
            spec = await ctx2.new_page()
            await h.attach(spec)
            await spec.goto(f"{E.BASE}/?room={room.code}&dev=Watcher")
            await spec.wait_for_selector("#screen-game.active", timeout=15000)
            await asyncio.sleep(0.6)
            await check("spectator banner", await spec.evaluate("!!document.querySelector('#xspec')"))
            await check("watch count on player", (await page.inner_text("#xd-n")) == "1")
            await spec.click("#xd-react")
            await spec.click("#xtray [data-e='🔥']")
            await asyncio.sleep(0.5)
            await check("reaction floats on player screen", await page.evaluate("!!document.querySelector('.xfloat')"))
            await page.screenshot(path=str(OUT / "v21_room.png"))
            await spec.screenshot(path=str(OUT / "v21_spectator.png"))
            await b.close()
    finally:
        server.terminate()
    print("JS errors:", h.errors or "none")
    print("FAILED:", fails or "none")
    return 1 if fails or h.errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""Smoke test for the party games: lobby -> play -> auto-played rounds, screenshots, zero JS errors."""
import asyncio
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e2e_shots as E  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

GAMES = {"mafia": 5, "hangman": 2, "mastermind": 1, "trivia": 2}  # bots to add


async def main():
    server = subprocess.Popen([sys.executable, "-m", "http.server", str(E.PORT), "--directory", str(E.ROOT / "webapp")],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(0.8)
    h = E.Harness()
    fails = []
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch()
            for key, bots in GAMES.items():
                ctx = await b.new_context(viewport=E.VIEW, device_scale_factor=2)
                page = await ctx.new_page()
                await h.attach(page)
                me = h.user("Alex")["id"]
                room = h.rm.create(me, key, 0)
                await page.goto(f"{E.BASE}/?room={room.code}&dev=Alex")
                await page.wait_for_selector(".lobby .plist", timeout=15000)
                for _ in range(bots):
                    await h.rm.handle(room, me, {"t": "add_bot"})
                await asyncio.sleep(0.5)
                await page.screenshot(path=str(E.OUT / f"{key}_lobby.png"))
                room.turn_seconds = 4
                await page.click("#start")
                await page.wait_for_selector("#screen-game.active", timeout=15000)
                for i in range(4):
                    await asyncio.sleep(2.5)
                    await page.screenshot(path=str(E.OUT / f"{key}_play{i}.png"))
                inner = await page.inner_text("#screen-game")
                ok = len(inner) > 20 and room.status in ("playing", "finished")
                print(("ok  " if ok else "FAIL"), key, room.status, len(inner))
                if not ok:
                    fails.append(key)
                await ctx.close()
            await b.close()
    finally:
        server.terminate()
    print("JS errors:", h.errors or "none")
    print("FAILED:", fails or "none")
    return 1 if fails or h.errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

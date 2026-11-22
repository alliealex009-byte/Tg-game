"""Browser test for arcade batch 4 (snake, flap, galaxy, stack, roadrush, mole)."""
import asyncio
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e2e_shots as E  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402


async def main():
    server = subprocess.Popen([sys.executable, "-m", "http.server", str(E.PORT), "--directory", str(E.ROOT / "webapp")],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(0.8)
    h = E.Harness()
    fails = []
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch()
            ctx = await b.new_context(viewport=E.VIEW, device_scale_factor=1)
            page = await ctx.new_page()
            await h.attach(page)
            await page.goto(f"{E.BASE}/?dev=Alex")
            await page.wait_for_selector(".home .gcard", timeout=15000)
            for k in ("snake", "flap", "galaxy", "stack", "roadrush", "mole", "cricketblitz", "ponyrush", "panipuri", "memoflip"):
                await page.click("#h-arcade")
                await page.wait_for_selector(".xitem")
                await page.click(f"[data-k='{k}']")
                await page.wait_for_selector("#xc", timeout=5000)
                box = await page.locator("#xc").bounding_box()
                cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                for i in range(6):
                    await page.mouse.click(cx + (i % 3 - 1) * 60, cy + (i % 2) * 40)
                    await asyncio.sleep(0.45)
                await page.screenshot(path=str(E.OUT / f"arc4_{k}.png"))
                ok = await page.evaluate("!!document.querySelector('#xc')")
                print(("ok  " if ok else "FAIL"), k)
                if not ok:
                    fails.append(k)
                await page.evaluate("document.querySelector('#xscreen .xhead button, #xscreen button')?.click()")
                await asyncio.sleep(0.3)
                await page.goto(f"{E.BASE}/?dev=Alex")
                await page.wait_for_selector(".home .gcard", timeout=15000)
            await b.close()
    finally:
        server.terminate()
    print("JS errors:", h.errors or "none")
    print("FAILED:", fails or "none")
    return 1 if fails or h.errors else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

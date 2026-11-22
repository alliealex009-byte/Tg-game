"""Browser test for the second batch of arcade games."""
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
            await page.click("#h-arcade")
            await page.wait_for_selector(".xitem")
            n = await page.evaluate("document.querySelectorAll('.xitem').length")
            if n != 24:
                fails.append(f"arcade items {n}")
            for k, sel in (("byteblock", "#bb"), ("tiledash", "#td"), ("neonslice", "#xc"), ("minttap", "#mtgo"), ("turbocoin", "#tcb")):
                await page.click(f"[data-k='{k}']")
                await page.wait_for_selector(sel, timeout=5000)
                if k == "byteblock":
                    for d in ((200, 0), (-200, 0), (0, 200), (0, -200)):
                        box = await page.locator("#bb").bounding_box()
                        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                        await page.mouse.move(cx, cy); await page.mouse.down(); await page.mouse.move(cx + d[0] / 4, cy + d[1] / 4); await page.mouse.up()
                elif k == "tiledash":
                    for _ in range(5):
                        await page.click(".tdc.on")
                elif k == "neonslice":
                    await page.mouse.move(100, 300); await page.mouse.down(); await page.mouse.move(300, 400, steps=8); await page.mouse.up()
                elif k == "minttap":
                    for _ in range(3):
                        await page.click("#mtgo"); await asyncio.sleep(0.2)
                else:
                    for _ in range(5):
                        await page.click("#tcb")
                await asyncio.sleep(0.6)
                await page.screenshot(path=str(E.OUT / f"arc2_{k}.png"))
                await page.click("#xback")
                await page.wait_for_selector(".xitem")
            for k, sel in (("sprout", "#idc"), ("paws", "#idf"), ("world", ".idp"), ("realm", "#idm button")):
                await page.click(f"[data-k='{k}']")
                await page.wait_for_selector(sel, timeout=5000)
                if k == "sprout":
                    await page.click("#idu")
                elif k == "paws":
                    await page.click("#idf"); await asyncio.sleep(0.3); await page.click("#idp")
                elif k == "world":
                    await page.click(".idp >> nth=0"); await asyncio.sleep(0.4)
                    if not await page.evaluate("!!document.querySelector('.idp.full')"):
                        fails.append("world build failed")
                else:
                    await page.click("#idm button >> nth=0"); await asyncio.sleep(0.4)
                    if "Out on" not in await page.inner_text("#idc"):
                        fails.append("realm mission not started")
                await asyncio.sleep(0.4)
                await page.screenshot(path=str(E.OUT / f"arc3_{k}.png"))
                await page.click("#xback")
                await page.wait_for_selector(".xitem")
            if h.errors:
                fails.append(f"JS errors: {h.errors[:3]}")
            await b.close()
    finally:
        server.terminate()
    print("FAILED:", fails or "none")
    sys.exit(1 if fails else 0)


asyncio.run(main())

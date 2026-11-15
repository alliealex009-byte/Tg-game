"""Rate-limited broadcast loop. `send(target)` is injected and returns 'ok' | 'blocked' | 'gone' | 'fail' | ('retry', seconds)."""
from __future__ import annotations

import asyncio


async def run(targets, send, delay: float = 0.05, progress=None, cancel=None):
    """Send to every target, honouring flood-wait hints. Returns a result dict."""
    res = {"ok": 0, "blocked": 0, "gone": 0, "fail": 0, "total": len(targets), "blocked_ids": [], "gone_ids": []}
    for i, t in enumerate(targets):
        if cancel is not None and cancel():
            res["cancelled"] = True
            break
        r = await send(t)
        if isinstance(r, tuple) and r[0] == "retry":
            await asyncio.sleep(min(float(r[1]), 30))
            r = await send(t)
            if isinstance(r, tuple):
                r = "fail"
        if r == "ok":
            res["ok"] += 1
        elif r == "blocked":
            res["blocked"] += 1
            res["blocked_ids"].append(t)
        elif r == "gone":
            res["gone"] += 1
            res["gone_ids"].append(t)
        else:
            res["fail"] += 1
        if progress is not None and (i + 1) % 25 == 0:
            await progress(i + 1, len(targets))
        await asyncio.sleep(delay)
    return res

/* More solo arcade games: ByteBlock, TileDash, NeonSlice, MintTap, TurboCoin. Scores are validated and capped by the server (app/arcade.py). */
(function () {
  const HUB = window.HUB, A = HUB.arc, games = A.games;
  const $ = (s) => document.querySelector(s);
  const start = (game) => A.post("/api/arcade/start", { game });

  /* ---------------- ByteBlock (2048-style) ---------------- */
  games.byteblock = async function () {
    HUB.overlay2("🟦 ByteBlock", '<div class="xarc"><div class="xhud" id="xhud"></div><div id="bb" class="bbgrid" style="touch-action:none"></div><div class="xnote">Swipe to slide · equal blocks merge</div></div>');
    try { await start("byteblock"); } catch (e) { return HUB.toast(e.message); }
    const N = 4, LEN = 90000; let g = Array.from({ length: N }, () => Array(N).fill(0)), score = 0, done = false, t0 = performance.now();
    const box = $("#bb").parentNode, el = $("#bb");
    const add = () => { const f = []; g.forEach((r, i) => r.forEach((v, j) => { if (!v) f.push([i, j]); })); if (f.length) { const [i, j] = f[Math.floor(Math.random() * f.length)]; g[i][j] = Math.random() < 0.9 ? 2 : 4; } };
    const COL = { 0: "#262a33", 2: "#4285f4", 4: "#34a853", 8: "#fbbc05", 16: "#f57c00", 32: "#ea4335", 64: "#ab47bc", 128: "#00acc1", 256: "#7cb342", 512: "#ec407a", 1024: "#5c6bc0", 2048: "#ffd54f" };
    const draw = () => { el.innerHTML = g.flat().map((v) => `<div class="bbc" style="background:${COL[v] || "#fff"}">${v || ""}</div>`).join(""); };
    const line = (a) => { const v = a.filter(Boolean); for (let i = 0; i < v.length - 1; i++) if (v[i] === v[i + 1]) { v[i] *= 2; score += v[i]; v.splice(i + 1, 1); } while (v.length < N) v.push(0); return v; };
    const finish = () => { if (done) return; done = true; A.claim("byteblock", score, box); };
    const moves = () => { for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) { if (!g[i][j]) return true; if (j < N - 1 && g[i][j] === g[i][j + 1]) return true; if (i < N - 1 && g[i][j] === g[i + 1][j]) return true; } return false; };
    function move(d) {
      if (done) return; const before = JSON.stringify(g);
      if (d === "l" || d === "r") g = g.map((r) => (d === "l" ? line(r) : line([...r].reverse()).reverse()));
      else for (let j = 0; j < N; j++) { const col = g.map((r) => r[j]); const o = d === "u" ? line(col) : line([...col].reverse()).reverse(); o.forEach((v, i) => { g[i][j] = v; }); }
      if (JSON.stringify(g) !== before) { add(); HUB.sfx.place(); draw(); if (!moves()) finish(); } else HUB.sfx.miss();
    }
    let sx = 0, sy = 0;
    el.addEventListener("pointerdown", (e) => { sx = e.clientX; sy = e.clientY; });
    el.addEventListener("pointerup", (e) => { const dx = e.clientX - sx, dy = e.clientY - sy; if (Math.max(Math.abs(dx), Math.abs(dy)) < 24) return; move(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "r" : "l") : (dy > 0 ? "d" : "u")); });
    add(); add(); draw();
    A.timer(setInterval(() => { const left = Math.max(0, Math.ceil((LEN - (performance.now() - t0)) / 1000)); $("#xhud").textContent = `⭐ ${score}   ⏱ ${left}s`; if (left <= 0) finish(); }, 250));
  };

  /* ---------------- TileDash ---------------- */
  games.tiledash = async function () {
    HUB.overlay2("⚡ TileDash", '<div class="xarc"><div class="xhud" id="xhud"></div><div id="td" class="tdgrid"></div></div>');
    try { await start("tiledash"); } catch (e) { return HUB.toast(e.message); }
    const LEN = 30000, t0 = performance.now(); let score = 0, lit = -1, done = false, miss = 0;
    const box = $("#td").parentNode, el = $("#td");
    el.innerHTML = Array.from({ length: 16 }, (_, i) => `<button class="tdc" data-i="${i}"></button>`).join("");
    const cells = [...el.children];
    const next = () => { let n; do { n = Math.floor(Math.random() * 16); } while (n === lit); if (cells[lit]) cells[lit].classList.remove("on"); lit = n; cells[lit].classList.add("on"); };
    el.addEventListener("pointerdown", (e) => {
      const b = e.target.closest(".tdc"); if (!b || done) return;
      if (+b.dataset.i === lit) { score++; HUB.sfx.pop(); HUB.haptic(); next(); } else { miss++; HUB.sfx.miss(); score = Math.max(0, score - 1); }
    });
    next();
    A.timer(setInterval(() => { const left = Math.max(0, Math.ceil((LEN - (performance.now() - t0)) / 1000)); $("#xhud").textContent = `⚡ ${score}   ⏱ ${left}s`; if (left <= 0 && !done) { done = true; A.claim("tiledash", score, box); } }, 200));
  };

  /* ---------------- NeonSlice ---------------- */
  games.neonslice = async function () {
    const g = A.canvasGame("🍉 NeonSlice", "neonslice", 340, 460);
    try { await start("neonslice"); } catch (e) { return HUB.toast(e.message); }
    const { c, ctx, w, h } = g, LEN = 30000, t0 = performance.now(); let score = 0, lives = 3, last = t0, done = false, spawnAt = 0, trail = [];
    const orbs = [], COL = ["#ff4081", "#18ffff", "#76ff03", "#ffea00"];
    const spawn = () => { const bomb = Math.random() < 0.18; orbs.push({ x: 30 + Math.random() * (w - 60), y: h + 20, vx: (Math.random() - 0.5) * 120, vy: -(330 + Math.random() * 120), r: 22, bomb, col: bomb ? "#555" : COL[Math.floor(Math.random() * 4)] }); };
    const cut = (x, y) => { orbs.forEach((o) => { if (!o.dead && Math.hypot(o.x - x, o.y - y) < o.r + 6) { o.dead = true; if (o.bomb) { lives--; HUB.sfx.hit(); HUB.haptic("heavy"); } else { score++; HUB.sfx.pop(); } } }); };
    const pt = (ev) => { const r = c.getBoundingClientRect(), t = ev.touches ? ev.touches[0] : ev; return [t.clientX - r.left, t.clientY - r.top]; };
    let down = false;
    const mv = (ev) => { if (!down) return; const [x, y] = pt(ev); trail.push([x, y, performance.now()]); cut(x, y); };
    c.addEventListener("pointerdown", (e) => { down = true; mv(e); }); c.addEventListener("pointermove", mv); window.addEventListener("pointerup", () => { down = false; });
    function loop(now) {
      const dt = Math.min(0.05, (now - last) / 1000); last = now; const el = now - t0;
      if (now > spawnAt) { spawn(); if (Math.random() < 0.4) spawn(); spawnAt = now + 550 + Math.random() * 350; }
      ctx.fillStyle = "#101820"; ctx.fillRect(0, 0, w, h);
      orbs.forEach((o) => { o.vy += 520 * dt; o.x += o.vx * dt; o.y += o.vy * dt; });
      for (let i = orbs.length - 1; i >= 0; i--) if (orbs[i].dead || orbs[i].y > h + 40) orbs.splice(i, 1);
      orbs.forEach((o) => { ctx.beginPath(); ctx.arc(o.x, o.y, o.r, 0, 7); ctx.fillStyle = o.col; ctx.shadowColor = o.col; ctx.shadowBlur = o.bomb ? 0 : 14; ctx.fill(); ctx.shadowBlur = 0; if (o.bomb) { ctx.fillStyle = "#fff"; ctx.font = "20px sans-serif"; ctx.textAlign = "center"; ctx.fillText("💣", o.x, o.y + 7); } });
      trail = trail.filter((p) => now - p[2] < 180);
      ctx.strokeStyle = "#fff"; ctx.lineWidth = 3; ctx.beginPath(); trail.forEach((p, i) => (i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]))); ctx.stroke();
      g.hud.textContent = `🍉 ${score}   ❤️ ${Math.max(0, lives)}   ⏱ ${Math.max(0, Math.ceil((LEN - el) / 1000))}s`;
      if (!done && (el >= LEN || lives <= 0)) { done = true; return A.claim("neonslice", score, g.box); }
      A.raf(requestAnimationFrame(loop));
    }
    A.raf(requestAnimationFrame(loop));
  };

  /* ---------------- MintTap ---------------- */
  games.minttap = async function () {
    HUB.overlay2("🎯 MintTap", '<div class="xarc"><div class="xhud" id="xhud"></div><div class="mtbar" id="mtbar"><i id="mtz"></i><b id="mtk"></b></div><button class="btn primary mtbtn" id="mtgo">TAP!</button><div id="mtmsg" class="xnote">Stop the marker inside the green zone</div></div>');
    try { await start("minttap"); } catch (e) { return HUB.toast(e.message); }
    const LEN = 30000, t0 = performance.now(); let score = 0, combo = 0, done = false, pos = 0, dir = 1, zone = 40, zw = 22, spd = 1.0, last = t0;
    const box = $("#mtbar").parentNode, zEl = $("#mtz"), kEl = $("#mtk");
    const reroll = () => { zw = Math.max(9, 22 - combo * 1.2); zone = 4 + Math.random() * (92 - zw); zEl.style.left = zone + "%"; zEl.style.width = zw + "%"; };
    reroll();
    $("#mtgo").addEventListener("pointerdown", (e) => {
      e.preventDefault(); if (done) return;
      const hit = pos >= zone && pos <= zone + zw, perfect = hit && Math.abs(pos - (zone + zw / 2)) < zw * 0.2;
      if (hit) { combo++; const pts = (perfect ? 3 : 1) + Math.min(2, Math.floor(combo / 4)); score += pts; spd = Math.min(2.4, spd + 0.06); $("#mtmsg").textContent = (perfect ? "PERFECT +" : "Nice +") + pts + "  ×" + combo; HUB.sfx.pop(); HUB.haptic(); }
      else { combo = 0; spd = 1.0; $("#mtmsg").textContent = "Missed!"; HUB.sfx.miss(); }
      reroll();
    });
    function loop(now) {
      const dt = (now - last) / 1000; last = now; pos += dir * dt * 80 * spd; if (pos > 100) { pos = 100; dir = -1; } if (pos < 0) { pos = 0; dir = 1; }
      kEl.style.left = pos + "%";
      const left = Math.max(0, Math.ceil((LEN - (now - t0)) / 1000)); $("#xhud").textContent = `🎯 ${score}   ⏱ ${left}s`;
      if (left <= 0 && !done) { done = true; return A.claim("minttap", score, box); }
      A.raf(requestAnimationFrame(loop));
    }
    A.raf(requestAnimationFrame(loop));
  };

  /* ---------------- TurboCoin ---------------- */
  games.turbocoin = async function () {
    HUB.overlay2("🚀 TurboCoin", '<div class="xarc tv"><div class="xhud" id="xhud">Tap to start!</div><button id="tcb" class="tvbtn">🚀</button></div>');
    try { await start("turbocoin"); } catch (e) { return HUB.toast(e.message); }
    const box = $("#tcb").parentNode; let n = 0, t0 = 0, done = false, tm = 0;
    $("#tcb").addEventListener("pointerdown", (e) => {
      e.preventDefault(); if (done) return;
      if (!t0) { t0 = performance.now(); tm = setInterval(() => { const left = Math.max(0, 10 - (performance.now() - t0) / 1000); $("#xhud").textContent = `🚀 ${n}   ⏱ ${left.toFixed(1)}s`; if (left <= 0) { clearInterval(tm); done = true; A.claim("turbocoin", n, box); } }, 100); A.timer(tm); }
      n++; HUB.sfx.pop(); $("#tcb").animate([{ transform: "scale(.9)" }, { transform: "scale(1)" }], { duration: 80 });
    });
  };
})();

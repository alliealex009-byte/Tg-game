/* Arcade: solo games that pay coins. The server validates every claim (see app/arcade.py). */
(function () {
  const HUB = window.HUB;
  const $ = (s) => document.querySelector(s);
  const games = (HUB.arcadeGames = {});
  HUB.overlay2 = (t, h) => HUB.overlay(t, h, HUB.openArcade);
  let raf = 0, timers = [];
  HUB.stopArcade = function () { cancelAnimationFrame(raf); timers.forEach(clearInterval); timers = []; };
  const post = (p, b) => HUB.api(p, { method: "POST", body: p === "/api/arcade/start" ? Object.assign({ gid: HUB.S.gid }, b || {}) : (b || {}) });

  async function claim(game, score, box) {
    HUB.stopArcade();
    let msg;
    try {
      const r = await post("/api/arcade/claim", { game, score, gid: HUB.S.gid });
      msg = (r.coins ? `+${r.coins} coins 🎉` : "Daily arcade limit reached") + (r.group ? " · counted on your group board 🏆" : "");
      if (HUB.S.me) HUB.S.me.coins = r.balance;
      if (r.coins) { HUB.sfx.win(); HUB.confetti(40); }
    } catch (e) { msg = /too short/i.test(e.message) ? "That run was too short to pay coins - play a little longer!" : e.message; }
    box.insertAdjacentHTML("beforeend", `<div class="xres"><div class="big">Score ${score}</div><div>${HUB.esc(msg)}</div>
      <button class="btn primary" id="again">Play again</button></div>`);
    $("#again").addEventListener("click", () => games[game]());
  }

  function canvasGame(title, key, W, H) {
    const w = Math.min(W, window.innerWidth - 24), h = Math.round(w * H / W);
    HUB.overlay2(title, `<div class="xarc" id="xarc"><div class="xhud" id="xhud"></div>
      <canvas id="xc" width="${w * 2}" height="${h * 2}" style="width:${w}px;height:${h}px"></canvas></div>`);
    const c = $("#xc"), ctx = c.getContext("2d");
    ctx.scale(2, 2);
    return { c, ctx, w, h, box: $("#xarc"), hud: $("#xhud") };
  }
  const posX = (c, ev) => { const r = c.getBoundingClientRect(); const t = ev.touches ? ev.touches[0] : ev; return t.clientX - r.left; };

  /* ---------------- Break Bricks ---------------- */
  games.bricks = async function () {
    const g = canvasGame("🧱 Break Bricks", "bricks", 360, 520);
    try { await post("/api/arcade/start", { game: "bricks" }); } catch (e) { return HUB.toast(e.message); }
    const { c, ctx, w, h } = g;
    const cols = 8, rows = 6, bw = (w - 20) / cols, bh = 18;
    const COLS = ["#ef5350", "#ffa726", "#ffee58", "#66bb6a", "#42a5f5", "#ab47bc"];
    const bricks = [];
    for (let r = 0; r < rows; r++) for (let q = 0; q < cols; q++) bricks.push({ x: 10 + q * bw, y: 50 + r * (bh + 4), alive: true, col: COLS[r] });
    const pad = { x: w / 2 - 36, w: 72, h: 12, y: h - 36 };
    const ball = { x: w / 2, y: pad.y - 10, vx: 160, vy: -260, r: 7, stuck: true };
    let lives = 3, score = 0, last = performance.now(), over = false;
    const move = (ev) => { pad.x = Math.max(0, Math.min(w - pad.w, posX(c, ev) - pad.w / 2)); if (ball.stuck) ball.x = pad.x + pad.w / 2; ev.preventDefault && ev.preventDefault(); };
    c.addEventListener("pointermove", move); c.addEventListener("touchmove", move, { passive: false });
    c.addEventListener("pointerdown", (ev) => { move(ev); ball.stuck = false; });
    function loop(now) {
      const dt = Math.min(0.033, (now - last) / 1000); last = now;
      if (!ball.stuck && !over) {
        ball.x += ball.vx * dt; ball.y += ball.vy * dt;
        if (ball.x < ball.r) { ball.x = ball.r; ball.vx *= -1; HUB.sfx.step(); }
        if (ball.x > w - ball.r) { ball.x = w - ball.r; ball.vx *= -1; HUB.sfx.step(); }
        if (ball.y < ball.r) { ball.y = ball.r; ball.vy *= -1; HUB.sfx.step(); }
        if (ball.vy > 0 && ball.y + ball.r >= pad.y && ball.y - ball.r <= pad.y + pad.h && ball.x >= pad.x - 4 && ball.x <= pad.x + pad.w + 4) {
          const k = (ball.x - (pad.x + pad.w / 2)) / (pad.w / 2);
          const sp = Math.min(520, Math.hypot(ball.vx, ball.vy) * 1.02);
          ball.vx = k * sp * 0.75; ball.vy = -Math.sqrt(Math.max(sp * sp - ball.vx * ball.vx, 1)); ball.y = pad.y - ball.r; HUB.sfx.place();
        }
        for (const b of bricks) {
          if (!b.alive) continue;
          if (ball.x + ball.r > b.x && ball.x - ball.r < b.x + bw - 2 && ball.y + ball.r > b.y && ball.y - ball.r < b.y + bh) {
            b.alive = false; score++; ball.vy *= -1; HUB.sfx.pop(); HUB.haptic();
            ball.vx *= 1.01; ball.vy *= 1.01; break;
          }
        }
        if (ball.y > h + 10) {
          lives--; HUB.sfx.bad();
          ball.stuck = true; ball.vx = 160 * (Math.random() < 0.5 ? -1 : 1); ball.vy = -260; ball.y = pad.y - 10;
          if (lives <= 0) over = true;
        }
        if (bricks.every((b) => !b.alive)) over = true;
      }
      ctx.fillStyle = "#101820"; ctx.fillRect(0, 0, w, h);
      for (const b of bricks) if (b.alive) { ctx.fillStyle = b.col; ctx.beginPath(); ctx.roundRect(b.x, b.y, bw - 2, bh, 4); ctx.fill(); }
      ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.roundRect(pad.x, pad.y, pad.w, pad.h, 6); ctx.fill();
      ctx.beginPath(); ctx.arc(ball.x, ball.y, ball.r, 0, 7); ctx.fillStyle = "#ffd24a"; ctx.fill();
      g.hud.textContent = `🧱 ${score}   ❤️ ${"♥".repeat(Math.max(lives, 0))}${ball.stuck && !over ? "   · tap to launch" : ""}`;
      if (over) return claim("bricks", score, g.box);
      raf = requestAnimationFrame(loop);
    }
    raf = requestAnimationFrame(loop);
  };

  /* ---------------- QuickDrop ---------------- */
  games.quickdrop = async function () {
    const g = canvasGame("☄️ QuickDrop", "quickdrop", 360, 520);
    try { await post("/api/arcade/start", { game: "quickdrop" }); } catch (e) { return HUB.toast(e.message); }
    const { c, ctx, w, h } = g;
    const basket = { x: w / 2 - 30, w: 60, y: h - 40 };
    const items = []; let score = 0, spawn = 0, last = performance.now(); const t0 = last, LEN = 30000;
    const move = (ev) => { basket.x = Math.max(0, Math.min(w - basket.w, posX(c, ev) - basket.w / 2)); ev.preventDefault && ev.preventDefault(); };
    c.addEventListener("pointermove", move); c.addEventListener("touchmove", move, { passive: false }); c.addEventListener("pointerdown", move);
    ctx.font = "26px system-ui"; ctx.textAlign = "center";
    function loop(now) {
      const dt = Math.min(0.033, (now - last) / 1000); last = now;
      const el = now - t0;
      spawn -= dt;
      if (spawn <= 0) { items.push({ x: 20 + Math.random() * (w - 40), y: -20, bomb: Math.random() < 0.28, v: 140 + Math.random() * 120 + el / 300 }); spawn = Math.max(0.3, 0.7 - el / 60000); }
      for (let i = items.length - 1; i >= 0; i--) {
        const it = items[i]; it.y += it.v * dt;
        if (it.y > basket.y - 8 && it.y < basket.y + 20 && it.x > basket.x - 6 && it.x < basket.x + basket.w + 6) {
          if (it.bomb) { score = Math.max(0, score - 3); HUB.sfx.bad(); HUB.haptic("heavy"); } else { score++; HUB.sfx.cash(); }
          items.splice(i, 1);
        } else if (it.y > h + 20) items.splice(i, 1);
      }
      ctx.fillStyle = "#12182b"; ctx.fillRect(0, 0, w, h);
      for (const it of items) ctx.fillText(it.bomb ? "💣" : "🪙", it.x, it.y);
      ctx.fillText("🧺", basket.x + basket.w / 2, basket.y + 16);
      g.hud.textContent = `🪙 ${score}   ⏱ ${Math.max(0, Math.ceil((LEN - el) / 1000))}s`;
      if (el >= LEN) return claim("quickdrop", score, g.box);
      raf = requestAnimationFrame(loop);
    }
    raf = requestAnimationFrame(loop);
  };

  /* ---------------- GridPop ---------------- */
  games.gridpop = async function () {
    HUB.overlay2("🔷 GridPop", '<div class="xarc"><div class="xhud" id="xhud"></div><div id="gp" class="gpgrid"></div></div>');
    try { await post("/api/arcade/start", { game: "gridpop" }); } catch (e) { return HUB.toast(e.message); }
    const N = 8, COL = ["#ef5350", "#42a5f5", "#66bb6a", "#fdd835", "#ab47bc"];
    let grid = Array.from({ length: N }, () => Array.from({ length: N }, () => Math.floor(Math.random() * 4)));
    let score = 0, t0 = performance.now(); const LEN = 60000, box = $("#xarc"); let done = false;
    const el = $("#gp");
    function group(r, q) {
      const v = grid[r][q]; if (v < 0) return [];
      const seen = new Set([r * N + q]), st = [[r, q]], out = [];
      while (st.length) {
        const [a, b] = st.pop(); out.push([a, b]);
        for (const [da, db] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
          const x = a + da, y = b + db;
          if (x >= 0 && y >= 0 && x < N && y < N && grid[x][y] === v && !seen.has(x * N + y)) { seen.add(x * N + y); st.push([x, y]); }
        }
      }
      return out;
    }
    function hasMove() { for (let r = 0; r < N; r++) for (let q = 0; q < N; q++) if (grid[r][q] >= 0 && group(r, q).length > 1) return true; return false; }
    function draw() {
      el.innerHTML = grid.map((row, r) => row.map((v, q) => `<button class="gpc ${v < 0 ? "e" : ""}" data-r="${r}" data-q="${q}" style="background:${v < 0 ? "transparent" : COL[v]}"></button>`).join("")).join("");
    }
    function finish() { if (done) return; done = true; claim("gridpop", score, box); }
    el.addEventListener("click", (e) => {
      const b = e.target.closest(".gpc"); if (!b || done) return;
      const g = group(+b.dataset.r, +b.dataset.q);
      if (g.length < 2) { HUB.sfx.miss(); return; }
      g.forEach(([r, q]) => { grid[r][q] = -1; });
      score += g.length * g.length; HUB.sfx.pop(); HUB.haptic();
      for (let q = 0; q < N; q++) {            // gravity
        const col = []; for (let r = N - 1; r >= 0; r--) if (grid[r][q] >= 0) col.push(grid[r][q]);
        for (let r = N - 1; r >= 0; r--) grid[r][q] = col[N - 1 - r] === undefined ? -1 : col[N - 1 - r];
      }
      draw();
      if (!hasMove()) finish();
    });
    draw();
    timers.push(setInterval(() => {
      const left = Math.max(0, Math.ceil((LEN - (performance.now() - t0)) / 1000));
      $("#xhud").textContent = `⭐ ${score}   ⏱ ${left}s`;
      if (left <= 0) finish();
    }, 250));
  };

  /* ---------------- TapVerse (tap to earn) ---------------- */
  games.tapverse = async function () {
    const o = HUB.overlay2("🪙 TapVerse", '<div class="xarc tv"><div id="tvcoins" class="tvc"></div><button id="tvbtn" class="tvbtn">🪙</button>' +
      '<div class="tvbar"><i id="tvfill"></i></div><div id="tvinfo" class="xnote"></div><button class="btn" id="tvup"></button></div>');
    let st;
    try { st = await post("/api/tap", {}); } catch (e) { return HUB.toast(e.message); }
    let pending = 0, energy = st.energy;
    const render = () => {
      $("#tvcoins").textContent = "💰 " + st.coins;
      $("#tvfill").style.width = (100 * energy / st.max) + "%";
      $("#tvinfo").textContent = `⚡ ${Math.floor(energy)}/${st.max} · +${st.level} per tap · ${st.left} arcade coins left today`;
      $("#tvup").textContent = st.level >= 10 ? "Max level" : `⬆ Upgrade tap power (${st.upgrade} coins)`;
    };
    render();
    const btn = $("#tvbtn");
    btn.addEventListener("pointerdown", (ev) => {
      if (energy < 1) { HUB.sfx.miss(); return; }
      energy -= 1; pending++; st.coins += st.level; HUB.sfx.chip(); HUB.haptic();
      const f = document.createElement("div"); f.className = "tvf"; f.textContent = "+" + st.level;
      f.style.left = ev.clientX + "px"; f.style.top = ev.clientY + "px"; document.body.appendChild(f);
      f.animate([{ transform: "translateY(0)", opacity: 1 }, { transform: "translateY(-70px)", opacity: 0 }], { duration: 700 }).finished.then(() => f.remove(), () => f.remove());
      btn.animate([{ transform: "scale(.92)" }, { transform: "scale(1)" }], { duration: 120 });
      render();
    });
    const flush = async () => {
      if (!pending) { try { st = await post("/api/tap", {}); energy = st.energy; } catch (e) { /* ignore */ } render(); return; }
      const n = pending; pending = 0;
      try { st = await post("/api/tap", { n }); energy = st.energy + pending; if (HUB.S.me) HUB.S.me.coins = st.coins; } catch (e) { HUB.toast(e.message); }
      render();
    };
    timers.push(setInterval(flush, 1200));
    timers.push(setInterval(() => { energy = Math.min(st.max, energy + 0.5 / 4); render(); }, 250));
    $("#tvup").addEventListener("click", async () => {
      try { await flush(); st = await post("/api/tap/upgrade"); energy = st.energy; HUB.sfx.win(); render(); } catch (e) { HUB.toast(e.message); }
    });
  };

  /* ---------------- PocketFarm (idle) ---------------- */
  games.pocketfarm = async function () {
    HUB.overlay2("🌱 PocketFarm", '<div class="xarc"><div id="pfc" class="tvc"></div><div id="pf" class="pfgrid"></div><div id="pfi" class="xnote"></div></div>');
    let st;
    const load = async (body) => { try { st = await post("/api/farm", body); render(); } catch (e) { HUB.toast(e.message); } };
    function render() {
      $("#pfc").textContent = "💰 " + st.coins;
      $("#pfi").textContent = `Seed ${st.seed} coins · ripe in ${st.grow}s · harvest pays ${st.harvest}`;
      $("#pf").innerHTML = st.plots.map((p, i) => p === null
        ? `<button class="pfp" data-i="${i}" data-a="plant">🟫<small>Plant</small></button>`
        : p.ripe ? `<button class="pfp ripe" data-i="${i}" data-a="harvest">🥕<small>Harvest</small></button>`
          : `<button class="pfp grow" disabled>🌱<small>${p.left}s</small></button>`).join("");
    }
    $("#pf").addEventListener("click", (e) => {
      const b = e.target.closest(".pfp"); if (!b || !b.dataset.a) return;
      HUB.sfx.chip(); load({ idx: +b.dataset.i, action: b.dataset.a });
    });
    await load({});
    timers.push(setInterval(() => {
      if (!st) return;
      st.plots = st.plots.map((p) => (p === null ? null : { left: Math.max(0, p.left - 1), ripe: p.left <= 1 }));
      render();
    }, 1000));
  };
  HUB.arc = { claim, canvasGame, posX, post, timer: (id) => timers.push(id), raf: (id) => { raf = id; }, games };
})();
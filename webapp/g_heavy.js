/* Heavy-visual upgrades (canvas): Car Racing with an animated track, particles and screen shake.
   Loaded after g_arena.js, so it replaces HUB.UI.race. Falls back gracefully if canvas is unavailable. */
(function () {
  "use strict";
  const HUB = window.HUB;
  if (!HUB || !HUB.UI || !HUB.UI.race) return;
  const $ = (s, r) => (r || document).querySelector(s);
  const K = () => HUB.kit;
  const room = () => HUB.S.room;
  const playing = (s) => s.game.players.some((p) => p.uid === s.you);
  const sfx = (n) => { try { HUB.sfx[n](); } catch (e) { /* ignore */ } };
  const tone = (...a) => { try { HUB.tone(...a); } catch (e) { /* ignore */ } };
  const GEAR = { cruise: ["🚗", "Cruise", "+2"], boost: ["🏎️", "Boost", "+3 · heat+1"], nitro: ["🚀", "Nitro", "+5 · heat+2"] };
  const COLORS = ["#4285f4", "#ea4335", "#34a853", "#fbbc05"];
  const LANE_H = 58, PAD_L = 14, PAD_R = 34;

  function car(ctx, x, y, col, rot, glow) {
    ctx.save(); ctx.translate(x, y); ctx.rotate(rot);
    if (glow) { ctx.shadowColor = glow; ctx.shadowBlur = 16; }
    ctx.fillStyle = "#0006"; ctx.beginPath(); ctx.ellipse(1, 4, 21, 9, 0, 0, 7); ctx.fill(); ctx.shadowBlur = 0;
    ctx.fillStyle = col; ctx.beginPath(); ctx.roundRect(-20, -9, 40, 18, 7); ctx.fill();
    ctx.fillStyle = "#ffffff55"; ctx.beginPath(); ctx.roundRect(-18, -8, 34, 5, 3); ctx.fill();
    ctx.fillStyle = "#16202c"; ctx.beginPath(); ctx.roundRect(-5, -6.5, 14, 13, 4); ctx.fill();   // cabin
    ctx.fillStyle = "#cfe8ff"; ctx.fillRect(5, -5.5, 3, 11);                                          // windscreen
    ctx.fillStyle = "#fff8c0"; ctx.fillRect(18, -7, 3, 4); ctx.fillRect(18, 3, 3, 4);                 // lights
    ctx.fillStyle = "#111"; [[-12, -10], [-12, 10], [10, -10], [10, 10]].forEach(([a, b]) => ctx.fillRect(a - 4, b - 2, 8, 4));
    ctx.restore();
  }

  function build(s) {
    const g = s.game, n = g.players.length;
    K().newUI("race", s, { lastSeq: 0, locked: false, cur: {}, tgt: {}, rot: {}, fx: [], shake: 0, t: 0, nitro: {}, smoke: {}, raf: 0 });
    K().shell(s, `<div class="gx-box"><canvas id="gxcv" class="hv-cv" style="width:100%;height:${n * LANE_H + 16}px"></canvas>
      <div class="gx-msg" id="gxmsg">Pick a gear — everyone chooses at once!</div>
      <div class="gx-gears" id="gxgears">${Object.entries(GEAR).map(([k, v]) => `<button class="gx-g" data-g="${k}"><span>${v[0]}</span><b>${v[1]}</b><small>${v[2]}</small></button>`).join("")}</div></div>`);
    const ui = HUB.S.ui;
    g.players.forEach((p) => { ui.cur[p.uid] = p.pos; ui.tgt[p.uid] = p.pos; ui.rot[p.uid] = 0; });
    $("#gxgears").onclick = (e) => {
      const b = e.target.closest(".gx-g"), s2 = room();
      if (!b || b.disabled || !playing(s2) || ui.locked) return;
      ui.locked = true; HUB.send({ t: "gear", gear: b.dataset.g }); HUB.haptic("medium"); sfx("pop");
      document.querySelectorAll(".gx-g").forEach((x) => x.classList.toggle("sel", x === b));
      $("#gxmsg").textContent = "Locked in " + b.dataset.g + " — waiting…";
    };
    loop(ui);
  }

  function burst(ui, x, y, color, n, spd) {
    for (let i = 0; i < n; i++) {
      const a = Math.random() * 6.28, v = (0.4 + Math.random()) * (spd || 2.5);
      ui.fx.push({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life: 1, d: 0.025 + Math.random() * 0.03, c: color, r: 1.5 + Math.random() * 2.5 });
    }
  }

  function loop(ui) {
    const cv = $("#gxcv");
    if (!cv || HUB.S.ui !== ui) return;                       // screen changed: stop the loop
    const g = room().game, n = g.players.length, dpr = Math.min(2, window.devicePixelRatio || 1);
    const W = cv.clientWidth || 340, H = n * LANE_H + 16;
    if (cv.width !== Math.round(W * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
    const ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ui.t += 1;
    const sh = ui.shake > 0.2 ? (Math.random() - 0.5) * ui.shake : 0; ui.shake *= 0.88;
    ctx.save(); ctx.translate(sh, sh * 0.6);
    // grass + road
    ctx.fillStyle = "#2e6b34"; ctx.fillRect(0, 0, W, H);
    const trackW = W - PAD_L - PAD_R, unit = trackW / g.length;
    ctx.fillStyle = "#3a3d44"; ctx.fillRect(0, 8, W, n * LANE_H);
    ctx.fillStyle = "#ffffff30";
    for (let i = 1; i < n; i++) { for (let x = -((ui.t * 2) % 36); x < W; x += 36) ctx.fillRect(x, 8 + i * LANE_H - 1.5, 18, 3); }
    ctx.fillStyle = "#fff"; ctx.fillRect(0, 7, W, 2); ctx.fillRect(0, 8 + n * LANE_H - 1, W, 2);
    // tile ticks
    ctx.fillStyle = "#ffffff18"; for (let i = 1; i < g.length; i++) ctx.fillRect(PAD_L + i * unit, 8, 1, n * LANE_H);
    // finish line chequer
    const fx = PAD_L + g.length * unit;
    for (let r = 0; r < n * LANE_H / 8; r++) for (let c = 0; c < 3; c++) { ctx.fillStyle = (r + c) % 2 ? "#fff" : "#111"; ctx.fillRect(fx + c * 8 - 4, 8 + r * 8, 8, 8); }
    // oil slicks
    g.oil.forEach((o) => g.players.forEach((p, i) => {
      const ox = PAD_L + o * unit, oy = 8 + i * LANE_H + LANE_H / 2;
      ctx.fillStyle = "#0b0b10"; ctx.beginPath(); ctx.ellipse(ox, oy, 13, 8, 0, 0, 7); ctx.fill();
      ctx.fillStyle = "#6a5acd55"; ctx.beginPath(); ctx.ellipse(ox - 3, oy - 2, 6, 3, 0.4, 0, 7); ctx.fill();
    }));
    // cars
    g.players.forEach((p, i) => {
      const u = p.uid, y = 8 + i * LANE_H + LANE_H / 2;
      const d = ui.tgt[u] - ui.cur[u];
      const speed = Math.abs(d) > 0.02 ? Math.min(Math.abs(d), 0.12 + Math.abs(d) * 0.07) * Math.sign(d) : d;
      ui.cur[u] += speed;
      const x = PAD_L + ui.cur[u] * unit + 20;
      ui.rot[u] *= 0.9;
      const moving = Math.abs(d) > 0.05;
      if (moving && ui.t % 2 === 0) {
        ui.fx.push({ x: x - 22, y: y + (Math.random() - 0.5) * 6, vx: -1.2, vy: (Math.random() - 0.5) * 0.4, life: 1, d: 0.05, c: ui.nitro[u] ? "#ff9d2e" : "#cfcfcf", r: ui.nitro[u] ? 4 : 2.5 });
        if (ui.nitro[u]) for (let k = 0; k < 3; k++) ctx.fillStyle = "#ff7a1a", ctx.fillRect(x - 22 - k * 6, y - 3 + k, 6, 2);
        ctx.fillStyle = "#ffffff30"; for (let k = 1; k < 5; k++) ctx.fillRect(x - 30 - k * 14, y - 12 + k * 5, 18, 1.5);   // speed lines
      }
      if (ui.smoke[u]) ui.fx.push({ x: x, y: y - 6, vx: (Math.random() - 0.5) * 0.4, vy: -0.7, life: 1, d: 0.025, c: "#8a8a8a", r: 4 + Math.random() * 3 });
      if (p.stalled && ui.t % 3 === 0) ui.fx.push({ x: x, y: y - 8, vx: 0, vy: -0.6, life: 1, d: 0.03, c: "#777", r: 5 });
      car(ctx, x, y, COLORS[i % 4], ui.rot[u], u === room().you ? "#ffffffaa" : (ui.nitro[u] && moving ? "#ff9d2e" : null));
      ctx.fillStyle = "#fff"; ctx.font = "700 10px system-ui"; ctx.textAlign = "left";
      ctx.fillText((u === room().you ? "You" : (K().nameOf(room(), u) || "").slice(0, 8)), 4, y - 20);
      // heat bar
      ctx.fillStyle = "#0008"; ctx.fillRect(W - PAD_R + 6, y - 14, 6, 28);
      ctx.fillStyle = p.heat >= 3 ? "#ff3b30" : p.heat >= 2 ? "#ff9d2e" : "#34c759"; const hh = Math.min(28, p.heat * 7); ctx.fillRect(W - PAD_R + 6, y + 14 - hh, 6, hh);
    });
    // particles
    ui.fx = ui.fx.filter((f) => f.life > 0);
    ui.fx.forEach((f) => { f.x += f.vx; f.y += f.vy; f.life -= f.d; ctx.globalAlpha = Math.max(0, f.life); ctx.fillStyle = f.c; ctx.beginPath(); ctx.arc(f.x, f.y, f.r * (f.c === "#8a8a8a" || f.c === "#777" ? 2 - f.life : f.life + 0.3), 0, 7); ctx.fill(); });
    ctx.globalAlpha = 1; ctx.restore();
    ui.raf = requestAnimationFrame(() => loop(ui));
  }

  function apply(s) {
    const ui = HUB.S.ui, g = s.game, lr = g.last_round;
    if (!ui || !ui.cur) return;
    if (ui.first) { ui.first = false; if (lr) ui.lastSeq = lr.seq; g.players.forEach((p) => { ui.cur[p.uid] = ui.tgt[p.uid] = p.pos; }); }
    else if (lr && lr.seq > ui.lastSeq) {
      ui.lastSeq = lr.seq; ui.locked = false;
      sfx("roll"); HUB.haptic("light");
      g.players.forEach((p) => { ui.tgt[p.uid] = p.pos; const m = lr.moves[p.uid]; ui.nitro[p.uid] = m && m.gear === "nitro"; });
      const gearsMax = Math.max(...Object.values(lr.moves).map((m) => m.gain));
      tone(110, 0.5, "sawtooth", 0.12, 0, 90 + gearsMax * 40);                           // engine rev
      const label = { stall: "stalled 🥵", overheat: "overheated 🔥", oil: "hit oil 🛢️", bump: "got bumped 💥" };
      lr.events.forEach((e, k) => {
        const i = g.players.findIndex((p) => p.uid === e.uid), y = 8 + i * LANE_H + LANE_H / 2, x = PAD_L + (ui.tgt[e.uid]) * ((($("#gxcv") || {}).clientWidth || 340) - PAD_L - PAD_R) / g.length + 20;
        setTimeout(() => {
          if (e.e === "bump") { ui.shake = 14; burst(ui, x, y, "#ffd24a", 16, 3.5); sfx("capture"); HUB.haptic("heavy"); }
          if (e.e === "oil") { ui.rot[e.uid] = 1.6; burst(ui, x, y, "#222", 10, 2); tone(500, 0.35, "sawtooth", 0.15, 0, 120); }
          if (e.e === "overheat") { ui.smoke[e.uid] = true; sfx("miss"); }
          if (e.e === "stall") { ui.smoke[e.uid] = false; burst(ui, x, y, "#999", 8, 1.2); }
        }, 650 + k * 120);
      });
      $("#gxmsg").textContent = lr.events.map((e) => `${e.uid === s.you ? "You" : K().nameOf(s, e.uid)} ${label[e.e]}`).join(" · ") || "Round " + lr.round;
      if (s.status === "finished") setTimeout(() => g.players.forEach((p) => burst(ui, 0, 0, "#ffd24a", 0)), 900);
    } else g.players.forEach((p) => { if (Math.abs(ui.tgt[p.uid] - p.pos) > 0.01 && !lr) ui.tgt[p.uid] = p.pos; });
    const me = playing(s), ok = me && s.status === "playing" && !g.picked[s.you];
    if (ok) { ui.locked = false; document.querySelectorAll(".gx-g").forEach((x) => x.classList.remove("sel")); }
    const mine = g.players.find((p) => p.uid === s.you);
    document.querySelectorAll(".gx-g").forEach((b) => { b.disabled = !ok || (mine && mine.stalled); });
    $("#gxgears").classList.toggle("hidden", !me);
    if (me && mine.stalled && ok) $("#gxmsg").textContent = "🥵 Engine stalled — you lose this round";
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).pos + "/" + g.length }));
    K().setHint(me ? (g.picked[s.you] ? "Waiting for other drivers…" : "Heat 4 = stall! Nitro is fast but hot") : "👀 Watching the race");
  }
  HUB.UI.race = { build, apply };

  /* ---------------- Tank Duel: muzzle flash, smoke trail, explosion, screen shake, damage popups ---------------- */
  const T = HUB.UI.tank;
  if (T) {
    const orig = T.apply;
    const spawn = (host, x, y, css, anim, ms) => {
      const d = document.createElement("i");
      d.style.cssText = `position:absolute;left:${x}px;top:${y}px;pointer-events:none;border-radius:50%;z-index:9;${css}`;
      host.appendChild(d);
      if (d.animate) d.animate(anim, { duration: ms, easing: "ease-out" }).onfinish = () => d.remove(); else setTimeout(() => d.remove(), ms);
    };
    T.apply = function (s) {
      const ui = HUB.S.ui, g = s.game, ls = g.last_shot, svg = $("#gxsky");
      const fresh = svg && !ui.first && ls && ls.seq > ui.lastSeq && ls.path && ls.path.length;
      const r = orig(s);
      if (fresh) {
        const host = svg.parentElement; host.style.position = "relative";
        const box = svg.getBoundingClientRect(), hb = host.getBoundingClientRect();
        const px = (x) => box.left - hb.left + ((x + 0.5) / g.w) * box.width, py = (y) => box.top - hb.top + ((20 - y) / 20) * box.height;
        const p0 = ls.path[0];
        spawn(host, px(p0[0]) - 12, py(p0[1]) - 12, "width:24px;height:24px;background:radial-gradient(#fff,#ffd24a 50%,transparent 70%)", [{ transform: "scale(.3)", opacity: 1 }, { transform: "scale(2.2)", opacity: 0 }], 260);
        tone(160, 0.25, "sawtooth", 0.25, 0, 50);
        ls.path.forEach((pt, i) => { if (i % 2 === 0) setTimeout(() => spawn(host, px(pt[0]) - 3, py(pt[1]) - 3, "width:7px;height:7px;background:#bbb", [{ opacity: 0.7, transform: "scale(.6)" }, { opacity: 0, transform: "scale(2)" }], 500), i * 28); });
        if (ls.kind !== "out" && ls.impact) {
          setTimeout(() => {
            const ix = px(ls.impact[0]), iy = py(ls.impact[1]), hit = Object.values(ls.dmg || {}).some((d) => d > 0);
            for (let i = 0; i < 18; i++) {
              const a = Math.random() * 6.28, d = 20 + Math.random() * 46;
              spawn(host, ix, iy, `width:${4 + Math.random() * 6}px;height:${4 + Math.random() * 6}px;background:${["#ff7043", "#ffd24a", "#555", "#8b5a2b"][i % 4]}`,
                [{ transform: "translate(0,0) scale(1)", opacity: 1 }, { transform: `translate(${Math.cos(a) * d}px,${Math.sin(a) * d - 14}px) scale(.2)`, opacity: 0 }], 500 + Math.random() * 350);
            }
            spawn(host, ix - 30, iy - 30, "width:60px;height:60px;background:radial-gradient(#fff,#ff9d2e 40%,transparent 70%)", [{ transform: "scale(.2)", opacity: 1 }, { transform: "scale(1.6)", opacity: 0 }], 420);
            if (host.animate) host.animate([{ transform: "translate(0,0)" }, { transform: `translate(${hit ? -6 : -2}px,3px)` }, { transform: "translate(5px,-3px)" }, { transform: "translate(-3px,2px)" }, { transform: "none" }], { duration: hit ? 420 : 220 });
            if (hit) Object.entries(ls.dmg).filter(([, d]) => d > 0).forEach(([u, d]) => {
              const t = document.querySelector(`#gxsky .tk[data-uid="${u}"]`), tb = t && t.getBoundingClientRect();
              if (tb) spawn(host, tb.left - hb.left, tb.top - hb.top - 14, "color:#ff5a4f;font:800 16px system-ui;text-shadow:0 1px 3px #000;border-radius:0", [{ transform: "translateY(0)", opacity: 1 }, { transform: "translateY(-34px)", opacity: 0 }], 900);
              const el = host.lastElementChild; if (el && tb) el.textContent = "-" + d;
            });
            tone(90, 0.45, "sawtooth", 0.3, 0, 30);
          }, ls.path.length * 28);
        }
      }
      return r;
    };
  }
})();

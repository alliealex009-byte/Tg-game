/* ---- Batch 7: rich versions of Pony Rush, Pani Puri Rush and Memo Flip (override the simple ones; same keys/rules/score ranges) ---- */
(function () {
  const HUB = window.HUB, A = HUB.arc, games = A.games, mk0 = A.mk;
  const rnd = (a, b) => a + Math.random() * (b - a);
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const lerp = (a, b, t) => a + (b - a) * t;
  const ease = (t) => 1 - Math.pow(1 - t, 3);
  const rr = (ctx, x, y, w, h, r) => { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); };
  const text = (ctx, s, x, y, size, col, al, wt) => { ctx.font = `${wt || 800} ${size}px system-ui,sans-serif`; ctx.textAlign = al || "center"; ctx.fillStyle = col; ctx.fillText(s, x, y); };
  const hex = (h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  const mix = (c1, c2, t) => { const a = hex(c1), b = hex(c2); return `rgb(${Math.round(lerp(a[0], b[0], t))},${Math.round(lerp(a[1], b[1], t))},${Math.round(lerp(a[2], b[2], t))})`; };
  const grad = (ctx, x0, y0, x1, y1, stops) => { const g = ctx.createLinearGradient(x0, y0, x1, y1); for (const s of stops) g.addColorStop(s[0], s[1]); return g; };
  const intro = (ctx, w, h, t, l1, l2, y) => {
    if (t > 2.5) return;
    ctx.save(); ctx.globalAlpha = t > 2 ? (2.5 - t) / 0.5 : Math.min(1, t * 4);
    ctx.fillStyle = "rgba(20,10,5,.72)"; rr(ctx, 20, y, w - 40, 62, 16); ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,.3)"; ctx.lineWidth = 1.5; ctx.stroke();
    text(ctx, l1, w / 2, y + 26, 16, "#fff"); text(ctx, l2, w / 2, y + 48, 12.5, "#ffe0b2", "center", 600);
    ctx.restore();
  };
  // harness wrapper: canvas may be narrower than logical size, so scale everything
  const mk = (key, title, W, H, setup) => mk0(key, title, W, H, (a) => {
    const k = a.w / W;
    const a2 = { w: W, h: H, hud: a.hud, finish: a.finish, S: a.S, sfx: a.sfx, tone: a.tone, shake: a.shake, box: a.box,
      burst: (x, y, c, n, sp) => a.burst(x * k, y * k, c, n, (sp || 120) * k) };
    const g = setup(a2), w = {};
    if (g.down) w.down = (x, y) => g.down(x / k, y / k);
    if (g.move) w.move = (x, y) => g.move(x / k, y / k);
    if (g.up) w.up = (x, y) => g.up(x / k, y / k);
    if (g.key) w.key = g.key;
    w.update = g.update;
    w.draw = (ctx) => { ctx.save(); ctx.scale(k, k); g.draw(ctx); ctx.restore(); };
    return w;
  });

  /* ================================ PONY RUSH ================================ */
  games.ponyrush = mk("ponyrush", "🐎 Pony Rush", 340, 400, (a) => {
    const W = a.w, H = a.h, GY = H - 62, PX = 84, S = a.S;
    const mesas = [], cacti = [], dust = [], pops = [], lines = [];
    for (let i = 0; i < 6; i++) mesas.push({ x: i * 120, w: rnd(80, 130), h: rnd(40, 80), top: rnd(0.55, 0.8) });
    for (let i = 0; i < 7; i++) cacti.push({ x: i * 70 + rnd(0, 40), s: rnd(0.6, 1) });
    for (let i = 0; i < 14; i++) lines.push({ x: rnd(0, W), y: rnd(40, GY), l: rnd(20, 50) });
    let py = GY, vy = 0, jumps = 0, dist = 0, speed = 210, score = 0, coins = 0, bags = 0, spawn = 1.2, ph = 0, dustT = 0, fall = 0, ride = 0;
    let obs = [], picks = [];
    const bump = (s, x, y, c) => pops.push({ s, x, y, c, t: 0 });
    const jump = () => {
      if (S.over || fall) return;
      if (jumps === 0) { vy = -560; jumps = 1; a.sfx("pop"); a.burst(PX - 10, GY, "#d7ccc8", 8, 60); }
      else if (jumps === 1) { vy = -470; jumps = 2; a.sfx("good"); a.burst(PX, py + 6, "#fff", 10, 90); }
    };
    const die = (pit) => { a.sfx("capture"); a.shake(12); a.burst(PX, py - 20, "#ffb74d", 28, 180); if (pit) fall = 0.01; a.finish(score); };
    const addPicks = () => {
      const kind = Math.random() < 0.35 ? "bag" : "coin", n = kind === "bag" ? 1 : 3 + Math.floor(rnd(0, 3)), y0 = GY - rnd(46, 120);
      for (let i = 0; i < n; i++) picks.push({ x: W + 30 + i * 28, y: y0 - Math.sin(i / Math.max(1, n - 1) * Math.PI) * 26, k: kind });
    };
    const addObs = () => {
      const r = Math.random(), x = W + 40;
      if (r < 0.22) obs.push({ t: "fence", x, w: 44, h: 30 });
      else if (r < 0.42) obs.push({ t: "rock", x, w: 30, h: 24 });
      else if (r < 0.62) obs.push({ t: "cactus", x, w: 24, h: rnd(40, 56) });
      else if (r < 0.8) obs.push({ t: "weed", x, w: 26, h: 26, r: 0 });
      else obs.push({ t: "gap", x, w: rnd(54, 70), h: 0 });
    };
    const horse = (ctx, ox, oy, air, t) => {
      ctx.save(); ctx.translate(ox, oy); ctx.lineCap = "round"; ctx.lineJoin = "round";
      ctx.fillStyle = "#0003"; ctx.beginPath(); ctx.ellipse(0, 2 - (oy - GY) * 0, 30, 4, 0, 0, 7); ctx.fill();
      const leg = (hx, hy, p, col, front) => {
        const up = air ? (front ? -0.9 : 0.9) : Math.sin(p) * 0.85, lo = air ? (front ? 0.5 : -0.5) : Math.max(0, Math.sin(p + 1.4)) * 1.3 * (front ? 1 : -1) * -1;
        const kx = hx + Math.sin(up) * 12, ky = hy + Math.cos(up) * 12, fx = kx + Math.sin(up - lo * (front ? 1 : -1)) * 12, fy = ky + Math.cos(up - lo * (front ? 1 : -1)) * 12;
        ctx.strokeStyle = col; ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(hx, hy); ctx.lineTo(kx, ky); ctx.lineTo(fx, fy); ctx.stroke();
        ctx.strokeStyle = "#2b1a12"; ctx.lineWidth = 5.5; ctx.beginPath(); ctx.moveTo(fx - 0.5, fy - 1.5); ctx.lineTo(fx, fy); ctx.stroke();
      };
      leg(-16, -24, t + Math.PI, "#5a331c", false); leg(16, -24, t + 0.6, "#5a331c", true);
      // tail
      ctx.strokeStyle = "#2b1a12"; ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(-26, -40); ctx.quadraticCurveTo(-40, -36 + Math.sin(t * 1.2) * 5, -46, -22 + Math.sin(t) * 7); ctx.stroke();
      // body
      ctx.fillStyle = grad(ctx, 0, -56, 0, -16, [[0, "#b5703a"], [1, "#7a4421"]]);
      ctx.beginPath(); ctx.ellipse(0, -34, 28, 14, 0, 0, 7); ctx.fill();
      ctx.beginPath(); ctx.moveTo(14, -40); ctx.quadraticCurveTo(28, -58, 34, -60); ctx.lineTo(42, -52); ctx.quadraticCurveTo(30, -42, 24, -26); ctx.fill();   // neck
      ctx.beginPath(); ctx.ellipse(42, -55, 11, 6.5, 0.55, 0, 7); ctx.fill();   // head
      ctx.fillStyle = "#e8c9a0"; ctx.beginPath(); ctx.ellipse(49, -50, 4, 3.5, 0.55, 0, 7); ctx.fill();   // muzzle
      ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(42, -58, 2, 0, 7); ctx.fill(); ctx.fillStyle = "#111"; ctx.beginPath(); ctx.arc(42.6, -58, 1.1, 0, 7); ctx.fill();
      ctx.fillStyle = "#2b1a12"; ctx.beginPath(); ctx.moveTo(34, -62); ctx.lineTo(36, -69); ctx.lineTo(39, -62); ctx.fill();   // ear
      ctx.strokeStyle = "#2b1a12"; ctx.lineWidth = 3.5; ctx.beginPath(); ctx.moveTo(24, -58); for (let i = 1; i <= 4; i++) ctx.lineTo(24 - i * 5 + Math.sin(t + i) * 2, -54 + i * 5 + Math.sin(t * 1.3 + i) * 2); ctx.stroke(); // mane
      // saddle + blanket
      ctx.fillStyle = "#c62828"; rr(ctx, -10, -50, 22, 8, 3); ctx.fill(); ctx.fillStyle = "#4e2a14"; rr(ctx, -7, -53, 16, 6, 3); ctx.fill();
      ctx.strokeStyle = "#1b1b1b"; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.moveTo(34, -62); ctx.lineTo(38, -50); ctx.stroke();  // rein
      leg(-10, -24, t, "#7a4421", false); leg(22, -24, t + Math.PI + 0.6, "#7a4421", true);
      // rider
      const lean = air ? -0.1 : Math.sin(t * 2) * 0.03;
      ctx.save(); ctx.translate(0, -52); ctx.rotate(lean + 0.12);
      ctx.fillStyle = "#1e4f9c"; rr(ctx, -5, -22, 12, 22, 4); ctx.fill();                // torso
      ctx.fillStyle = "#f2c99a"; ctx.beginPath(); ctx.arc(2, -27, 6.5, 0, 7); ctx.fill();   // face
      ctx.fillStyle = "#222"; ctx.fillRect(5, -28, 2, 2);
      ctx.fillStyle = "#6b3d1a"; ctx.beginPath(); ctx.ellipse(2, -32, 13, 3.2, 0, 0, 7); ctx.fill(); rr(ctx, -4, -42, 12, 11, 4); ctx.fill();   // hat
      ctx.fillStyle = "#d9a441"; ctx.fillRect(-4, -34, 12, 2.5);
      ctx.strokeStyle = "#1e4f9c"; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(1, -17); ctx.lineTo(14, -12); ctx.stroke();  // arm
      // scarf
      ctx.strokeStyle = "#e53935"; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(-1, -21); for (let i = 1; i <= 5; i++) ctx.lineTo(-1 - i * 6, -21 + Math.sin(t * 1.6 + i * 0.9) * (2 + i));  ctx.stroke();
      ctx.fillStyle = "#e53935"; ctx.beginPath(); ctx.moveTo(-31, -22 + Math.sin(t * 1.6 + 4.5) * 7); ctx.lineTo(-38, -26 + Math.sin(t * 1.6 + 5.4) * 8); ctx.lineTo(-37, -17 + Math.sin(t * 1.6 + 5.4) * 8); ctx.fill();
      ctx.restore();
      ctx.restore();
    };
    const drawObs = (ctx, o) => {
      const x = o.x, b = GY;
      if (o.t === "fence") {
        ctx.fillStyle = "#0003"; ctx.fillRect(x - 2, b - 2, o.w + 6, 4);
        ctx.fillStyle = "#8d5a2b"; ctx.fillRect(x + 2, b - 30, 7, 30); ctx.fillRect(x + o.w - 9, b - 30, 7, 30);
        ctx.fillStyle = "#b47a3c"; ctx.fillRect(x - 2, b - 26, o.w + 4, 6); ctx.fillRect(x - 2, b - 13, o.w + 4, 6);
        ctx.fillStyle = "#ffffff30"; ctx.fillRect(x - 2, b - 26, o.w + 4, 2); ctx.fillRect(x - 2, b - 13, o.w + 4, 2);
      } else if (o.t === "rock") {
        ctx.fillStyle = "#0003"; ctx.beginPath(); ctx.ellipse(x + 15, b, 20, 4, 0, 0, 7); ctx.fill();
        ctx.fillStyle = grad(ctx, 0, b - 24, 0, b, [[0, "#9a8f86"], [1, "#5d524b"]]);
        ctx.beginPath(); ctx.moveTo(x, b); ctx.lineTo(x + 4, b - 14); ctx.lineTo(x + 13, b - 24); ctx.lineTo(x + 25, b - 17); ctx.lineTo(x + 30, b); ctx.fill();
        ctx.fillStyle = "#ffffff30"; ctx.beginPath(); ctx.moveTo(x + 6, b - 14); ctx.lineTo(x + 13, b - 24); ctx.lineTo(x + 16, b - 12); ctx.fill();
      } else if (o.t === "cactus") {
        const h = o.h, cx = x + 12;
        ctx.fillStyle = "#0003"; ctx.beginPath(); ctx.ellipse(cx, b, 16, 3.5, 0, 0, 7); ctx.fill();
        ctx.fillStyle = "#3c8d40"; rr(ctx, cx - 6, b - h, 12, h, 6); ctx.fill();
        rr(ctx, cx - 17, b - h * 0.65, 8, 5, 2.5); ctx.fill(); rr(ctx, cx - 17, b - h * 0.65 - 13, 6, 18, 3); ctx.fill();
        rr(ctx, cx + 9, b - h * 0.5, 8, 5, 2.5); ctx.fill(); rr(ctx, cx + 11, b - h * 0.5 - 12, 6, 17, 3); ctx.fill();
        ctx.fillStyle = "#66bb6a"; ctx.fillRect(cx - 3, b - h + 3, 3, h - 5);
        ctx.fillStyle = "#e91e63"; ctx.beginPath(); ctx.arc(cx, b - h, 3, 0, 7); ctx.fill();
      } else if (o.t === "weed") {
        ctx.fillStyle = "#0003"; ctx.beginPath(); ctx.ellipse(x + 13, b, 14, 3, 0, 0, 7); ctx.fill();
        ctx.save(); ctx.translate(x + 13, b - 13 - Math.abs(Math.sin(o.r * 1.3)) * 4); ctx.rotate(o.r); ctx.strokeStyle = "#a57b3f"; ctx.lineWidth = 1.5;
        for (let i = 0; i < 6; i++) { ctx.beginPath(); ctx.ellipse(0, 0, 13, 7 + (i % 3) * 2, i * 0.55, 0, 7); ctx.stroke(); }
        ctx.restore();
      }
    };
    return {
      down: jump, key(k) { if (k === " " || k === "ArrowUp") jump(); },
      update(dt) {
        if (fall) { fall += dt; py += 260 * dt; return; }
        ride += dt; speed = Math.min(440, 210 + S.t * 5.5); dist += speed * dt; score = Math.floor(dist / 18) + coins * 5 + bags * 12; ph += dt * (speed / 24);
        vy += 1500 * dt; py += vy * dt;
        let ground = true;
        for (const o of obs) if (o.t === "gap" && PX + 8 > o.x + 4 && PX - 8 < o.x + o.w - 4) ground = false;
        if (py >= GY && ground) { py = GY; vy = 0; jumps = 0; }
        else if (py >= GY && !ground && py > GY + 6) { return die(true); }
        spawn -= dt;
        if (spawn <= 0) { spawn = rnd(0.95, 1.7) * (250 / speed + 0.55); if (Math.random() < 0.68) addObs(); else addPicks(); }
        for (const o of obs) { o.x -= speed * dt; if (o.t === "weed") { o.x -= 40 * dt; o.r -= dt * 7; } }
        for (const p of picks) p.x -= speed * dt;
        for (const o of obs) if (o.t !== "gap" && PX + 14 > o.x + 4 && PX - 14 < o.x + o.w - 4 && py > GY - o.h + 4) return die(false);
        for (let i = picks.length - 1; i >= 0; i--) { const p = picks[i]; if (Math.abs(p.x - PX) < 24 && Math.abs(p.y - (py - 34)) < 38) {
          if (p.k === "bag") { bags++; bump("+12", p.x, p.y, "#ffcc80"); a.sfx("win"); a.burst(p.x, p.y, "#ffcc80", 14); } else { coins++; bump("+5", p.x, p.y, "#ffd24a"); a.sfx("cash"); a.burst(p.x, p.y, "#ffd24a", 8); }
          picks.splice(i, 1); } }
        obs = obs.filter((o) => o.x > -80); picks = picks.filter((p) => p.x > -30);
        dustT -= dt; if (dustT <= 0 && py >= GY - 1) { dustT = 0.05; dust.push({ x: PX - 24, y: GY - 2, vx: -speed * 0.25 - rnd(0, 30), vy: -rnd(10, 40), r: rnd(3, 6), l: 1 }); }
        for (let i = dust.length - 1; i >= 0; i--) { const d = dust[i]; d.x += d.vx * dt; d.y += d.vy * dt; d.r += dt * 10; d.l -= dt * 2.2; if (d.l <= 0) dust.splice(i, 1); }
        for (let i = pops.length - 1; i >= 0; i--) { pops[i].t += dt; pops[i].x -= 20 * dt; if (pops[i].t > 0.9) pops.splice(i, 1); }
        for (const l of lines) { l.x -= speed * 1.6 * dt; if (l.x < -l.l) { l.x = W + rnd(0, 80); l.y = rnd(40, GY); } }
        a.hud(`🐎 ${score}   🪙 ${coins}   ✉️ ${bags}`);
      },
      draw(ctx) {
        const tt = clamp(dist / 5000, 0, 1), sunY = lerp(64, GY - 40, tt);
        ctx.fillStyle = grad(ctx, 0, 0, 0, GY, [[0, mix("#4aa3df", "#3b2a6b", tt)], [0.65, mix("#bfe4f5", "#f06a4a", tt)], [1, mix("#fff1c9", "#ffb347", tt)]]); ctx.fillRect(0, 0, W, GY);
        ctx.fillStyle = mix("#fff6c4", "#ffd54f", tt) + ""; ctx.globalAlpha = 0.25; ctx.beginPath(); ctx.arc(250, sunY, 52, 0, 7); ctx.fill(); ctx.globalAlpha = 1;
        ctx.fillStyle = mix("#fff3a0", "#ff7043", tt); ctx.beginPath(); ctx.arc(250, sunY, 28, 0, 7); ctx.fill();
        ctx.fillStyle = "#ffffff"; ctx.globalAlpha = 0.5 - tt * 0.3;
        for (let i = 0; i < 3; i++) { const cx = ((i * 150 - dist * 0.03) % (W + 100) + W + 100) % (W + 100) - 50; ctx.beginPath(); ctx.ellipse(cx, 50 + i * 22, 34, 9, 0, 0, 7); ctx.ellipse(cx + 16, 44 + i * 22, 20, 8, 0, 0, 7); ctx.fill(); }
        ctx.globalAlpha = 1;
        // far mesas
        const span = 6 * 120;
        for (const m of mesas) {
          const x = (((m.x - dist * 0.1) % span) + span) % span - 130, top = GY - 30 - m.h;
          ctx.fillStyle = mix("#b98a6a", "#6a3a55", tt);
          ctx.beginPath(); ctx.moveTo(x, GY); ctx.lineTo(x + 8, top + 14); ctx.lineTo(x + 14, top); ctx.lineTo(x + m.w - 14, top); ctx.lineTo(x + m.w - 6, top + 14); ctx.lineTo(x + m.w, GY); ctx.fill();
          ctx.fillStyle = mix("#d3a47f", "#8a4a60", tt); ctx.fillRect(x + 14, top, m.w - 28, 4);
        }
        ctx.fillStyle = mix("#d9b078", "#a0584a", tt); ctx.fillRect(0, GY - 22, W, 22);
        // mid cacti silhouettes
        const cs = 7 * 70; ctx.fillStyle = mix("#6f8a3c", "#3d2f45", tt);
        for (const c of cacti) { const x = (((c.x - dist * 0.35) % cs) + cs) % cs - 30, h = 30 * c.s; rr(ctx, x, GY - 12 - h, 7, h, 3); ctx.fill(); rr(ctx, x - 8, GY - 12 - h * 0.6, 5, 3, 1.5); ctx.fill(); rr(ctx, x - 8, GY - 12 - h * 0.6 - 8, 3.5, 10, 1.7); ctx.fill(); }
        // ground
        ctx.fillStyle = grad(ctx, 0, GY, 0, H, [[0, mix("#d2965a", "#8e4f48", tt)], [1, mix("#8a5a30", "#4a2a35", tt)]]);
        ctx.fillRect(0, GY, W, H - GY);
        ctx.fillStyle = mix("#e3ab70", "#a86050", tt); ctx.fillRect(0, GY, W, 3);
        ctx.fillStyle = mix("#7a4c26", "#3a2030", tt); for (let x = -((dist * 1.0) % 46); x < W; x += 46) { ctx.fillRect(x, GY + 14, 18, 3); ctx.fillRect(x + 22, GY + 30, 12, 2); }
        for (const o of obs) if (o.t === "gap") { ctx.fillStyle = "#1a0d08"; ctx.beginPath(); ctx.moveTo(o.x, GY); ctx.lineTo(o.x + o.w, GY); ctx.lineTo(o.x + o.w - 8, H); ctx.lineTo(o.x + 8, H); ctx.fill(); ctx.fillStyle = "#6b4023"; ctx.fillRect(o.x - 3, GY, 5, 6); ctx.fillRect(o.x + o.w - 2, GY, 5, 6); }
        for (const l of lines) { ctx.globalAlpha = 0.22 + tt * 0.0; ctx.fillStyle = "#fff"; ctx.fillRect(l.x, l.y, l.l, 1.5); } ctx.globalAlpha = 1;
        for (const o of obs) if (o.t !== "gap") drawObs(ctx, o);
        for (const p of picks) {
          const bob = Math.sin(S.t * 5 + p.x * 0.05) * 3;
          if (p.k === "coin") { const sx = Math.abs(Math.cos(S.t * 6 + p.x * 0.1)); ctx.fillStyle = "#c8921a"; ctx.beginPath(); ctx.ellipse(p.x, p.y + bob, 9 * sx + 1.5, 9.5, 0, 0, 7); ctx.fill(); ctx.fillStyle = "#ffd54f"; ctx.beginPath(); ctx.ellipse(p.x, p.y + bob, 7 * sx + 1, 7.5, 0, 0, 7); ctx.fill(); if (sx > 0.5) text(ctx, "$", p.x, p.y + bob + 4, 10, "#a06c00"); }
          else { const y = p.y + bob; ctx.fillStyle = "#6b3d1a"; rr(ctx, p.x - 13, y - 9, 26, 19, 4); ctx.fill(); ctx.fillStyle = "#8d5a2b"; ctx.beginPath(); ctx.moveTo(p.x - 13, y - 9); ctx.lineTo(p.x + 13, y - 9); ctx.lineTo(p.x, y + 3); ctx.fill(); ctx.fillStyle = "#ffd54f"; ctx.fillRect(p.x - 2, y, 4, 4); ctx.fillStyle = "#fff"; ctx.fillRect(p.x - 5, y - 17, 10, 7); ctx.fillStyle = "#e53935"; ctx.fillRect(p.x - 5, y - 14, 10, 1.5); }
        }
        for (const d of dust) { ctx.globalAlpha = d.l * 0.5; ctx.fillStyle = mix("#e0c39a", "#c08a7a", tt); ctx.beginPath(); ctx.arc(d.x, d.y, d.r, 0, 7); ctx.fill(); } ctx.globalAlpha = 1;
        if (!fall || fall < 0.6) horse(ctx, PX, py, py < GY - 2, ph);
        for (const p of pops) { ctx.globalAlpha = 1 - p.t / 0.9; text(ctx, p.s, p.x, p.y - p.t * 40, 16, p.c); } ctx.globalAlpha = 1;
        ctx.fillStyle = grad(ctx, 0, 0, 0, H, [[0, "#0000"], [1, mix("#000000", "#10001a", tt) + ""]]); ctx.globalAlpha = 0.12 + tt * 0.18; ctx.fillRect(0, 0, W, H); ctx.globalAlpha = 1;
        intro(ctx, W, H, S.t, "Tap to jump - tap again in the air!", "Deliver mail, grab coins, mind the gaps", 60);
      },
    };
  });

  /* ============================== PANI PURI RUSH ============================== */
  games.panipuri = mk("panipuri", "🥟 Pani Puri Rush", 340, 470, (a) => {
    const W = a.w, H = a.h, S = a.S, CY = 192, BY = H - 118;
    const FL = [{ n: "Mint", c: "#3fae49", d: "#1f7a2b" }, { n: "Tamarind", c: "#9a5a26", d: "#5e3412" }, { n: "Spicy", c: "#e5392f", d: "#9a1a14" }];
    const slotX = (i) => 52 + i * 78;
    const mkCanvas = (h) => { const c = document.createElement("canvas"); c.width = W * 2; c.height = h * 2; const x = c.getContext("2d"); x.scale(2, 2); return [c, x]; };
    const icon = (ctx, f, x, y, s) => {
      ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
      if (f === 0) { ctx.fillStyle = "#2e9e3e"; ctx.beginPath(); ctx.moveTo(-9, 6); ctx.quadraticCurveTo(-6, -10, 9, -8); ctx.quadraticCurveTo(10, 8, -9, 6); ctx.fill(); ctx.strokeStyle = "#a8e6a0"; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.moveTo(-9, 6); ctx.lineTo(5, -4); ctx.stroke(); }
      else if (f === 1) { ctx.fillStyle = "#7a431c"; ctx.beginPath(); ctx.moveTo(-10, 3); ctx.quadraticCurveTo(-8, -9, 0, -5); ctx.quadraticCurveTo(8, -9, 10, 2); ctx.quadraticCurveTo(0, 9, -10, 3); ctx.fill(); ctx.fillStyle = "#b9763a"; ctx.beginPath(); ctx.ellipse(-4, -1, 3, 2, 0, 0, 7); ctx.ellipse(4, 0, 3, 2, 0, 0, 7); ctx.fill(); }
      else { ctx.strokeStyle = "#d32f2f"; ctx.lineWidth = 6; ctx.lineCap = "round"; ctx.beginPath(); ctx.moveTo(-8, 7); ctx.quadraticCurveTo(0, 6, 8, -6); ctx.stroke(); ctx.strokeStyle = "#2e7d32"; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(8, -6); ctx.lineTo(10, -10); ctx.stroke(); }
      ctx.restore();
    };
    // static wall + counter layers
    const [wallC, wx] = mkCanvas(CY + 4), [cntC, cx] = mkCanvas(H - CY);
    (() => {
      wx.fillStyle = grad(wx, 0, 0, 0, CY, [[0, "#ffcf70"], [1, "#f4a640"]]); wx.fillRect(0, 0, W, CY);
      wx.strokeStyle = "#ffffff30"; wx.lineWidth = 1; for (let y = 52; y < CY; y += 22) for (let x = ((y / 22) % 2) * 20; x < W; x += 40) wx.strokeRect(x, y, 40, 22);
      wx.fillStyle = grad(wx, 0, 0, 0, CY, [[0, "#0000"], [1, "#6a2d0033"]]); wx.fillRect(0, 0, W, CY);
      // awning
      const n = 10, sw = W / n;
      for (let i = 0; i < n; i++) { wx.fillStyle = i % 2 ? "#fff3e0" : "#d32f2f"; wx.beginPath(); wx.moveTo(i * sw, 0); wx.lineTo((i + 1) * sw, 0); wx.lineTo((i + 1) * sw, 30); wx.arc(i * sw + sw / 2, 30, sw / 2, 0, Math.PI); wx.fill(); }
      wx.fillStyle = "#00000022"; wx.fillRect(0, 0, W, 6);
      wx.fillStyle = "#00000018"; for (let i = 0; i < n; i++) { wx.beginPath(); wx.arc(i * sw + sw / 2, 33, sw / 2, 0, Math.PI); wx.fill(); }
      // sign board
      wx.fillStyle = "#3e2210"; rr(wx, W / 2 - 62, 40, 124, 20, 6); wx.fill(); wx.fillStyle = "#ffd54f"; rr(wx, W / 2 - 59, 42, 118, 16, 5); wx.fill();
      text(wx, "PANI PURI", W / 2, 55, 13, "#b71c1c", "center", 900);
      // bunting
      wx.strokeStyle = "#5d4037"; wx.lineWidth = 1; wx.beginPath(); wx.moveTo(0, 66); wx.quadraticCurveTo(W / 2, 90, W, 66); wx.stroke();
      const cols = ["#e91e63", "#2196f3", "#4caf50", "#ffeb3b", "#ff5722"];
      for (let i = 1; i < 17; i++) { const t = i / 17, x = t * W, y = 66 + 24 * 4 * t * (1 - t) * 0.5 * 2 / 2 + 0; wx.fillStyle = cols[i % 5]; wx.beginPath(); wx.moveTo(x - 6, y); wx.lineTo(x + 6, y); wx.lineTo(x, y + 12); wx.fill(); }
      // counter
      cx.fillStyle = grad(cx, 0, 0, 0, 20, [[0, "#b9804a"], [1, "#8a5a30"]]); cx.fillRect(0, 0, W, 20);
      cx.fillStyle = "#ffffff40"; cx.fillRect(0, 0, W, 2);
      cx.fillStyle = grad(cx, 0, 20, 0, H - CY, [[0, "#6d4421"], [1, "#4a2a12"]]); cx.fillRect(0, 20, W, H - CY - 20);
      cx.strokeStyle = "#00000030"; cx.lineWidth = 1; for (let x = 0; x < W; x += 34) { cx.beginPath(); cx.moveTo(x, 20); cx.lineTo(x, H - CY); cx.stroke(); }
      cx.fillStyle = "#ffcc80"; cx.fillRect(0, 20, W, 3);
      // stack of puris in a steel bowl
      const bx = 44, by = 76;
      for (let r = 0; r < 3; r++) for (let i = 0; i < 4 - r; i++) { const px = bx + (i - (3 - r) / 2) * 14, py = by - 6 - r * 11; cx.fillStyle = grad(cx, px - 7, py - 7, px + 7, py + 7, [[0, "#ffd987"], [1, "#d08a2a"]]); cx.beginPath(); cx.arc(px, py, 8, 0, 7); cx.fill(); }
      cx.fillStyle = grad(cx, bx - 34, 0, bx + 34, 0, [[0, "#8d99a5"], [0.5, "#eef2f6"], [1, "#7c8895"]]); cx.beginPath(); cx.moveTo(bx - 36, by - 2); cx.lineTo(bx + 36, by - 2); cx.quadraticCurveTo(bx + 30, by + 22, bx, by + 22); cx.quadraticCurveTo(bx - 30, by + 22, bx - 36, by - 2); cx.fill();
      text(cx, "FRESH PURI", bx, by + 40, 9, "#ffe0b2", "center", 800);
      // tip jar
      const jx = W - 36, jy = 60; cx.fillStyle = "#cfe8f588"; rr(cx, jx - 16, jy - 26, 32, 40, 6); cx.fill(); cx.fillStyle = "#ffd54f"; for (let i = 0; i < 8; i++) { cx.beginPath(); cx.ellipse(jx - 8 + (i % 3) * 8, jy + 8 - Math.floor(i / 3) * 4, 5, 2.5, 0, 0, 7); cx.fill(); }
      cx.strokeStyle = "#ffffffaa"; cx.lineWidth = 1.5; rr(cx, jx - 16, jy - 26, 32, 40, 6); cx.stroke(); cx.fillStyle = "#c62828"; rr(cx, jx - 18, jy - 30, 36, 6, 3); cx.fill();
      text(cx, "TIPS", jx, jy + 28, 9, "#ffe0b2", "center", 800);
    })();
    const looks = [
      { skin: "#e0a77a", cloth: "#2e6fd0", turban: "#e65100", kind: 0 }, { skin: "#c98a5e", cloth: "#d81b60", dup: "#f8bbd0", kind: 1 },
      { skin: "#d9a070", cloth: "#6d4c41", hair: "#eeeeee", kind: 2 }, { skin: "#e8b88a", cloth: "#43a047", cap: "#1565c0", kind: 3 },
      { skin: "#b97a50", cloth: "#7b1fa2", topi: "#fafafa", kind: 4 }, { skin: "#d49a6a", cloth: "#00897b", dup: "#ffcc80", kind: 1 },
    ];
    const face = (ctx, L, x, y, mood, t) => {
      // body
      ctx.fillStyle = L.cloth; ctx.beginPath(); ctx.moveTo(x - 25, y + 64); ctx.quadraticCurveTo(x - 24, y + 22, x, y + 20); ctx.quadraticCurveTo(x + 24, y + 22, x + 25, y + 64); ctx.fill();
      ctx.fillStyle = "#0000001f"; ctx.fillRect(x - 25, y + 52, 50, 12);
      ctx.fillStyle = L.skin; ctx.fillRect(x - 5, y + 12, 10, 12);
      if (L.dup) { ctx.fillStyle = L.dup; ctx.beginPath(); ctx.moveTo(x - 26, y + 62); ctx.quadraticCurveTo(x - 30, y + 26, x - 10, y + 22); ctx.lineTo(x + 18, y + 30); ctx.lineTo(x + 24, y + 62); ctx.fill(); }
      if (L.kind === 4) { ctx.fillStyle = "#ffffff55"; ctx.fillRect(x - 3, y + 24, 6, 36); }
      // back hair (pigtails / bun)
      if (L.kind === 3) { ctx.fillStyle = "#2b1a12"; ctx.beginPath(); ctx.arc(x - 20, y + 4, 6, 0, 7); ctx.arc(x + 20, y + 4, 6, 0, 7); ctx.fill(); }
      ctx.fillStyle = L.skin; ctx.beginPath(); ctx.ellipse(x, y, 18, 19, 0, 0, 7); ctx.fill();
      ctx.fillStyle = "#00000014"; ctx.beginPath(); ctx.ellipse(x + 6, y + 6, 12, 13, 0, 0, 7); ctx.fill();
      ctx.fillStyle = L.skin; ctx.beginPath(); ctx.arc(x - 18, y + 2, 4, 0, 7); ctx.arc(x + 18, y + 2, 4, 0, 7); ctx.fill();
      // head gear
      if (L.turban) { ctx.fillStyle = L.turban; ctx.beginPath(); ctx.ellipse(x, y - 11, 20, 13, 0, Math.PI, 0); ctx.fill(); ctx.beginPath(); ctx.ellipse(x, y - 9, 21, 6, 0, 0, 7); ctx.fill(); ctx.strokeStyle = "#ffffff55"; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(x, y - 6, 18, Math.PI * 1.1, Math.PI * 1.9); ctx.moveTo(x - 14, y - 15); ctx.quadraticCurveTo(x, y - 8, x + 14, y - 18); ctx.stroke(); ctx.fillStyle = "#ffd54f"; ctx.beginPath(); ctx.arc(x, y - 16, 2.5, 0, 7); ctx.fill(); }
      else if (L.hair && L.kind === 2) { ctx.fillStyle = L.hair; ctx.beginPath(); ctx.ellipse(x, y - 8, 18, 11, 0, Math.PI, 0); ctx.fill(); ctx.fillRect(x - 19, y - 8, 4, 12); ctx.fillRect(x + 15, y - 8, 4, 12); }
      else if (L.cap) { ctx.fillStyle = L.cap; ctx.beginPath(); ctx.ellipse(x, y - 8, 19, 12, 0, Math.PI, 0); ctx.fill(); ctx.fillRect(x - 4, y - 8, 24, 4); ctx.fillStyle = "#2b1a12"; ctx.fillRect(x - 18, y - 8, 36, 3); }
      else if (L.topi) { ctx.fillStyle = L.topi; ctx.beginPath(); ctx.moveTo(x - 14, y - 12); ctx.lineTo(x + 14, y - 12); ctx.lineTo(x + 11, y - 24); ctx.lineTo(x - 11, y - 24); ctx.fill(); ctx.fillStyle = "#2b1a12"; ctx.beginPath(); ctx.ellipse(x, y - 8, 18, 9, 0, Math.PI, 0); ctx.fill(); }
      else if (L.kind === 1) { ctx.fillStyle = "#1e120b"; ctx.beginPath(); ctx.ellipse(x, y - 7, 19, 13, 0, Math.PI, 0); ctx.fill(); ctx.fillStyle = L.dup; ctx.beginPath(); ctx.ellipse(x, y - 6, 20, 9, 0, Math.PI * 1.05, Math.PI * 1.95); ctx.fill(); ctx.fillStyle = "#d32f2f"; ctx.beginPath(); ctx.arc(x, y - 7, 2, 0, 7); ctx.fill(); }
      // eyes
      const blink = Math.sin(t * 1.7 + x) > 0.985;
      ctx.fillStyle = "#fff";
      if (!blink) { ctx.beginPath(); ctx.ellipse(x - 7, y - 1, 4.2, mood === 1 ? 2.6 : 4.2, 0, 0, 7); ctx.ellipse(x + 7, y - 1, 4.2, mood === 1 ? 2.6 : 4.2, 0, 0, 7); ctx.fill(); ctx.fillStyle = "#1a1010"; ctx.beginPath(); ctx.arc(x - 6.5, y - 1, 2.2, 0, 7); ctx.arc(x + 7.5, y - 1, 2.2, 0, 7); ctx.fill(); }
      ctx.strokeStyle = "#2b1a12"; ctx.lineWidth = 1.8; ctx.lineCap = "round"; ctx.beginPath();
      if (mood >= 2) { const tl = mood === 3 ? 4 : 1.5; ctx.moveTo(x - 12, y - 10 - tl); ctx.lineTo(x - 3, y - 7); ctx.moveTo(x + 12, y - 10 - tl); ctx.lineTo(x + 3, y - 7); }
      else { ctx.moveTo(x - 11, y - 8); ctx.quadraticCurveTo(x - 7, y - 11, x - 3, y - 8); ctx.moveTo(x + 11, y - 8); ctx.quadraticCurveTo(x + 7, y - 11, x + 3, y - 8); }
      ctx.stroke();
      ctx.fillStyle = "#00000022"; ctx.beginPath(); ctx.ellipse(x, y + 4, 2.4, 3, 0, 0, 7); ctx.fill();
      if (L.kind === 0 || L.kind === 2 || L.kind === 4) { ctx.fillStyle = L.kind === 2 ? "#eee" : "#2b1a12"; ctx.beginPath(); ctx.ellipse(x, y + 8, 8, 2.8, 0, 0, 7); ctx.fill(); }
      if (L.kind === 4) { ctx.fillStyle = "#2b1a12"; ctx.beginPath(); ctx.ellipse(x, y + 17, 11, 6, 0, 0, Math.PI); ctx.fill(); }
      if (L.kind === 2) { ctx.strokeStyle = "#333"; ctx.lineWidth = 1.3; ctx.beginPath(); ctx.arc(x - 7, y - 1, 5.5, 0, 7); ctx.arc(x + 7, y - 1, 5.5, 0, 7); ctx.moveTo(x - 1.5, y - 1); ctx.lineTo(x + 1.5, y - 1); ctx.stroke(); }
      // mouth
      ctx.strokeStyle = "#7a2a1a"; ctx.lineWidth = 2; ctx.beginPath();
      if (mood === 1) { ctx.fillStyle = "#8a2a1a"; ctx.beginPath(); ctx.arc(x, y + 9, 6, 0, Math.PI); ctx.fill(); ctx.fillStyle = "#fff"; ctx.fillRect(x - 4, y + 9, 8, 2); }
      else if (mood === 0) { ctx.moveTo(x - 4, y + 12); ctx.lineTo(x + 4, y + 12); ctx.stroke(); }
      else { ctx.arc(x, y + 17, 6, Math.PI * 1.15, Math.PI * 1.85); ctx.stroke(); }
      if (mood === 2) { ctx.fillStyle = "#6ec6ff"; ctx.beginPath(); ctx.ellipse(x + 18, y - 12, 2.2, 3.4, 0, 0, 7); ctx.fill(); }
      if (mood === 3) { text(ctx, "💢", x + 18, y - 16, 14); }
    };
    const puri = (ctx, x, y, fill, col, dark) => {
      ctx.fillStyle = "#0003"; ctx.beginPath(); ctx.ellipse(x, y + 18, 20, 5, 0, 0, 7); ctx.fill();
      ctx.fillStyle = "#f5f5f5"; ctx.beginPath(); ctx.ellipse(x, y + 16, 26, 7, 0, 0, 7); ctx.fill(); ctx.fillStyle = "#cfd8dc"; ctx.beginPath(); ctx.ellipse(x, y + 16, 19, 4.5, 0, 0, 7); ctx.fill();
      ctx.fillStyle = grad(ctx, x - 14, y - 14, x + 14, y + 14, [[0, "#ffe29a"], [1, "#d58f2a"]]); ctx.beginPath(); ctx.arc(x, y, 15, 0, 7); ctx.fill();
      if (fill > 0) { ctx.save(); ctx.beginPath(); ctx.arc(x, y, 12.5, 0, 7); ctx.clip(); ctx.globalAlpha = 0.9; ctx.fillStyle = col; ctx.fillRect(x - 14, y + 13 - 26 * fill, 28, 28); ctx.fillStyle = dark; ctx.fillRect(x - 14, y + 13 - 26 * fill, 28, 3); ctx.restore(); }
      ctx.fillStyle = "#6a3b0a"; ctx.beginPath(); ctx.ellipse(x, y - 9, 8, 3.2, 0, 0, 7); ctx.fill();
      ctx.fillStyle = "#ffffff70"; ctx.beginPath(); ctx.ellipse(x - 6, y - 4, 3, 5, 0.6, 0, 7); ctx.fill();
    };
    const pot = (ctx, x, y, f, press) => {
      const F = FL[f], w = 84, h = 82 - press * 4;
      ctx.fillStyle = "#0003"; ctx.beginPath(); ctx.ellipse(x, y + h + 4, w / 2, 6, 0, 0, 7); ctx.fill();
      ctx.fillStyle = grad(ctx, x - w / 2, 0, x + w / 2, 0, [[0, "#7b8794"], [0.3, "#f1f5f9"], [0.6, "#b4bdc7"], [1, "#6c7783"]]);
      ctx.beginPath(); ctx.moveTo(x - w / 2 + 6, y + 14); ctx.lineTo(x + w / 2 - 6, y + 14); ctx.quadraticCurveTo(x + w / 2 + 4, y + h * 0.7, x + w / 2 - 12, y + h); ctx.lineTo(x - w / 2 + 12, y + h); ctx.quadraticCurveTo(x - w / 2 - 4, y + h * 0.7, x - w / 2 + 6, y + 14); ctx.fill();
      ctx.fillStyle = "#e9eef3"; ctx.beginPath(); ctx.ellipse(x, y + 14, w / 2 - 4, 9, 0, 0, 7); ctx.fill();
      ctx.fillStyle = F.d; ctx.beginPath(); ctx.ellipse(x, y + 15, w / 2 - 9, 6.5, 0, 0, 7); ctx.fill(); ctx.fillStyle = F.c; ctx.beginPath(); ctx.ellipse(x, y + 14, w / 2 - 11, 5, 0, 0, 7); ctx.fill();
      ctx.fillStyle = "#ffffff55"; ctx.beginPath(); ctx.ellipse(x - 10, y + 12.5, 12, 1.8, 0, 0, 7); ctx.fill();
      ctx.fillStyle = F.c; rr(ctx, x - 26, y + 38, 52, 22, 8); ctx.fill(); ctx.strokeStyle = "#fff9"; ctx.lineWidth = 1.5; ctx.stroke();
      icon(ctx, f, x - 13, y + 49, 0.9); text(ctx, String(f + 1), x + 12, y + 55, 15, "#fff", "center", 900);
      text(ctx, F.n, x, y + 76 - press * 4, 12, "#fff", "center", 800);
    };
    let cust = [], leaving = [], tips = [], pour = null, lives = 3, served = 0, spawn = 0.4, flash = 0, combo = 0, best = 0, rushT = 0, rushed = false, pressT = [0, 0, 0];
    const hud = () => a.hud(`🥟 ${served}   ❤️ ${lives}${combo > 2 ? "   🔥x" + combo : ""}`);
    const leave = (c, mood) => { leaving.push({ slot: c.slot, look: c.look, mood, t: 0 }); };
    const serve = (f) => {
      if (S.over || !cust.length) return; const c = cust[0]; pressT[f] = 0.25;
      pour = { f, x: slotX(c.slot), t: 0 };
      if (c.want === f) {
        served++; combo++; best = Math.max(best, combo); a.sfx(combo > 2 ? "win" : "good"); a.burst(slotX(c.slot), 190, FL[f].c, 14, 110);
        leave(c, 1); tips.push({ x: slotX(c.slot), y: 120, t: 0, big: combo > 2 }); cust.shift(); flash = 0;
      } else { lives--; combo = 0; a.sfx("bad"); a.shake(8); flash = 0.3; c.mood = 3; c.angry = 0.5; pour.bad = true; if (lives <= 0) a.finish(served); }
      hud();
    };
    const lose = () => { lives--; combo = 0; a.sfx("miss"); a.shake(6); flash = 0.25; hud(); if (lives <= 0) a.finish(served); };
    hud();
    return {
      down(x, y) { if (y > BY - 10) serve(clamp(Math.floor(x / (W / 3)), 0, 2)); },
      key(k) { if (k === "1" || k === "2" || k === "3") serve(+k - 1); },
      update(dt) {
        flash = Math.max(0, flash - dt); spawn -= dt; rushT = Math.max(0, rushT - dt);
        if (!rushed && S.t > 20) { rushed = true; rushT = 2.2; a.sfx("turn"); }
        for (let i = 0; i < 3; i++) pressT[i] = Math.max(0, pressT[i] - dt);
        if (pour) { pour.t += dt; if (pour.t > 0.75) pour = null; }
        if (spawn <= 0 && cust.length < 4) {
          spawn = Math.max(0.8, 2.2 - S.t * 0.03); const used = cust.map((c) => c.slot), slot = [0, 1, 2, 3].find((s) => !used.includes(s));
          if (slot !== undefined) cust.push({ slot, want: Math.floor(rnd(0, 3)), pat: 1, rate: Math.min(0.5, 0.17 + S.t * 0.004), look: looks[Math.floor(rnd(0, looks.length))], age: 0, mood: 0, angry: 0 });
        }
        cust.forEach((c) => { c.pat -= dt * c.rate; c.age += dt; c.angry = Math.max(0, c.angry - dt); });
        if (cust.length && cust[0].pat <= 0) { leave(cust[0], 3); cust.shift(); lose(); }
        else for (let i = cust.length - 1; i > 0; i--) if (cust[i].pat <= 0) { leave(cust[i], 3); cust.splice(i, 1); lose(); }
        for (let i = leaving.length - 1; i >= 0; i--) { leaving[i].t += dt; if (leaving[i].t > 0.7) leaving.splice(i, 1); }
        for (let i = tips.length - 1; i >= 0; i--) { const tp = tips[i]; tp.t += dt * 1.5; if (tp.t >= 1) { a.sfx("cash"); a.burst(W - 36, CY + 54, "#ffd54f", 6, 60); tips.splice(i, 1); } }
      },
      draw(ctx) {
        ctx.drawImage(wallC, 0, 0, W, CY + 4);
        // customers (behind counter)
        for (let i = 0; i < cust.length; i++) {
          const c = cust[i], x = slotX(c.slot), enter = ease(clamp(c.age * 3, 0, 1)), y = 128 + (1 - enter) * 40 + Math.sin(S.t * 3 + c.slot) * 0.8;
          const mood = c.angry > 0 ? 3 : c.pat < 0.25 ? 2 : c.pat < 0.55 ? 0 : 0;
          ctx.save(); ctx.globalAlpha = enter; face(ctx, c.look, x + (c.angry > 0 ? Math.sin(S.t * 60) * 2 : 0), y, mood, S.t); ctx.restore();
          if (i === 0) { ctx.strokeStyle = "#fff"; ctx.lineWidth = 2.5; ctx.setLineDash([6, 4]); ctx.lineDashOffset = -S.t * 12; rr(ctx, x - 36, 44, 72, 148, 14); ctx.stroke(); ctx.setLineDash([]); }
          // bubble
          const by = 74 - (i === 0 ? Math.sin(S.t * 4) * 1.5 : 0);
          ctx.fillStyle = "#fff"; rr(ctx, x - 26, by - 22, 52, 38, 12); ctx.fill(); ctx.beginPath(); ctx.moveTo(x - 6, by + 15); ctx.lineTo(x, by + 24); ctx.lineTo(x + 6, by + 15); ctx.fill();
          ctx.strokeStyle = FL[c.want].c; ctx.lineWidth = 2; rr(ctx, x - 26, by - 22, 52, 38, 12); ctx.stroke();
          icon(ctx, c.want, x, by - 3, 1.5);
        }
        for (const l of leaving) {
          const x = slotX(l.slot), p = ease(clamp(l.t / 0.7, 0, 1)); ctx.save(); ctx.globalAlpha = 1 - p;
          face(ctx, l.look, x + (l.mood === 3 ? Math.sin(S.t * 60) * 2 : 0), 128 - (l.mood === 1 ? Math.abs(Math.sin(l.t * 14)) * 8 : 0) + p * 14, l.mood, S.t); ctx.restore();
        }
        ctx.drawImage(cntC, 0, CY, W, H - CY);
        // combo meter
        const mx = W / 2 - 38, my = CY + 90;
        ctx.fillStyle = "#00000055"; rr(ctx, mx - 4, my - 4, 126, 34, 10); ctx.fill();
        for (let i = 0; i < 5; i++) { const on = combo % 5 > i || (combo >= 5 && combo % 5 === 0); ctx.fillStyle = on ? (combo > 2 ? "#ff9800" : "#ffd54f") : "#ffffff22"; rr(ctx, mx + i * 24, my + 14, 20, 10, 4); ctx.fill(); }
        text(ctx, combo > 1 ? `COMBO x${combo}` : "COMBO", mx + 59, my + 8, 11 + (combo > 2 ? Math.sin(S.t * 10) : 0), combo > 2 ? "#ffd54f" : "#ffe0b2", "center", 900);
        // plates & puris
        const drawPlate = (x, f, fill, bad) => { puri(ctx, x, CY + 6, fill, bad ? "#7b7b3a" : FL[f].c, FL[f].d); };
        if (cust.length && !(pour && pour.x === slotX(cust[0].slot))) puri(ctx, slotX(cust[0].slot), CY + 6, 0, "#fff", "#fff");
        if (pour) {
          const p = pour, fill = clamp(p.t / 0.35, 0, 1), F = FL[p.f];
          drawPlate(p.x, p.f, ease(fill), p.bad);
          if (p.t < 0.4) {
            ctx.fillStyle = "#c0c8d0"; ctx.save(); ctx.translate(p.x + 26, 136); ctx.rotate(-0.7); rr(ctx, -10, -9, 22, 16, 4); ctx.fill(); ctx.fillStyle = F.c; ctx.fillRect(-9, -9, 5, 6); ctx.restore();
            ctx.strokeStyle = F.c; ctx.lineWidth = 3.5; ctx.lineCap = "round"; ctx.beginPath(); ctx.moveTo(p.x + 12, 142); ctx.quadraticCurveTo(p.x + 5, 150, p.x, CY - 8); ctx.stroke();
            ctx.fillStyle = F.c; for (let i = 0; i < 4; i++) { const k = (p.t * 6 + i * 0.25) % 1; ctx.beginPath(); ctx.arc(p.x + (i - 1.5) * 6 * k, CY - 6 - k * 10, 2, 0, 7); ctx.fill(); }
          }
          if (p.t >= 0.3) { const k = (p.t - 0.3) / 0.45; ctx.globalAlpha = 1 - k; ctx.fillStyle = F.c; for (let i = 0; i < 6; i++) { const ang = i / 6 * 6.28; ctx.beginPath(); ctx.arc(p.x + Math.cos(ang) * (12 + k * 14), CY + 6 - Math.abs(Math.sin(ang)) * k * 22 + k * k * 14, 2.6 * (1 - k * 0.5), 0, 7); ctx.fill(); } ctx.globalAlpha = 1; }
          if (p.bad) text(ctx, "WRONG!", p.x, CY - 24 - p.t * 14, 14, "#ff5252", "center", 900);
        }
        // patience bars on counter
        for (let i = 0; i < cust.length; i++) { const c = cust[i], x = slotX(c.slot), v = clamp(c.pat, 0, 1); ctx.fillStyle = "#0008"; rr(ctx, x - 26, CY + 28, 52, 8, 4); ctx.fill(); ctx.fillStyle = v > 0.5 ? "#66bb6a" : v > 0.25 ? "#ffa726" : "#ef5350"; if (v > 0) { rr(ctx, x - 26, CY + 28, 52 * v, 8, 4); ctx.fill(); } }
        // tip coins
        for (const tp of tips) { const t = ease(tp.t), x = lerp(tp.x, W - 36, t), y = lerp(tp.y, CY + 40, t) - Math.sin(t * Math.PI) * 50, sx = Math.abs(Math.cos(tp.t * 14)); ctx.fillStyle = "#c8921a"; ctx.beginPath(); ctx.ellipse(x, y, 8 * sx + 1.5, 8.5, 0, 0, 7); ctx.fill(); ctx.fillStyle = "#ffd54f"; ctx.beginPath(); ctx.ellipse(x, y, 6 * sx + 1, 6.5, 0, 0, 7); ctx.fill(); if (tp.big) text(ctx, "TIP+", x, y - 12, 10, "#fff"); }
        // pots / buttons
        ctx.fillStyle = grad(ctx, 0, BY - 12, 0, H, [[0, "#3a210f"], [1, "#24140a"]]); ctx.fillRect(0, BY - 10, W, H - BY + 10);
        for (let i = 0; i < 3; i++) pot(ctx, W / 6 + i * (W / 3), BY + 4 + pressT[i] * 12, i, pressT[i] * 4);
        if (rushT > 0) { ctx.globalAlpha = Math.min(1, rushT); text(ctx, "RUSH HOUR!", W / 2, 120, 34, "#fff", "center", 900); ctx.strokeStyle = "#d32f2f"; ctx.lineWidth = 3; ctx.strokeText("RUSH HOUR!", W / 2, 120); ctx.fillStyle = "#fff"; ctx.fillText("RUSH HOUR!", W / 2, 120); ctx.globalAlpha = 1; }
        if (flash > 0) { ctx.fillStyle = `rgba(255,0,0,${flash * 0.8})`; ctx.fillRect(0, 0, W, H); }
        intro(ctx, W, H, S.t, "Serve the FIRST customer (dashed frame)", "Tap the pani they ask for - or keys 1 2 3", CY + 14);
      },
    };
  });

  /* ================================ MEMO FLIP ================================ */
  games.memoflip = mk("memoflip", "🧠 Memo Flip", 340, 440, (a) => {
    const W = a.w, H = a.h, S = a.S, CW = 68, CH = 76;
    const EM = ["🍎", "🚀", "🐱", "⚽", "🎸", "🍕", "🌈", "👑"], TINT = ["#e53935", "#3949ab", "#fb8c00", "#43a047", "#8e24aa", "#f4511e", "#00acc1", "#fdd835"];
    const deck = [...EM, ...EM].sort(() => Math.random() - 0.5).map((e, i) => ({ e, i, up: 0, s: 0, done: false, glow: 0, shk: 0, tint: TINT[EM.indexOf(e)] }));
    let first = null, lock = 0, time = 60, pairs = 0, combo = 0, bestMsg = 0, msg = "", ended = false;
    const pops = [];
    const pos = (i) => [20 + (i % 4) * 78, 70 + Math.floor(i / 4) * 85];
    const mkC = () => { const c = document.createElement("canvas"); c.width = CW * 2; c.height = CH * 2; const x = c.getContext("2d"); x.scale(2, 2); return [c, x]; };
    const [backC, bx] = mkC(), [faceC, fx] = mkC();
    (() => {
      bx.fillStyle = grad(bx, 0, 0, CW, CH, [[0, "#8a5cf0"], [0.5, "#5a2fc0"], [1, "#35188a"]]); rr(bx, 0, 0, CW, CH, 10); bx.fill();
      bx.save(); rr(bx, 5, 5, CW - 10, CH - 10, 7); bx.clip();
      bx.strokeStyle = "#ffffff26"; bx.lineWidth = 1;
      for (let i = -CH; i < CW + CH; i += 10) { bx.beginPath(); bx.moveTo(i, 0); bx.lineTo(i + CH, CH); bx.moveTo(i, CH); bx.lineTo(i + CH, 0); bx.stroke(); }
      bx.restore();
      bx.strokeStyle = "#ffd76a"; bx.lineWidth = 2; rr(bx, 5, 5, CW - 10, CH - 10, 7); bx.stroke();
      bx.strokeStyle = "#ffd76a80"; bx.lineWidth = 1; rr(bx, 8.5, 8.5, CW - 17, CH - 17, 5); bx.stroke();
      bx.fillStyle = "#2a1070"; bx.beginPath(); bx.arc(CW / 2, CH / 2, 15, 0, 7); bx.fill(); bx.strokeStyle = "#ffd76a"; bx.lineWidth = 1.8; bx.stroke();
      bx.fillStyle = "#ffd76a"; bx.beginPath(); for (let i = 0; i < 10; i++) { const r = i % 2 ? 4.5 : 11, an = -Math.PI / 2 + i * Math.PI / 5; bx.lineTo(CW / 2 + Math.cos(an) * r, CH / 2 + Math.sin(an) * r); } bx.fill();
      bx.fillStyle = grad(bx, 0, 0, CW, CH, [[0, "#ffffff55"], [0.45, "#ffffff10"], [0.46, "#ffffff00"], [1, "#00000033"]]); rr(bx, 0, 0, CW, CH, 10); bx.fill();
      bx.strokeStyle = "#00000055"; bx.lineWidth = 1.5; rr(bx, 0.75, 0.75, CW - 1.5, CH - 1.5, 10); bx.stroke();
      fx.fillStyle = grad(fx, 0, 0, 0, CH, [[0, "#ffffff"], [1, "#efe6d2"]]); rr(fx, 0, 0, CW, CH, 10); fx.fill();
      fx.strokeStyle = "#00000040"; fx.lineWidth = 1.5; rr(fx, 0.75, 0.75, CW - 1.5, CH - 1.5, 10); fx.stroke();
      fx.fillStyle = "#ffffff99"; rr(fx, 3, 3, CW - 6, 10, 6); fx.fill();
    })();
    const table = (() => {
      const c = document.createElement("canvas"); c.width = W * 2; c.height = H * 2; const x = c.getContext("2d"); x.scale(2, 2);
      x.fillStyle = grad(x, 0, 0, 0, H, [[0, "#1c7a4a"], [1, "#0f5232"]]); x.fillRect(0, 0, W, H);
      const rg = x.createRadialGradient(W / 2, H * 0.5, 40, W / 2, H * 0.5, H * 0.75); rg.addColorStop(0, "#ffffff18"); rg.addColorStop(1, "#00000066"); x.fillStyle = rg; x.fillRect(0, 0, W, H);
      x.fillStyle = "#ffffff07"; for (let i = 0; i < 700; i++) x.fillRect(rnd(0, W), rnd(0, H), 1.2, 1.2);
      x.strokeStyle = "#ffffff16"; x.lineWidth = 1.5; rr(x, 8, 62, W - 16, H - 70, 18); x.stroke();
      return c;
    })();
    const hudT = () => a.hud(`🧠 ${pairs}/8   ⏱ ${Math.max(0, Math.ceil(time))}${combo > 1 ? "   🔥x" + combo : ""}`);
    const end = (sc) => { if (ended) return; ended = true; a.finish(sc); };
    return {
      down(x, y) {
        if (lock > 0 || S.over) return;
        const i = deck.findIndex((c, k) => { const [cx, cy] = pos(k); return x > cx - 3 && x < cx + CW + 3 && y > cy - 3 && y < cy + CH + 3; });
        if (i < 0 || deck[i].up || deck[i].done) return;
        deck[i].up = 1; a.sfx("flip");
        if (first === null) first = i;
        else {
          const A1 = deck[first], B = deck[i];
          if (A1.e === B.e) {
            A1.done = B.done = true; pairs++; combo++; first = null; lock = 0.3;
            setTimeout(() => {
              if (S.over && !ended) return; a.sfx(combo > 2 ? "win" : "good"); A1.glow = B.glow = 1;
              for (const c of [A1, B]) { const p = pos(c.i); a.burst(p[0] + CW / 2, p[1] + CH / 2, "#ffd24a", 12, 120); a.burst(p[0] + CW / 2, p[1] + CH / 2, "#ffffff", 6, 80); }
              const p1 = pos(A1.i), p2 = pos(B.i); pops.push({ x: (p1[0] + p2[0]) / 2 + CW / 2, y: (p1[1] + p2[1]) / 2 + 10, t: 0, s: combo > 1 ? `PAIR! x${combo}` : "PAIR!" });
            }, 250);
            if (pairs === 8) { a.sfx("win"); end(pairs * 10 + Math.ceil(time)); }
          } else {
            lock = 0.7; combo = 0; const f = first; first = null;
            setTimeout(() => { deck[f].shk = deck[i].shk = 0.45; }, 260);
            setTimeout(() => { deck[f].up = 0; deck[i].up = 0; a.sfx("miss"); }, 650);
          }
        }
      },
      key() {},
      update(dt) {
        lock = Math.max(0, lock - dt); time -= dt; if (time <= 0) { time = 0; end(pairs * 10); }
        for (const c of deck) { c.s += (c.up - c.s) * Math.min(1, dt * 14); c.glow = Math.max(0, c.glow - dt * 0.8); c.shk = Math.max(0, c.shk - dt); }
        for (let i = pops.length - 1; i >= 0; i--) { pops[i].t += dt; if (pops[i].t > 1) pops.splice(i, 1); }
        hudT();
      },
      draw(ctx) {
        ctx.drawImage(table, 0, 0, W, H);
        // timer bar
        const f = clamp(time / 60, 0, 1), low = time < 10;
        ctx.fillStyle = "#0006"; rr(ctx, 20, 44, W - 40, 12, 6); ctx.fill();
        if (f > 0) { ctx.fillStyle = grad(ctx, 20, 0, W - 20, 0, low ? [[0, "#ff5252"], [1, "#ff8a65"]] : [[0, "#ffd54f"], [1, "#66bb6a"]]); rr(ctx, 20, 44, (W - 40) * f, 12, 6); ctx.fill(); ctx.fillStyle = "#ffffff55"; rr(ctx, 22, 46, Math.max(0, (W - 40) * f - 4), 3, 2); ctx.fill(); }
        if (low) text(ctx, "HURRY!", W / 2, 38, 11 + Math.sin(S.t * 12), "#ff8a80", "center", 900);
        for (let k = 0; k < 16; k++) {
          const c = deck[k], [px, py] = pos(k), sx = Math.abs(Math.cos(c.s * Math.PI)), face = c.s > 0.5, lift = 1 + Math.sin(clamp(c.s, 0, 1) * Math.PI) * 0.1;
          const bob = c.done ? Math.sin(S.t * 3 + k) * 2 - 2 : 0, sh = c.shk > 0 && c.shk < 0.4 ? Math.sin(c.shk * 60) * 5 * (c.shk / 0.4) : 0;
          const cx = px + CW / 2 + sh, cy = py + CH / 2 + bob;
          ctx.fillStyle = "#0000004d"; ctx.beginPath(); ctx.ellipse(cx + 2, py + CH - 2 + 5 - bob * 0.3, CW / 2 * sx * 0.95, 6, 0, 0, 7); ctx.fill();
          if (c.done) { const g = 0.25 + c.glow * 0.5 + Math.sin(S.t * 4 + k) * 0.06; ctx.fillStyle = `rgba(255,215,80,${g * 0.5})`; rr(ctx, cx - CW / 2 - 6, cy - CH / 2 - 6, CW + 12, CH + 12, 15); ctx.fill(); ctx.fillStyle = `rgba(255,235,140,${g})`; rr(ctx, cx - CW / 2 - 3, cy - CH / 2 - 3, CW + 6, CH + 6, 13); ctx.fill(); }
          ctx.save(); ctx.translate(cx, cy); ctx.scale(Math.max(0.04, sx) * lift, lift);
          ctx.drawImage(face ? faceC : backC, -CW / 2, -CH / 2, CW, CH);
          if (face) {
            ctx.strokeStyle = c.done ? "#e0a800" : c.tint; ctx.lineWidth = 3; rr(ctx, -CW / 2 + 4, -CH / 2 + 4, CW - 8, CH - 8, 7); ctx.stroke();
            ctx.font = "34px system-ui,'Apple Color Emoji','Noto Color Emoji',sans-serif"; ctx.textAlign = "center"; ctx.fillStyle = "#000"; ctx.fillText(c.e, 0, 12);
            ctx.font = "11px system-ui,'Noto Color Emoji',sans-serif"; ctx.fillText(c.e, -CW / 2 + 12, -CH / 2 + 18); ctx.fillText(c.e, CW / 2 - 12, CH / 2 - 9);
            if (c.done) { ctx.fillStyle = "#ffe08a30"; rr(ctx, -CW / 2, -CH / 2, CW, CH, 10); ctx.fill(); }
          }
          ctx.restore();
        }
        for (const p of pops) { ctx.globalAlpha = 1 - p.t; text(ctx, p.s, p.x, p.y - p.t * 36, 17, "#fff2a8", "center", 900); } ctx.globalAlpha = 1;
        if (combo > 1) text(ctx, `COMBO x${combo}`, W / 2, H - 14, 16 + Math.sin(S.t * 8) * 1.5, "#ffd54f", "center", 900);
        else text(ctx, `${pairs} of 8 pairs found`, W / 2, H - 14, 12, "#c8e6c9", "center", 700);
        intro(ctx, W, H, S.t, "Flip two cards and find matching pairs", "Find all 8 in 60s - faster = more points", H / 2 - 31);
      },
    };
  });
})();

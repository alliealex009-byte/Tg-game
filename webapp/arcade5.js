/* ---- Batch 6: Rail Runner, Bubble Shooter, Block Drop, Hoop Shot (all drawn with canvas, no assets) ---- */
(function () {
  const HUB = window.HUB, A = HUB.arc, games = A.games;
  const mk0 = A.mk;
  const rnd = (a, b) => a + Math.random() * (b - a);
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const lerp = (a, b, t) => a + (b - a) * t;
  const rr = (ctx, x, y, w, h, r) => { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); };
  const text = (ctx, s, x, y, size, col, al, wt) => { ctx.font = `${wt || 800} ${size}px system-ui,sans-serif`; ctx.textAlign = al || "center"; ctx.fillStyle = col; ctx.fillText(s, x, y); };
  const vgrad = (ctx, y0, y1, stops) => { const g = ctx.createLinearGradient(0, y0, 0, y1); stops.forEach((s, i) => g.addColorStop(s[0], s[1])); return g; };
  const intro = (ctx, w, h, t, l1, l2) => {
    if (t > 2.5) return;
    ctx.save(); ctx.globalAlpha = t > 2 ? (2.5 - t) / 0.5 : Math.min(1, t * 4);
    ctx.fillStyle = "rgba(10,8,30,.72)"; rr(ctx, 24, h * 0.4 - 8, w - 48, 74, 16); ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,.25)"; ctx.lineWidth = 1.5; ctx.stroke();
    text(ctx, l1, w / 2, h * 0.4 + 26, 16, "#fff", "center", 800); text(ctx, l2, w / 2, h * 0.4 + 50, 13, "#cfd3ff", "center", 600);
    ctx.restore();
  };
  // harness wrapper: the canvas may be narrower than the logical size on small phones, so scale everything
  const mk = (key, title, W, H, setup) => mk0(key, title, W, H, (a) => {
    const k = a.w / W;
    const a2 = { w: W, h: H, hud: a.hud, finish: a.finish, S: a.S, sfx: a.sfx, tone: a.tone, shake: a.shake, box: a.box,
      burst: (x, y, c, n, sp) => a.burst(x * k, y * k, c, n, (sp || 120) * k) };
    const g = setup(a2);
    const w = {};
    if (g.down) w.down = (x, y) => g.down(x / k, y / k);
    if (g.move) w.move = (x, y) => g.move(x / k, y / k);
    if (g.up) w.up = (x, y) => g.up(x / k, y / k);
    if (g.key) w.key = g.key;
    w.update = g.update;
    w.draw = (ctx) => { ctx.save(); ctx.scale(k, k); g.draw(ctx); ctx.restore(); };
    return w;
  });

  /* =============================== RAIL RUNNER =============================== */
  games.railrunner = mk("railrunner", "🚆 Rail Runner", 340, 520, (a) => {
    const W = a.w, H = a.h, VX = W / 2, HY = 186, PY = H - 96, LS = 86, D0 = 70, SCL = (PY - HY);
    const proj = (d) => 1 / (1 + d / D0);
    const S = a.S;
    let px = 0, lane = 0, dist = 0, speed = 250, coins = 0, score = 0, jh = 0, jv = 0, air = false, roll = 0, queueRoll = false, ph = 0;
    let nextRow = 420, ents = [], dead = false, deadAt = 0, combo = 0, lastHud = "";
    let tx = 0, ty = 0, tt = 0, tracking = false;
    // cached gradients
    let G = null;
    const getG = (ctx) => {
      if (G) return G;
      const sky = vgrad(ctx, 0, HY + 4, [[0, "#140b4f"], [0.45, "#7a2a8f"], [0.8, "#ff5f7e"], [1, "#ffb066"]]);
      const ground = vgrad(ctx, HY, H, [[0, "#2a1a4a"], [0.3, "#1b1236"], [1, "#0a0720"]]);
      const bed = vgrad(ctx, HY, H, [[0, "#3a2f5e"], [1, "#26203f"]]);
      const fog = vgrad(ctx, HY - 20, HY + 70, [[0, "rgba(255,150,120,0)"], [0.3, "rgba(255,140,130,.55)"], [1, "rgba(60,30,90,0)"]]);
      const sun = ctx.createRadialGradient(VX + 50, HY - 50, 6, VX + 50, HY - 50, 70);
      sun.addColorStop(0, "#fff7b0"); sun.addColorStop(0.35, "#ffc85a"); sun.addColorStop(0.7, "#ff6c8a"); sun.addColorStop(1, "rgba(255,90,140,0)");
      const sun2 = vgrad(ctx, HY - 100, HY, [[0, "#fff2a0"], [0.5, "#ff9a5a"], [1, "#ff4f8a"]]);
      return (G = { sky, ground, bed, fog, sun, sun2 });
    };
    // skyline layers
    const mkCity = (n, minH, maxH, minW, maxW) => { const b = []; let x = 0; while (x < W + 140) { const w = rnd(minW, maxW); b.push({ x, w, h: rnd(minH, maxH), s: Math.floor(rnd(0, 1000)) }); x += w + rnd(0, 6); } return { b, span: x }; };
    const farC = mkCity(0, 30, 80, 20, 40), nearC = mkCity(0, 24, 62, 22, 46);
    const stars = Array.from({ length: 30 }, () => [rnd(0, W), rnd(0, HY - 60), rnd(0.5, 1.4)]);

    const jump = () => { if (dead) return; if (!air && roll <= 0) { jv = 560; air = true; roll = 0; a.sfx("pop"); a.burst(VX + px * LS, PY + 4, "#cfc4ff", 8, 70); } else if (air) { jv = Math.min(jv, -520); queueRoll = true; } };
    const slide = () => { if (dead) return; if (air) { jv = Math.min(jv, -620); queueRoll = true; } else if (roll <= 0) { roll = 0.62; a.sfx("flip"); } };
    const go = (d) => { if (dead) return; const nl = clamp(lane + d, -1, 1); if (nl !== lane) { lane = nl; a.sfx("turn"); } };
    const gesture = (x, y) => {
      if (!tracking) return; const dx = x - tx, dy = y - ty;
      if (Math.hypot(dx, dy) < 24) return; tracking = false;
      if (Math.abs(dx) > Math.abs(dy)) go(dx > 0 ? 1 : -1); else if (dy < 0) jump(); else slide();
    };
    const crash = () => {
      dead = true; deadAt = S.t; a.sfx("bad"); a.shake(16); a.burst(VX + px * LS, PY - 30 - jh, "#ffd24a", 26, 220); a.burst(VX + px * LS, PY - 20 - jh, "#ff5d8f", 16, 160);
      a.finish(Math.min(score, 24 * S.t));
    };
    const spawnRow = () => {
      const t = S.t, d0 = 780, free = [0, 1, 2];
      const k = t > 14 && Math.random() < 0.45 ? 2 : 1;
      const blocked = [];
      for (let i = 0; i < k; i++) { const j = Math.floor(rnd(0, free.length)); blocked.push(free[j]); free.splice(j, 1); }
      let arcLane = -1;
      blocked.forEach((l) => {
        const r = Math.random(); let type = r < 0.38 ? "low" : r < 0.68 ? "high" : "train";
        if (t < 6 && type === "train") type = "low";
        const o = { type, l: l - 1, d: d0, len: type === "train" ? rnd(170, 230) : 14 };
        ents.push(o);
        if (type === "low" && arcLane < 0 && Math.random() < 0.55) arcLane = l - 1;
      });
      if (arcLane >= 0) { for (let i = 0; i < 4; i++) ents.push({ type: "coin", l: arcLane, d: d0 - 45 + i * 30, h: 12 + 58 * Math.sin(Math.PI * i / 3), ph: i }); }
      else if (Math.random() < 0.55) { const f = free[Math.floor(rnd(0, free.length))] - 1; for (let i = 0; i < 4; i++) ents.push({ type: "coin", l: f, d: d0 - 50 + i * 34, h: 12, ph: i }); }
    };
    const quad = (ctx, x1, y1, x2, y2, x3, y3, x4, y4, col) => { ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.lineTo(x3, y3); ctx.lineTo(x4, y4); ctx.closePath(); ctx.fill(); };
    const drawTrain = (ctx, o) => {
      const dF = Math.max(o.d, -34), dB = Math.max(o.d + o.len, -34); if (dB <= dF) return;
      const pF = proj(dF), pB = proj(dB), X = o.l * LS, hw = 33, h = 100;
      const fl = VX + (X - hw) * pF, fr = VX + (X + hw) * pF, fyb = HY + SCL * pF, fyt = fyb - h * pF;
      const bl = VX + (X - hw) * pB, br = VX + (X + hw) * pB, byb = HY + SCL * pB, byt = byb - h * pB;
      quad(ctx, fl, fyt, fr, fyt, br, byt, bl, byt, "#8db4ff");
      if (o.l < 0) { quad(ctx, fr, fyt, br, byt, br, byb, fr, fyb, "#2a4396"); quad(ctx, fr, fyt + 30 * pF, br, byt + 30 * pB, br, byt + 40 * pB, fr, fyt + 40 * pF, "#ffd24a"); }
      else if (o.l > 0) { quad(ctx, fl, fyt, bl, byt, bl, byb, fl, fyb, "#2a4396"); quad(ctx, fl, fyt + 30 * pF, bl, byt + 30 * pB, bl, byt + 40 * pB, fl, fyt + 40 * pF, "#ffd24a"); }
      const w = fr - fl, hh = fyb - fyt;
      ctx.fillStyle = "#3f6fe0"; ctx.fillRect(fl, fyt, w, hh);
      ctx.fillStyle = "#2c4fb3"; ctx.fillRect(fl, fyt + hh * 0.78, w, hh * 0.22);
      ctx.fillStyle = "#ffd24a"; ctx.fillRect(fl, fyt + hh * 0.7, w, hh * 0.07);
      ctx.fillStyle = "#142046"; rr(ctx, fl + w * 0.1, fyt + hh * 0.1, w * 0.8, hh * 0.34, 4 * pF); ctx.fill();
      ctx.fillStyle = "rgba(160,210,255,.55)"; ctx.fillRect(fl + w * 0.14, fyt + hh * 0.14, w * 0.3, hh * 0.12);
      ctx.fillStyle = "#fff6b0"; ctx.beginPath(); ctx.arc(fl + w * 0.22, fyt + hh * 0.62, 5.5 * pF, 0, 7); ctx.arc(fr - w * 0.22, fyt + hh * 0.62, 5.5 * pF, 0, 7); ctx.fill();
      ctx.globalAlpha = 0.22; ctx.beginPath(); ctx.arc(fl + w * 0.22, fyt + hh * 0.62, 13 * pF, 0, 7); ctx.arc(fr - w * 0.22, fyt + hh * 0.62, 13 * pF, 0, 7); ctx.fill(); ctx.globalAlpha = 1;
    };
    const drawLow = (ctx, o) => {
      const p = proj(Math.max(o.d, -34)), X = o.l * LS, x = VX + X * p, y = HY + SCL * p, w = 64 * p, h = 28 * p;
      ctx.fillStyle = "rgba(0,0,0,.35)"; ctx.beginPath(); ctx.ellipse(x, y + 1, w * 0.55, 4 * p, 0, 0, 7); ctx.fill();
      ctx.fillStyle = "#56627f"; ctx.fillRect(x - w * 0.42, y - h, 5 * p, h); ctx.fillRect(x + w * 0.42 - 5 * p, y - h, 5 * p, h);
      const by = y - h - 2 * p; ctx.fillStyle = "#fff"; rr(ctx, x - w / 2, by, w, h * 0.55, 3 * p); ctx.fill();
      ctx.save(); rr(ctx, x - w / 2, by, w, h * 0.55, 3 * p); ctx.clip(); ctx.fillStyle = "#ff4f4f";
      for (let i = -2; i < 6; i++) { const sx = x - w / 2 + i * w * 0.2; ctx.beginPath(); ctx.moveTo(sx, by + h * 0.55); ctx.lineTo(sx + w * 0.1, by + h * 0.55); ctx.lineTo(sx + w * 0.2, by); ctx.lineTo(sx + w * 0.1, by); ctx.fill(); }
      ctx.restore();
    };
    const drawHigh = (ctx, o) => {
      const p = proj(Math.max(o.d, -34)), X = o.l * LS, x = VX + X * p, y = HY + SCL * p, w = 74 * p;
      ctx.fillStyle = "rgba(0,0,0,.3)"; ctx.beginPath(); ctx.ellipse(x, y + 1, w * 0.55, 4 * p, 0, 0, 7); ctx.fill();
      ctx.fillStyle = "#56627f"; ctx.fillRect(x - w / 2, y - 92 * p, 6 * p, 92 * p); ctx.fillRect(x + w / 2 - 6 * p, y - 92 * p, 6 * p, 92 * p);
      const by = y - 80 * p, bh = 26 * p; ctx.fillStyle = "#ffd24a"; ctx.fillRect(x - w / 2, by, w, bh);
      ctx.fillStyle = "#1c1c28"; for (let i = 0; i < 6; i++) { const sx = x - w / 2 + i * w / 6; ctx.beginPath(); ctx.moveTo(sx, by + bh); ctx.lineTo(sx + w / 12, by + bh); ctx.lineTo(sx + w / 12 + bh * 0.4, by); ctx.lineTo(sx + bh * 0.4, by); ctx.fill(); }
      ctx.fillStyle = (Math.floor(S.t * 5) & 1) ? "#ff3b3b" : "#7a1a1a"; ctx.beginPath(); ctx.arc(x, by - 5 * p, 4 * p, 0, 7); ctx.fill();
    };
    const drawCoin = (ctx, o) => {
      const p = proj(o.d), x = VX + o.l * LS * p, y = HY + SCL * p - (o.h + 8) * p, r = 9 * p, sq = Math.abs(Math.cos(S.t * 6 + o.ph * 0.8));
      ctx.fillStyle = "rgba(0,0,0,.25)"; ctx.beginPath(); ctx.ellipse(x, HY + SCL * p, 7 * p, 2.5 * p, 0, 0, 7); ctx.fill();
      ctx.fillStyle = "#c98a00"; ctx.beginPath(); ctx.ellipse(x, y, r * (0.25 + 0.75 * sq) + 1.2 * p, r, 0, 0, 7); ctx.fill();
      ctx.fillStyle = "#ffd84a"; ctx.beginPath(); ctx.ellipse(x, y, r * (0.25 + 0.75 * sq), r * 0.92, 0, 0, 7); ctx.fill();
      ctx.fillStyle = "#fff6b8"; ctx.beginPath(); ctx.ellipse(x - r * 0.15 * sq, y - r * 0.25, r * 0.22 * sq + 0.5, r * 0.3, 0, 0, 7); ctx.fill();
    };
    const drawRunner = (ctx, x, gy) => {
      const sw = Math.max(6, 20 - jh * 0.12);
      ctx.fillStyle = "rgba(0,0,0,.38)"; ctx.beginPath(); ctx.ellipse(x, gy + 3, sw, 5, 0, 0, 7); ctx.fill();
      ctx.save(); ctx.translate(x, gy - jh);
      if (dead) { const k = Math.min(1, (S.t - deadAt) * 3); ctx.rotate(k * 1.2); ctx.translate(0, -k * 4); }
      if (roll > 0 && !dead) {
        ctx.translate(0, -15); ctx.rotate(S.t * 17);
        ctx.fillStyle = "#ff5d8f"; ctx.beginPath(); ctx.arc(0, 0, 14, 0, 7); ctx.fill();
        ctx.fillStyle = "#2b3a67"; ctx.beginPath(); ctx.arc(6, 8, 7, 0, 7); ctx.fill();
        ctx.fillStyle = "#ffd2a8"; ctx.beginPath(); ctx.arc(-7, -5, 7, 0, 7); ctx.fill();
        ctx.fillStyle = "#20c997"; ctx.beginPath(); ctx.arc(-7, -8, 6.5, Math.PI, 0); ctx.fill();
      } else {
        const lean = clamp((VX + lane * LS - (VX + px * LS)) * 0.006, -0.3, 0.3); ctx.rotate(lean);
        const bob = air ? 0 : Math.abs(Math.sin(ph)) * 3, hipY = -25 - bob;
        const limb = (sgn, back) => {
          let a1, b;
          if (air) { a1 = sgn * 0.8; b = sgn > 0 ? 0.5 : 1.4; } else { a1 = Math.sin(ph + (sgn > 0 ? 0 : Math.PI)) * 0.95; b = 0.9 * (0.5 + 0.5 * Math.cos(ph + (sgn > 0 ? 0 : Math.PI))); }
          const kx = Math.sin(a1) * 12, ky = hipY + Math.cos(a1) * 12, sa = a1 - b, fx = kx + Math.sin(sa) * 12, fy = ky + Math.cos(sa) * 12;
          ctx.strokeStyle = back ? "#1c2850" : "#2b3a67"; ctx.lineWidth = 7; ctx.lineCap = "round"; ctx.lineJoin = "round";
          ctx.beginPath(); ctx.moveTo(0, hipY); ctx.lineTo(kx, ky); ctx.lineTo(fx, fy); ctx.stroke();
          ctx.fillStyle = back ? "#c9c9d8" : "#fff"; ctx.beginPath(); ctx.ellipse(fx + 2, fy + 1, 6, 3.5, 0, 0, 7); ctx.fill();
        };
        const arm = (sgn, back) => {
          const ang = air ? (sgn > 0 ? -2.4 : -1.9) : -Math.sin(ph + (sgn > 0 ? 0 : Math.PI)) * 0.95;
          const sy = -43 - bob, ex = Math.sin(ang) * 10, ey = sy + Math.cos(ang) * 10, ha = ang + 1.3, hx = ex + Math.sin(ha) * 9, hy = ey + Math.cos(ha) * 9;
          ctx.strokeStyle = back ? "#c4466f" : "#ff5d8f"; ctx.lineWidth = 6; ctx.beginPath(); ctx.moveTo(0, sy); ctx.lineTo(ex, ey); ctx.lineTo(hx, hy); ctx.stroke();
          ctx.fillStyle = "#ffd2a8"; ctx.beginPath(); ctx.arc(hx, hy, 3, 0, 7); ctx.fill();
        };
        limb(-1, true); arm(-1, true);
        ctx.fillStyle = "#e4376f"; rr(ctx, -15, -44 - bob, 8, 17, 3); ctx.fill();
        ctx.fillStyle = "#ff5d8f"; rr(ctx, -9, -47 - bob, 18, 24, 6); ctx.fill();
        ctx.fillStyle = "rgba(255,255,255,.35)"; ctx.fillRect(-7, -45 - bob, 4, 18);
        ctx.fillStyle = "#ff8fb1"; ctx.fillRect(-9, -33 - bob, 18, 3);
        limb(1, false); arm(1, false);
        ctx.fillStyle = "#ffd2a8"; ctx.beginPath(); ctx.arc(2, -56 - bob, 9, 0, 7); ctx.fill();
        ctx.fillStyle = "#20c997"; ctx.beginPath(); ctx.arc(2, -58 - bob, 9.5, Math.PI, 0); ctx.fill(); ctx.fillRect(2, -59 - bob, 13, 3.5);
        ctx.fillStyle = "#222"; ctx.beginPath(); ctx.arc(7, -55 - bob, 1.5, 0, 7); ctx.fill();
      }
      ctx.restore();
    };

    return {
      down(x, y) { tx = x; ty = y; tracking = true; },
      move(x, y) { gesture(x, y); },
      up(x, y) { gesture(x, y); tracking = false; },
      key(k) { if (k === "ArrowLeft") go(-1); else if (k === "ArrowRight") go(1); else if (k === "ArrowUp" || k === " ") jump(); else if (k === "ArrowDown") slide(); },
      update(dt) {
        speed = Math.min(480, 250 + S.t * 4); dist += speed * dt; ph += dt * (9 + speed * 0.012);
        px += (lane - px) * Math.min(1, dt * 13);
        if (air) { jh += jv * dt; jv -= 1700 * dt; if (jh <= 0) { jh = 0; jv = 0; air = false; a.burst(VX + px * LS, PY + 4, "#cfc4ff", 6, 60); if (queueRoll) { queueRoll = false; roll = 0.55; } } }
        if (roll > 0) roll -= dt;
        nextRow -= speed * dt; if (nextRow <= 0) { spawnRow(); nextRow = speed * rnd(0.95, 1.5) + 30; }
        for (let i = ents.length - 1; i >= 0; i--) {
          const o = ents[i]; o.d -= speed * dt;
          if (o.d + (o.len || 0) < -45) { ents.splice(i, 1); continue; }
          if (o.type === "coin") {
            if (Math.abs(px - o.l) < 0.5 && Math.abs(o.d) < 14 && Math.abs(o.h - (jh + 20)) < 36) { ents.splice(i, 1); coins++; combo++; a.burst(VX + o.l * LS, PY - o.h - 10, "#ffd84a", 10, 120); a.tone(640 + (combo % 8) * 70, 0.07, "triangle", 0.12); }
            continue;
          }
          if (Math.abs(px - o.l) >= 0.52) continue;
          if (o.type === "train" ? (o.d < 12 && o.d + o.len > -12) : Math.abs(o.d) < 9) {
            if ((o.type === "low" && jh < 26) || (o.type === "high" && roll <= 0) || o.type === "train") { crash(); return; }
          }
        }
        score = Math.floor(dist / 30) + coins * 5;
        const h = "🚆 " + score + "   🪙 " + coins; if (h !== lastHud) { lastHud = h; a.hud(h); }
      },
      draw(ctx) {
        const g = getG(ctx), t = S.t, off = dist * 0.012 + px * 14;
        ctx.fillStyle = g.sky; ctx.fillRect(0, 0, W, HY + 4);
        ctx.fillStyle = "rgba(255,255,255,.8)"; stars.forEach((s) => { ctx.globalAlpha = 0.35 + 0.35 * Math.sin(t * 2 + s[0]); ctx.fillRect(s[0], s[1], s[2], s[2]); }); ctx.globalAlpha = 1;
        ctx.fillStyle = g.sun; ctx.fillRect(VX - 40, HY - 140, 180, 150);
        ctx.fillStyle = g.sun2; ctx.beginPath(); ctx.arc(VX + 50, HY - 50, 34, 0, 7); ctx.fill();
        ctx.fillStyle = "#c9477f"; for (let i = 0; i < 5; i++) ctx.fillRect(VX + 12, HY - 40 + i * 7, 76, 1.5 + i * 0.9);
        // far skyline
        let ox = -((off * 0.4) % farC.span); ctx.fillStyle = "#3a1f68";
        for (let rep = 0; rep < 2; rep++) farC.b.forEach((b) => { ctx.fillRect(b.x + ox + rep * farC.span, HY - b.h, b.w, b.h + 2); });
        // near skyline with windows
        ox = -((off * 0.9) % nearC.span);
        for (let rep = 0; rep < 2; rep++) nearC.b.forEach((b) => { const bx = b.x + ox + rep * nearC.span; ctx.fillStyle = "#1c1040"; ctx.fillRect(bx, HY - b.h, b.w, b.h + 2); ctx.fillStyle = "#2a1a5c"; ctx.fillRect(bx, HY - b.h, 3, b.h); });
        ctx.fillStyle = "rgba(255,214,120,.8)"; ctx.beginPath();
        for (let rep = 0; rep < 2; rep++) nearC.b.forEach((b) => { const bx = b.x + ox + rep * nearC.span; for (let wy = 6; wy < b.h - 4; wy += 9) for (let wx = 5; wx < b.w - 5; wx += 8) if (((b.s + wx * 7 + wy * 13) % 5) === 0) ctx.rect(bx + wx, HY - b.h + wy, 3, 4); });
        ctx.fill();
        // ground + track
        ctx.fillStyle = g.ground; ctx.fillRect(0, HY, W, H - HY);
        const k = (H - HY) / SCL, edge = (1.5 * LS + 40) * k;
        ctx.fillStyle = g.bed; ctx.beginPath(); ctx.moveTo(VX, HY); ctx.lineTo(VX + edge, H); ctx.lineTo(VX - edge, H); ctx.closePath(); ctx.fill();
        // sleepers
        const sp = 44, d0 = -((dist) % sp);
        for (let d = d0 - sp; d < 900; d += sp) {
          const p = proj(d); if (p > 2.6) continue; const y = HY + SCL * p, th = Math.max(0.6, 6 * p); ctx.globalAlpha = Math.min(1, p * 5 + 0.15);
          ctx.fillStyle = "#6b4a3a"; for (let l = -1; l <= 1; l++) ctx.fillRect(VX + (l * LS - 29) * p, y, 58 * p, th);
          ctx.fillStyle = "rgba(255,255,255,.08)"; for (let l = -1; l <= 1; l++) ctx.fillRect(VX + (l * LS - 29) * p, y, 58 * p, Math.max(0.4, th * 0.3));
        }
        ctx.globalAlpha = 1;
        // rails
        ctx.lineCap = "butt";
        for (let l = -1; l <= 1; l++) for (let s = -1; s <= 1; s += 2) {
          const X = l * LS + s * 16;
          ctx.strokeStyle = "#7f8aa8"; ctx.lineWidth = 3.4; ctx.beginPath(); ctx.moveTo(VX, HY); ctx.lineTo(VX + X * k, H); ctx.stroke();
          ctx.strokeStyle = "rgba(255,255,255,.5)"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(VX, HY); ctx.lineTo(VX + X * k - 0.8, H); ctx.stroke();
        }
        // overhead poles
        const ps = 150, pd = -((dist) % ps);
        for (let d = pd - ps; d < 900; d += ps) {
          const p = proj(d); if (p > 2.6 || p < 0.03) continue; const y = HY + SCL * p, hgt = 150 * p;
          for (let s = -1; s <= 1; s += 2) { const x = VX + s * 168 * p; ctx.fillStyle = "#39406a"; ctx.fillRect(x - 2.5 * p, y - hgt, 5 * p, hgt); ctx.fillRect(x - (s > 0 ? 34 * p : 0), y - hgt, 34 * p, 3 * p); ctx.fillStyle = "#ffe08a"; ctx.beginPath(); ctx.arc(x - s * 30 * p, y - hgt + 6 * p, 3 * p, 0, 7); ctx.fill(); }
        }
        // entities far -> near
        ents.sort((p, q) => q.d - p.d);
        let drewPlayer = false;
        const dp = () => { if (drewPlayer) return; drewPlayer = true; ctx.fillStyle = g.fog; ctx.fillRect(0, HY - 20, W, 90); drawRunner(ctx, VX + px * LS, PY); };
        for (let i = 0; i < ents.length; i++) {
          const o = ents[i]; if (o.d < -6 && !drewPlayer) dp();
          if (o.type === "train") drawTrain(ctx, o); else if (o.type === "low") drawLow(ctx, o); else if (o.type === "high") drawHigh(ctx, o); else drawCoin(ctx, o);
        }
        dp();
        // speed lines
        ctx.strokeStyle = "rgba(255,255,255,.12)"; ctx.lineWidth = 1.2;
        for (let i = 0; i < 9; i++) { const q = ((dist * 0.01 + i * 0.37) % 1), s = i % 2 ? 1 : -1; const x0 = VX + s * (60 + (i * 53) % 90) * (0.2 + q), y0 = HY + SCL * q * 0.9 + 10; ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x0 + s * 18 * q, y0 + 40 * q); ctx.stroke(); }
        intro(ctx, W, H, t, "Swipe ◀ ▶ change lane", "▲ jump over barriers   ▼ slide under bars");
      },
    };
  });

  /* =============================== BUBBLE SHOOTER =============================== */
  games.bubbleshot = mk("bubbleshot", "🫧 Bubble Shooter", 340, 520, (a) => {
    const W = a.w, H = a.h, R = 15, D = 30, ROWH = 26, X0 = 5, Y0 = 46, PX = W / 2, PY = H - 50, MAXR = 17, OVER = 14, S = a.S;
    const PAL = [["#ff9aae", "#ff3d63", "#a8183a"], ["#ffe08a", "#ffae1f", "#b36a00"], ["#c4f5a0", "#5fcf3a", "#2a7d1a"], ["#a6ebff", "#25b9f5", "#0b6a9a"], ["#c5baff", "#7b64ff", "#3a2bb0"], ["#ffc2f0", "#ff5fd2", "#9c1f84"]];
    const spr = PAL.map((p) => {
      const c = document.createElement("canvas"); c.width = c.height = 64; const x = c.getContext("2d");
      const g = x.createRadialGradient(24, 22, 3, 32, 32, 31); g.addColorStop(0, p[0]); g.addColorStop(0.55, p[1]); g.addColorStop(1, p[2]);
      x.fillStyle = g; x.beginPath(); x.arc(32, 32, 30, 0, 7); x.fill();
      x.strokeStyle = "rgba(255,255,255,.3)"; x.lineWidth = 2.5; x.beginPath(); x.arc(32, 32, 25, 0.2, 1.3); x.stroke();
      x.strokeStyle = "rgba(0,0,0,.28)"; x.lineWidth = 2; x.beginPath(); x.arc(32, 32, 29, 0, 7); x.stroke();
      x.fillStyle = "rgba(255,255,255,.8)"; x.beginPath(); x.ellipse(21, 18, 9, 5.5, -0.7, 0, 7); x.fill();
      x.fillStyle = "rgba(255,255,255,.4)"; x.beginPath(); x.arc(45, 46, 3, 0, 7); x.fill();
      return c;
    });
    const blit = (ctx, c, x, y, s) => { const d = (D + 1) * (s == null ? 1 : s); ctx.drawImage(spr[c], x - d / 2, y - d / 2, d, d); };
    const rows = []; let par = 0, slide = 0, score = 0, shots = 0, sinceDrop = 0, shot = null, over = false, lastHud = "";
    let cur = 0, nxt = 0, reload = 1, ang = 0, aiming = false, dx0 = 0, dy0 = 0;
    const pops = [], falls = [], floats = [];
    const mkRow = () => new Array(11).fill(-1);
    const ensure = (r) => { while (rows.length <= r) rows.push(mkRow()); };
    const shifted = (r) => (r + par) & 1, maxc = (r) => (shifted(r) ? 10 : 11);
    const cx = (r, c) => X0 + R + c * D + (shifted(r) ? R : 0), cy = (r) => Y0 + R + r * ROWH + slide;
    const at = (r, c) => (r < 0 || r >= rows.length || c < 0 || c >= maxc(r) ? -2 : rows[r][c]);
    const nbs = (r, c, fn) => { const o = shifted(r) ? 0 : -1; fn(r, c - 1); fn(r, c + 1); fn(r - 1, c + o); fn(r - 1, c + o + 1); fn(r + 1, c + o); fn(r + 1, c + o + 1); };
    const present = () => { const s = new Set(); rows.forEach((row) => row.forEach((v) => { if (v >= 0) s.add(v); })); return [...s]; };
    const pick = () => { const p = present(); return p.length ? p[Math.floor(rnd(0, p.length))] : Math.floor(rnd(0, 6)); };
    const addTopRow = () => { rows.unshift(mkRow()); par ^= 1; const row = rows[0], pr = present(), pool = pr.length ? pr : [0, 1, 2, 3, 4, 5]; for (let c = 0; c < maxc(0); c++) row[c] = Math.random() < 0.45 && c > 0 && row[c - 1] >= 0 ? row[c - 1] : (Math.random() < 0.25 ? Math.floor(rnd(0, 6)) : pool[Math.floor(rnd(0, pool.length))]); while (rows.length > MAXR) rows.pop(); };
    for (let r = 0; r < 7; r++) { ensure(r); for (let c = 0; c < maxc(r); c++) rows[r][c] = Math.random() < 0.5 && c > 0 ? rows[r][c - 1] : Math.floor(rnd(0, 5)); }
    cur = pick(); nxt = pick();
    const bokeh = Array.from({ length: 14 }, () => ({ x: rnd(0, W), y: rnd(0, H), r: rnd(18, 50), s: rnd(4, 12), c: Math.floor(rnd(0, 6)) }));
    let BG = null;
    const hits = (x, y) => {
      if (y <= Y0 + R) return true;
      const r0 = Math.floor((y - Y0 - R) / ROWH);
      for (let r = Math.max(0, r0 - 1); r <= Math.min(rows.length - 1, r0 + 2); r++) for (let c = 0; c < maxc(r); c++) if (rows[r][c] >= 0) { const dx = cx(r, c) - x, dy = cy(r) - y; if (dx * dx + dy * dy < (D - 4) * (D - 4)) return true; }
      return false;
    };
    const addFloat = (x, y, s, col) => floats.push({ x, y, t: 0, s, col });
    const land = (x, y) => {
      const rr0 = Math.round((y - Y0 - R - slide) / ROWH); let best = null, bd = 1e9;
      for (let r = Math.max(0, rr0 - 1); r <= Math.min(MAXR - 1, rr0 + 1); r++) { ensure(r); for (let c = 0; c < maxc(r); c++) if (rows[r][c] < 0) { const dx = cx(r, c) - x, dy = cy(r) - y, d = dx * dx + dy * dy; if (d < bd) { bd = d; best = [r, c]; } } }
      return best;
    };
    const place = (r, c, col) => {
      rows[r][c] = col;
      const seen = new Set([r * 20 + c]), st = [[r, c]], grp = [];
      while (st.length) { const [r1, c1] = st.pop(); grp.push([r1, c1]); nbs(r1, c1, (r2, c2) => { const k = r2 * 20 + c2; if (seen.has(k)) return; if (at(r2, c2) === col) { seen.add(k); st.push([r2, c2]); } }); }
      let popped = 0, dropped = 0;
      if (grp.length >= 3) {
        grp.sort((p, q) => Math.hypot(cx(p[0], p[1]) - cx(r, c), cy(p[0]) - cy(r)) - Math.hypot(cx(q[0], q[1]) - cx(r, c), cy(q[0]) - cy(r)));
        grp.forEach((g, i) => { pops.push({ x: cx(g[0], g[1]), y: cy(g[0]), c: col, d: i * 0.035, t: 0, fired: false }); rows[g[0]][g[1]] = -1; });
        popped = grp.length;
        const reach = new Set(), q = [];
        for (let c2 = 0; c2 < maxc(0); c2++) if (rows[0][c2] >= 0) { reach.add(c2); q.push([0, c2]); }
        while (q.length) { const [r1, c1] = q.pop(); nbs(r1, c1, (r2, c2) => { const k = r2 * 20 + c2; if (!reach.has(k) && at(r2, c2) >= 0) { reach.add(k); q.push([r2, c2]); } }); }
        for (let r1 = 0; r1 < rows.length; r1++) for (let c1 = 0; c1 < maxc(r1); c1++) if (rows[r1][c1] >= 0 && !reach.has(r1 * 20 + c1)) {
          falls.push({ x: cx(r1, c1), y: cy(r1), vx: rnd(-50, 50), vy: rnd(-120, -20) - dropped * 0, c: rows[r1][c1], rot: 0, vr: rnd(-6, 6), d: 0.12 + dropped * 0.02 }); rows[r1][c1] = -1; dropped++;
        }
        score += popped * 10 + dropped * 20;
        addFloat(cx(r, c), cy(r) - 10, "+" + (popped * 10 + dropped * 20), dropped ? "#fff29a" : "#fff");
        a.sfx(dropped ? "win" : "good"); a.tone(520 + Math.min(8, popped) * 60, 0.12, "triangle", 0.15);
        if (dropped) a.shake(4 + Math.min(6, dropped));
      } else a.sfx("place");
      return popped;
    };
    const descend = () => {
      addTopRow(); slide = -ROWH; a.sfx("miss"); a.shake(5);
    };
    const checkEnd = () => {
      for (let r = OVER; r < rows.length; r++) if (rows[r].some((v) => v >= 0)) { over = true; a.sfx("bad"); a.shake(12); a.finish(Math.min(score, 11 * S.t)); return true; }
      return false;
    };
    const fire = () => {
      if (shot || over || reload < 0.6) return;
      const sx = Math.sin(ang), sy = -Math.cos(ang); shot = { x: PX + sx * 36, y: PY + sy * 36, ux: sx, uy: sy, c: cur }; reload = 0; a.sfx("flip");
    };
    const aimAt = (x, y) => { const dx = x - PX, dy = PY - y; if (dy < 8) { ang = dx > 0 ? 1.35 : -1.35; return; } ang = clamp(Math.atan2(dx, dy), -1.35, 1.35); };
    const swap = () => { const t = cur; cur = nxt; nxt = t; a.sfx("chip"); };
    return {
      down(x, y) { dx0 = x; dy0 = y; aiming = true; aimAt(x, y); },
      move(x, y) { if (y < PY - 8 || aiming) aimAt(x, y); },
      up(x, y) {
        if (!aiming) return; aiming = false; aimAt(x, y);
        if (Math.hypot(x - PX, y - PY) < 30 && Math.hypot(dx0 - PX, dy0 - PY) < 30) return swap();
        if (Math.hypot(x - (PX - 92), y - (PY + 8)) < 28 && Math.hypot(dx0 - (PX - 92), dy0 - (PY + 8)) < 28) return swap();
        if (y < PY - 8) fire();
      },
      key(k) { if (k === "ArrowLeft") ang = clamp(ang - 0.06, -1.35, 1.35); else if (k === "ArrowRight") ang = clamp(ang + 0.06, -1.35, 1.35); else if (k === " " || k === "ArrowUp") fire(); else if (k === "x") swap(); },
      update(dt) {
        reload = Math.min(1, reload + dt * 4.5); slide += (0 - slide) * Math.min(1, dt * 12); if (Math.abs(slide) < 0.2) slide = 0;
        if (shot) {
          let rem = 640 * dt;
          while (rem > 0 && shot) {
            const st = Math.min(5, rem); rem -= st; shot.x += shot.ux * st; shot.y += shot.uy * st;
            if (shot.x < X0 + R) { shot.x = X0 + R; shot.ux = -shot.ux; a.sfx("pop"); } else if (shot.x > W - X0 - R) { shot.x = W - X0 - R; shot.ux = -shot.ux; a.sfx("pop"); }
            if (hits(shot.x, shot.y)) {
              const cell = land(shot.x, shot.y); const col = shot.c; shot = null;
              if (cell) {
                place(cell[0], cell[1], col); shots++; sinceDrop++;
                const N = shots > 30 ? 5 : 6; if (sinceDrop >= N) { descend(); sinceDrop = 0; }
                if (!checkEnd()) {
                  if (!rows.some((row) => row.some((v) => v >= 0))) { for (let i = 0; i < 4; i++) addTopRow(); slide = -ROWH * 4; score += 100; addFloat(W / 2, 200, "CLEARED! +100", "#7dffb0"); a.sfx("win"); }
                  cur = nxt; if (present().indexOf(cur) < 0) cur = pick(); nxt = pick(); reload = 0;
                }
              }
            }
          }
        }
        for (let i = pops.length - 1; i >= 0; i--) { const p = pops[i]; p.d -= dt; if (p.d > 0) continue; if (!p.fired) { p.fired = true; a.burst(p.x, p.y, PAL[p.c][1], 7, 130); a.burst(p.x, p.y, "#fff", 3, 90); } p.t += dt; if (p.t > 0.25) pops.splice(i, 1); }
        for (let i = falls.length - 1; i >= 0; i--) { const f = falls[i]; if (f.d > 0) { f.d -= dt; continue; } f.vy += 1100 * dt; f.x += f.vx * dt; f.y += f.vy * dt; f.rot += f.vr * dt; if (f.y > H + 30) falls.splice(i, 1); }
        for (let i = floats.length - 1; i >= 0; i--) { floats[i].t += dt; if (floats[i].t > 1) floats.splice(i, 1); }
        const h = "🫧 " + score + "   ▼ " + Math.max(0, (shots > 30 ? 5 : 6) - sinceDrop); if (h !== lastHud) { lastHud = h; a.hud(h); }
      },
      draw(ctx) {
        const t = S.t;
        if (!BG) BG = vgrad(ctx, 0, H, [[0, "#171a52"], [0.55, "#2c1760"], [1, "#150d34"]]);
        ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
        bokeh.forEach((b) => { const y = ((b.y - t * b.s) % (H + 100) + H + 100) % (H + 100) - 50; ctx.globalAlpha = 0.07; ctx.fillStyle = PAL[b.c][1]; ctx.beginPath(); ctx.arc(b.x, y, b.r, 0, 7); ctx.fill(); }); ctx.globalAlpha = 1;
        // playfield + walls
        ctx.fillStyle = "rgba(0,0,0,.28)"; ctx.fillRect(X0, Y0, W - X0 * 2, H - Y0);
        ctx.fillStyle = "rgba(140,170,255,.5)"; ctx.fillRect(X0 - 2, Y0, 2, H); ctx.fillRect(W - X0, Y0, 2, H);
        // danger line
        const dyL = Y0 + OVER * ROWH, near = rows.slice(OVER - 3).some((row) => row.some((v) => v >= 0));
        ctx.strokeStyle = near ? `rgba(255,80,90,${0.5 + 0.4 * Math.sin(t * 8)})` : "rgba(255,120,140,.35)"; ctx.lineWidth = 2; ctx.setLineDash([8, 6]); ctx.beginPath(); ctx.moveTo(X0, dyL); ctx.lineTo(W - X0, dyL); ctx.stroke(); ctx.setLineDash([]);
        // bubbles
        for (let r = 0; r < rows.length; r++) for (let c = 0; c < maxc(r); c++) { const v = rows[r][c]; if (v >= 0) blit(ctx, v, cx(r, c), cy(r)); }
        // pops
        pops.forEach((p) => { if (p.d > 0) { blit(ctx, p.c, p.x, p.y); return; } const k = p.t / 0.25; ctx.globalAlpha = 1 - k; blit(ctx, p.c, p.x, p.y, 1 + k * 0.5); ctx.strokeStyle = "#fff"; ctx.lineWidth = 2 * (1 - k); ctx.beginPath(); ctx.arc(p.x, p.y, R + k * 14, 0, 7); ctx.stroke(); ctx.globalAlpha = 1; });
        falls.forEach((f) => { ctx.save(); ctx.translate(f.x, f.y); ctx.rotate(f.rot); blit(ctx, f.c, 0, 0); ctx.restore(); });
        // ceiling
        const warn = (shots > 30 ? 5 : 6) - sinceDrop <= 2;
        ctx.fillStyle = "rgba(0,0,0,.35)"; ctx.fillRect(0, Y0 - 2, W, 6);
        ctx.fillStyle = vgrad(ctx, 0, Y0, warn ? [[0, "#7a1d2e"], [1, "#4a0f1c"]] : [[0, "#46508c"], [1, "#272c58"]]); ctx.fillRect(0, 0, W, Y0 - 3);
        ctx.fillStyle = warn ? `rgba(255,90,100,${0.35 + 0.35 * Math.sin(t * 9)})` : "rgba(255,255,255,.18)"; ctx.fillRect(0, Y0 - 6, W, 3);
        const N = shots > 30 ? 5 : 6;
        for (let i = 0; i < N; i++) { const x = W / 2 + (i - (N - 1) / 2) * 20, on = i >= sinceDrop; ctx.fillStyle = on ? (warn ? "#ff8a96" : "#ffe27a") : "rgba(0,0,0,.35)"; ctx.beginPath(); ctx.arc(x, 20, 6, 0, 7); ctx.fill(); if (on) { ctx.fillStyle = "rgba(255,255,255,.6)"; ctx.beginPath(); ctx.arc(x - 1.5, 18, 2, 0, 7); ctx.fill(); } }
        ctx.fillStyle = "rgba(255,255,255,.25)"; for (let x = 12; x < W; x += 36) { ctx.beginPath(); ctx.arc(x, 6, 1.6, 0, 7); ctx.arc(x, Y0 - 12, 1.6, 0, 7); ctx.fill(); }
        text(ctx, "▼", 28, 26, 14, warn ? "#ff9aa6" : "#b8c2ff", "center", 800); text(ctx, "▼", W - 28, 26, 14, warn ? "#ff9aa6" : "#b8c2ff", "center", 800);
        // aim guide
        if (!shot && !over) {
          let gx = PX, gy = PY, ux = Math.sin(ang), uy = -Math.cos(ang); ctx.fillStyle = PAL[cur][0];
          for (let i = 0; i < 70; i++) {
            gx += ux * 8; gy += uy * 8; if (gx < X0 + R) { gx = X0 + R; ux = -ux; } else if (gx > W - X0 - R) { gx = W - X0 - R; ux = -ux; }
            if (hits(gx, gy)) { ctx.globalAlpha = 0.5; ctx.beginPath(); ctx.arc(gx, gy, R, 0, 7); ctx.strokeStyle = PAL[cur][0]; ctx.lineWidth = 1.5; ctx.stroke(); break; }
            if (i % 2 === 1 && i > 3) { ctx.globalAlpha = 0.85 - i * 0.01; ctx.beginPath(); ctx.arc(gx, gy, 2.3, 0, 7); ctx.fill(); }
          }
          ctx.globalAlpha = 1;
        }
        // shooter
        ctx.fillStyle = "rgba(0,0,0,.3)"; ctx.fillRect(0, dyL + 8, W, H - dyL);
        ctx.save(); ctx.translate(PX, PY); ctx.rotate(ang);
        ctx.fillStyle = vgrad(ctx, -52, 0, [[0, "#9aa6e8"], [1, "#4a5499"]]); rr(ctx, -9, -50, 18, 54, 6); ctx.fill(); ctx.fillStyle = "rgba(255,255,255,.35)"; ctx.fillRect(-6, -48, 3, 46); ctx.fillStyle = "#2c3370"; rr(ctx, -11, -52, 22, 8, 3); ctx.fill();
        ctx.restore();
        ctx.fillStyle = "#2d3475"; ctx.beginPath(); ctx.arc(PX, PY + 6, 27, Math.PI, 0); ctx.lineTo(PX + 27, PY + 40); ctx.lineTo(PX - 27, PY + 40); ctx.fill();
        ctx.fillStyle = "#4a56a8"; ctx.beginPath(); ctx.arc(PX, PY + 6, 21, 0, 7); ctx.fill();
        if (!shot) blit(ctx, cur, PX, PY + 4, 0.6 + 0.4 * reload * reload * (3 - 2 * reload)); else if (reload >= 0.6) blit(ctx, cur, PX, PY + 4, 0.6 + 0.4 * reload);
        else if (reload > 0) blit(ctx, nxt, PX, PY + 4, reload);
        ctx.fillStyle = "rgba(255,255,255,.08)"; rr(ctx, PX - 118, PY - 14, 52, 46, 14); ctx.fill();
        blit(ctx, nxt, PX - 92, PY + 8, 0.82); text(ctx, "NEXT", PX - 92, PY - 20 + 2, 10, "#aeb6ff", "center", 800);
        text(ctx, "tap = swap", PX + 92, PY + 12, 10, "rgba(200,208,255,.55)", "center", 600);
        if (shot) { ctx.fillStyle = "rgba(255,255,255,.18)"; ctx.beginPath(); ctx.ellipse(shot.x - shot.ux * 12, shot.y - shot.uy * 12, 11, 11, 0, 0, 7); ctx.fill(); blit(ctx, shot.c, shot.x, shot.y); }
        floats.forEach((f) => { ctx.globalAlpha = 1 - f.t; text(ctx, f.s, f.x, f.y - f.t * 36, 18 + (1 - f.t) * 4, f.col, "center", 900); }); ctx.globalAlpha = 1;
        intro(ctx, W, H, t, "Drag to aim, release to shoot", "Match 3+ colours · tap the cannon to swap");
      },
    };
  });

  /* =============================== BLOCK DROP =============================== */
  games.blockdrop = mk("blockdrop", "🧩 Block Drop", 340, 520, (a) => {
    const W = a.w, H = a.h, CS = 26, BW = 10, BH = 16, BX = 8, BY = 14, S = a.S;
    const COL = [null, "#27d9e0", "#ffd23f", "#b266ff", "#4be866", "#ff5470", "#4d7cff", "#ff9a3c"];
    const SH = { I: [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]], O: [[1, 1], [1, 1]], T: [[0, 1, 0], [1, 1, 1], [0, 0, 0]], S: [[0, 1, 1], [1, 1, 0], [0, 0, 0]], Z: [[1, 1, 0], [0, 1, 1], [0, 0, 0]], J: [[1, 0, 0], [1, 1, 1], [0, 0, 0]], L: [[0, 0, 1], [1, 1, 1], [0, 0, 0]] };
    const IDX = { I: 1, O: 2, T: 3, S: 4, Z: 5, J: 6, L: 7 };
    const spr = COL.map((c) => {
      if (!c) return null; const s = 52, b = 7, cv = document.createElement("canvas"); cv.width = cv.height = s; const x = cv.getContext("2d");
      x.fillStyle = c; x.fillRect(0, 0, s, s);
      const poly = (pts, col) => { x.fillStyle = col; x.beginPath(); x.moveTo(pts[0], pts[1]); for (let i = 2; i < pts.length; i += 2) x.lineTo(pts[i], pts[i + 1]); x.fill(); };
      poly([0, 0, s, 0, s - b, b, b, b], "rgba(255,255,255,.55)"); poly([0, 0, b, b, b, s - b, 0, s], "rgba(255,255,255,.3)");
      poly([s, 0, s - b, b, s - b, s - b, s, s], "rgba(0,0,0,.25)"); poly([0, s, b, s - b, s - b, s - b, s, s], "rgba(0,0,0,.42)");
      const g = x.createLinearGradient(b, b, s - b, s - b); g.addColorStop(0, "rgba(255,255,255,.28)"); g.addColorStop(1, "rgba(0,0,0,.12)"); x.fillStyle = g; x.fillRect(b, b, s - 2 * b, s - 2 * b);
      x.fillStyle = "rgba(255,255,255,.55)"; x.beginPath(); x.ellipse(17, 16, 7, 3.5, -0.6, 0, 7); x.fill();
      x.strokeStyle = "rgba(0,0,0,.4)"; x.lineWidth = 1.5; x.strokeRect(0.75, 0.75, s - 1.5, s - 1.5);
      return cv;
    });
    const rot = (m) => { const n = m.length, o = []; for (let r = 0; r < n; r++) { o.push([]); for (let c = 0; c < n; c++) o[r].push(m[n - 1 - c][r]); } return o; };
    const board = Array.from({ length: BH }, () => new Array(BW).fill(0));
    let bag = [], piece = null, next = null, acc = 0, lock = 0, lockMoves = 0, visX = 0, score = 0, lines = 0, level = 1, clearing = null, flashT = 0, lastHud = "", toast = 0, toastTxt = "", btnHold = null, repT = 0, tr = null, softAcc = 0;
    const take = () => { if (!bag.length) { bag = Object.keys(SH); for (let i = bag.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [bag[i], bag[j]] = [bag[j], bag[i]]; } } const k = bag.pop(); return { k, m: SH[k].map((r) => r.slice()), x: 0, y: 0 }; };
    const hit = (m, x, y) => { for (let r = 0; r < m.length; r++) for (let c = 0; c < m.length; c++) if (m[r][c]) { const bx = x + c, by = y + r; if (bx < 0 || bx >= BW || by >= BH) return true; if (by >= 0 && board[by][bx]) return true; } return false; };
    const spawn = () => {
      piece = next || take(); next = take(); const n = piece.m.length; piece.x = Math.floor((BW - n) / 2); piece.y = piece.k === "I" ? -1 : 0; visX = piece.x; acc = 0; lock = 0; lockMoves = 0;
      if (hit(piece.m, piece.x, piece.y)) { a.sfx("bad"); a.shake(10); piece = null; a.finish(Math.min(score, 19 * S.t)); }
    };
    spawn();
    const move = (d) => { if (!piece || clearing) return false; if (!hit(piece.m, piece.x + d, piece.y)) { piece.x += d; if (lock > 0 && lockMoves < 12) { lock = 0; lockMoves++; } a.sfx("chip"); return true; } return false; };
    const rotate = () => {
      if (!piece || clearing) return; const m = rot(piece.m);
      for (const k of [0, -1, 1, -2, 2]) if (!hit(m, piece.x + k, piece.y)) { piece.m = m; piece.x += k; if (lock > 0 && lockMoves < 12) { lock = 0; lockMoves++; } a.sfx("flip"); return; }
      for (const k of [-1, 1]) if (!hit(m, piece.x, piece.y - 1)) { piece.m = m; piece.y -= 1; return; }
    };
    const ghostY = () => { let y = piece.y; while (!hit(piece.m, piece.x, y + 1)) y++; return y; };
    const lockPiece = () => {
      let over = false;
      for (let r = 0; r < piece.m.length; r++) for (let c = 0; c < piece.m.length; c++) if (piece.m[r][c]) { const by = piece.y + r, bx = piece.x + c; if (by < 0) over = true; else board[by][bx] = IDX[piece.k]; }
      a.sfx("place");
      const full = []; for (let r = 0; r < BH; r++) if (board[r].every((v) => v)) full.push(r);
      if (over) { piece = null; a.sfx("bad"); a.shake(10); a.finish(Math.min(score, 19 * S.t)); return; }
      if (full.length) {
        clearing = { rows: full, t: 0 }; piece = null; const pts = [0, 100, 300, 500, 800][full.length]; score += pts; lines += full.length;
        const nl = 1 + Math.floor(lines / 6); if (nl > level) { level = nl; toast = 1.4; toastTxt = "LEVEL " + level; a.sfx("win"); }
        toastTxt = toast > 0 && toastTxt.startsWith("LEVEL") ? toastTxt : ["", "NICE", "GREAT!", "AWESOME!", "BLOCK DROP!"][full.length]; if (!(toast > 0 && toastTxt.startsWith("LEVEL")) || true) toast = Math.max(toast, 1.1);
        a.sfx(full.length >= 4 ? "win" : "good"); a.shake(full.length * 3);
        full.forEach((r) => { for (let c = 0; c < BW; c++) if (c % 2 === 0) a.burst(BX + c * CS + CS / 2, BY + r * CS + CS / 2, COL[board[r][c]], 3, 170); });
      } else spawn();
    };
    const hard = () => { if (!piece || clearing) return; const gy = ghostY(); score += (gy - piece.y) * 2; a.burst(BX + (piece.x + piece.m.length / 2) * CS, BY + (gy + 2) * CS, "#fff", 8, 100); piece.y = gy; a.shake(3); lockPiece(); };
    const step = () => { if (!hit(piece.m, piece.x, piece.y + 1)) { piece.y++; acc = 0; return true; } return false; };
    const BTN = [["◀", 8], ["▶", 91], ["⟳", 174], ["⤓", 257]], BTY = 446;
    const press = (i) => { if (i === 0) move(-1); else if (i === 1) move(1); else if (i === 2) rotate(); else hard(); };
    const fall = () => Math.max(0.07, 0.75 * Math.pow(0.82, level - 1));
    let startX = 0, startY = 0, startT = 0, movedCols = 0, dropped = false, moved = false;
    return {
      down(x, y) {
        if (y >= BTY - 6) { const i = BTN.findIndex((b) => x >= b[1] && x < b[1] + 76); if (i >= 0) { press(i); if (i < 2) { btnHold = i; repT = -0.17; } else btnHold = null; tr = null; a.S.btn = i; } return; }
        tr = true; startX = x; startY = y; startT = S.t; movedCols = 0; dropped = false; moved = false;
      },
      move(x, y) {
        if (!tr || !piece) return; const dx = x - startX, dy = y - startY, cols = Math.trunc(dx / 22);
        while (movedCols < cols) { move(1); movedCols++; moved = true; } while (movedCols > cols) { move(-1); movedCols--; moved = true; }
        if (!dropped && dy > 70 && dy > Math.abs(dx) * 1.6) { dropped = true; hard(); tr = null; }
      },
      up(x, y) {
        btnHold = null; if (!tr) return; tr = null;
        const dx = x - startX, dy = y - startY;
        if (!dropped && !moved && Math.hypot(dx, dy) < 12 && S.t - startT < 0.4) rotate();
        else if (!dropped && dy > 45 && dy > Math.abs(dx) * 1.3) hard();
      },
      key(k) { if (k === "ArrowLeft") move(-1); else if (k === "ArrowRight") move(1); else if (k === "ArrowUp") rotate(); else if (k === "ArrowDown") { if (piece && !clearing && step()) { score += 1; a.sfx("chip"); } } else if (k === " ") hard(); },
      update(dt) {
        toast = Math.max(0, toast - dt);
        if (btnHold !== null && piece) { repT += dt; while (repT >= 0.07) { repT -= 0.07; move(btnHold ? 1 : -1); } }
        if (clearing) {
          clearing.t += dt; if (clearing.t > 0.34) {
            clearing.rows.sort((p, q) => p - q); clearing.rows.forEach((r) => { board.splice(r, 1); board.unshift(new Array(BW).fill(0)); }); clearing = null; spawn();
          }
        } else if (piece) {
          visX += (piece.x - visX) * Math.min(1, dt * 28);
          if (!hit(piece.m, piece.x, piece.y + 1)) { acc += dt; lock = 0; if (acc >= fall()) { acc = 0; piece.y++; } } else { lock += dt; if (lock > 0.4) lockPiece(); }
        }
        const h = `🧩 ${score}   ▤ ${lines}   Lv ${level}`; if (h !== lastHud) { lastHud = h; a.hud(h); }
      },
      draw(ctx) {
        const t = S.t;
        ctx.fillStyle = vgrad(ctx, 0, H, [[0, "#0d0a2e"], [1, "#2b1a66"]]); ctx.fillRect(0, 0, W, H);
        ctx.save(); ctx.globalAlpha = 0.07; ctx.fillStyle = "#8f7bff"; for (let i = 0; i < 6; i++) { const x = ((i * 90 + t * 12) % (W + 120)) - 60; ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x + 30, 0); ctx.lineTo(x - 60, H); ctx.lineTo(x - 90, H); ctx.fill(); } ctx.restore();
        // board
        ctx.fillStyle = "rgba(0,0,0,.45)"; rr(ctx, BX - 2, BY + 4, BW * CS + 4, BH * CS + 4, 6); ctx.fill();
        ctx.fillStyle = vgrad(ctx, BY, BY + BH * CS, [[0, "#12113a"], [1, "#0a0924"]]); rr(ctx, BX - 3, BY - 3, BW * CS + 6, BH * CS + 6, 6); ctx.fill();
        ctx.strokeStyle = "#6e7be0"; ctx.lineWidth = 2; ctx.stroke();
        ctx.strokeStyle = "rgba(255,255,255,.05)"; ctx.lineWidth = 1; ctx.beginPath();
        for (let c = 1; c < BW; c++) { ctx.moveTo(BX + c * CS, BY); ctx.lineTo(BX + c * CS, BY + BH * CS); } for (let r = 1; r < BH; r++) { ctx.moveTo(BX, BY + r * CS); ctx.lineTo(BX + BW * CS, BY + r * CS); } ctx.stroke();
        for (let r = 0; r < BH; r++) for (let c = 0; c < BW; c++) { const v = board[r][c]; if (v) ctx.drawImage(spr[v], BX + c * CS, BY + r * CS, CS, CS); }
        if (piece) {
          const gy = ghostY(), idx = IDX[piece.k];
          ctx.globalAlpha = 0.22; for (let r = 0; r < piece.m.length; r++) for (let c = 0; c < piece.m.length; c++) if (piece.m[r][c]) ctx.drawImage(spr[idx], BX + (piece.x + c) * CS, BY + (gy + r) * CS, CS, CS);
          ctx.globalAlpha = 1; ctx.strokeStyle = COL[idx]; ctx.lineWidth = 1.2; ctx.globalAlpha = 0.5;
          for (let r = 0; r < piece.m.length; r++) for (let c = 0; c < piece.m.length; c++) if (piece.m[r][c]) ctx.strokeRect(BX + (piece.x + c) * CS + 1, BY + (gy + r) * CS + 1, CS - 2, CS - 2);
          ctx.globalAlpha = 1;
          const vy = piece.y + (hit(piece.m, piece.x, piece.y + 1) ? 0 : Math.min(0.9, acc / fall()));
          for (let r = 0; r < piece.m.length; r++) for (let c = 0; c < piece.m.length; c++) if (piece.m[r][c]) { const yy = BY + (vy + r) * CS; if (yy > BY - CS) ctx.drawImage(spr[idx], BX + (visX + c) * CS, yy, CS, CS); }
          if (lock > 0) { ctx.globalAlpha = lock * 0.8; ctx.fillStyle = "#fff"; for (let r = 0; r < piece.m.length; r++) for (let c = 0; c < piece.m.length; c++) if (piece.m[r][c]) ctx.fillRect(BX + (piece.x + c) * CS, BY + (piece.y + r) * CS, CS, CS); ctx.globalAlpha = 1; }
        }
        if (clearing) { const k = clearing.t / 0.34; clearing.rows.forEach((r) => { ctx.fillStyle = `rgba(255,255,255,${0.95 - k * 0.5})`; ctx.fillRect(BX, BY + r * CS, BW * CS * Math.min(1, k * 2.2 + 0.2), CS); ctx.fillStyle = `rgba(150,220,255,${1 - k})`; ctx.fillRect(BX, BY + r * CS + CS * k * 0.5, BW * CS, CS * (1 - k)); }); }
        // side panel
        const px = BX + BW * CS + 14, pw = W - px - 6;
        ctx.fillStyle = "rgba(255,255,255,.07)"; rr(ctx, px, BY, pw, 74, 10); ctx.fill(); text(ctx, "NEXT", px + pw / 2, BY + 14, 10, "#aeb6ff", "center", 800);
        if (next) { const m = next.m, n = m.length, cs = 13, ox = px + pw / 2 - n * cs / 2, oy = BY + 38 - n * cs / 2 + (next.k === "I" ? -4 : 2); for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (m[r][c]) ctx.drawImage(spr[IDX[next.k]], ox + c * cs, oy + r * cs, cs, cs); }
        const stat = (y, l, v) => { ctx.fillStyle = "rgba(255,255,255,.07)"; rr(ctx, px, y, pw, 46, 10); ctx.fill(); text(ctx, l, px + pw / 2, y + 15, 10, "#aeb6ff", "center", 800); text(ctx, String(v), px + pw / 2, y + 36, 17, "#fff", "center", 900); };
        stat(BY + 84, "SCORE", score); stat(BY + 136, "LINES", lines); stat(BY + 188, "LEVEL", level);
        // buttons
        BTN.forEach((b, i) => { const down = (btnHold === i) || (a.S.btn === i && false); ctx.fillStyle = "rgba(0,0,0,.35)"; rr(ctx, b[1], BTY + 4, 76, 52, 14); ctx.fill(); ctx.fillStyle = vgrad(ctx, BTY, BTY + 52, down ? [[0, "#4a56a8"], [1, "#2d3475"]] : [[0, "#5a68c8"], [1, "#363f8c"]]); rr(ctx, b[1], BTY + (down ? 2 : 0), 76, 52, 14); ctx.fill(); ctx.strokeStyle = "rgba(255,255,255,.25)"; ctx.lineWidth = 1.5; ctx.stroke(); text(ctx, b[0], b[1] + 38, BTY + 36, 24, "#fff", "center", 800); });
        if (toast > 0) { ctx.globalAlpha = Math.min(1, toast * 2); text(ctx, toastTxt, BX + BW * CS / 2, BY + BH * CS * 0.4 - (1.4 - toast) * 20, 30, "#ffe27a", "center", 900); ctx.globalAlpha = 1; }
        intro(ctx, W, H, t, "Drag ◀ ▶ move · tap rotate", "Swipe ▼ hard drop · or use the buttons");
      },
    };
  });

  /* =============================== HOOP SHOT =============================== */
  games.hoopshot = mk("hoopshot", "🏀 Hoop Shot", 340, 520, (a) => {
    const W = a.w, H = a.h, BX = W / 2, BY = H - 76, RIMY = 190, T = 0.85, ARC = 120, S = a.S;
    let score = 0, streak = 0, time = 45, hp = 0, hx = BX, idleT = 0, idleOn = true, bonusTime = 0, netAmp = 0, flash = 0, boardShake = 0, finished = false, finT = 0, lastHud = "";
    const fl = [], floats = [], trail = [], samples = []; let tracking = false;
    const ballSpr = (() => {
      const c = document.createElement("canvas"); c.width = c.height = 64; const x = c.getContext("2d");
      const g = x.createRadialGradient(24, 22, 3, 32, 32, 31); g.addColorStop(0, "#ffb15c"); g.addColorStop(0.6, "#f07a1c"); g.addColorStop(1, "#a63f08");
      x.fillStyle = g; x.beginPath(); x.arc(32, 32, 30, 0, 7); x.fill();
      x.strokeStyle = "#3a1805"; x.lineWidth = 2; x.beginPath(); x.arc(32, 32, 29.5, 0, 7); x.moveTo(2, 32); x.lineTo(62, 32); x.moveTo(32, 2); x.lineTo(32, 62); x.stroke();
      x.beginPath(); x.arc(-6, 32, 27, -1.2, 1.2); x.stroke(); x.beginPath(); x.arc(70, 32, 27, Math.PI - 1.2, Math.PI + 1.2); x.stroke();
      x.fillStyle = "rgba(255,255,255,.3)"; x.beginPath(); x.ellipse(21, 17, 9, 5, -0.7, 0, 7); x.fill();
      return c;
    })();
    const crowd = []; for (let r = 0; r < 4; r++) for (let i = 0; i < 17; i++) crowd.push({ x: i * 21 + (r % 2) * 10 + rnd(-3, 3), y: 52 + r * 17, c: `hsl(${Math.floor(rnd(0, 360))},55%,${42 + r * 4}%)`, ph: rnd(0, 6) });
    let BG = null;
    const idle = { s: 0 };
    const hoopX = () => hx;
    const ready = () => !finished && time > 0 && idleOn && idle.s > 0.8;
    const addFloat = (x, y, s, col, sz) => floats.push({ x, y, t: 0, s, col, sz: sz || 22 });
    const throwBall = (dx, dy, spd) => {
      const r = clamp(spd / 1.5, 0.4, 1.8);
      let ax = BX + (dx / dy) * (BY - RIMY) * 0.85; ax += (hx - ax) * 0.2; ax = clamp(ax, 10, W - 10);
      const ay = RIMY - (r - 1) * 125;
      fl.push({ st: "fly", x: BX, y: BY, s: 1, rot: 0, sp: rnd(-8, 8), t: 0, ax, ay, layer: 0, scored: false });
      idleOn = false; idleT = 0.75; idle.s = 0; a.sfx("flip");
    };
    const settle = (b) => {
      const e = b.ay - RIMY, d = b.ax - hx, ad = Math.abs(d);
      const vx0 = (b.ax - BX) / T, vy0 = ((b.ay - BY) + 4 * ARC) / T;
      b.t = 0; b.x = b.ax; b.y = b.ay; b.vx = vx0; b.vy = vy0;
      if (ad <= 14 && e > -16 && e < 20) { b.st = "net"; b.swish = true; b.sy = b.y; b.sx = b.x; }
      else if (e <= -16 && e > -78 && ad < 40) { boardShake = 1; a.sfx("hit"); if (ad < 26) { b.st = "net"; b.swish = false; b.bank = true; b.sy = b.y; b.sx = b.x; } else { b.st = "free"; b.vx = (d > 0 ? 1 : -1) * 90; b.vy = -160; b.layer = 1; } }
      else if (e >= 20 && e < 50 && ad < 36) { a.sfx("hit"); a.shake(3); if (Math.random() < 0.5) { b.st = "rim"; b.swish = false; b.sx = b.x; b.sy = b.y; } else { b.st = "free"; b.vx = (d > 0 ? 1 : -1) * rnd(100, 170); b.vy = -260; b.layer = 1; } }
      else { b.st = "free"; b.layer = e < -78 ? 0 : 1; if (e >= 50 && ad < 40) { b.vy = -140; b.vx *= 0.3; a.sfx("hit"); } if (e < -78) { b.vy = vy0 * 0.4; } miss(b); }
    };
    const miss = (b) => { if (b.counted) return; b.counted = true; if (streak > 1) addFloat(hx, RIMY + 70, "streak lost", "#ff9a9a", 14); streak = 0; };
    const makeScore = (b) => {
      if (b.scored) return; b.scored = true; streak++; let pts = b.swish ? 3 : 2, bonus = 0; if (streak % 3 === 0) bonus = 1; pts += bonus; score += pts; flash = 1; netAmp = 1;
      a.sfx(b.swish ? "win" : "good"); a.tone(b.swish ? 880 : 660, 0.14, "triangle", 0.15); a.burst(hx, RIMY + 8, "#ffd24a", 14, 150); a.burst(hx, RIMY + 8, "#fff", 8, 100);
      addFloat(hx, RIMY - 36, (b.swish ? "SWISH! +" : "+") + pts, b.swish ? "#7dffb0" : "#fff", b.swish ? 26 : 22);
      if (bonus) addFloat(hx, RIMY - 66, "🔥 streak x" + streak, "#ffb347", 16);
    };
    const drawBall = (ctx, x, y, s, rot) => { const r = 24 * s; ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.drawImage(ballSpr, -r, -r, r * 2, r * 2); ctx.restore(); };
    return {
      down(x, y) { if (y < H * 0.4 || !ready()) return; tracking = true; samples.length = 0; samples.push(x, y, S.t); },
      move(x, y) { if (tracking) samples.push(x, y, S.t); },
      up(x, y) {
        if (!tracking) return; tracking = false; samples.push(x, y, S.t); const n = samples.length;
        const x0 = samples[0], y0 = samples[1], dx = x - x0, dy = y0 - y; if (dy < 35) { addFloat(BX, BY - 50, "Swipe up!", "#fff", 16); return; }
        const tl = samples[n - 1]; let j = n - 3; while (j > 0 && tl - samples[j + 2] < 0.12) j -= 3;
        const dt = Math.max(0.016, tl - samples[j + 2]) * 1000, spd = Math.max(0.1, (samples[j + 1] - y) / dt);
        throwBall(dx, dy, spd);
      },
      key(k) { if (k === " " || k === "ArrowUp") { if (ready()) throwBall(0, 100, 1.5); } },
      update(dt) {
        time = Math.max(0, time - dt); flash = Math.max(0, flash - dt * 1.8); netAmp = Math.max(0, netAmp - dt * 1.1); boardShake = Math.max(0, boardShake - dt * 3);
        const t = S.t; hp += dt * (1.2 + t * 0.032); const amp = Math.min(105, 12 + t * 2.3); hx = BX + amp * Math.sin(hp);
        if (!idleOn) { idleT -= dt; if (idleT <= 0 && time > 0) { idleOn = true; } } else idle.s = Math.min(1, idle.s + dt * 4.5);
        for (let i = fl.length - 1; i >= 0; i--) {
          const b = fl[i]; b.t += dt; b.rot += b.sp * dt;
          if (b.st === "fly") {
            const u = Math.min(1, b.t / T); b.x = lerp(BX, b.ax, u); b.y = lerp(BY, b.ay, u) - ARC * 4 * u * (1 - u); b.s = 1 - 0.52 * u;
            trail.push(b.x, b.y, b.s, S.t); if (trail.length > 40) trail.splice(0, 4);
            if (u >= 1) settle(b);
          } else if (b.st === "net" || b.st === "rim") {
            if (b.st === "rim") { b.x = b.sx + Math.sin(b.t * 30) * 8 * (1 - b.t / 0.35); b.y = b.sy - 4 + Math.abs(Math.sin(b.t * 20)) * -6; if (b.t > 0.35) { b.st = "net"; b.t = 0; b.sx = b.x; b.sy = b.y; } continue; }
            const k = Math.min(1, b.t / 0.32); b.x = lerp(b.sx, hx, k); b.y = lerp(b.sy < RIMY - 16 ? b.sy : RIMY - 14, RIMY + 38, k * k * (3 - 2 * k)) ; b.s = 0.48;
            if (b.t > 0.08) makeScore(b);
            if (k >= 1) { b.st = "free"; b.vx = 0; b.vy = 260; b.layer = 1; b.t = 0; b.s = 0.48; }
          } else {
            b.vy += 1100 * dt; b.x += b.vx * dt; b.y += b.vy * dt; b.s = Math.min(0.95, b.s + dt * (b.layer ? 0.5 : 0.2));
            if (b.y > H + 60 || b.x < -60 || b.x > W + 60 || b.t > 3) fl.splice(i, 1);
          }
        }
        for (let i = floats.length - 1; i >= 0; i--) { floats[i].t += dt; if (floats[i].t > 1.1) floats.splice(i, 1); }
        if (trail.length && !fl.some((b) => b.st === "fly")) trail.splice(0, 4);
        if (time <= 0 && !finished) { finT += dt; if ((!fl.length && finT > 0.4) || finT > 1.6) { finished = true; a.sfx("win"); a.finish(Math.min(score, 140)); } }
        const h = `🏀 ${score}   ⏱ ${Math.ceil(time)}${streak >= 2 ? "   🔥" + streak : ""}`; if (h !== lastHud) { lastHud = h; a.hud(h); }
      },
      draw(ctx) {
        const t = S.t;
        if (!BG) BG = { wall: vgrad(ctx, 0, 300, [[0, "#14123e"], [1, "#3a2a82"]]), floor: vgrad(ctx, 300, H, [[0, "#c88a4a"], [1, "#8a5428"]]) };
        ctx.fillStyle = BG.wall; ctx.fillRect(0, 0, W, 310);
        // crowd
        crowd.forEach((c) => { const j = flash > 0 ? Math.abs(Math.sin(t * 12 + c.ph)) * 7 * flash : Math.sin(t * 2 + c.ph) * 1.2; ctx.fillStyle = c.c; ctx.beginPath(); ctx.arc(c.x, c.y - j, 6.5, 0, 7); ctx.fill(); ctx.fillRect(c.x - 7, c.y + 4 - j, 14, 12); });
        ctx.fillStyle = "rgba(20,14,60,.45)"; ctx.fillRect(0, 40, W, 90);
        if (flash > 0) { ctx.fillStyle = `rgba(255,240,170,${flash * 0.25})`; ctx.fillRect(0, 40, W, 100); ctx.fillStyle = "#fff"; for (let i = 0; i < 5; i++) { const q = Math.sin(t * 17 + i * 7.3); if (q > 0.7) ctx.fillRect(15 + ((i * 71 + Math.floor(t * 17) * 37) % 310), 55 + (i * 23) % 70, 3, 3); } }
        // light beams
        ctx.fillStyle = "rgba(255,240,200,.05)"; [60, 170, 280].forEach((x, i) => { ctx.beginPath(); ctx.moveTo(x - 8, 0); ctx.lineTo(x + 8, 0); ctx.lineTo(x + 70 * Math.sin(t * 0.5 + i) + 40, 330); ctx.lineTo(x - 70 + 70 * Math.sin(t * 0.5 + i), 330); ctx.fill(); });
        // floor
        ctx.fillStyle = BG.floor; ctx.fillRect(0, 300, W, H - 300);
        ctx.strokeStyle = "rgba(60,30,10,.25)"; ctx.lineWidth = 1; ctx.beginPath(); for (let i = -8; i <= 8; i++) { ctx.moveTo(BX + i * 14, 300); ctx.lineTo(BX + i * 60, H); } ctx.stroke();
        ctx.fillStyle = "rgba(255,255,255,.07)"; ctx.fillRect(0, 300, W, 3);
        ctx.fillStyle = "rgba(190,40,50,.5)"; ctx.beginPath(); ctx.moveTo(BX - 46, 304); ctx.lineTo(BX + 46, 304); ctx.lineTo(BX + 120, H); ctx.lineTo(BX - 120, H); ctx.fill();
        ctx.strokeStyle = "rgba(255,255,255,.5)"; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.ellipse(BX, H - 40, 120, 38, 0, Math.PI, 0); ctx.stroke();
        // scoreboard
        ctx.fillStyle = "#0b0a22"; rr(ctx, BX - 78, 4, 156, 34, 8); ctx.fill(); ctx.strokeStyle = "#5a66c8"; ctx.lineWidth = 1.5; ctx.stroke();
        text(ctx, String(Math.ceil(time)).padStart(2, "0"), BX - 40, 30, 24, time <= 10 && (Math.floor(t * 3) & 1) ? "#ff5a5a" : "#ffd24a", "center", 900);
        text(ctx, String(score).padStart(3, "0"), BX + 40, 30, 24, "#7dffb0", "center", 900); text(ctx, "TIME", BX - 40, 13, 8, "#8a92d8", "center", 800); text(ctx, "PTS", BX + 40, 13, 8, "#8a92d8", "center", 800);
        // support cables
        const bs = boardShake * Math.sin(t * 50) * 2;
        ctx.strokeStyle = "#2a2f55"; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(hx - 30, RIMY - 78); ctx.lineTo(hx - 12, 40); ctx.moveTo(hx + 30, RIMY - 78); ctx.lineTo(hx + 12, 40); ctx.stroke();
        // backboard
        const bx = hx + bs, by = RIMY - 82;
        ctx.fillStyle = "rgba(0,0,0,.3)"; rr(ctx, bx - 48, by + 6, 100, 82, 8); ctx.fill();
        ctx.fillStyle = vgrad(ctx, by, by + 80, [[0, "rgba(235,245,255,.95)"], [1, "rgba(170,200,240,.9)"]]); rr(ctx, bx - 50, by, 100, 80, 8); ctx.fill();
        ctx.strokeStyle = "#cfd8f0"; ctx.lineWidth = 3; ctx.stroke(); ctx.strokeStyle = "#e5483d"; ctx.lineWidth = 3; ctx.strokeRect(bx - 20, by + 38, 40, 30);
        ctx.fillStyle = "rgba(255,255,255,.55)"; ctx.beginPath(); ctx.moveTo(bx - 44, by + 6); ctx.lineTo(bx - 24, by + 6); ctx.lineTo(bx - 44, by + 40); ctx.fill();
        // back rim
        const rimRX = 29, rimRY = 7;
        ctx.strokeStyle = "#9a2a12"; ctx.lineWidth = 4; ctx.beginPath(); ctx.ellipse(hx, RIMY, rimRX, rimRY, 0, Math.PI, Math.PI * 2); ctx.stroke();
        // balls behind net
        for (let i = 0; i < fl.length; i++) { const b = fl[i]; if (b.layer === 0) drawBall(ctx, b.x, b.y, b.s, b.rot); }
        // trail
        for (let i = 0; i < trail.length; i += 4) { ctx.globalAlpha = (i / trail.length) * 0.35; ctx.fillStyle = "#ffb15c"; ctx.beginPath(); ctx.arc(trail[i], trail[i + 1], 22 * trail[i + 2] * 0.8, 0, 7); ctx.fill(); } ctx.globalAlpha = 1;
        // net
        const sw = netAmp * Math.sin(t * 26) * 7, NS = 7; ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = 1.3; ctx.beginPath();
        for (let i = 0; i < NS; i++) { const th = Math.PI * i / (NS - 1), tx = hx + Math.cos(th) * rimRX, ty = RIMY + Math.sin(th) * rimRY, bx2 = hx + Math.cos(th) * 15 + sw * 0.8, by2 = RIMY + 44 + Math.sin(th) * 4; ctx.moveTo(tx, ty); ctx.quadraticCurveTo((tx + bx2) / 2 + sw * 0.5, (ty + by2) / 2 + netAmp * 3, bx2, by2); }
        for (let k = 1; k <= 3; k++) { const f = k / 4, yy = RIMY + 44 * f; for (let i = 0; i < NS; i++) { const th = Math.PI * i / (NS - 1), xr = lerp(rimRX, 15, f), x = hx + Math.cos(th) * xr + sw * f * 0.8, y = yy + Math.sin(th) * lerp(rimRY, 4, f); if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); } }
        ctx.stroke();
        // front rim
        ctx.strokeStyle = "#ff5a2a"; ctx.lineWidth = 4.5; ctx.beginPath(); ctx.ellipse(hx, RIMY, rimRX, rimRY, 0, 0, Math.PI); ctx.stroke();
        ctx.strokeStyle = "rgba(255,255,255,.45)"; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.ellipse(hx, RIMY - 1, rimRX - 2, rimRY - 1, 0, 0.3, Math.PI - 0.3); ctx.stroke();
        for (let i = 0; i < fl.length; i++) { const b = fl[i]; if (b.layer === 1) drawBall(ctx, b.x, b.y, b.s, b.rot); }
        // idle ball
        if (idleOn) {
          const s = idle.s, bob = Math.sin(t * 4) * 2, sc = s < 1 ? s * (1 + 0.25 * (1 - s)) : 1;
          ctx.fillStyle = "rgba(0,0,0,.3)"; ctx.beginPath(); ctx.ellipse(BX, BY + 28, 22 * sc, 6, 0, 0, 7); ctx.fill();
          drawBall(ctx, BX, BY + bob - 2, sc, t * 0.6);
          if (s >= 1 && time > 40) { ctx.globalAlpha = 0.5 + 0.5 * Math.sin(t * 6); text(ctx, "▲", BX, BY - 38 - Math.abs(Math.sin(t * 5)) * 8, 18, "#fff", "center", 900); ctx.globalAlpha = 1; }
        }
        if (tracking && samples.length > 3) { ctx.strokeStyle = "rgba(255,255,255,.35)"; ctx.lineWidth = 3; ctx.lineCap = "round"; ctx.beginPath(); for (let i = 0; i < samples.length; i += 3) { if (i === 0) ctx.moveTo(samples[i], samples[i + 1]); else ctx.lineTo(samples[i], samples[i + 1]); } ctx.stroke(); }
        floats.forEach((f) => { ctx.globalAlpha = Math.min(1, (1.1 - f.t) * 2); text(ctx, f.s, f.x, f.y - f.t * 38, f.sz + (f.t < 0.15 ? f.t * 30 : 0), f.col, "center", 900); }); ctx.globalAlpha = 1;
        if (time <= 0) text(ctx, "TIME!", W / 2, H / 2 - 60, 44, "#ffd24a", "center", 900);
        intro(ctx, W, H, t, "Swipe up to shoot", "Aim with swipe direction · power = speed");
      },
    };
  });
})();

/* Cricket Blitz v2 - top-down stadium: aim the shot into the gaps between fielders, time it for power.
   Own art & code. 18 balls (3 overs), 3 wickets. */
(function () {
  const HUB = window.HUB, A = HUB.arc, games = A.games, mk = A.mk;
  const rnd = (a, b) => a + Math.random() * (b - a), clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const VW = 340, VH = 560, CX = 170, BX = 170, BY = 428, BOWL = 176, RX = 158, RY = 252, GY = 292;
  const rope = (dx, dy) => { const l = Math.hypot(dx, dy) || 1; return l / Math.hypot(dx / RX, dy / RY) / l * l; };   // distance from batter along (dx,dy) unit to the rope ellipse about (CX,GY)
  function ropeDist(ux, uy) {            // solve |(BX-CX + s ux)/RX, (BY-GY + s uy)/RY| = 1
    const ox = BX - CX, oy = BY - GY, a = (ux / RX) ** 2 + (uy / RY) ** 2, b = 2 * (ox * ux / RX ** 2 + oy * uy / RY ** 2), c = (ox / RX) ** 2 + (oy / RY) ** 2 - 1;
    const d = b * b - 4 * a * c; return (-b + Math.sqrt(Math.max(0, d))) / (2 * a);
  }
  const SHOTS = { 0: ["straight drive", "down the ground"], 1: ["cover drive", "square cut"], "-1": ["pulled", "on-side flick"] };
  games.cricketblitz = mk("cricketblitz", "🏏 Cricket Blitz", VW, VH, (a) => {
    const sc = a.w / VW;
    let balls = 18, wk = 3, runs = 0, ball = null, wait = 0.9, swing = 0, msg = "", msgT = 0, msgCol = "#fff", crowd = 0, aim = 0, comm = "", streak = 0, ended = false, fly = null, bowlAnim = 0, lastRes = "";
    const fielders = [];
    const placeField = () => {
      fielders.length = 0;
      const slots = [-95, -62, -30, 0, 28, 60, 92, 150, -150];
      slots.sort(() => Math.random() - 0.5).slice(0, 8).forEach((deg, i) => {
        const ang = (deg + rnd(-9, 9)) * Math.PI / 180, inner = i < 3, d = inner ? rnd(0.3, 0.55) : rnd(0.78, 0.93);
        // deg measured from straight up (0) ; fielders behind (|deg|>110) sit near the keeper side
        const ux = Math.sin(ang), uy = -Math.cos(ang), R = ropeDist(ux, uy) * d;
        fielders.push({ x: BX + ux * R, y: BY + uy * R, hx: 0, hy: 0, ox: 0, oy: 0, ang: deg, run: null });
        const f = fielders[fielders.length - 1]; f.hx = f.x; f.hy = f.y;
      });
    };
    placeField();
    const hud = () => a.hud(`🏏 ${runs}/${3 - wk}   ⚾ ${balls}${streak > 1 ? "   🔥" + streak : ""}`);
    const say = (t, col) => { msg = t; msgCol = col || "#fff"; msgT = 1.2; };
    const bowl = () => {
      const fast = Math.random() < 0.35;
      ball = { t: 0, dur: (fast ? rnd(0.62, 0.8) : rnd(0.85, 1.25)) - Math.min(0.12, (18 - balls) * 0.008), x: BX + rnd(-12, 12), swing: rnd(-14, 14), done: false, bounceAt: rnd(0.55, 0.68), fast };
      bowlAnim = 1;
    };
    const outBall = (why) => { wk--; streak = 0; say(why, "#ff5252"); a.sfx("bad"); a.shake(12); a.burst(BX, BY - 14, "#ff5252", 22); comm = why === "BOWLED!" ? "Timber! The stumps are shattered." : "Gone! Big wicket."; };
    const hit = (x) => {
      const e = ball.t - 1, ad = Math.abs(e);
      swing = 0.32; ball.done = true; ball.hit = true; balls--;
      if (ad > 0.27) { outBall(e < 0 ? "MISSED - BOWLED!" : "BOWLED!"); return finishBall(); }
      let q = clamp(1 - ad / 0.27, 0, 1);
      const perfect = ad < 0.045;
      let ang = clamp((x - CX) / 150, -1, 1) * 70 - e * 110;                // aim by tap position; mistiming drags it leg/off side
      const rad = ang * Math.PI / 180, ux = Math.sin(rad), uy = -Math.cos(rad), R = ropeDist(ux, uy);
      const loft = perfect || q > 0.86, D = R * (loft ? 1.05 : 0.22 + 0.8 * q);
      // fielders on the path
      let stop = null;
      for (const f of fielders) {
        const rx = f.x - BX, ry = f.y - BY, s = rx * ux + ry * uy;
        if (s < 12 || s > D + 14) continue;
        const dp = Math.abs(rx * uy * -1 + ry * ux * -1 + 0) ; // placeholder (recomputed below)
        const px = BX + ux * s, py = BY + uy * s, dd = Math.hypot(f.x - px, f.y - py);
        const reach = loft ? 15 : 24;
        if (dd < reach && (!stop || s < stop.s)) stop = { f, s, dd };
      }
      let res, text, col = "#fff", runsNow = 0, out = false, endS = Math.min(D, R);
      if (stop && loft && stop.s > R * 0.55) { out = true; text = "CAUGHT!"; endS = stop.s; }
      else if (stop && loft && stop.s <= R * 0.55 && q > 0.86 && stop.dd < 12) { out = true; text = "CAUGHT!"; endS = stop.s; }
      else if (stop && !loft) { endS = stop.s; const fr = stop.s / R; runsNow = fr < 0.35 ? 0 : fr < 0.7 ? 1 : 2; text = runsNow ? `${runsNow} run${runsNow > 1 ? "s" : ""}` : "DOT BALL"; col = runsNow ? "#fff" : "#9fb3c8"; }
      else if (loft) { runsNow = 6; text = "SIX!"; col = "#ffd24a"; }
      else if (q > 0.62) { runsNow = 4; text = "FOUR!"; col = "#ffd24a"; endS = R; }
      else { const fr = D / R; runsNow = fr < 0.4 ? 1 : fr < 0.7 ? 2 : 3; text = `${runsNow} run${runsNow > 1 ? "s" : ""}`; }
      fly = { ux, uy, s: 0, D: endS, t: 0, dur: loft && !out ? 1.05 : 0.2 + endS / 330, loft: loft, six: runsNow === 6, out, stop: stop ? stop.f : null, R };
      ball.res = { runsNow, text, col, out, perfect, ang };
      return;
    };
    const applyRes = () => {
      const r = ball.res; if (!r) return;
      if (r.out) { outBall(r.text); }
      else {
        runs += r.runsNow; streak = r.runsNow >= 4 ? streak + 1 : r.runsNow > 0 ? Math.max(0, streak) : 0;
        if (r.runsNow === 0) streak = 0;
        say(r.text, r.col); a.sfx(r.runsNow === 6 ? "win" : r.runsNow === 4 ? "good" : r.runsNow ? "place" : "pop");
        a.burst(fly.ux * fly.D + BX, fly.uy * fly.D + BY, r.col, r.runsNow * 3 + 4, 120);
        if (r.runsNow >= 4) { crowd = 1.4; a.shake(r.runsNow === 6 ? 8 : 4); }
        const k = Math.abs(r.ang) < 18 ? 0 : r.ang > 0 ? 1 : -1; const arr = SHOTS[k];
        comm = r.perfect ? (r.runsNow === 6 ? "Absolute cracker! Sails over the rope." : "Perfectly timed, " + arr[0] + "!") : r.runsNow >= 4 ? "Races away: " + arr[1] + "." : r.runsNow ? "Pushed into the gap for " + r.runsNow + "." : "Straight to the fielder.";
      }
      finishBall(); ball.res = null;
    };
    const finishBall = () => {
      hud();
      if (balls <= 0 || wk <= 0) { ended = true; setTimeout(() => a.finish(runs), 1100); }
      else if (Math.random() < 0.5) placeField();
    };
    hud();
    const p = (ev) => ev;
    return {
      down(x) {
        x = x / sc;
        if (ended || swing > 0 || !ball || ball.done) { aim = clamp((x - CX) / 150, -1, 1); return; }
        hit(x);
      },
      move(x) { aim = clamp((x / sc - CX) / 150, -1, 1); },
      key(k) { if (k === " ") this.down(CX * sc); if (k === "ArrowLeft") aim = clamp(aim - 0.2, -1, 1); if (k === "ArrowRight") aim = clamp(aim + 0.2, -1, 1); },
      update(dt) {
        swing = Math.max(0, swing - dt); msgT = Math.max(0, msgT - dt); crowd = Math.max(0, crowd - dt); bowlAnim = Math.max(0, bowlAnim - dt * 1.6);
        fielders.forEach((f) => { if (f.run) { f.x += (f.run.x - f.x) * Math.min(1, dt * 7); f.y += (f.run.y - f.y) * Math.min(1, dt * 7); } else { f.x += (f.hx + Math.sin(a.S.t * 2 + f.ang) * 1.2 - f.x) * dt * 3; f.y += (f.hy - f.y) * dt * 3; } });
        if (fly) {
          fly.t += dt; const k = Math.min(1, fly.t / fly.dur); fly.s = fly.D * (1 - (1 - k) * (1 - k));
          if (fly.stop) fly.stop.run = { x: BX + fly.ux * fly.s, y: BY + fly.uy * fly.s };
          if (k >= 1 && !fly.done) { fly.done = true; fly.hold = 0.5; applyRes(); }
          if (fly.done) { fly.hold -= dt; if (fly.hold <= 0) { fielders.forEach((f) => { f.run = null; }); fly = null; ball = null; wait = 0.8; } }
          return;
        }
        if (ended) return;
        if (!ball) { wait -= dt; if (wait <= 0) bowl(); return; }
        if (ball.done) return;
        ball.t += dt / ball.dur;
        if (ball.t > 1.28) { ball.done = true; balls--; outBall("BOWLED!"); finishBall(); setTimeout(() => { ball = null; wait = 0.9; }, 900); }
      },
      draw(ctx) {
        ctx.save(); ctx.scale(sc, sc);
        // night sky + stands
        const g0 = ctx.createLinearGradient(0, 0, 0, VH); g0.addColorStop(0, "#0d1b3a"); g0.addColorStop(1, "#14305f"); ctx.fillStyle = g0; ctx.fillRect(0, 0, VW, VH);
        for (let i = 0; i < 70; i++) { const x = (i * 53) % VW, y = (i * 97) % 70; ctx.fillStyle = "#ffffff" + (i % 3 ? "55" : "aa"); ctx.fillRect(x, y, 1.5, 1.5); }
        // crowd ring (outside rope)
        ctx.save(); ctx.beginPath(); ctx.ellipse(CX, GY, RX + 46, RY + 40, 0, 0, 7); ctx.ellipse(CX, GY, RX + 4, RY + 4, 0, 0, 7); ctx.clip("evenodd");
        const sg = ctx.createLinearGradient(0, 0, 0, VH); sg.addColorStop(0, "#37474f"); sg.addColorStop(1, "#263238"); ctx.fillStyle = sg; ctx.fillRect(0, 0, VW, VH);
        const cols = ["#ef5350", "#ffd54f", "#42a5f5", "#ffffff", "#66bb6a", "#ff8a65"];
        for (let i = 0; i < 260; i++) { const th = i * 0.0242 * 1.0, rr = 1 + (i % 3) * 0.045 / 1, ex = CX + Math.cos(th * 6.1) * (RX + 14 + (i % 3) * 11), ey = GY + Math.sin(th * 6.1) * (RY + 14 + (i % 3) * 11); const bob = crowd > 0 ? Math.abs(Math.sin(a.S.t * 12 + i)) * 4 : Math.sin(a.S.t * 2 + i) * 0.6; ctx.fillStyle = cols[i % 6]; ctx.beginPath(); ctx.arc(ex, ey - bob, 2.6, 0, 7); ctx.fill(); }
        ctx.restore();
        // boundary advert boards
        ctx.lineWidth = 6; ctx.strokeStyle = "#e53935"; ctx.beginPath(); ctx.ellipse(CX, GY, RX + 4, RY + 4, 0, 0, 7); ctx.stroke(); ctx.lineWidth = 2; ctx.strokeStyle = "#fff"; ctx.setLineDash([10, 8]); ctx.stroke(); ctx.setLineDash([]);
        // grass with mowing stripes
        ctx.save(); ctx.beginPath(); ctx.ellipse(CX, GY, RX, RY, 0, 0, 7); ctx.clip();
        for (let i = 0; i < 14; i++) { ctx.fillStyle = i % 2 ? "#2e7d32" : "#388e3c"; ctx.fillRect(0, GY - RY + i * (RY * 2 / 14), VW, RY * 2 / 14 + 1); }
        ctx.strokeStyle = "#ffffff55"; ctx.setLineDash([6, 6]); ctx.lineWidth = 2; ctx.beginPath(); ctx.ellipse(CX, GY, RX * 0.62, RY * 0.62, 0, 0, 7); ctx.stroke(); ctx.setLineDash([]);
        // pitch
        const pg = ctx.createLinearGradient(0, BOWL - 20, 0, BY + 30); pg.addColorStop(0, "#d9b77c"); pg.addColorStop(1, "#c79a5a"); ctx.fillStyle = pg; ctx.beginPath(); ctx.roundRect(CX - 20, BOWL - 22, 40, BY - BOWL + 52, 6); ctx.fill();
        ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(CX - 26, BOWL + 8); ctx.lineTo(CX + 26, BOWL + 8); ctx.moveTo(CX - 26, BY - 10); ctx.lineTo(CX + 26, BY - 10); ctx.moveTo(CX - 18, BY + 14); ctx.lineTo(CX + 18, BY + 14); ctx.stroke();
        ctx.restore();
        // stumps
        [[BOWL - 14], [BY + 26]].forEach(([y]) => { ctx.fillStyle = "#fff8e1"; [-6, 0, 6].forEach((dx) => ctx.fillRect(CX + dx - 1, y - 6, 2, 12)); });
        // fielders
        const dude = (x, y, col, big) => { ctx.fillStyle = "#0005"; ctx.beginPath(); ctx.ellipse(x + 2, y + 6, 8, 4, 0, 0, 7); ctx.fill(); ctx.fillStyle = col; ctx.beginPath(); ctx.roundRect(x - 6, y - 5, 12, 12, 4); ctx.fill(); ctx.fillStyle = "#ffcc80"; ctx.beginPath(); ctx.arc(x, y - 9, 5, 0, 7); ctx.fill(); ctx.fillStyle = "#0d47a1"; ctx.beginPath(); ctx.arc(x, y - 11, 5, Math.PI, 0); ctx.fill(); };
        fielders.forEach((f) => dude(f.x, f.y, "#1e88e5"));
        // bowler run-up
        const by = BOWL - 6 - (1 - Math.min(1, bowlAnim)) * 0; dude(CX + 14, BOWL - 8 + (bowlAnim > 0 ? bowlAnim * 22 - 22 : 0), "#e53935");
        // keeper
        dude(CX, BY + 44, "#fdd835");
        // aim guide (only while waiting/ball in flight)
        if (!fly && !ended) {
          const rad = aim * 70 * Math.PI / 180, ux = Math.sin(rad), uy = -Math.cos(rad), R = ropeDist(ux, uy);
          ctx.strokeStyle = "#ffffff77"; ctx.lineWidth = 2; ctx.setLineDash([4, 7]); ctx.beginPath(); ctx.moveTo(BX, BY); ctx.lineTo(BX + ux * R * 0.9, BY + uy * R * 0.9); ctx.stroke(); ctx.setLineDash([]);
          ctx.fillStyle = "#ffd24a"; ctx.beginPath(); ctx.arc(BX + ux * R * 0.9, BY + uy * R * 0.9, 5, 0, 7); ctx.fill();
        }
        // ball
        const shadow = (x, y, r) => { ctx.fillStyle = "#0006"; ctx.beginPath(); ctx.ellipse(x, y, r, r * 0.5, 0, 0, 7); ctx.fill(); };
        if (ball && !fly && !ball.done) {
          const t = Math.min(1.28, ball.t), y = BOWL + (BY - 8 - BOWL) * t, x = BX + (ball.x - BX) * (1 - t) + Math.sin(t * 5) * ball.swing * t;
          const bounceH = t < ball.bounceAt ? Math.sin(t / ball.bounceAt * Math.PI / 2) * 26 : Math.abs(Math.sin((t - ball.bounceAt) / (1 - ball.bounceAt) * Math.PI)) * 14 * (1 - t * 0.4);
          const r = 3 + t * 2.6; shadow(x, y + 1, r + 1);
          ctx.fillStyle = "#c62828"; ctx.beginPath(); ctx.arc(x, y - bounceH, r, 0, 7); ctx.fill(); ctx.fillStyle = "#ffffff88"; ctx.fillRect(x - r, y - bounceH - 0.5, r * 2, 1);
          ctx.strokeStyle = "#ffffff30"; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x, y - bounceH - r); ctx.lineTo(x, y - bounceH - r - 14); ctx.stroke();
          // timing ring around the batter
          const near = clamp(1 - Math.abs(t - 1) * 5, 0, 1); ctx.strokeStyle = `rgba(255,210,74,${0.25 + near * 0.6})`; ctx.lineWidth = 2 + near * 2; ctx.beginPath(); ctx.arc(BX, BY - 4, 20 + (1 - near) * 4, 0, 7); ctx.stroke();
        }
        if (fly) {
          const k = Math.min(1, fly.t / fly.dur), x = BX + fly.ux * fly.s, y = BY + fly.uy * fly.s, h = fly.loft ? Math.sin(k * Math.PI) * (fly.six ? 90 : 55) : Math.abs(Math.sin(k * 7)) * 6 * (1 - k);
          const big = fly.six && k > 0.6 ? 1 - (k - 0.6) * 0.9 : 1;
          shadow(x, y, 4); ctx.fillStyle = "#c62828"; ctx.beginPath(); ctx.arc(x, y - h, 4.5 * big, 0, 7); ctx.fill();
          ctx.strokeStyle = "#ffffff55"; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(BX, BY); ctx.lineTo(x, y - h * 0.5); ctx.stroke();
        }
        // batter (top-down 3/4): pads, helmet, bat that swings
        ctx.fillStyle = "#0004"; ctx.beginPath(); ctx.ellipse(BX + 3, BY + 8, 12, 6, 0, 0, 7); ctx.fill();
        ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.roundRect(BX - 9, BY - 4, 18, 20, 5); ctx.fill();                       // body whites
        ctx.fillStyle = "#e3f2fd"; ctx.fillRect(BX - 8, BY + 10, 6, 10); ctx.fillRect(BX + 2, BY + 10, 6, 10);                // pads
        ctx.fillStyle = "#1565c0"; ctx.beginPath(); ctx.arc(BX, BY - 9, 8, 0, 7); ctx.fill(); ctx.fillStyle = "#0d47a1"; ctx.fillRect(BX - 8, BY - 8, 16, 3);   // helmet + grille
        ctx.save(); ctx.translate(BX + 9, BY + 2); const sw = swing > 0 ? (1 - swing / 0.32) : 0, dir = aim >= 0 ? 1 : -1; ctx.rotate(swing > 0 ? (-1.3 + sw * 3.2) * dir : -0.5 * dir + Math.sin(a.S.t * 3) * 0.04);
        ctx.fillStyle = "#e0b36a"; ctx.beginPath(); ctx.roundRect(-3, -42, 7, 40, 3); ctx.fill(); ctx.fillStyle = "#6d4c41"; ctx.fillRect(-2, -4, 5, 10); ctx.restore();
        ctx.restore();
        // overlay texts in screen space
        ctx.save(); ctx.scale(sc, sc);
        if (msgT > 0) { ctx.globalAlpha = Math.min(1, msgT * 2); ctx.fillStyle = "#000a"; ctx.font = `900 ${46 + (1.2 - msgT) * 16}px system-ui`; ctx.textAlign = "center"; ctx.fillText(msg, CX + 2, 252); ctx.fillStyle = msgCol; ctx.fillText(msg, CX, 250); ctx.globalAlpha = 1; }
        ctx.fillStyle = "#000a"; ctx.beginPath(); ctx.roundRect(8, VH - 40, VW - 16, 30, 10); ctx.fill(); ctx.fillStyle = "#e3f2fd"; ctx.font = "600 13px system-ui"; ctx.textAlign = "center";
        ctx.fillText(balls === 18 && !ball ? "Tap left/right to AIM into gaps · tap when ball reaches the bat" : comm || "Find the gap between the fielders!", CX, VH - 20);
        ctx.restore();
      },
    };
  });
})();

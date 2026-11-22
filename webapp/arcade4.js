/* Arcade batch 4 - 90s classics: Snake, Flappy Wing, Galaxy Shooter, Stack Tower, Road Rush, Whack-a-Mole.
   Same rules as every arcade game: the server checks run length and score (app/arcade.py). */
(function () {
  const HUB = window.HUB, A = HUB.arc, games = A.games;
  const sfx = (n) => { try { HUB.sfx[n](); } catch (e) { /* ignore */ } };
  const tone = (...a) => { try { HUB.tone(...a); } catch (e) { /* ignore */ } };
  const rnd = (a, b) => a + Math.random() * (b - a);

  /* generic harness: setup(g) returns {update(dt), draw(ctx), down(x,y), move(x,y), key(k)} */
  function run(key, title, W, H, setup) {
    return async function () {
      const g = A.canvasGame(title, key, W, H);
      try { await A.post("/api/arcade/start", { game: key }); } catch (e) { return HUB.toast(e.message); }
      const { c, ctx, w, h } = g;
      const fx = [], S = { shake: 0, over: false, t: 0 };
      const burst = (x, y, col, n, sp) => { for (let i = 0; i < n; i++) { const a = rnd(0, 6.28), v = rnd(0.3, 1) * (sp || 120); fx.push({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life: 1, col, r: rnd(1.5, 3.5) }); } };
      const finish = (score) => { if (S.over) return; S.over = true; setTimeout(() => A.claim(key, Math.max(0, Math.floor(score)), g.box), 650); };
      const api = { w, h, hud: (t) => { g.hud.textContent = t; }, burst, finish, S, sfx, tone, shake: (n) => { S.shake = n; } };
      const game = setup(api);
      const pos = (ev) => { const r = c.getBoundingClientRect(), t = ev.touches ? ev.touches[0] : ev; return [t.clientX - r.left, t.clientY - r.top]; };
      c.addEventListener("pointerdown", (ev) => { const [x, y] = pos(ev); game.down && game.down(x, y); });
      c.addEventListener("pointermove", (ev) => { const [x, y] = pos(ev); game.move && game.move(x, y); });
      c.addEventListener("touchmove", (ev) => { ev.preventDefault(); }, { passive: false });
      const onKey = (ev) => { if (!document.body.contains(c)) return removeEventListener("keydown", onKey); game.key && game.key(ev.key); };
      addEventListener("keydown", onKey);
      let last = performance.now();
      (function loop(now) {
        if (!document.body.contains(c)) return;
        const dt = Math.min(0.033, (now - last) / 1000); last = now; S.t += dt;
        if (!S.over) game.update(dt);
        ctx.save(); S.shake *= 0.86; if (S.shake > 0.3) ctx.translate(rnd(-S.shake, S.shake), rnd(-S.shake, S.shake));
        game.draw(ctx);
        for (let i = fx.length - 1; i >= 0; i--) { const p = fx[i]; p.x += p.vx * dt; p.y += p.vy * dt; p.life -= dt * 2; if (p.life <= 0) { fx.splice(i, 1); continue; } ctx.globalAlpha = p.life; ctx.fillStyle = p.col; ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 7); ctx.fill(); }
        ctx.globalAlpha = 1; ctx.restore();
        if (S.over) { ctx.fillStyle = "#000a"; ctx.fillRect(0, 0, w, h); ctx.fillStyle = "#fff"; ctx.font = "800 30px system-ui"; ctx.textAlign = "center"; ctx.fillText("GAME OVER", w / 2, h / 2); }
        A.raf(requestAnimationFrame(loop));
      })(last);
    };
  }
  const bg = (ctx, w, h, a, b) => { const gr = ctx.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, a); gr.addColorStop(1, b); ctx.fillStyle = gr; ctx.fillRect(0, 0, w, h); };

  /* ------------------------------ SNAKE ------------------------------ */
  games.snake = run("snake", "🐍 Snake", 340, 400, (a) => {
    const N = 17, cell = a.w / N, rows = Math.floor(a.h / cell);
    let go = false, body = [[8, 8], [7, 8], [6, 8]], dir = [1, 0], nd = [1, 0], food = null, score = 0, tick = 0, speed = 0.15;
    const place = () => { do { food = [Math.floor(rnd(0, N)), Math.floor(rnd(0, rows))]; } while (body.some((b) => b[0] === food[0] && b[1] === food[1])); };
    place();
    const turn = (dx, dy) => { go = true; if (dx !== -dir[0] || dy !== -dir[1]) nd = [dx, dy]; };
    let sx = 0, sy = 0;
    return {
      down(x, y) { sx = x; sy = y; go = true; },
      move(x, y) { const dx = x - sx, dy = y - sy; if (Math.hypot(dx, dy) > 22) { Math.abs(dx) > Math.abs(dy) ? turn(Math.sign(dx), 0) : turn(0, Math.sign(dy)); sx = x; sy = y; } },
      key(k) { ({ ArrowUp: () => turn(0, -1), ArrowDown: () => turn(0, 1), ArrowLeft: () => turn(-1, 0), ArrowRight: () => turn(1, 0) }[k] || (() => {}))(); },
      update(dt) {
        if (!go) return; tick += dt; if (tick < speed) return; tick = 0; dir = nd;
        const hd = [body[0][0] + dir[0], body[0][1] + dir[1]];
        if (hd[0] < 0 || hd[1] < 0 || hd[0] >= N || hd[1] >= rows || body.some((b) => b[0] === hd[0] && b[1] === hd[1])) { a.sfx("bad"); a.shake(8); a.burst(hd[0] * cell, hd[1] * cell, "#7bed9f", 20); return a.finish(score); }
        body.unshift(hd);
        if (hd[0] === food[0] && hd[1] === food[1]) { score++; speed = Math.max(0.07, speed - 0.004); a.sfx("good"); a.burst((hd[0] + .5) * cell, (hd[1] + .5) * cell, "#ff6b6b", 10, 90); place(); } else body.pop();
        a.hud("🍎 " + score);
      },
      draw(ctx) {
        bg(ctx, a.w, a.h, "#0f2a1a", "#08150d");
        ctx.fillStyle = "#ffffff08"; for (let x = 0; x < N; x++) for (let y = 0; y < rows; y++) if ((x + y) % 2) ctx.fillRect(x * cell, y * cell, cell, cell);
        const pulse = 1 + Math.sin(a.S.t * 8) * 0.08;
        ctx.fillStyle = "#ff4d4d"; ctx.beginPath(); ctx.arc((food[0] + .5) * cell, (food[1] + .5) * cell, cell * 0.38 * pulse, 0, 7); ctx.fill();
        body.forEach((b, i) => { ctx.fillStyle = i === 0 ? "#b8ffcf" : `hsl(${140 - i * 2},70%,${52 - Math.min(i, 20)}%)`; ctx.beginPath(); ctx.roundRect(b[0] * cell + 1.5, b[1] * cell + 1.5, cell - 3, cell - 3, 5); ctx.fill(); });
        const hd = body[0]; ctx.fillStyle = "#111"; ctx.fillRect((hd[0] + .3 + dir[0] * .1) * cell, (hd[1] + .3) * cell, 3, 3); ctx.fillRect((hd[0] + .6 + dir[0] * .1) * cell, (hd[1] + .3) * cell, 3, 3);
      },
    };
  });

  /* ---------------------------- FLAPPY WING ---------------------------- */
  games.flap = run("flap", "🐤 Flappy Wing", 340, 500, (a) => {
    const bird = { x: 90, y: 220, vy: 0 }, pipes = []; let score = 0, spawn = 0, started = false;
    const flap = () => { started = true; bird.vy = -300; a.sfx("pop"); a.burst(bird.x - 8, bird.y + 6, "#fff", 4, 40); };
    return {
      down: flap, key: (k) => { if (k === " " || k === "ArrowUp") flap(); },
      update(dt) {
        if (!started) return;
        bird.vy += 900 * dt; bird.y += bird.vy * dt; spawn -= dt;
        if (spawn <= 0) { spawn = 1.55; pipes.push({ x: a.w + 30, gap: rnd(130, a.h - 210), done: false }); }
        const gapH = 135;
        pipes.forEach((p) => {
          p.x -= 135 * dt;
          if (!p.done && p.x + 26 < bird.x) { p.done = true; score++; a.sfx("good"); a.hud("⭐ " + score); }
          if (bird.x + 12 > p.x - 26 && bird.x - 12 < p.x + 26 && (bird.y - 12 < p.gap || bird.y + 12 > p.gap + gapH)) bird.y = 9999;
        });
        while (pipes.length && pipes[0].x < -40) pipes.shift();
        if (bird.y > a.h - 24 || bird.y < -20) { a.sfx("bad"); a.shake(9); a.burst(bird.x, Math.min(bird.y, a.h - 30), "#ffd24a", 24); a.finish(score); bird.y = a.h - 30; }
      },
      draw(ctx) {
        bg(ctx, a.w, a.h, "#4fc3f7", "#b3e5fc");
        ctx.fillStyle = "#ffffffaa"; [[60, 80], [200, 130], [290, 60]].forEach(([x, y], i) => { const ox = (x - a.S.t * 8 * (i + 1)) % (a.w + 80); ctx.beginPath(); ctx.ellipse(ox < -40 ? ox + a.w + 80 : ox, y, 34, 14, 0, 0, 7); ctx.fill(); });
        pipes.forEach((p) => { ctx.fillStyle = "#43a047"; ctx.fillRect(p.x - 26, 0, 52, p.gap); ctx.fillRect(p.x - 26, p.gap + 135, 52, a.h); ctx.fillStyle = "#2e7d32"; ctx.fillRect(p.x - 32, p.gap - 18, 64, 18); ctx.fillRect(p.x - 32, p.gap + 135, 64, 18); });
        ctx.fillStyle = "#8d6e63"; ctx.fillRect(0, a.h - 14, a.w, 14);
        ctx.save(); ctx.translate(bird.x, bird.y); ctx.rotate(Math.max(-0.5, Math.min(1, bird.vy / 500)));
        ctx.fillStyle = "#ffd54f"; ctx.beginPath(); ctx.ellipse(0, 0, 15, 12, 0, 0, 7); ctx.fill();
        ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(6, -4, 5, 0, 7); ctx.fill(); ctx.fillStyle = "#222"; ctx.beginPath(); ctx.arc(7, -4, 2, 0, 7); ctx.fill();
        ctx.fillStyle = "#ff7043"; ctx.beginPath(); ctx.moveTo(12, 0); ctx.lineTo(21, 3); ctx.lineTo(12, 6); ctx.fill();
        ctx.fillStyle = "#ffb300"; ctx.beginPath(); ctx.ellipse(-4, 3 + Math.sin(a.S.t * 25) * 3, 8, 5, 0, 0, 7); ctx.fill(); ctx.restore();
        if (!started) { ctx.fillStyle = "#fff"; ctx.font = "700 18px system-ui"; ctx.textAlign = "center"; ctx.fillText("Tap to flap!", a.w / 2, 150); }
      },
    };
  });

  /* --------------------------- GALAXY SHOOTER --------------------------- */
  games.galaxy = run("galaxy", "🚀 Galaxy Shooter", 340, 520, (a) => {
    const ship = { x: a.w / 2, y: a.h - 60 }, shots = [], foes = [], stars = Array.from({ length: 40 }, () => ({ x: rnd(0, a.w), y: rnd(0, a.h), s: rnd(20, 90) }));
    let score = 0, lives = 3, fire = 0, spawn = 0, inv = 0;
    return {
      move(x, y) { ship.x = Math.max(18, Math.min(a.w - 18, x)); ship.y = Math.max(a.h * 0.45, Math.min(a.h - 30, y - 26)); },
      down(x, y) { this.move(x, y); },
      update(dt) {
        fire -= dt; spawn -= dt; inv -= dt;
        if (fire <= 0) { fire = 0.2; shots.push({ x: ship.x, y: ship.y - 18 }); tone(900, 0.04, "square", 0.05, 0, 400); }
        if (spawn <= 0) { spawn = Math.max(0.35, 1 - a.S.t * 0.012); foes.push({ x: rnd(20, a.w - 20), y: -20, hp: Math.random() < 0.2 ? 3 : 1, vy: rnd(60, 110) + a.S.t * 1.2, ph: rnd(0, 6) }); }
        shots.forEach((s) => { s.y -= 520 * dt; }); foes.forEach((f) => { f.y += f.vy * dt; f.x += Math.sin(a.S.t * 2 + f.ph) * 40 * dt; });
        for (let i = foes.length - 1; i >= 0; i--) {
          const f = foes[i];
          for (let j = shots.length - 1; j >= 0; j--) if (Math.abs(shots[j].x - f.x) < 17 && Math.abs(shots[j].y - f.y) < 17) { shots.splice(j, 1); f.hp--; a.burst(f.x, f.y, "#ffd24a", 3, 60); break; }
          if (f.hp <= 0) { score += f.vy > 140 || f.hp < -0 ? 1 : 1; a.sfx("capture"); a.burst(f.x, f.y, "#ff7a3d", 16, 140); foes.splice(i, 1); a.hud(`💥 ${score}   ❤️ ${lives}`); continue; }
          if (inv <= 0 && Math.abs(ship.x - f.x) < 22 && Math.abs(ship.y - f.y) < 22) { foes.splice(i, 1); lives--; inv = 1.4; a.sfx("hit"); a.shake(10); a.burst(ship.x, ship.y, "#6bd6ff", 20); a.hud(`💥 ${score}   ❤️ ${lives}`); if (lives <= 0) a.finish(score); continue; }
          if (f.y > a.h + 20) foes.splice(i, 1);
        }
        while (shots.length && shots[0].y < -20) shots.shift();
        stars.forEach((s) => { s.y += s.s * dt; if (s.y > a.h) { s.y = 0; s.x = rnd(0, a.w); } });
      },
      draw(ctx) {
        bg(ctx, a.w, a.h, "#050816", "#101a3a");
        ctx.fillStyle = "#fff"; stars.forEach((s) => ctx.fillRect(s.x, s.y, 1.5, s.s / 40));
        shots.forEach((s) => { ctx.fillStyle = "#7dffb2"; ctx.fillRect(s.x - 2, s.y - 8, 4, 12); });
        foes.forEach((f) => { ctx.fillStyle = f.hp > 1 ? "#ab47bc" : "#ef5350"; ctx.beginPath(); ctx.moveTo(f.x, f.y + 16); ctx.lineTo(f.x - 16, f.y - 10); ctx.lineTo(f.x, f.y - 3); ctx.lineTo(f.x + 16, f.y - 10); ctx.fill(); ctx.fillStyle = "#fff8"; ctx.fillRect(f.x - 3, f.y - 4, 6, 4); });
        if (inv <= 0 || Math.floor(a.S.t * 14) % 2) { ctx.fillStyle = "#6bd6ff"; ctx.beginPath(); ctx.moveTo(ship.x, ship.y - 20); ctx.lineTo(ship.x - 16, ship.y + 14); ctx.lineTo(ship.x, ship.y + 7); ctx.lineTo(ship.x + 16, ship.y + 14); ctx.fill(); ctx.fillStyle = "#ffb74d"; ctx.fillRect(ship.x - 3, ship.y + 10, 6, 6 + Math.random() * 8); }
      },
    };
  });

  /* ---------------------------- STACK TOWER ---------------------------- */
  games.stack = run("stack", "🏗️ Stack Tower", 320, 500, (a) => {
    const BH = 26; let layers = [{ x: 80, w: 160 }], cur = { x: 0, w: 160, dir: 1 }, speed = 150, score = 0, cam = 0;
    const drop = () => {
      const top = layers[layers.length - 1], ov = Math.min(cur.x + cur.w, top.x + top.w) - Math.max(cur.x, top.x);
      if (ov <= 4) { a.sfx("bad"); a.shake(8); a.burst(cur.x + cur.w / 2, a.h - 60 - layers.length * BH + cam, "#ffd24a", 20); return a.finish(score); }
      const perfect = Math.abs(cur.x - top.x) < 5;
      const nx = perfect ? top.x : Math.max(cur.x, top.x), nw = perfect ? top.w : ov;
      layers.push({ x: nx, w: nw }); score++; speed = Math.min(330, speed + 6);
      a.sfx(perfect ? "win" : "place"); if (perfect) { a.burst(nx + nw / 2, a.h - 60 - layers.length * BH + cam, "#fff", 16, 120); tone(880 + score * 20, 0.2, "triangle", 0.2); }
      cur = { x: cur.dir > 0 ? 0 : a.w - nw, w: nw, dir: cur.dir * -1 };
      a.hud("🏗️ " + score + (perfect ? "  PERFECT!" : ""));
    };
    return {
      down: drop, key: (k) => { if (k === " ") drop(); },
      update(dt) { cur.x += cur.dir * speed * dt; if (cur.x < 0) { cur.x = 0; cur.dir = 1; } if (cur.x + cur.w > a.w) { cur.x = a.w - cur.w; cur.dir = -1; } const want = Math.max(0, (layers.length - 8) * BH); cam += (want - cam) * 0.1; },
      draw(ctx) {
        bg(ctx, a.w, a.h, "#1a237e", "#5c6bc0");
        layers.forEach((l, i) => { ctx.fillStyle = `hsl(${(i * 24) % 360},70%,58%)`; ctx.fillRect(l.x, a.h - 40 - (i + 1) * BH + cam, l.w, BH - 2); ctx.fillStyle = "#fff3"; ctx.fillRect(l.x, a.h - 40 - (i + 1) * BH + cam, l.w, 4); });
        if (!a.S.over) { ctx.fillStyle = `hsl(${(layers.length * 24) % 360},70%,66%)`; ctx.fillRect(cur.x, a.h - 40 - (layers.length + 1) * BH + cam, cur.w, BH - 2); }
        ctx.fillStyle = "#2e7d32"; ctx.fillRect(0, a.h - 40 + cam, a.w, 60);
      },
    };
  });

  /* ----------------------------- ROAD RUSH ----------------------------- */
  games.roadrush = run("roadrush", "🏎️ Road Rush", 320, 520, (a) => {
    const lanes = 3, lw = (a.w - 40) / lanes; let lane = 1, x = 0, cars = [], coins = [], dist = 0, spawn = 0, speed = 220, score = 0, line = 0;
    const lx = (i) => 20 + i * lw + lw / 2;
    x = lx(lane);
    const go = (d) => { lane = Math.max(0, Math.min(lanes - 1, lane + d)); a.sfx("step"); };
    return {
      down(px) { go(px < a.w / 2 ? -1 : 1); }, key(k) { if (k === "ArrowLeft") go(-1); if (k === "ArrowRight") go(1); },
      update(dt) {
        x += (lx(lane) - x) * Math.min(1, dt * 14); speed = Math.min(520, 220 + a.S.t * 7); dist += speed * dt; score = Math.floor(dist / 12); line = (line + speed * dt) % 60; spawn -= dt;
        if (spawn <= 0) { spawn = rnd(0.45, 0.9) * (260 / speed + 0.4); const l = Math.floor(rnd(0, lanes)); if (Math.random() < 0.3) coins.push({ l, y: -30 }); else cars.push({ l, y: -60, col: `hsl(${Math.floor(rnd(0, 360))},70%,55%)` }); }
        cars.forEach((c) => { c.y += speed * 0.62 * dt; }); coins.forEach((c) => { c.y += speed * 0.62 * dt; });
        const py = a.h - 90;
        for (let i = coins.length - 1; i >= 0; i--) { const c = coins[i]; if (c.l === lane && Math.abs(c.y - py) < 30) { score += 0; dist += 240; a.sfx("cash"); a.burst(lx(c.l), c.y, "#ffd24a", 10); coins.splice(i, 1); } else if (c.y > a.h + 30) coins.splice(i, 1); }
        for (let i = cars.length - 1; i >= 0; i--) { const c = cars[i]; if (c.y > a.h + 60) { cars.splice(i, 1); continue; } if (Math.abs(lx(c.l) - x) < lw * 0.6 && Math.abs(c.y - py) < 50) { a.sfx("capture"); a.shake(14); a.burst(x, py, "#ff7a3d", 30, 200); return a.finish(score); } }
        a.hud("🏁 " + score);
      },
      draw(ctx) {
        ctx.fillStyle = "#2e7d32"; ctx.fillRect(0, 0, a.w, a.h); ctx.fillStyle = "#37393f"; ctx.fillRect(20, 0, a.w - 40, a.h);
        ctx.fillStyle = "#fff"; for (let i = 1; i < lanes; i++) for (let y = -60 + line; y < a.h; y += 60) ctx.fillRect(20 + i * lw - 2, y, 4, 30);
        ctx.fillStyle = "#ffd24a"; ctx.fillRect(18, 0, 3, a.h); ctx.fillRect(a.w - 21, 0, 3, a.h);
        coins.forEach((c) => { ctx.fillStyle = "#ffd24a"; ctx.beginPath(); ctx.ellipse(lx(c.l), c.y, 10 * Math.abs(Math.cos(a.S.t * 6)) + 2, 10, 0, 0, 7); ctx.fill(); });
        const carAt = (cx, cy, col) => { ctx.fillStyle = "#0006"; ctx.fillRect(cx - 17, cy - 28, 38, 60); ctx.fillStyle = col; ctx.beginPath(); ctx.roundRect(cx - 18, cy - 30, 36, 60, 8); ctx.fill(); ctx.fillStyle = "#16202c"; ctx.fillRect(cx - 12, cy - 14, 24, 20); ctx.fillStyle = "#fff9"; ctx.fillRect(cx - 14, cy - 28, 8, 4); ctx.fillRect(cx + 6, cy - 28, 8, 4); };
        cars.forEach((c) => carAt(lx(c.l), c.y, c.col)); carAt(x, a.h - 90, "#e53935");
      },
    };
  });

  /* ---------------------------- WHACK-A-MOLE ---------------------------- */
  games.mole = run("mole", "🔨 Whack-a-Mole", 320, 420, (a) => {
    const holes = Array.from({ length: 9 }, (_, i) => ({ x: 60 + (i % 3) * 100, y: 120 + Math.floor(i / 3) * 95, up: 0, kind: "m", hit: 0 }));
    let score = 0, spawn = 0, time = 30, miss = 0;
    return {
      down(px, py) {
        for (const h of holes) if (h.up > 0 && !h.hit && Math.hypot(px - h.x, py - (h.y - 10)) < 38) {
          h.hit = 0.35;
          if (h.kind === "b") { score = Math.max(0, score - 3); a.sfx("bad"); a.shake(8); a.burst(h.x, h.y, "#ff5252", 16); } else { score++; a.sfx("hit"); a.burst(h.x, h.y - 10, "#ffd24a", 12, 110); }
          a.hud(`🔨 ${score}   ⏱ ${Math.ceil(time)}`); return;
        }
        miss++; a.sfx("miss");
      },
      update(dt) {
        time -= dt; spawn -= dt; if (time <= 0) { a.sfx("win"); return a.finish(score); }
        if (spawn <= 0) { spawn = Math.max(0.28, 0.8 - a.S.t * 0.015); const h = holes[Math.floor(rnd(0, 9))]; if (!h.up) { h.up = rnd(0.7, 1.2) * Math.max(0.55, 1 - a.S.t * 0.012); h.kind = Math.random() < 0.18 ? "b" : "m"; h.hit = 0; } }
        holes.forEach((h) => { if (h.up > 0) { h.up -= dt; if (h.hit > 0) h.hit -= dt; if (h.hit <= 0 && h.hit !== 0) h.hit = 0; if (h.up <= 0) { h.up = 0; h.hit = 0; } } });
        a.hud(`🔨 ${score}   ⏱ ${Math.ceil(time)}`);
      },
      draw(ctx) {
        bg(ctx, a.w, a.h, "#81c784", "#388e3c");
        holes.forEach((h) => {
          ctx.fillStyle = "#3e2723"; ctx.beginPath(); ctx.ellipse(h.x, h.y + 6, 36, 14, 0, 0, 7); ctx.fill();
          if (h.up > 0) {
            const k = Math.min(1, h.up * 6, (h.hit ? 0.5 : 1)), y = h.y + 10 - 44 * k;
            ctx.save(); ctx.beginPath(); ctx.rect(h.x - 40, 0, 80, h.y + 8); ctx.clip();
            ctx.fillStyle = h.kind === "b" ? "#37474f" : "#8d6e63"; ctx.beginPath(); ctx.ellipse(h.x, y + 18, 24, 28, 0, 0, 7); ctx.fill();
            ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(h.x - 9, y + 8, 5, 0, 7); ctx.arc(h.x + 9, y + 8, 5, 0, 7); ctx.fill(); ctx.fillStyle = "#222"; ctx.beginPath(); ctx.arc(h.x - 9, y + 9, 2, 0, 7); ctx.arc(h.x + 9, y + 9, 2, 0, 7); ctx.fill();
            ctx.fillStyle = h.kind === "b" ? "#ff5252" : "#f8bbd0"; ctx.beginPath(); ctx.ellipse(h.x, y + 18, 7, 5, 0, 0, 7); ctx.fill();
            if (h.kind === "b") { ctx.fillStyle = "#ff5252"; ctx.font = "700 14px system-ui"; ctx.textAlign = "center"; ctx.fillText("BOMB", h.x, y - 6); }
            ctx.restore();
          }
          ctx.fillStyle = "#4e342e"; ctx.beginPath(); ctx.ellipse(h.x, h.y + 10, 36, 9, 0, 0, Math.PI); ctx.fill();
        });
      },
    };
  });
})();

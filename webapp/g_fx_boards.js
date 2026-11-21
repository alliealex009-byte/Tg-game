/* g_fx_boards.js - extra motion + sound for checkers, battleship, connect4, memory, tictactoe.
   Wraps HUB.UI[key].apply; never edits the renderers. Every effect is try/catch'd and < 600ms. */
(function () {
  "use strict";
  const HUB = window.HUB; if (!HUB || !HUB.UI) return;
  const reduce = () => { try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { return false; } };
  const tone = (...a) => { try { HUB.tone && HUB.tone(...a); } catch (e) { /* audio */ } };
  const noise = (...a) => { try { HUB.noise && HUB.noise(...a); } catch (e) { /* audio */ } };
  const later = (fn, ms) => setTimeout(() => { try { fn(); } catch (e) { /* fx */ } }, ms);
  const rel = (el) => { if (el && getComputedStyle(el).position === "static") el.style.position = "relative"; };

  /* spawn a one-shot absolutely positioned element inside host at (x,y) host-local px */
  function spawn(host, x, y, css, frames, ms, text, delay) {
    if (!host || !host.animate) return null;
    const d = document.createElement("i");
    d.style.cssText = `position:absolute;left:${x}px;top:${y}px;pointer-events:none;z-index:9;font-style:normal;${css}`;
    if (text) d.textContent = text;
    host.appendChild(d);
    const a = d.animate(frames, { duration: ms, delay: delay || 0, easing: "ease-out", fill: "backwards" });
    a.onfinish = () => d.remove(); a.oncancel = () => d.remove();
    setTimeout(() => d.remove(), ms + (delay || 0) + 200);
    return d;
  }
  function sparks(host, cx, cy, n, cols, dist, ms, size) {
    for (let i = 0; i < n; i++) {
      const a = (i / n) * 6.283 + Math.random(), d = dist * (0.5 + Math.random() * 0.6), sz = (size || 5) * (0.6 + Math.random() * 0.8);
      spawn(host, cx - sz / 2, cy - sz / 2, `width:${sz}px;height:${sz}px;border-radius:50%;background:${cols[i % cols.length]}`,
        [{ transform: "translate(0,0) scale(1)", opacity: 1 }, { transform: `translate(${Math.cos(a) * d}px,${Math.sin(a) * d}px) scale(.2)`, opacity: 0 }], ms);
    }
  }
  function ring(host, cx, cy, size, color, ms, delay) {
    spawn(host, cx - size / 2, cy - size / 2, `width:${size}px;height:${size}px;border-radius:50%;border:2px solid ${color}`,
      [{ transform: "scale(.2)", opacity: 0.9 }, { transform: "scale(1.6)", opacity: 0 }], ms, "", delay);
  }
  const center = (el) => ({ x: el.offsetWidth / 2, y: el.offsetHeight / 2 });
  function shake(el, px, ms) {
    if (el && el.animate) el.animate([{ transform: "translate(0,0)" }, { transform: `translate(${-px}px,${px / 2}px)` }, { transform: `translate(${px}px,${-px / 2}px)` }, { transform: `translate(${-px / 2}px,0)` }, { transform: "none" }], { duration: ms || 320 });
  }

  /* wrap helper: fn(s, ui, st) runs after the original; st.isNew tells whether a new move was detected via seqOf(s) */
  function wrap(key, seqOf, after) {
    const U = HUB.UI[key]; if (!U || !U.apply || U.apply.__fx) return;
    const orig = U.apply;
    U.apply = function (s) {
      let ctx = null;
      try {
        const ui = HUB.S.ui, g = s.game, seq = seqOf(g);
        if (ui && ui.type === key || ui) {
          const fx = ui.__fx || (ui.__fx = { first: true, seq: 0, prev: null });
          ctx = { ui, fx, g, seq, isNew: !fx.first && seq != null && seq > fx.seq };
          if (seq != null) fx.seq = Math.max(fx.seq, seq);
        }
      } catch (e) { ctx = null; }
      const r = orig.apply(this, arguments);
      const run = () => { if (!ctx) return; try { after(s, ctx); } catch (e) { /* fx */ } ctx.fx.first = false; };
      run();
      return r;
    };
    U.apply.__fx = true;
  }

  /* ---------------- CHECKERS ---------------- */
  wrap("checkers", (g) => g.last_move && g.last_move.seq, (s, c) => {
    const { ui, g } = c, lm = g.last_move;
    if (!c.isNew || !lm || reduce()) return;
    const to = lm.path[lm.path.length - 1], dest = ui.cells[to], pc = dest && dest.querySelector(".gb-pc");
    if (pc && pc.animate) {                         // hop arc layered on the renderer's slide (independent `translate`/`scale`)
      const hops = Math.max(1, lm.path.length - 1);
      try { pc.animate([{ translate: "0 0", scale: "1" }, { translate: "0 -14px", scale: "1.18", offset: 0.45 }, { translate: "0 0", scale: "1" }], { duration: Math.min(540, 260 + (hops - 1) * 120), easing: "ease-in-out" }); } catch (e) { /* old webview */ }
    }
    (lm.captured || []).forEach((sq, i) => {
      const cell = typeof sq === "number" ? ui.cells[sq] : null; if (!cell) return;
      rel(cell); const m = center(cell);
      later(() => {
        sparks(cell, m.x, m.y, 10, ["#ffd24a", "#ff7043", "#fff"], 30, 420, 6);
        ring(cell, m.x, m.y, m.x * 1.6, "#ffd24a", 380);
        noise(0.12, 0.2, 0, 1600); tone(520 - i * 60, 0.14, "square", 0.1, 0, 200);
      }, 140 + i * 110);
    });
    if (lm.crowned && dest) {
      rel(dest); const m = center(dest);
      later(() => {
        sparks(dest, m.x, m.y, 12, ["#ffd24a", "#fff6c0"], 34, 520, 5);
        spawn(dest, m.x - 10, m.y - m.y * 1.1, "font-size:18px;line-height:1;color:#ffd24a;text-shadow:0 0 6px #ffd24a", [{ transform: "translateY(10px) scale(.4)", opacity: 0 }, { transform: "translateY(-6px) scale(1.2)", opacity: 1, offset: 0.4 }, { transform: "translateY(-14px) scale(.8)", opacity: 0 }], 520, "\u{1F451}");
        [1046, 1318, 1568].forEach((f, i) => tone(f, 0.12, "triangle", 0.12, i * 0.07));
      }, 280);
    }
  });

  /* ---------------- BATTLESHIP ---------------- */
  wrap("battleship", (g) => g.last_move && g.last_move.seq, (s, c) => {
    const { ui, g } = c, lm = g.last_move;
    if (!c.isNew || !lm) return;
    const ps = g.players.map((p) => p.uid), playing = ps.includes(s.you), foe = playing ? ps.find((u) => u !== s.you) : ps[1];
    const cells = lm.target === foe ? ui.en : ui.fl, cell = cells && cells[lm.cell]; if (!cell) return;
    const grid = cell.parentElement; rel(grid);
    const cx = cell.offsetLeft + cell.offsetWidth / 2, cy = cell.offsetTop + cell.offsetHeight / 2, cw = cell.offsetWidth;
    if (lm.hit || lm.sunk) {
      tone(90, 0.3, "sawtooth", 0.22, 0, 35);
      if (reduce()) return;
      spawn(grid, cx - cw, cy - cw, `width:${cw * 2}px;height:${cw * 2}px;border-radius:50%;background:radial-gradient(#fff,#ff9d2e 40%,transparent 70%)`, [{ transform: "scale(.2)", opacity: 1 }, { transform: "scale(1.3)", opacity: 0 }], 420);
      sparks(grid, cx, cy, 12, ["#ff7043", "#ffd24a", "#555"], cw * 1.1, 480, 5);
      shake(grid, lm.sunk ? 7 : 4, lm.sunk ? 480 : 300);
      if (lm.sunk) later(() => {
        grid.querySelectorAll(".gb-wc.sunk").forEach((el) => { if (el.animate) el.animate([{ filter: "brightness(1)" }, { filter: "brightness(3.2)", offset: 0.3 }, { filter: "brightness(1)" }], { duration: 520 }); });
        [330, 262, 196].forEach((f, i) => tone(f, 0.16, "sawtooth", 0.12, i * 0.09, f * 0.7));
      }, 200);
    } else {
      noise(0.2, 0.18, 0, 900);
      if (reduce()) return;
      ring(grid, cx, cy, cw * 1.4, "#9fd3ff", 520); ring(grid, cx, cy, cw * 1.4, "#9fd3ff", 520, 120);
      sparks(grid, cx, cy, 6, ["#cfeaff", "#9fd3ff"], cw * 0.7, 420, 4);
    }
  });

  /* ---------------- CONNECT FOUR ---------------- */
  wrap("connect4", (g) => g.last_move && g.last_move.seq, (s, c) => {
    const { g } = c, lm = g.last_move, board = document.getElementById("c4");
    if (!board) return;
    if (c.isNew && lm && !reduce()) {
      const hole = board.querySelector(`.hole[data-i="${lm.row * 7 + lm.col}"]`), disc = hole && hole.firstElementChild;
      if (disc && disc.animate) {                   // gravity bounce after the renderer's fall (~450ms)
        try { disc.animate([{ translate: "0 0", scale: "1 1" }, { translate: "0 -14%", scale: "1 1", offset: 0.4 }, { translate: "0 0", scale: "1.12 .88", offset: 0.7 }, { translate: "0 0", scale: "1 1" }], { duration: 180, delay: 430, easing: "ease-out", fill: "backwards" }); } catch (e) { /* old webview */ }
      }
      later(() => tone(110, 0.09, "sine", 0.25, 0, 70), 440);
      later(() => { if (hole) { rel(hole); const m = center(hole); ring(hole, m.x, m.y * 1.6, m.x * 1.5, "#ffffffaa", 300); } }, 440);
    }
    if (g.line && !c.fx.line) {
      c.fx.line = true;
      if (!reduce()) g.line.forEach((i, k) => {
        const h = board.querySelector(`.hole[data-i="${i}"]`); if (!h) return;
        rel(h); const m = center(h);
        later(() => { sparks(h, m.x, m.y, 7, ["#fff", "#ffd24a"], m.x * 1.4, 480, 4); tone(784 + k * 160, 0.12, "triangle", 0.12); }, 480 + k * 90);
      });
    }
    if (!g.line) c.fx.line = false;
  });

  /* ---------------- MEMORY ---------------- */
  wrap("memory", (g) => g.last_flip && g.last_flip.seq, (s, c) => {
    const { g, fx } = c, grid = document.getElementById("mg"); if (!grid) return;
    const owners = g.owner.map((o) => (o == null ? 0 : 1)), prev = fx.prev; fx.prev = owners;
    if (!prev) return;
    const cards = grid.querySelectorAll(".mcard");
    const matched = owners.map((o, i) => (o && !prev[i] ? i : -1)).filter((i) => i >= 0);
    if (matched.length) {
      matched.forEach((i, k) => later(() => {
        const el = cards[i]; if (!el) return; rel(el); const m = center(el);
        if (!reduce()) {
          sparks(el, m.x, m.y, 10, ["#ffd24a", "#4ade80", "#fff", "#4aa8ff"], m.x * 1.3, 520, 6);
          el.animate && el.animate([{ transform: "scale(1)" }, { transform: "scale(1.14)", offset: 0.4 }, { transform: "scale(1)" }], { duration: 380 });
        }
        if (k === 0) [880, 1109, 1318].forEach((f, j) => tone(f, 0.16, "triangle", 0.16, j * 0.08));
      }, 330));
    } else if (c.isNew && g.up.length === 2 && g.cards[g.up[0]] !== g.cards[g.up[1]]) {
      later(() => {
        tone(220, 0.2, "sawtooth", 0.1, 0, 140);
        if (reduce()) return;
        g.up.forEach((i) => { const el = cards[i]; if (el && el.animate) el.animate([{ translate: "0 0" }, { translate: "-5px 0" }, { translate: "5px 0" }, { translate: "-3px 0" }, { translate: "0 0" }], { duration: 360 }); });
      }, 380);
    }
  });

  /* ---------------- TIC-TAC-TOE ---------------- */
  wrap("tictactoe", (g) => (g.board || []).filter(Boolean).length, (s, c) => {
    const { g, fx } = c, tb = document.getElementById("tb"); if (!tb) return;
    const snap = (g.board || []).join("|"), prev = fx.prevBoard; fx.prevBoard = snap;
    if (prev == null || prev === snap) { if (!g.line) fx.line = false; return; }
    const was = prev.split("|"), now = snap.split("|");
    if (!reduce()) now.forEach((v, i) => {
      if (v && v !== was[i]) {
        const el = tb.children[i];                  // handwritten draw-in: reveal left to right
        if (el && el.animate) el.animate([{ clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0 0 0)" }], { duration: 300, easing: "ease-out" });
      }
    });
    tone(now.filter(Boolean).length % 2 ? 660 : 520, 0.08, "triangle", 0.12);
    if (g.line && !fx.line) {
      fx.line = true;
      const a = tb.children[g.line[0]], b = tb.children[g.line[g.line.length - 1]];
      if (a && b && !reduce()) later(() => {
        rel(tb);
        const x1 = a.offsetLeft + a.offsetWidth / 2, y1 = a.offsetTop + a.offsetHeight / 2, x2 = b.offsetLeft + b.offsetWidth / 2, y2 = b.offsetTop + b.offsetHeight / 2;
        const len = Math.hypot(x2 - x1, y2 - y1) + a.offsetWidth * 0.5, ang = Math.atan2(y2 - y1, x2 - x1);
        const ln = spawn(tb, x1 - a.offsetWidth * 0.25, y1 - 3, `width:${len}px;height:6px;border-radius:3px;background:linear-gradient(90deg,#ffd24a,#fff);box-shadow:0 0 10px #ffd24a;transform-origin:0 50%;transform:rotate(${ang}rad)`,
          [{ transform: `rotate(${ang}rad) scaleX(0)`, opacity: 1 }, { transform: `rotate(${ang}rad) scaleX(1)`, opacity: 1, offset: 0.7 }, { transform: `rotate(${ang}rad) scaleX(1)`, opacity: 0.9 }], 560);
        if (ln) ln.style.opacity = "0";
        [660, 784, 988].forEach((f, j) => tone(f, 0.14, "triangle", 0.14, j * 0.1));
      }, 250);
    }
  });
})();

/* Extra polish (animation / sound / movement) wrapped around existing renderers: dominoes, dots, bingo,
   hangman, mafia, trivia, scribble. Loads after the renderers; wraps HUB.UI[key].apply only. */
(function () {
  "use strict";
  const HUB = window.HUB;
  if (!HUB || !HUB.UI) return;
  const $ = (q) => document.querySelector(q);
  const rm = () => { try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { return false; } };
  const tone = (...a) => { try { HUB.tone && HUB.tone(...a); } catch (e) { /* ignore */ } };
  const anim = (el, kf, opt) => { try { if (el && el.animate && !rm()) return el.animate(kf, Object.assign({ easing: "ease-out" }, opt)); } catch (e) { /* ignore */ } return null; };
  const COLS = ["#ffd24a", "#4ade80", "#4aa8ff", "#c084fc", "#ff7043", "#fff"];

  function burst(x, y, n, cols, spread) {
    if (rm()) return;
    cols = cols || COLS; spread = spread || 70;
    for (let i = 0; i < n; i++) {
      const d = document.createElement("i"); d.className = "fxp";
      const sz = 4 + Math.random() * 5;
      d.style.cssText = `left:${x}px;top:${y}px;width:${sz}px;height:${sz}px;background:${cols[i % cols.length]}`;
      document.body.appendChild(d);
      const a = Math.random() * 6.283, r = spread * (0.4 + Math.random() * 0.6);
      const an = anim(d, [{ transform: "translate(0,0) scale(1)", opacity: 1 }, { transform: `translate(${Math.cos(a) * r}px,${Math.sin(a) * r - 12}px) scale(.2)`, opacity: 0 }], { duration: 420 + Math.random() * 140 });
      if (an) an.onfinish = () => d.remove(); else d.remove();
    }
  }
  function burstAt(el, n, cols, spread) { if (!el) return; const b = el.getBoundingClientRect(); burst(b.left + b.width / 2, b.top + b.height / 2, n, cols, spread); }
  function flash(color, ms) {
    if (rm()) return;
    const d = document.createElement("div"); d.className = "fxflash"; d.style.background = color;
    document.body.appendChild(d);
    const an = anim(d, [{ opacity: 0 }, { opacity: 0.55 }, { opacity: 0 }], { duration: ms || 420 });
    if (an) an.onfinish = () => d.remove(); else d.remove();
  }
  function pop(text, x, y, color) {
    if (rm()) return;
    const d = document.createElement("div"); d.className = "fxpop"; d.textContent = text;
    d.style.cssText = `left:${x}px;top:${y}px;color:${color || "#ffd24a"}`;
    document.body.appendChild(d);
    const an = anim(d, [{ transform: "translate(-50%,0) scale(.5)", opacity: 0 }, { transform: "translate(-50%,-18px) scale(1.15)", opacity: 1, offset: 0.35 }, { transform: "translate(-50%,-48px) scale(1)", opacity: 0 }], { duration: 580 });
    if (an) an.onfinish = () => d.remove(); else d.remove();
  }
  const shake = (el, px) => anim(el, [{ transform: "translate(0,0)" }, { transform: `translate(${-px}px,2px)` }, { transform: `translate(${px}px,-2px)` }, { transform: `translate(${-px / 2}px,1px)` }, { transform: "none" }], { duration: 320 });
  // wrap helper: fx(before, after) around orig; any failure in effects never breaks the renderer
  function wrap(key, pre, post) {
    const U = HUB.UI[key]; if (!U || U.__fx) return;
    const orig = U.apply;
    U.apply = function (s) {
      let ctx = null;
      try { ctx = pre ? pre(s, HUB.S.ui) : null; } catch (e) { ctx = null; }
      const r = orig.apply(this, arguments);
      const run = () => { try { if (post && HUB.S.ui) post(s, HUB.S.ui, ctx); } catch (e) { /* effects are optional */ } };
      if (r && typeof r.then === "function") { run(); } else run();
      return r;
    };
    U.__fx = true;
  }

  /* ---------------- DOMINOES ---------------- */
  wrap("dominoes", (s, ui) => {
    const lm = s.game.last_move;
    if (ui.fxSeq === undefined) { ui.fxSeq = lm ? lm.seq : 0; return { fresh: null }; }
    const fresh = lm && lm.seq > ui.fxSeq ? lm : null; if (fresh) ui.fxSeq = lm.seq;
    return { fresh };
  }, (s, ui, c) => {
    const g = s.game, chain = $("#dmchain"); if (!chain) return;
    const tiles = chain.querySelectorAll(".dm-t");
    const my = s.status === "playing" && g.turn === s.you && (g.can || []).length;
    if (my && tiles.length) { tiles[0].classList.add("fx-end"); tiles[tiles.length - 1].classList.add("fx-end"); }
    const lm = c && c.fresh; if (!lm) return;
    if (lm.kind === "play" && tiles.length) {
      const t = lm.end === "L" ? tiles[0] : tiles[tiles.length - 1];
      anim(t, [{ transform: "translateY(-46px) scale(1.7) rotate(-8deg)", opacity: 0, boxShadow: "0 26px 22px #000a" },
        { transform: "translateY(0) scale(.92)", opacity: 1, boxShadow: "0 1px 2px #0008", offset: 0.62 },
        { transform: "none", boxShadow: "0 2px 3px #0006" }], { duration: 360, easing: "cubic-bezier(.3,1.3,.5,1)" });
      anim(chain, [{ transform: "translateY(0)" }, { transform: "translateY(2px)", offset: 0.62 }, { transform: "none" }], { duration: 360 });
      tone(110, 0.14, "sine", 0.35, 0.2, 55); if (HUB.noise) HUB.noise(0.05, 0.25, 0.2, 700);
      setTimeout(() => { try { burstAt(t, 5, ["#f5f1e6", "#caa56a"], 26); } catch (e) { /* */ } }, 220);
    } else if (lm.kind === "draw") tone(500, 0.07, "triangle", 0.12);
  });

  /* ---------------- DOTS & BOXES ---------------- */
  wrap("dots", (s, ui) => {
    const lm = s.game.last_move;
    if (ui.fxSeq === undefined) { ui.fxSeq = lm ? lm.seq : 0; return { fresh: null }; }
    const fresh = lm && lm.seq > ui.fxSeq ? lm : null; if (fresh) ui.fxSeq = lm.seq;
    return { fresh };
  }, (s, ui, c) => {
    const lm = c && c.fresh; if (!lm) return;
    const line = $(`#gde${lm.d}${lm.r}_${lm.c}`);
    if (line) { line.classList.remove("fx-glow"); void line.getBoundingClientRect(); line.classList.add("fx-glow"); setTimeout(() => line.classList.remove("fx-glow"), 500); }
    (lm.boxes || []).forEach((b, i) => {
      const r = Array.isArray(b) ? b[0] : b.r, cc = Array.isArray(b) ? b[1] : b.c, el = $(`#gdb${r}_${cc}`); if (!el) return;
      const col = el.style.fill || "#ffd24a";
      setTimeout(() => {
        try {
          flash(col, 380); burstAt(el, 12, [col, "#fff", "#ffd24a"], 52);
          [784, 988, 1175].forEach((f, k) => tone(f + i * 90, 0.18, "triangle", 0.16, k * 0.06));
        } catch (e) { /* */ }
      }, 120 + i * 140);
    });
  });

  /* ---------------- BINGO ---------------- */
  wrap("bingo", (s, ui) => {
    const g = s.game, marks = g.card ? g.marks : [];
    if (ui.fxCall === undefined) { ui.fxCall = g.last_call ? g.last_call.seq : 0; ui.fxMarks = new Set(marks); ui.fxRev = !!g.reveal; return { call: null, added: [], rev: false }; }
    const call = g.last_call && g.last_call.seq > ui.fxCall ? g.last_call : null; if (call) ui.fxCall = call.seq;
    const added = marks.filter((n) => !ui.fxMarks.has(n)); ui.fxMarks = new Set(marks);
    const rev = !!g.reveal && !ui.fxRev; ui.fxRev = !!g.reveal;
    return { call, added, rev };
  }, (s, ui, c) => {
    if (!c) return;
    const ball = $("#gdball");
    if (c.call && ball) {
      const n = c.call.n; let i = 0;
      clearInterval(ui.fxRoll);
      if (!rm()) {
        ball.textContent = 1 + Math.floor(Math.random() * 75);
        ui.fxRoll = setInterval(() => {
          if (++i > 5 || !ball.isConnected) { clearInterval(ui.fxRoll); if (ball.isConnected) ball.textContent = n; return; }
          ball.textContent = 1 + Math.floor(Math.random() * 75); tone(400 + i * 60, 0.03, "square", 0.04);
        }, 60);
        anim(ball, [{ transform: "rotate(0) scale(1)" }, { transform: "rotate(300deg) scale(1.15)", offset: 0.6 }, { transform: "rotate(360deg) scale(1)" }], { duration: 420 });
      }
      tone(900, 0.1, "triangle", 0.12, 0.4, 600);
    }
    (c.added || []).forEach((n) => {
      const cell = document.querySelector(`#gdcard .gd-cell[data-n="${n}"]`); if (!cell) return;
      anim(cell, [{ transform: "scale(1.9) rotate(-14deg)", opacity: 0.2 }, { transform: "scale(.88) rotate(3deg)", opacity: 1, offset: 0.6 }, { transform: "none" }], { duration: 300, easing: "cubic-bezier(.3,1.3,.5,1)" });
      tone(150, 0.1, "sine", 0.3, 0, 80); if (HUB.noise) HUB.noise(0.04, 0.18, 0, 1800);
      burstAt(cell, 4, ["#ffd24a", "#fff"], 24);
    });
    if (c.rev) {
      const card = $("#gdcard"); flash("#ffd24a", 520);
      const b = card ? card.getBoundingClientRect() : { left: innerWidth / 2, top: innerHeight / 3, width: 0 };
      pop("BINGO!", b.left + b.width / 2, b.top + 20, "#ffd24a");
      [523, 659, 784, 1046].forEach((f, k) => tone(f, 0.2, "triangle", 0.2, k * 0.08));
      document.querySelectorAll("#gdcard .gd-cell.win").forEach((cell, k) => setTimeout(() => { try { burstAt(cell, 6, COLS, 40); } catch (e) { /* */ } }, k * 60));
    }
  });

  /* ---------------- HANGMAN ---------------- */
  wrap("hangman", (s, ui) => {
    const g = s.game;
    if (ui.fxWrong === undefined) { ui.fxWrong = g.wrong; ui.fxMask = g.mask.map((x) => x || "").join("|"); ui.fxRound = g.round; return null; }
    const c = { prevWrong: ui.fxWrong, prevMask: ui.fxMask.split("|"), sameRound: ui.fxRound === g.round };
    ui.fxWrong = g.wrong; ui.fxMask = g.mask.map((x) => x || "").join("|"); ui.fxRound = g.round;
    return c;
  }, (s, ui, c) => {
    if (!c || !c.sameRound) return;
    const g = s.game;
    if (g.wrong > c.prevWrong) {
      const parts = document.querySelectorAll(".gp-gal .gp-part.on");
      for (let i = c.prevWrong; i < g.wrong && i < parts.length; i++) {
        const p = parts[i]; p.classList.add("fx-part");
        anim(p, [{ transform: "scale(.1) translateY(-14px)", opacity: 0 }, { transform: "scale(1.25)", opacity: 1, offset: 0.55 }, { transform: "scale(.94)", offset: 0.8 }, { transform: "none" }], { duration: 440, easing: "ease-out" });
      }
      shake($("#gphgal"), 5); tone(120, 0.18, "sawtooth", 0.2, 0, 60);
    } else {
      const spans = document.querySelectorAll("#gphword span");
      let k = 0;
      g.mask.forEach((ch, i) => {
        if (ch && !c.prevMask[i] && spans[i]) {
          const el = spans[i];
          anim(el, [{ transform: "rotateX(90deg) scale(.6)", opacity: 0 }, { transform: "rotateX(0) scale(1.3)", opacity: 1, offset: 0.7 }, { transform: "none" }], { duration: 380, delay: k * 70, fill: "backwards" });
          tone(700 + k * 120, 0.1, "triangle", 0.12, k * 0.07); k++;
        }
      });
    }
  });

  /* ---------------- MAFIA ---------------- */
  wrap("mafia", (s, ui) => {
    const g = s.game, key = g.phase + ":" + g.day, ev = g.last_event, tally = {};
    Object.values(g.votes || {}).forEach((t) => { tally[t] = (tally[t] || 0) + 1; });
    if (ui.fxKey === undefined) { ui.fxKey = key; ui.fxEv = ev ? ev.seq : 0; ui.fxTally = tally; return null; }
    const c = { phase: key !== ui.fxKey ? g.phase : null, ev: ev && ev.seq > ui.fxEv ? ev : null, prev: ui.fxTally, tally };
    ui.fxKey = key; if (ev) ui.fxEv = ev.seq; ui.fxTally = tally;
    return c;
  }, (s, ui, c) => {
    if (!c) return;
    if (c.phase && s.status === "playing") {
      const sym = c.phase === "night" ? "🌙" : c.phase === "day" ? "☀️" : "⚖️";
      const d = document.createElement("div"); d.className = "fxsweep " + c.phase; d.textContent = sym;
      document.body.appendChild(d);
      const an = anim(d, [{ transform: "translate(-30vw,40vh) scale(.6)", opacity: 0 }, { transform: "translate(0,-8vh) scale(1.5)", opacity: 1, offset: 0.5 }, { transform: "translate(30vw,40vh) scale(.6)", opacity: 0 }], { duration: 580, easing: "ease-in-out" });
      flash(c.phase === "night" ? "#0a1030" : c.phase === "day" ? "#ffd27a" : "#8a5cf6", 560);
      if (an) an.onfinish = () => d.remove(); else d.remove();
    }
    if (c.ev && (c.ev.killed || c.ev.eliminated)) {
      const uid = c.ev.killed || c.ev.eliminated;
      flash("#7a0a0a", 520); tone(90, 0.5, "sawtooth", 0.2, 0.05, 40);
      const t = document.querySelector(`.gp-tile[data-uid="${uid}"]`); if (t) { shake(t, 4); burstAt(t, 8, ["#ff5a5a", "#555", "#222"], 40); }
    }
    const pulse = () => {
      if (HUB.S.ui !== ui) return;
      Object.keys(c.tally).forEach((u) => {
        if (c.tally[u] !== (c.prev[u] || 0)) {
          const v = document.querySelector(`.gp-tile[data-uid="${u}"] .gp-votes`);
          if (v) { anim(v, [{ transform: "scale(1)" }, { transform: "scale(1.8)", offset: 0.4 }, { transform: "scale(1)" }], { duration: 360, easing: "cubic-bezier(.3,1.5,.5,1)" }); tone(500 + c.tally[u] * 90, 0.08, "square", 0.08); }
        }
      });
    };
    pulse(); setTimeout(pulse, 450);
  });

  /* ---------------- TRIVIA ---------------- */
  wrap("trivia", (s, ui) => {
    const rv = s.game.reveal;
    if (ui.fxRv === undefined) { ui.fxRv = rv ? rv.seq : 0; ui.fxStreak = 0; return null; }
    const fresh = rv && rv.seq > ui.fxRv ? rv : null; if (fresh) ui.fxRv = rv.seq;
    return { fresh };
  }, (s, ui, c) => {
    const rv = c && c.fresh; if (!rv || !s.game.players.some((p) => p.uid === s.you)) return;
    const mine = rv.gained[String(s.you)], box = document.querySelector(".gp-trv");
    ui.fxStreak = mine ? (ui.fxStreak || 0) + 1 : 0;
    if (mine) {
      flash("#22c55e", 420); burstAt(document.querySelector(".gp-opt.right"), 14, ["#4ade80", "#ffd24a", "#fff"], 60);
      if (ui.fxStreak >= 2) {
        const b = box ? box.getBoundingClientRect() : { left: innerWidth / 2, top: 200, width: 0 };
        pop("🔥 x" + ui.fxStreak, b.left + b.width / 2, b.top + 60, "#ff9d2e");
        [880, 1100, 1320].forEach((f, k) => tone(f, 0.14, "triangle", 0.14, 0.1 + k * 0.07));
      }
    } else { flash("#ef4444", 420); shake(box, 6); }
  });

  /* ---------------- SCRIBBLE (polish only) ---------------- */
  wrap("scribble", (s, ui) => {
    const g = s.game, key = (g.turn_no || 0) + ":" + (g.word || g.len);
    if (ui.fxG === undefined) { ui.fxG = g.guessed.length; ui.fxWord = key; return { first: true }; }
    const c = { newG: g.guessed.length > ui.fxG ? g.guessed.length - ui.fxG : 0, word: key !== ui.fxWord, turnChanged: false, fresh: g.guessed.slice(ui.fxG) };
    ui.fxG = g.guessed.length; ui.fxWord = key;
    return c;
  }, (s, ui, c) => {
    const g = s.game;
    if (!ui.fxTm && $("#sctime")) {
      ui.fxTm = setInterval(() => {
        try {
          const el = $("#sctime");
          if (!el || HUB.S.ui !== ui) { clearInterval(ui.fxTm); return; }
          const left = Math.ceil(ui.left - (Date.now() - ui.t0) / 1000), urg = s.status === "playing" && left <= 10 && left > 0;
          if (urg !== el.classList.contains("fx-urgent")) el.classList.toggle("fx-urgent", urg);
          if (urg && ui.fxTick !== left) { ui.fxTick = left; tone(left <= 3 ? 1300 : 900, 0.04, "square", left <= 3 ? 0.1 : 0.05); }
        } catch (e) { /* */ }
      }, 250);
    }
    if (!c || c.first) return;
    if (c.newG > 0) {
      const cv = $("#sccv"), b = cv ? cv.getBoundingClientRect() : { left: innerWidth / 2, top: 200, width: 0, height: 0 };
      burst(b.left + b.width / 2, b.top + b.height / 2, 22, COLS, 90);
      pop("✅ Correct!", b.left + b.width / 2, b.top + b.height / 3, "#4ade80");
      [660, 880, 1100].forEach((f, k) => tone(f, 0.14, "triangle", 0.16, k * 0.07));
    }
    if (c.word) {
      const w = $("#scword"); if (!w || rm()) return;
      const txt = w.textContent; w.textContent = "";
      Array.from(txt).forEach((ch, i) => {
        const sp = document.createElement("span"); sp.className = "fxl"; sp.textContent = ch; w.appendChild(sp);
        if (ch.trim()) anim(sp, [{ transform: "translateY(-12px) rotateX(90deg)", opacity: 0 }, { transform: "translateY(0) scale(1.25)", opacity: 1, offset: 0.7 }, { transform: "none" }], { duration: 300, delay: Math.min(i * 35, 260), fill: "backwards" });
      });
      tone(520, 0.08, "sine", 0.08);
    }
  });
})();

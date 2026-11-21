/* Renderers for Chess, Checkers, Reversi, Gomoku, Ultimate Tic-Tac-Toe and Battleship.
   Each registers { build(state), apply(state) } in HUB.UI. Spectators (state.you not a player) get a read-only view. */
(function () {
  "use strict";
  window.HUB = window.HUB || { UI: {} };
  const HUB = window.HUB;
  const $ = (s, r) => (r || document).querySelector(s);
  const K = () => HUB.kit;
  const isPlayer = (s) => s.game.players.some((p) => p.uid === s.you);
  const myTurn = (s) => s.status === "playing" && s.game.turn === s.you;
  const seatOf = (s, uid) => s.game.players.findIndex((p) => p.uid === uid);

  function newBoardUI(type, s, body, extra) {
    const ui = K().newUI(type, s, Object.assign({ lastSeq: 0, sel: null, cells: [] }, extra));
    K().shell(s, body);
    return ui;
  }
  function slide(ui, from, to, ms) {
    const a = ui.cells[from], b = ui.cells[to];
    if (!a || !b) return;
    const pc = b.querySelector(".gb-pc");
    if (!pc || !pc.animate) return;
    const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    pc.style.zIndex = 5;
    pc.animate([{ transform: `translate(${ra.left - rb.left}px,${ra.top - rb.top}px)` }, { transform: "none" }],
      { duration: ms || 230, easing: "cubic-bezier(.2,.8,.3,1)" }).onfinish = () => { pc.style.zIndex = ""; };
  }
  /* chess: arc-lift slide, captured piece bursts away, castling rook, check shake, promotion sparkle */
  function chessSlide(ui, from, to, ms, big) {
    const a = ui.cells[from], b = ui.cells[to];
    const pc = b && b.querySelector(".gb-pc");
    if (!a || !pc || !pc.animate) return;
    const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    const dx = ra.left - rb.left, dy = ra.top - rb.top, dist = Math.hypot(dx, dy) / rb.width;
    pc.style.zIndex = 6;
    const lift = big ? 1.28 : 1.18;
    pc.animate([
      { transform: `translate(${dx}px,${dy}px) scale(1)`, filter: "drop-shadow(0 0 0 #0000)" },
      { transform: `translate(${dx * 0.5}px,${dy * 0.5}px) scale(${lift})`, filter: "drop-shadow(0 8px 6px #0007)", offset: 0.55 },
      { transform: "translate(0,0) scale(1.06)", offset: 0.88 },
      { transform: "none", filter: "drop-shadow(0 0 0 #0000)" },
    ], { duration: ms || Math.min(520, 220 + dist * 55), easing: "cubic-bezier(.3,.7,.25,1)" }).onfinish = () => { pc.style.zIndex = ""; };
  }
  function burst(cell, glyph, white) {
    if (!cell || !cell.animate) return;
    const g = document.createElement("span");
    g.className = "gb-ghost " + (white ? "w" : "b"); g.textContent = glyph || "";
    cell.appendChild(g);
    g.animate([{ transform: "scale(1) rotate(0)", opacity: 1 }, { transform: "scale(1.5) rotate(25deg)", opacity: 0.8, offset: 0.35 }, { transform: "scale(.2) rotate(80deg)", opacity: 0 }],
      { duration: 480, easing: "ease-out" }).onfinish = () => g.remove();
    for (let i = 0; i < 9; i++) {
      const d = document.createElement("i"), ang = (i / 9) * Math.PI * 2 + Math.random(), r = 26 + Math.random() * 22;
      d.className = "gb-spark"; cell.appendChild(d);
      d.animate([{ transform: "translate(-50%,-50%) scale(1)", opacity: 1 }, { transform: `translate(calc(-50% + ${Math.cos(ang) * r}px),calc(-50% + ${Math.sin(ang) * r}px)) scale(.1)`, opacity: 0 }],
        { duration: 420 + Math.random() * 200, easing: "ease-out" }).onfinish = () => d.remove();
    }
  }
  function shake(el) {
    if (el && el.animate) el.animate([{ transform: "translateX(0)" }, { transform: "translateX(-4px)" }, { transform: "translateX(4px)" }, { transform: "translateX(-3px)" }, { transform: "translateX(2px)" }, { transform: "none" }], { duration: 420 });
  }
  function pop(el) {
    if (el && el.animate) el.animate([{ transform: "scale(.2)", opacity: 0 }, { transform: "scale(1.15)", opacity: 1 }, { transform: "none" }], { duration: 260, easing: "ease-out" });
  }
  function fresh(ui, g) {           // is last_move a move we haven't animated yet?
    const m = g.last_move;
    if (!m || m.seq <= ui.lastSeq) return false;
    const was = ui.first;
    ui.lastSeq = m.seq;
    return !was;
  }
  function finish(s, ui) {
    K().turnFx(ui, s);
  }
  const scoreInfo = (f) => (uid) => f(uid);

  /* ======================= CHESS ======================= */
  const GL = { K: "♚", Q: "♛", R: "♜", B: "♝", N: "♞", P: "♟", k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟" };
  const CHESS_FILES = "abcdefgh";
  function boardGrid(cls, n) {
    let h = `<div class="gb-board ${cls}" id="gbb">`;
    for (let i = 0; i < n; i++) h += `<div class="gb-sq" data-i="${i}"></div>`;
    return h + "</div>";
  }
  function buildChess(s) {
    const me = s.game.players.findIndex((p) => p.uid === s.you);
    const ui = newBoardUI("chess", s, `<div class="gb-wrap"><div class="gb-cap" id="gbtop"></div>${boardGrid("gb-chess", 64)}<div class="gb-cap" id="gbbot"></div></div><div class="gb-modal hidden" id="gbpromo"></div>`, { flip: me === 1 });
    ui.cells = [];
    document.querySelectorAll("#gbb .gb-sq").forEach((el, d) => {
      const sq = ui.flip ? 63 - d : d;
      el.dataset.sq = sq; ui.cells[sq] = el;
      const r = Math.floor(sq / 8), c = sq % 8;
      el.classList.add((r + c) % 2 ? "dk" : "lt");
      if (c === (ui.flip ? 7 : 0)) el.insertAdjacentHTML("beforeend", `<i class="gb-co r">${8 - r}</i>`);
      if (r === (ui.flip ? 0 : 7)) el.insertAdjacentHTML("beforeend", `<i class="gb-co f">${CHESS_FILES[c]}</i>`);
    });
    $("#gbb").addEventListener("click", (e) => {
      const el = e.target.closest(".gb-sq"); if (!el) return;
      chessClick(S(), ui, +el.dataset.sq);
    });
  }
  const S = () => HUB.S.room;
  function chessClick(s, ui, sq) {
    const g = s.game;
    if (!myTurn(s)) return;
    const legal = g.legal || {};
    const mine = (p) => p !== "." && (g.side === "w" ? p === p.toUpperCase() : p === p.toLowerCase());
    if (ui.sel != null && (legal[ui.sel] || []).includes(sq)) {
      const piece = g.board[ui.sel], toRow = Math.floor(sq / 8);
      if (piece.toLowerCase() === "p" && (toRow === 0 || toRow === 7)) { askPromo(s, ui, ui.sel, sq); return; }
      HUB.send({ t: "move", from: ui.sel, to: sq }); ui.sel = null; HUB.haptic(); paintChess(s, ui);
      return;
    }
    ui.sel = mine(g.board[sq]) && legal[sq] ? sq : null;
    if (ui.sel != null) HUB.sfx.pop();
    paintChess(s, ui);
  }
  function askPromo(s, ui, f, t) {
    const box = $("#gbpromo"), white = s.game.side === "w";
    box.innerHTML = '<div class="gb-pbox"><b>Promote to</b><div>' + ["q", "r", "b", "n"].map((p) => `<button class="gb-pbtn ${white ? "w" : "b"}" data-p="${p}">${GL[p]}</button>`).join("") + "</div></div>";
    box.classList.remove("hidden");
    box.onclick = (e) => {
      const b = e.target.closest(".gb-pbtn");
      if (!b) { box.classList.add("hidden"); return; }
      box.classList.add("hidden");
      HUB.send({ t: "move", from: f, to: t, promo: b.dataset.p }); ui.sel = null; HUB.haptic();
    };
  }
  function paintChess(s, ui) {
    const g = s.game, lm = g.last_move, legal = g.legal || {};
    const targets = ui.sel != null ? legal[ui.sel] || [] : [];
    for (let sq = 0; sq < 64; sq++) {
      const el = ui.cells[sq], p = g.board[sq];
      let cls = "gb-sq " + ((Math.floor(sq / 8) + sq % 8) % 2 ? "dk" : "lt");
      if (lm && (lm.from === sq || lm.to === sq)) cls += " last";
      if (ui.sel === sq) cls += " sel";
      if (g.in_check === sq) cls += " chk";
      if (targets.includes(sq)) cls += p !== "." ? " cap" : " tgt";
      el.className = cls;
      const co = [...el.querySelectorAll(".gb-co")].map((x) => x.outerHTML).join("");
      el.innerHTML = co + (p !== "." ? `<span class="gb-pc ${p === p.toUpperCase() ? "w" : "b"}">${GL[p]}</span>` : "");
    }
  }
  const PV = { p: 1, n: 3, b: 3, r: 5, q: 9 };
  function chessCaps(g, side) {
    const list = (g.captured[side] || []).slice().sort((a, b) => PV[b.toLowerCase()] - PV[a.toLowerCase()]);
    return list.map((p) => GL[p]).join("");
  }
  function applyChess(s) {
    const ui = HUB.S.ui, g = s.game;
    const isNew = fresh(ui, g);
    if (ui.sel != null && (!myTurn(s) || !g.legal[ui.sel])) ui.sel = null;
    paintChess(s, ui);
    const lm = g.last_move;
    if (isNew && lm) {
      chessSlide(ui, lm.from, lm.to, 0, lm.capture);
      if (lm.castle) {                                   // the rook hops over the king
        const row = Math.floor(lm.to / 8), short = lm.to % 8 === 6;
        chessSlide(ui, row * 8 + (short ? 7 : 0), row * 8 + (short ? 5 : 3), 360);
      }
      if (lm.capture) {
        const cap = typeof lm.capture === "string" && lm.capture !== "." ? lm.capture : (lm.piece ? (lm.piece === lm.piece.toUpperCase() ? "p" : "P") : "P");
        const victimSq = lm.ep ? Math.floor(lm.from / 8) * 8 + lm.to % 8 : lm.to;
        setTimeout(() => burst(ui.cells[victimSq], GL[cap], cap === cap.toUpperCase()), 170);
        HUB.sfx.capture(); HUB.haptic("heavy");
      } else HUB.sfx.place();
      if (lm.castle) setTimeout(() => HUB.sfx.place(), 130);
      if (lm.promo) { setTimeout(() => { HUB.sfx.good(); pop(ui.cells[lm.to] && ui.cells[lm.to].querySelector(".gb-pc")); burst(ui.cells[lm.to], "✦", true); }, 260); }
      if (lm.check && !s.game.winner) setTimeout(() => {
        HUB.tone(880, 0.12, "square", 0.18); HUB.tone(660, 0.18, "square", 0.18, 0.12);
        const k = ui.cells[g.in_check]; if (k) { shake(k); k.classList.add("chkflash"); setTimeout(() => k.classList.remove("chkflash"), 900); }
      }, 260);
      if (g.reason === "checkmate" || (s.status === "finished" && lm.check)) setTimeout(() => {
        const k = ui.cells[g.in_check]; const pc = k && k.querySelector(".gb-pc");
        if (pc && pc.animate) pc.animate([{ transform: "none" }, { transform: "rotate(90deg) translateY(6px)" }], { duration: 600, fill: "forwards", easing: "ease-in" });
        HUB.sfx.bad && HUB.sfx.bad();
      }, 500);
    }
    const col = (uid) => (g.players.find((p) => p.uid === uid) || {}).color;
    K().updateBar(ui, s, (uid) => ({ score: chessCaps(g, col(uid)), sub: col(uid) === "w" ? "⚪ White" : "⚫ Black" }));
    const sanLine = lm ? `Last: ${lm.san || ""}` : "";
    K().setHint(!isPlayer(s) ? "👁 Watching · " + sanLine : myTurn(s) ? (g.in_check === ui.sel || g.legal && g.in_check != null ? "⚠️ Check! Your move" : "👉 Your move") : K().turnHint(s));
    finish(s, ui);
  }

  /* ======================= CHECKERS ======================= */
  function buildCheckers(s) {
    const me = seatOf(s, s.you);
    const ui = newBoardUI("checkers", s, `<div class="gb-wrap">${boardGrid("gb-chk", 64)}</div>`, { flip: me === 1 });
    document.querySelectorAll("#gbb .gb-sq").forEach((el, d) => {
      const sq = ui.flip ? 63 - d : d;
      el.dataset.sq = sq; ui.cells[sq] = el;
    });
    $("#gbb").addEventListener("click", (e) => {
      const el = e.target.closest(".gb-sq"); if (!el) return;
      const s2 = S(), g = s2.game, sq = +el.dataset.sq;
      if (!myTurn(s2)) return;
      if (ui.sel != null) {
        const path = (g.legal[ui.sel] || []).find((p) => p[p.length - 1] === sq);
        if (path) { HUB.send({ t: "move", path }); ui.sel = null; HUB.haptic(); return; }
      }
      if (g.legal[sq]) { ui.sel = sq; HUB.sfx.pop(); paintCheckers(s2, ui); } else { ui.sel = null; paintCheckers(s2, ui); }
    });
  }
  function paintCheckers(s, ui) {
    const g = s.game, lm = g.last_move;
    const tg = ui.sel != null ? (g.legal[ui.sel] || []).map((p) => p[p.length - 1]) : [];
    const movable = myTurn(s) ? Object.keys(g.legal).map(Number) : [];
    for (let sq = 0; sq < 64; sq++) {
      const el = ui.cells[sq], p = g.board[sq], r = Math.floor(sq / 8), c = sq % 8;
      let cls = "gb-sq " + ((r + c) % 2 ? "dk" : "lt");
      if (lm && (lm.path[0] === sq || lm.path[lm.path.length - 1] === sq)) cls += " last";
      if (ui.sel === sq) cls += " sel";
      if (tg.includes(sq)) cls += " tgt";
      el.className = cls;
      const king = p && p === p.toUpperCase();
      el.innerHTML = p ? `<span class="gb-pc gb-disc ${p.toLowerCase() === "w" ? "cw" : "cb"} ${king ? "king" : ""} ${movable.includes(sq) ? "can" : ""}">${king ? "♛" : ""}</span>` : "";
    }
  }
  function applyCheckers(s) {
    const ui = HUB.S.ui, g = s.game, isNew = fresh(ui, g);
    if (ui.sel != null && (!myTurn(s) || !g.legal[ui.sel])) ui.sel = null;
    paintCheckers(s, ui);
    const lm = g.last_move;
    if (isNew && lm) {
      slide(ui, lm.path[0], lm.path[lm.path.length - 1], 260);
      if (lm.captured && lm.captured.length) { HUB.sfx.capture(); HUB.haptic("heavy"); } else HUB.sfx.place();
      if (lm.crowned) setTimeout(() => HUB.sfx.good(), 150);
    }
    const col = (uid) => (g.players.find((p) => p.uid === uid) || {}).color;
    K().updateBar(ui, s, (uid) => ({ score: "● " + g.counts[col(uid)], sub: col(uid) === "w" ? "⚪ White" : "⚫ Black" }));
    K().setHint(!isPlayer(s) ? "👁 Watching" : myTurn(s) ? (g.must_capture ? "⚠️ You must capture" : "👉 Your move") : K().turnHint(s));
    finish(s, ui);
  }

  /* ======================= REVERSI ======================= */
  function buildReversi(s) {
    const ui = newBoardUI("reversi", s, `<div class="gb-wrap">${boardGrid("gb-rev", 64)}</div>`, {});
    document.querySelectorAll("#gbb .gb-sq").forEach((el, i) => { el.dataset.sq = i; ui.cells[i] = el; });
    $("#gbb").addEventListener("click", (e) => {
      const el = e.target.closest(".gb-sq"); if (!el) return;
      const s2 = S();
      if (myTurn(s2) && s2.game.legal.includes(+el.dataset.sq)) { HUB.send({ t: "place", cell: +el.dataset.sq }); HUB.haptic(); }
    });
  }
  function applyReversi(s) {
    const ui = HUB.S.ui, g = s.game, isNew = fresh(ui, g), lm = g.last_move;
    const legal = myTurn(s) ? g.legal : [];
    for (let i = 0; i < 64; i++) {
      const el = ui.cells[i], v = g.board[i];
      el.className = "gb-sq rv" + (lm && lm.cell === i ? " last" : "") + (legal.includes(i) ? " tgt" : "");
      el.innerHTML = v == null ? "" : `<span class="gb-pc gb-disc ${v === 0 ? "cb" : "cw"}"></span>`;
    }
    if (isNew && lm) {
      pop(ui.cells[lm.cell].firstElementChild);
      (lm.flips || []).forEach((f, k) => {
        const pc = ui.cells[f] && ui.cells[f].firstElementChild;
        if (pc && pc.animate) pc.animate([{ transform: "rotateY(0) scale(1)" }, { transform: "rotateY(90deg) scale(1.1)" }, { transform: "rotateY(180deg)" }, { transform: "none" }], { duration: 420, delay: 60 + k * 45, easing: "ease-in-out", fill: "backwards" });
        setTimeout(() => HUB.sfx.flip(), 60 + k * 45);
      });
      HUB.sfx.place(); HUB.haptic();
      if (lm.passed) HUB.toast("Pass: no legal move for " + K().nameOf(s, lm.passed === true ? g.turn : lm.passed));
    }
    K().updateBar(ui, s, (uid) => ({ score: g.counts[seatOf(s, uid) === 0 ? 0 : 1], sub: seatOf(s, uid) === 0 ? "⚫ Black" : "⚪ White" }));
    K().setHint(!isPlayer(s) ? "👁 Watching" : myTurn(s) ? "👉 Place a disc on a dotted square" : K().turnHint(s));
    finish(s, ui);
  }

  /* ======================= GOMOKU ======================= */
  function buildGomoku(s) {
    const n = s.game.size;
    let h = `<div class="gb-wrap"><div class="gb-gomoku" id="gbb" style="--n:${n}">`;
    for (let i = 0; i < n * n; i++) h += `<div class="gb-gp" data-i="${i}"></div>`;
    const ui = newBoardUI("gomoku", s, h + "</div></div>", { n });
    document.querySelectorAll("#gbb .gb-gp").forEach((el, i) => { ui.cells[i] = el; });
    $("#gbb").addEventListener("click", (e) => {
      const el = e.target.closest(".gb-gp"); if (!el) return;
      const s2 = S();
      if (myTurn(s2) && s2.game.board[+el.dataset.i] == null) { HUB.send({ t: "place", cell: +el.dataset.i }); HUB.haptic(); }
    });
  }
  function applyGomoku(s) {
    const ui = HUB.S.ui, g = s.game, isNew = fresh(ui, g), lm = g.last_move;
    const line = g.line || [];
    for (let i = 0; i < g.board.length; i++) {
      const el = ui.cells[i], v = g.board[i];
      const had = el.dataset.v;
      el.dataset.v = v == null ? "" : v;
      el.className = "gb-gp" + (myTurn(s) && v == null ? " can" : "") + (line.includes(i) ? " win" : "") + (lm && lm.cell === i ? " last" : "");
      el.innerHTML = v == null ? "" : `<span class="gb-stone ${v === 0 ? "cb" : "cw"}"></span>`;
      if (v != null && had === "" && isNew) pop(el.firstElementChild);
    }
    if (isNew) { HUB.sfx.place(); HUB.haptic(); }
    K().updateBar(ui, s, (uid) => ({ score: "", sub: seatOf(s, uid) === 0 ? "⚫ Black" : "⚪ White" }));
    K().setHint(!isPlayer(s) ? "👁 Watching" : myTurn(s) ? "👉 Get five in a row" : K().turnHint(s));
    finish(s, ui);
  }

  /* ======================= ULTIMATE TIC-TAC-TOE ======================= */
  function buildUttt(s) {
    let h = '<div class="gb-wrap"><div class="gb-ut" id="gbb">';
    for (let b = 0; b < 9; b++) {
      h += `<div class="gb-ub" data-b="${b}">`;
      for (let p = 0; p < 9; p++) h += `<button class="gb-uc" data-i="${b * 9 + p}"></button>`;
      h += '<div class="gb-uw"></div></div>';
    }
    const ui = newBoardUI("uttt", s, h + "</div></div>", {});
    document.querySelectorAll("#gbb .gb-uc").forEach((el) => { ui.cells[+el.dataset.i] = el; });
    $("#gbb").addEventListener("click", (e) => {
      const el = e.target.closest(".gb-uc"); if (!el) return;
      const s2 = S();
      if (myTurn(s2) && s2.game.legal.includes(+el.dataset.i)) { HUB.send({ t: "place", cell: +el.dataset.i }); HUB.haptic(); }
    });
  }
  const MK = ["X", "O"];
  function applyUttt(s) {
    const ui = HUB.S.ui, g = s.game, isNew = fresh(ui, g), lm = g.last_move;
    const legal = myTurn(s) ? g.legal : [];
    for (let i = 0; i < 81; i++) {
      const el = ui.cells[i], v = g.cells[i];
      const had = el.dataset.v;
      el.dataset.v = v == null ? "" : v;
      el.textContent = v == null ? "" : MK[v];
      el.className = "gb-uc" + (v != null ? " m" + v : "") + (legal.includes(i) ? " can" : "") + (lm && lm.cell === i ? " last" : "");
      if (v != null && had === "" && isNew) pop(el);
    }
    document.querySelectorAll("#gbb .gb-ub").forEach((bd) => {
      const b = +bd.dataset.b, w = g.boards[b], act = g.active === b || (g.active < 0 && w == null);
      bd.className = "gb-ub" + (act && s.status === "playing" ? " act" : "") + (w != null ? " done w" + w : "");
      bd.querySelector(".gb-uw").textContent = w == null ? "" : w === 2 ? "–" : MK[w];
    });
    if (isNew) { HUB.sfx.place(); HUB.haptic(); if (lm && lm.won_board) setTimeout(() => HUB.sfx.good(), 120); }
    K().updateBar(ui, s, (uid) => ({ score: MK[seatOf(s, uid)] || "", sub: g.boards.filter((b) => b === seatOf(s, uid)).length + " boards" }));
    K().setHint(!isPlayer(s) ? "👁 Watching" : myTurn(s) ? (g.active >= 0 ? "👉 Play in the glowing board" : "👉 Play in any open board") : K().turnHint(s));
    finish(s, ui);
  }

  /* ======================= BATTLESHIP ======================= */
  function waterGrid(id, n) {
    let h = `<div class="gb-water" id="${id}" style="--n:${n}">`;
    for (let i = 0; i < n * n; i++) h += `<div class="gb-wc" data-i="${i}"></div>`;
    return h + "</div>";
  }
  function buildBattleship(s) {
    const n = s.game.size;
    const ui = newBoardUI("battleship", s, `<div class="gb-wrap"><div class="gb-cap" id="gbt">Enemy waters</div>${waterGrid("gbe", n)}<div class="gb-cap" id="gbm">Your fleet</div>${waterGrid("gbf", n)}</div>`, { n });
    ui.en = [...document.querySelectorAll("#gbe .gb-wc")];
    ui.fl = [...document.querySelectorAll("#gbf .gb-wc")];
    $("#gbe").addEventListener("click", (e) => {
      const el = e.target.closest(".gb-wc"); if (!el) return;
      const s2 = S(), i = +el.dataset.i, w = foeWaters(s2);
      if (myTurn(s2) && w && !(String(i) in w.shots)) { HUB.send({ t: "fire", cell: i }); HUB.haptic(); }
    });
  }
  function foeUid(s) {
    const ps = s.game.players.map((p) => p.uid);
    return isPlayer(s) ? ps.find((u) => u !== s.you) : ps[1];
  }
  const foeWaters = (s) => s.game.waters[String(foeUid(s))];
  const ownUid = (s) => (isPlayer(s) ? s.you : s.game.players[0].uid);
  function paintWater(cells, w, showShips, canFire) {
    const sunk = new Set(); w.sunk.forEach((sh) => sh.cells.forEach((c) => sunk.add(c)));
    const ships = new Set(); (w.ships || []).forEach((sh) => sh.cells.forEach((c) => ships.add(c)));
    cells.forEach((el, i) => {
      const r = w.shots[String(i)];
      let cls = "gb-wc";
      if (showShips && ships.has(i)) cls += " ship";
      if (sunk.has(i)) cls += " sunk";
      if (r) cls += " " + r;
      if (!r && canFire) cls += " can";
      el.className = cls;
      el.textContent = r === "hit" ? "💥" : r === "miss" ? "•" : "";
    });
  }
  function applyBattleship(s) {
    const ui = HUB.S.ui, g = s.game, isNew = fresh(ui, g), lm = g.last_move;
    const fw = foeWaters(s), ow = g.waters[String(ownUid(s))];
    paintWater(ui.en, fw, !!(fw.ships), myTurn(s));
    paintWater(ui.fl, ow, true, false);
    if (isNew && lm) {
      const cells = lm.target === foeUid(s) ? ui.en : ui.fl;
      pop(cells[lm.cell]);
      if (lm.sunk) { HUB.sfx.capture(); HUB.haptic("heavy"); HUB.toast("💥 " + (lm.sunk.name || lm.sunk) + " sunk!"); }
      else if (lm.hit) { HUB.sfx.hit(); HUB.haptic("medium"); } else HUB.sfx.miss();
    }
    $("#gbt").textContent = isPlayer(s) ? "Enemy waters · ships left " + fw.left : "Player 2 waters · ships left " + fw.left;
    $("#gbm").textContent = isPlayer(s) ? "Your fleet · ships left " + ow.left : "Player 1 waters · ships left " + ow.left;
    K().updateBar(ui, s, (uid) => ({ score: g.waters[String(uid)].left + "🚢" }));
    K().setHint(!isPlayer(s) ? "👁 Watching" : myTurn(s) ? "🎯 Tap enemy waters to fire" : K().turnHint(s));
    finish(s, ui);
  }

  HUB.UI.chess = { build: buildChess, apply: applyChess };
  HUB.UI.checkers = { build: buildCheckers, apply: applyCheckers };
  HUB.UI.reversi = { build: buildReversi, apply: applyReversi };
  HUB.UI.gomoku = { build: buildGomoku, apply: applyGomoku };
  HUB.UI.uttt = { build: buildUttt, apply: applyUttt };
  HUB.UI.battleship = { build: buildBattleship, apply: applyBattleship };
})();

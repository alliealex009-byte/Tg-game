/* Renderers for Snakes & Ladders, Connect Four, Rock-Paper-Scissors, Memory Match and Carrom.
   Each registers { build(state), apply(state) } in HUB.UI; app.js provides the shared helpers on HUB. */
(function () {
  "use strict";
  window.HUB = window.HUB || { UI: {} };
  const HUB = window.HUB;
  const $ = (s, r) => (r || document).querySelector(s);
  const PCOL = ["#ea4335", "#00a14b", "#fbbc05", "#4285f4"];

  /* ---------- shared pieces ---------- */
  function bar(g) {
    return '<div class="pbar">' + g.players.map((p, i) =>
      `<div class="pchip" data-uid="${p.uid}" style="--pc:${PCOL[i % 4]}"><div class="ring"><div class="avatar"></div></div>` +
      '<div class="pi"><div class="tag name"></div><div class="sub"></div></div><div class="score"></div></div>').join("") + "</div>";
  }
  function updateBar(ui, s, info) {
    const by = {};
    s.players.forEach((p) => { by[p.uid] = p; });
    ui.rings = {};
    document.querySelectorAll("#screen-game .pchip").forEach((el) => {
      const uid = +el.dataset.uid, rp = by[uid] || {};
      el.classList.toggle("turn", s.status === "playing" && s.game.turn === uid);
      el.classList.toggle("left", !!rp.left);
      const av = el.querySelector(".avatar"), key = uid + "|" + (rp.photo || "");
      if (av.dataset.k !== key) { av.innerHTML = HUB.avatarInner(rp); av.dataset.k = key; }
      const nm = el.querySelector(".name");
      nm.textContent = rp.name || HUB.handle(rp);
      nm.classList.toggle("you", uid === s.you);
      const i = (info && info(uid, rp)) || {};
      el.querySelector(".sub").textContent = i.sub != null ? i.sub : (rp.is_bot ? "Computer" : "💰 " + rp.coins) + (rp.afk ? " · AFK" : "");
      el.querySelector(".score").textContent = i.score != null ? i.score : "";
      ui.rings[uid] = el.querySelector(".ring");
    });
  }
  function nameOf(s, uid) { const p = s.players.find((x) => x.uid === uid); return p ? p.name : "Player"; }
  function setHint(text) { const h = $("#hint"); if (h) h.textContent = text || ""; }
  function turnHint(s) {
    if (s.status !== "playing") return "";
    return s.game.turn === s.you ? "👉 Your turn" : "Waiting for " + nameOf(s, s.game.turn) + "…";
  }
  function turnFx(ui, s) {
    if (s.status === "playing" && s.game.turn === s.you && ui.prevTurn !== s.you) { HUB.sfx.turn(); HUB.haptic(); }
    ui.prevTurn = s.game.turn;
  }
  function shell(s, body) {
    $("#screen-game").innerHTML = HUB.topbarHTML(s.code) + `<div class="gstage">${bar(s.game)}${body}<div class="hint" id="hint"></div></div>`;
  }
  function newUI(type, s, extra) {
    return (HUB.S.ui = Object.assign({ type, code: s.code, rings: {}, deadline: null, turnSeconds: s.turn_seconds, first: true, prevTurn: null, resultShown: false }, extra));
  }
  const iAmPlaying = (s) => s.game.players.some((p) => p.uid === s.you);

  /* =====================================================================
     SNAKES & LADDERS
     ===================================================================== */
  const slPoint = (n) => {
    const r = Math.floor((n - 1) / 10), c = r % 2 === 0 ? (n - 1) % 10 : 9 - ((n - 1) % 10);
    return [c * 10 + 5, (9 - r) * 10 + 5];
  };
  function ladderSVG(from, to) {
    const a = slPoint(from), b = slPoint(to);
    const dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy), ux = dx / len, uy = dy / len;
    const nx = -uy * 1.5, ny = ux * 1.5;
    let h = `<line x1="${a[0] + nx}" y1="${a[1] + ny}" x2="${b[0] + nx}" y2="${b[1] + ny}" stroke="#7a4a1d" stroke-width="0.95" stroke-linecap="round"/>` +
      `<line x1="${a[0] - nx}" y1="${a[1] - ny}" x2="${b[0] - nx}" y2="${b[1] - ny}" stroke="#7a4a1d" stroke-width="0.95" stroke-linecap="round"/>`;
    for (let t = 3; t < len - 1.5; t += 4.4) {
      const px = a[0] + ux * t, py = a[1] + uy * t;
      h += `<line x1="${px + nx}" y1="${py + ny}" x2="${px - nx}" y2="${py - ny}" stroke="#a8692b" stroke-width="0.7" stroke-linecap="round"/>`;
    }
    return h;
  }
  const SNAKE_COL = ["#2e9d4f", "#c0392b", "#8e44ad", "#e67e22", "#16a085", "#d35400", "#2980b9", "#c2185b", "#6d8f1f", "#7f5539"];
  function snakeSVG(from, to, i) {
    const a = slPoint(from), b = slPoint(to);   // head at the high square
    const dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1;
    const nx = -dy / len * Math.min(9, len * 0.28), ny = dx / len * Math.min(9, len * 0.28);
    const d = `M${a[0]} ${a[1]} C${a[0] + dx * 0.33 + nx} ${a[1] + dy * 0.33 + ny} ${a[0] + dx * 0.66 - nx} ${a[1] + dy * 0.66 - ny} ${b[0]} ${b[1]}`;
    const col = SNAKE_COL[i % SNAKE_COL.length];
    return `<path d="${d}" fill="none" stroke="${col}" stroke-width="2.3" stroke-linecap="round"/>` +
      `<path d="${d}" fill="none" stroke="#ffffff90" stroke-width="0.7" stroke-dasharray="1.2 1.7" stroke-linecap="round"/>` +
      `<circle cx="${a[0]}" cy="${a[1]}" r="2.5" fill="${col}"/><circle cx="${a[0] - 0.8}" cy="${a[1] - 0.7}" r="0.6" fill="#fff"/><circle cx="${a[0] + 0.8}" cy="${a[1] - 0.7}" r="0.6" fill="#fff"/>`;
  }

  function buildSnakes(s) {
    const g = s.game;
    newUI("snakes", s, { pos: {}, dice: null, rollerUid: null, lastRollSeq: 0, lastMoveSeq: 0, toks: {}, note: "" });
    let cells = "";
    for (let rt = 0; rt < 10; rt++) {
      const r = 9 - rt;
      for (let c = 0; c < 10; c++) {
        const n = r * 10 + (r % 2 === 0 ? c + 1 : 10 - c);
        cells += `<div class="slc ${(r + c) % 2 ? "b" : "a"}${n === 100 ? " goal" : ""}"><i>${n === 100 ? "🏁" : n}</i></div>`;
      }
    }
    let svg = "";
    Object.entries(g.ladders).forEach(([f, t]) => { svg += ladderSVG(+f, +t); });
    Object.entries(g.snakes).forEach(([f, t], i) => { svg += snakeSVG(+f, +t, i); });
    svg += '<text x="50" y="106.6" text-anchor="middle" font-size="3.6" fill="#9a9aa3" font-weight="700">START</text>';
    shell(s, `<div class="slbox"><div class="slgrid">${cells}</div>
      <svg class="slsvg" viewBox="0 0 100 110">${svg}</svg><div class="sltoks" id="sltoks"></div></div>
      <div class="slctl"><div class="dicebox2" id="sldice"></div><div class="slmsg" id="slmsg"></div>
      <button class="btn gold" id="slroll">🎲 Roll</button></div>`);
    const ui = HUB.S.ui, host = $("#sltoks");
    g.players.forEach((p, i) => {
      const t = document.createElement("div");
      t.className = "sltok";
      t.style.setProperty("--tc", PCOL[i % 4]);
      host.append(t);
      ui.toks[p.uid] = t;
    });
    $("#slroll").addEventListener("click", () => { HUB.send({ t: "roll" }); HUB.haptic("medium"); });
  }

  function renderToks(ui, g) {
    const groups = {};
    g.players.forEach((p, i) => {
      const pos = ui.pos[p.uid] || 0;
      const key = pos > 0 ? "p" + pos : "s" + i;
      (groups[key] = groups[key] || []).push([p, i, pos]);
    });
    for (const key in groups) {
      const arr = groups[key];
      arr.forEach(([p, i, pos], k) => {
        const el = ui.toks[p.uid];
        const base = pos > 0 ? slPoint(pos) : [12 + i * 11, 105];
        const off = (k - (arr.length - 1) / 2) * 2.4;
        el.style.left = base[0] + (pos > 0 ? off : 0) + "%";
        el.style.top = (base[1] + (pos > 0 ? off * 0.6 : 0)) / 1.1 + "%";
        el.style.display = p.left ? "none" : "";
      });
    }
  }

  function showSlDice(ui, s) {
    const box = $("#sldice");
    if (!box) return;
    box.innerHTML = ui.dice ? HUB.diceHTML(ui.dice) : "";
    $("#slmsg").textContent = ui.note || "";
  }

  async function slMove(ui, s, m) {
    const el = ui.toks[m.uid];
    const who = m.uid === s.you ? "You" : nameOf(s, m.uid);
    if (m.blocked) { ui.note = `${who} needs an exact roll`; showSlDice(ui, s); return; }
    for (let p = m.from + 1; p <= m.to; p++) {
      ui.pos[m.uid] = p; renderToks(ui, s.game); HUB.sfx.step(); await HUB.sleep(120);
    }
    if (m.kind) {
      ui.note = m.kind === "snake" ? `🐍 ${who} got bitten!` : `🪜 ${who} climbed a ladder!`;
      showSlDice(ui, s);
      await HUB.sleep(300);
      el.classList.add("jump");
      ui.pos[m.uid] = m.end; renderToks(ui, s.game);
      m.kind === "snake" ? HUB.sfx.capture() : HUB.sfx.win();
      await HUB.sleep(650);
      el.classList.remove("jump");
    } else {
      ui.note = "";
    }
  }

  async function applySnakes(s) {
    const ui = HUB.S.ui, g = s.game;
    if (ui.first) {
      ui.first = false;
      g.players.forEach((p) => { ui.pos[p.uid] = p.pos; });
      if (g.last_roll) { ui.lastRollSeq = g.last_roll.seq; ui.dice = g.last_roll.value; }
      if (g.last_move) ui.lastMoveSeq = g.last_move.seq;
    } else {
      if (g.last_roll && g.last_roll.seq > ui.lastRollSeq) {
        ui.lastRollSeq = g.last_roll.seq; ui.dice = g.last_roll.value;
        ui.note = (g.last_roll.uid === s.you ? "You" : nameOf(s, g.last_roll.uid)) + " rolled " + g.last_roll.value;
        showSlDice(ui, s);
        await HUB.tumble($("#sldice"), g.last_roll.value, 900);
        await HUB.sleep(100);
      }
      if (g.last_move && g.last_move.seq > ui.lastMoveSeq) { ui.lastMoveSeq = g.last_move.seq; await slMove(ui, s, g.last_move); }
      g.players.forEach((p) => { ui.pos[p.uid] = p.pos; });
    }
    renderToks(ui, g);
    showSlDice(ui, s);
    updateBar(ui, s, (uid) => ({ score: "📍" + (ui.pos[uid] || 0) }));
    const mine = s.status === "playing" && g.turn === s.you;
    const btn = $("#slroll");
    btn.disabled = !mine;
    btn.textContent = mine ? "🎲 Roll" : s.status === "playing" ? nameOf(s, g.turn) + "'s turn" : "Game over";
    setHint(turnHint(s));
    turnFx(ui, s);
  }

  /* =====================================================================
     CONNECT FOUR
     ===================================================================== */
  const C4COL = ["#ea4335", "#fbbc05"];
  function buildC4(s) {
    newUI("connect4", s, { lastSeq: 0 });
    let cols = "";
    for (let c = 0; c < 7; c++) {
      cols += `<div class="c4col" data-c="${c}">`;
      for (let r = 0; r < 6; r++) cols += `<div class="hole" data-i="${r * 7 + c}"></div>`;
      cols += "</div>";
    }
    shell(s, `<div class="c4wrap"><div class="c4board" id="c4">${cols}</div></div>`);
    $("#c4").addEventListener("click", (e) => {
      const col = e.target.closest(".c4col");
      const s2 = HUB.S.room;
      if (col && s2 && s2.status === "playing" && s2.game.turn === s2.you) { HUB.send({ t: "drop", col: +col.dataset.c }); HUB.haptic(); }
    });
  }
  async function applyC4(s) {
    const ui = HUB.S.ui, g = s.game;
    const colorOf = {};
    g.players.forEach((p, i) => { colorOf[p.uid] = C4COL[i]; });
    const fresh = !ui.first && g.last_move && g.last_move.seq > ui.lastSeq;
    ui.first = false;
    if (g.last_move) ui.lastSeq = g.last_move.seq;
    document.querySelectorAll("#c4 .hole").forEach((h) => {
      const i = +h.dataset.i, v = g.board[i];
      const isNew = fresh && g.last_move.row * 7 + g.last_move.col === i;
      if (!v) { h.innerHTML = ""; }
      else if (!h.firstChild || h.firstChild.dataset.u !== String(v) || isNew) {
        h.innerHTML = `<div class="disc${isNew ? " drop" : ""}" data-u="${v}" style="--dc:${colorOf[v]};--rows:${isNew ? g.last_move.row + 1 : 0}"></div>`;
      }
      h.classList.toggle("win", !!(g.line && g.line.includes(i)));
    });
    const mine = s.status === "playing" && g.turn === s.you;
    $("#c4").classList.toggle("can", mine);
    updateBar(ui, s, (uid) => ({ score: uid === g.players[0].uid ? "🔴" : "🟡" }));
    setHint(turnHint(s));
    if (fresh) { HUB.sfx.drop(); await HUB.sleep(450); }
    turnFx(ui, s);
  }

  /* =====================================================================
     ROCK PAPER SCISSORS
     ===================================================================== */
  const RPS = { rock: "✊", paper: "✋", scissors: "✌️" };
  function buildRPS(s) {
    newUI("rps", s, { lastSeq: 0, myPick: null, revealing: false });
    shell(s, `<div class="rps"><div class="rpsround" id="rround"></div><div class="rpsstage" id="rstage"></div>
      <div class="rpsbtns" id="rbtns">${Object.entries(RPS).map(([k, e]) => `<button class="rbtn" data-c="${k}"><span>${e}</span><i>${k}</i></button>`).join("")}</div></div>`);
    $("#rbtns").addEventListener("click", (e) => {
      const b = e.target.closest(".rbtn"), s2 = HUB.S.room, ui = HUB.S.ui;
      if (!b || !s2 || s2.status !== "playing" || s2.game.turn !== s2.you) return;
      ui.myPick = b.dataset.c;
      HUB.send({ t: "pick", choice: b.dataset.c });
      HUB.haptic("medium");
    });
  }
  async function applyRPS(s) {
    const ui = HUB.S.ui, g = s.game;
    const lr = g.last_round;
    if (ui.first) { ui.first = false; if (lr) ui.lastSeq = lr.seq; }
    else if (lr && lr.seq > ui.lastSeq) {
      ui.lastSeq = lr.seq;
      const mine = lr.picks[s.you], other = Object.keys(lr.picks).map(Number).find((u) => u !== s.you);
      const theirs = lr.picks[other];
      const verdict = lr.winner == null ? "🤝 Draw, go again" : lr.winner === s.you ? "🎉 You win the round!" : nameOf(s, lr.winner) + " wins the round";
      const mineEl = iAmPlaying(s) ? mine : lr.picks[g.players[0].uid], theirEl = iAmPlaying(s) ? theirs : lr.picks[g.players[1].uid];
      $("#rstage").innerHTML = `<div class="reveal"><span class="pop">${RPS[mineEl]}</span><b>VS</b><span class="pop pop2">${RPS[theirEl]}</span></div><div class="verdict">${verdict}</div>`;
      $("#rbtns").classList.add("off");
      HUB.sfx.pop();
      ui.myPick = null;
      await HUB.sleep(1900);
    }
    $("#rround").textContent = `Round ${Math.min(g.round, 9)} · first to ${g.win_score} wins`;
    const mine = s.status === "playing" && g.turn === s.you;
    $("#rbtns").classList.toggle("off", !mine);
    let stage = "";
    if (s.status !== "playing") stage = '<div class="verdict">Game over</div>';
    else if (mine) stage = '<div class="big">Make your pick!</div>';
    else if (g.picked[s.you] && ui.myPick) stage = `<div class="reveal"><span>${RPS[ui.myPick]}</span></div><div class="sub">Locked in. Waiting for ${nameOf(s, g.turn)}…</div>`;
    else stage = `<div class="big">Waiting for ${nameOf(s, g.turn)}…</div>`;
    $("#rstage").innerHTML = stage;
    updateBar(ui, s, (uid) => { const p = g.players.find((x) => x.uid === uid); return { score: p.score + "/" + g.win_score }; });
    setHint("");
    turnFx(ui, s);
  }

  /* =====================================================================
     MEMORY MATCH
     ===================================================================== */
  function buildMemory(s) {
    newUI("memory", s, { lastSeq: 0 });
    let h = '<div class="mgrid" id="mg">';
    for (let i = 0; i < 16; i++) h += `<button class="mcard" data-i="${i}"><div class="mi"><div class="mb">?</div><div class="mf"></div></div></button>`;
    shell(s, h + "</div>");
    $("#mg").addEventListener("click", (e) => {
      const c = e.target.closest(".mcard"), s2 = HUB.S.room;
      if (!c || !s2 || s2.status !== "playing" || s2.game.turn !== s2.you) return;
      const i = +c.dataset.i, g = s2.game;
      if (g.owner[i] != null || (g.up.includes(i) && g.up.length < 2)) return;
      HUB.send({ t: "flip", i });
      HUB.haptic();
    });
  }
  async function applyMemory(s) {
    const ui = HUB.S.ui, g = s.game;
    const idx = {};
    g.players.forEach((p, i) => { idx[p.uid] = i; });
    document.querySelectorAll("#mg .mcard").forEach((c) => {
      const i = +c.dataset.i, v = g.cards[i], own = g.owner[i];
      c.classList.toggle("up", v != null);
      c.classList.toggle("m", own != null);
      c.querySelector(".mf").textContent = v != null ? v : "";
      if (own != null) c.style.setProperty("--oc", PCOL[idx[own] % 4]);
    });
    const mine = s.status === "playing" && g.turn === s.you;
    $("#mg").classList.toggle("can", mine);
    if (!ui.first && g.last_flip && g.last_flip.seq > ui.lastSeq) HUB.sfx.flip();
    ui.first = false;
    if (g.last_flip) ui.lastSeq = g.last_flip.seq;
    updateBar(ui, s, (uid) => { const p = g.players.find((x) => x.uid === uid); return { score: p.score + " 🃏" }; });
    setHint(mine && g.up.length === 2 ? "No match. Remember them, then tap any card" : turnHint(s));
    turnFx(ui, s);
  }

  /* =====================================================================
     CARROM (canvas; the server simulates the physics and sends the frames)
     ===================================================================== */
  const CR = 17, SR = 21, POCKET = [[0, 0], [800, 0], [0, 800], [800, 800]];
  const CKIND = { w: ["#f6f1e6", "#b9ae94"], b: ["#2a2a2a", "#000"], q: ["#d63a3a", "#7d1414"] };

  function drawCarrom(ui, items, strikerAt) {
    const ctx = ui.ctx;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, 800, 800);
    if (ui.flip) { ctx.translate(800, 800); ctx.rotate(Math.PI); }
    ctx.fillStyle = "#ecc98f"; ctx.fillRect(0, 0, 800, 800);
    ctx.strokeStyle = "#8a5a2b"; ctx.lineWidth = 3;
    [110, 690].forEach((y) => {
      ctx.beginPath(); ctx.roundRect(150, y - 18, 500, 36, 18); ctx.stroke();
      [150, 650].forEach((x) => { ctx.beginPath(); ctx.arc(x, y, 14, 0, 7); ctx.fillStyle = "#c0392b"; ctx.fill(); ctx.stroke(); });
    });
    ctx.beginPath(); ctx.arc(400, 400, 100, 0, 7); ctx.stroke();
    ctx.beginPath(); ctx.arc(400, 400, 22, 0, 7); ctx.fillStyle = "#e7b9a0"; ctx.fill(); ctx.stroke();
    ctx.lineWidth = 2;
    [[170, 170], [630, 170], [170, 630], [630, 630]].forEach(([x, y]) => { ctx.beginPath(); ctx.arc(x, y, 18, 0, 7); ctx.stroke(); });
    POCKET.forEach(([x, y]) => {
      ctx.beginPath(); ctx.arc(x, y, 44, 0, 7); ctx.fillStyle = "#1a1208"; ctx.fill();
      ctx.beginPath(); ctx.arc(x, y, 44, 0, 7); ctx.strokeStyle = "#5c3a14"; ctx.lineWidth = 5; ctx.stroke();
    });
    items.forEach((it) => {
      if (it.striker) return;
      const col = CKIND[it.kind];
      ctx.beginPath(); ctx.arc(it.x + 2, it.y + 3, CR, 0, 7); ctx.fillStyle = "#0004"; ctx.fill();
      ctx.beginPath(); ctx.arc(it.x, it.y, CR, 0, 7); ctx.fillStyle = col[0]; ctx.fill();
      ctx.strokeStyle = col[1]; ctx.lineWidth = 2.5; ctx.stroke();
      ctx.beginPath(); ctx.arc(it.x, it.y, CR * 0.55, 0, 7); ctx.lineWidth = 1.5; ctx.stroke();
    });
    const st = items.find((i) => i.striker) || strikerAt;
    if (st) {
      ctx.beginPath(); ctx.arc(st.x + 2, st.y + 3, SR, 0, 7); ctx.fillStyle = "#0004"; ctx.fill();
      ctx.beginPath(); ctx.arc(st.x, st.y, SR, 0, 7); ctx.fillStyle = "#fffdf4"; ctx.fill();
      ctx.strokeStyle = "#3b6fd4"; ctx.lineWidth = 4; ctx.stroke();
      ctx.beginPath(); ctx.arc(st.x, st.y, 10, 0, 7); ctx.lineWidth = 2; ctx.stroke();
      if (ui.aim) {
        const a = ui.aim;
        ctx.setLineDash([10, 9]); ctx.strokeStyle = "#fff"; ctx.lineWidth = 4;
        ctx.beginPath(); ctx.moveTo(st.x, st.y); ctx.lineTo(st.x + Math.cos(a.angle) * (120 + 520 * a.power), st.y + Math.sin(a.angle) * (120 + 520 * a.power)); ctx.stroke();
        ctx.setLineDash([]); ctx.strokeStyle = "#e03a2e"; ctx.lineWidth = 6;
        ctx.beginPath(); ctx.moveTo(st.x, st.y); ctx.lineTo(a.px, a.py); ctx.stroke();
        ctx.beginPath(); ctx.arc(a.px, a.py, 9, 0, 7); ctx.fillStyle = "#e03a2e"; ctx.fill();
      }
    }
  }

  function buildCarrom(s) {
    const g = s.game;
    const me = g.players.findIndex((p) => p.uid === s.you);
    const ui = newUI("carrom", s, { flip: me === 1, me: Math.max(0, me), coins: g.coins.slice(), sx: 400, aim: null, pending: false, animating: false, lastSeq: 0 });
    shell(s, `<div class="cvwrap"><canvas id="cv" width="800" height="800"></canvas></div>
      <div class="cvctl"><span>◀</span><input type="range" id="cx" min="160" max="640" value="400"><span>▶</span></div>`);
    const cv = $("#cv");
    ui.ctx = cv.getContext("2d");
    const slider = $("#cx");
    const strikerPos = () => ({ x: ui.sx, y: HUB.S.room.game.base_y[ui.me] });
    const canShoot = () => { const r = HUB.S.room; return r && r.status === "playing" && r.game.turn === r.you && !ui.pending && !ui.animating; };
    const toBoard = (e) => {
      const rect = cv.getBoundingClientRect();
      let x = (e.clientX - rect.left) / rect.width * 800, y = (e.clientY - rect.top) / rect.height * 800;
      if (ui.flip) { x = 800 - x; y = 800 - y; }
      return [x, y];
    };
    const redraw = () => drawCarrom(ui, ui.coins.map((c) => ({ ...c })), HUB.S.room && HUB.S.room.status === "playing" ? strikerView() : null);
    ui.redraw = redraw;
    const strikerView = () => {
      const r = HUB.S.room, g2 = r.game, idx = g2.players.findIndex((p) => p.uid === g2.turn);
      if (idx < 0) return null;
      return { x: g2.turn === r.you ? ui.sx : 400, y: g2.base_y[idx] };
    };
    slider.addEventListener("input", () => {
      ui.sx = ui.flip ? 800 - +slider.value : +slider.value;
      redraw();
    });
    cv.addEventListener("pointerdown", (e) => {
      if (!canShoot()) return;
      cv.setPointerCapture(e.pointerId);
      ui.aim = { power: 0, angle: -Math.PI / 2, px: 0, py: 0 };
      cv.dispatchEvent(new PointerEvent("pointermove", e));
    });
    cv.addEventListener("pointermove", (e) => {
      if (!ui.aim) return;
      const st = strikerPos(), [px, py] = toBoard(e);
      const dx = st.x - px, dy = st.y - py, len = Math.hypot(dx, dy);
      ui.aim = { angle: Math.atan2(dy, dx), power: Math.min(1, len / 220), px, py, len };
      setHint("Power " + Math.round(ui.aim.power * 100) + "%");
      redraw();
    });
    const release = (e) => {
      if (!ui.aim) return;
      const a = ui.aim;
      ui.aim = null;
      if (a.len > 24 && canShoot()) {
        ui.pending = true;
        HUB.send({ t: "shoot", x: ui.sx, angle: a.angle, power: Math.max(0.08, a.power) });
        HUB.sfx.hit(); HUB.haptic("heavy");
      }
      setHint(turnHint(HUB.S.room));
      redraw();
    };
    cv.addEventListener("pointerup", release);
    cv.addEventListener("pointercancel", () => { ui.aim = null; redraw(); });
  }

  function playShot(ui, shot) {
    return new Promise((resolve) => {
      const frames = shot.frames, n = frames.length, fps = shot.fps, ids = shot.ids;
      const kindOf = {};
      ui.coins.forEach((c) => { kindOf[c.id] = c.kind; });
      const hideAt = {}, played = new Set();
      shot.out.forEach(([b, f]) => { hideAt[b] = f; });
      let done = false;
      const finish = () => { if (!done) { done = true; resolve(); } };
      setTimeout(finish, ((n - 1) / fps) * 1000 + 700); // safety net if the tab is hidden
      const t0 = performance.now();
      ui.animating = true;
      const tick = (now) => {
        if (done || HUB.S.ui !== ui) return finish();
        const t = Math.max(0, Math.min(((now - t0) / 1000) * fps, n - 1)), f = Math.floor(t), fr = t - f;  // rAF time can precede t0
        const A = frames[f], B = frames[Math.min(f + 1, n - 1)], items = [];
        for (let b = 0; b <= ids.length; b++) {
          const hf = hideAt[b];
          if (hf !== undefined && f >= hf) { if (!played.has(b)) { played.add(b); HUB.sfx.hit(); } continue; }
          const x = A[2 * b] + (B[2 * b] - A[2 * b]) * fr, y = A[2 * b + 1] + (B[2 * b + 1] - A[2 * b + 1]) * fr;
          items.push(b === 0 ? { striker: true, x, y } : { kind: kindOf[ids[b - 1]], x, y });
        }
        drawCarrom(ui, items, null);
        if (t >= n - 1) return finish();
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }).then(() => { ui.animating = false; });
  }

  async function applyCarrom(s) {
    const ui = HUB.S.ui, g = s.game, shot = g.last_shot;
    if (ui.first) {
      ui.first = false;
      if (shot) ui.lastSeq = shot.seq;
    } else if (shot && shot.seq > ui.lastSeq) {
      ui.lastSeq = shot.seq;
      await playShot(ui, shot);
      if (shot.striker_in) HUB.toast("Foul! Striker pocketed, turn lost");
    }
    ui.coins = g.coins.slice();
    ui.pending = false;
    const mine = s.status === "playing" && g.turn === s.you;
    $("#cx").disabled = !mine;
    ui.redraw();
    updateBar(ui, s, (uid) => { const p = g.players.find((x) => x.uid === uid); return { score: p.score + " pts", sub: p.kind === "w" ? "⚪ White" : "⚫ Black" }; });
    setHint(mine ? "Slide to place the striker, then drag back from it to aim and set power" : turnHint(s));
    turnFx(ui, s);
  }

  HUB.kit = { bar, updateBar, nameOf, setHint, turnHint, turnFx, shell, newUI, iAmPlaying, PCOL };
  HUB.UI.snakes = { build: buildSnakes, apply: applySnakes };
  HUB.UI.connect4 = { build: buildC4, apply: applyC4 };
  HUB.UI.rps = { build: buildRPS, apply: applyRPS };
  HUB.UI.memory = { build: buildMemory, apply: applyMemory };
  HUB.UI.carrom = { build: buildCarrom, apply: applyCarrom };
})();

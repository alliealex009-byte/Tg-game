/* Renderers for Pig, Liar's Dice, Bingo, Nim, Mancala and Dots & Boxes.
   Each registers { build(state), apply(state) } in HUB.UI. Spectators (state.you not a player) get read-only views. */
(function () {
  "use strict";
  window.HUB = window.HUB || { UI: {} };
  const HUB = window.HUB;
  const $ = (s, r) => (r || document).querySelector(s);
  const K = () => HUB.kit;
  const room = () => HUB.S.room;
  const mineTurn = (s) => s.status === "playing" && s.game.turn === s.you && s.game.players.some((p) => p.uid === s.you);
  const playing = (s) => s.game.players.some((p) => p.uid === s.you);
  const fx = (ui, s) => K().turnFx(ui, s);
  const sfx = (n) => { try { HUB.sfx[n](); } catch (e) { /* ignore */ } };
  const pcol = (s, uid) => K().PCOL[Math.max(0, s.game.players.findIndex((p) => p.uid === uid)) % 4];

  /* =====================================================================  PIG */
  function buildPig(s) {
    K().newUI("pig", s, { lastRoll: 0, lastHold: 0 });
    K().shell(s, `<div class="gd-pig">
      <div class="gd-target">First to <b>${s.game.target}</b> wins</div>
      <div class="gd-diebox" id="gdpigdie"></div>
      <div class="gd-total"><span>This turn</span><b id="gdptot">0</b></div>
      <div class="gd-btns"><button class="gd-btn roll" id="gdroll">🎲 ROLL</button><button class="gd-btn hold" id="gdhold">✋ HOLD</button></div>
      <div class="gd-msg" id="gdmsg"></div></div>`);
    $("#gdroll").addEventListener("click", () => { if (mineTurn(room())) { HUB.send({ t: "roll" }); HUB.haptic("medium"); } });
    $("#gdhold").addEventListener("click", () => { if (mineTurn(room())) { HUB.send({ t: "hold" }); HUB.haptic(); } });
  }
  async function applyPig(s) {
    const ui = HUB.S.ui, g = s.game, die = $("#gdpigdie"), msg = $("#gdmsg");
    const who = (u) => (u === s.you ? "You" : K().nameOf(s, u));
    if (ui.first) {
      ui.first = false;
      if (g.last_roll) { ui.lastRoll = g.last_roll.seq; die.innerHTML = HUB.diceHTML(g.last_roll.value); }
      if (g.last_hold) ui.lastHold = g.last_hold.seq;
    } else {
      const lr = g.last_roll, lh = g.last_hold;
      if (lr && lr.seq > ui.lastRoll) {
        ui.lastRoll = lr.seq;
        $("#gdptot").textContent = Math.max(0, g.turn_total - (lr.bust ? 0 : lr.value));
        await HUB.tumble(die, lr.value, 900);
        if (lr.bust) {
          msg.textContent = `💥 ${who(lr.uid)} rolled a 1 and lost the turn!`;
          die.classList.add("gd-bust"); sfx("bad"); HUB.haptic("heavy");
          await HUB.sleep(900); die.classList.remove("gd-bust");
        } else { sfx("good"); msg.textContent = `${who(lr.uid)} rolled ${lr.value}`; }
      }
      if (lh && lh.seq > ui.lastHold) {
        ui.lastHold = lh.seq; sfx("cash"); HUB.haptic();
        msg.textContent = `✋ ${who(lh.uid)} banked ${lh.gained}`;
        await HUB.sleep(500);
      }
    }
    $("#gdptot").textContent = g.turn_total;
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).score }));
    const mine = mineTurn(s);
    $("#gdroll").disabled = !mine; $("#gdhold").disabled = !mine || g.turn_total === 0;
    $("#gdroll").classList.toggle("hidden", !playing(s)); $("#gdhold").classList.toggle("hidden", !playing(s));
    K().setHint(mine ? "Roll again or hold to bank your points" : K().turnHint(s));
    fx(ui, s);
  }

  /* =====================================================================  LIAR'S DICE */
  function buildLiar(s) {
    K().newUI("liarsdice", s, { lastBid: 0, lastReveal: 0, round: 0, bidSeq: -1, q: 1, f: 2 });
    K().shell(s, `<div class="gd-liar">
      <div class="gd-others" id="gdothers"></div>
      <div class="gd-bid" id="gdbid"></div>
      <div class="gd-reveal hidden" id="gdreveal"></div>
      <div class="gd-mydice" id="gdmy"></div>
      <div class="gd-ctl" id="gdctl">
        <div class="gd-row"><button class="gd-step" data-a="q-">−</button><div class="gd-qv" id="gdq"></div><button class="gd-step" data-a="q+">+</button>
        <div class="gd-faces" id="gdf">${[1, 2, 3, 4, 5, 6].map((f) => `<button class="gd-face" data-f="${f}">${HUB.diceHTML(f)}</button>`).join("")}</div></div>
        <div class="gd-row"><button class="gd-btn roll" id="gdbidbtn">BID</button><button class="gd-btn liar" id="gdliar">🤥 LIAR!</button></div>
      </div></div>`);
    $("#gdctl").addEventListener("click", (e) => {
      const s2 = room(), ui = HUB.S.ui, g = s2.game;
      const st = e.target.closest(".gd-step"), fc = e.target.closest(".gd-face");
      if (st) { ui.q = Math.max(1, Math.min(g.total, ui.q + (st.dataset.a === "q+" ? 1 : -1))); HUB.haptic(); sfx("chip"); updLiarCtl(s2); }
      else if (fc) { ui.f = +fc.dataset.f; HUB.haptic(); sfx("pop"); updLiarCtl(s2); }
    });
    $("#gdbidbtn").addEventListener("click", () => { const s2 = room(), ui = HUB.S.ui; if (mineTurn(s2) && validBid(s2.game, ui.q, ui.f)) { HUB.send({ t: "bid", q: ui.q, face: ui.f }); HUB.haptic("medium"); } });
    $("#gdliar").addEventListener("click", () => { const s2 = room(); if (mineTurn(s2) && s2.game.bid) { HUB.send({ t: "liar" }); HUB.haptic("heavy"); } });
  }
  function validBid(g, q, f) {
    if (q < 1 || q > g.total || f < 1 || f > 6) return false;
    if (!g.bid) return true;
    return q > g.bid.q || (q === g.bid.q && f > g.bid.face);
  }
  function defaultBid(g) {
    if (!g.bid) return { q: 1, f: 2 };
    return g.bid.face < 6 ? { q: g.bid.q, f: g.bid.face + 1 } : { q: Math.min(g.total, g.bid.q + 1), f: 1 };
  }
  function updLiarCtl(s) {
    const ui = HUB.S.ui, g = s.game, mine = mineTurn(s);
    $("#gdctl").classList.toggle("hidden", !playing(s));
    $("#gdq").innerHTML = `<b>${ui.q}</b><i>×</i>`;
    $("#gdf").querySelectorAll(".gd-face").forEach((b) => b.classList.toggle("on", +b.dataset.f === ui.f));
    $("#gdbidbtn").disabled = !mine || !validBid(g, ui.q, ui.f);
    $("#gdliar").disabled = !mine || !g.bid;
  }
  async function applyLiar(s) {
    const ui = HUB.S.ui, g = s.game, who = (u) => (u === s.you ? "You" : K().nameOf(s, u));
    const bidEl = $("#gdbid"), my = $("#gdmy");
    const renderMy = (anim) => {
      my.innerHTML = g.my_dice.length ? g.my_dice.map((v) => `<div class="gd-d">${HUB.diceHTML(v)}</div>`).join("") : (playing(s) && s.status === "playing" ? '<div class="gd-out">Out of dice</div>' : "");
      if (anim) return Promise.all([...my.querySelectorAll(".gd-d")].map((el, i) => HUB.tumble(el, g.my_dice[i], 800 + i * 80)));
    };
    const renderOthers = () => {
      $("#gdothers").innerHTML = g.players.filter((p) => p.uid !== s.you || !playing(s)).map((p) =>
        `<div class="gd-opp ${g.turn === p.uid ? "turn" : ""} ${p.out || p.left ? "dead" : ""}" style="--pc:${pcol(s, p.uid)}"><b>${HUB.esc(K().nameOf(s, p.uid))}</b><span>${"🎲".repeat(Math.max(0, p.dice))}</span></div>`).join("");
    };
    const renderBid = () => {
      bidEl.innerHTML = g.bid
        ? `<small>${HUB.esc(who(g.bid.uid))} bid</small><div class="gd-bigbid"><b>${g.bid.q}</b><i>×</i><div class="gd-d sm">${HUB.diceHTML(g.bid.face)}</div></div>`
        : `<small>Round ${g.round}</small><div class="gd-bigbid dim">${g.total} dice in play — place the first bid</div>`;
    };
    if (ui.first) {
      ui.first = false; ui.lastBid = g.last_bid ? g.last_bid.seq : 0; ui.lastReveal = g.last_reveal ? g.last_reveal.seq : 0; ui.round = g.round;
      renderMy(false); renderOthers(); renderBid();
    } else {
      if (g.last_bid && g.last_bid.seq > ui.lastBid) { ui.lastBid = g.last_bid.seq; sfx("chip"); HUB.haptic(); renderOthers(); renderBid(); bidEl.classList.remove("gd-pop"); void bidEl.offsetWidth; bidEl.classList.add("gd-pop"); await HUB.sleep(250); }
      const lv = g.last_reveal;
      if (lv && lv.seq > ui.lastReveal) {
        ui.lastReveal = lv.seq;
        const box = $("#gdreveal");
        box.classList.remove("hidden");
        box.innerHTML = `<h4>🤥 ${HUB.esc(who(lv.challenger))} called LIAR on ${HUB.esc(who(lv.bidder))}!</h4>` +
          Object.entries(lv.dice).map(([u, ds]) => `<div class="gd-rrow"><b>${HUB.esc(who(+u))}</b>${ds.map((d) => `<span class="gd-rd ${d === lv.face ? "hit" : ""}">${HUB.diceHTML(d)}</span>`).join("")}</div>`).join("") +
          `<div class="gd-verdict">Bid ${lv.q} × ${lv.face} · actual <b>${lv.actual}</b> → ${HUB.esc(who(lv.loser))} lose${lv.loser === s.you ? "" : "s"} a die</div>`;
        sfx("flip"); HUB.haptic("heavy");
        await HUB.sleep(600); sfx(lv.loser === s.you ? "bad" : "good");
        await HUB.sleep(2600);
        box.classList.add("hidden");
      }
    }
    renderOthers(); renderBid();
    const newRound = g.round !== ui.round;
    ui.round = g.round;
    await renderMy(newRound && g.my_dice.length > 0);
    if (newRound) sfx("roll");
    if (ui.bidSeq !== (g.bid ? g.last_bid && g.last_bid.seq : 0)) { ui.bidSeq = g.bid && g.last_bid ? g.last_bid.seq : 0; const d = defaultBid(g); ui.q = d.q; ui.f = d.f; }
    ui.q = Math.min(ui.q, Math.max(1, g.total));
    updLiarCtl(s);
    K().updateBar(ui, s, (uid) => ({ score: "🎲 " + g.players.find((p) => p.uid === uid).dice }));
    K().setHint(mineTurn(s) ? (g.bid ? "Raise the bid or call Liar!" : "Make the first bid") : K().turnHint(s));
    fx(ui, s);
  }

  /* =====================================================================  BINGO */
  function buildBingo(s) {
    K().newUI("bingo", s, { lastCall: 0, lastClaim: 0 });
    K().shell(s, `<div class="gd-bingo">
      <div class="gd-ballrow"><div class="gd-ball" id="gdball">?</div><div class="gd-recent" id="gdrecent"></div></div>
      <div class="gd-cardwrap"><div class="gd-cardhead"><span>B</span><span>I</span><span>N</span><span>G</span><span>O</span></div><div class="gd-card" id="gdcard"></div></div>
      <button class="gd-btn bingo" id="gdbingo">🎉 BINGO!</button></div>`);
    $("#gdcard").addEventListener("click", (e) => {
      const c = e.target.closest(".gd-cell"), s2 = room();
      if (!c || !c.dataset.n || s2.status !== "playing" || !playing(s2)) return;
      HUB.send({ t: "mark", n: +c.dataset.n }); HUB.haptic();
    });
    $("#gdbingo").addEventListener("click", () => { const s2 = room(); if (s2.status === "playing" && playing(s2)) { HUB.send({ t: "bingo" }); HUB.haptic("heavy"); } });
  }
  async function applyBingo(s) {
    const ui = HUB.S.ui, g = s.game, ball = $("#gdball");
    const card = g.card || (g.reveal && g.reveal.card), marks = new Set(g.card ? g.marks : g.reveal ? g.reveal.marks : []);
    const called = new Set(g.called);
    if (ui.first) { ui.first = false; ui.lastCall = g.last_call ? g.last_call.seq : 0; ui.lastClaim = g.last_claim ? g.last_claim.seq : 0; if (g.last_call) ball.textContent = g.last_call.n; }
    else {
      if (g.last_call && g.last_call.seq > ui.lastCall) {
        ui.lastCall = g.last_call.seq;
        ball.textContent = g.last_call.n; ball.classList.remove("gd-drop"); void ball.offsetWidth; ball.classList.add("gd-drop");
        HUB.tone(520, 0.08, "triangle", 0.2); HUB.tone(780, 0.1, "triangle", 0.18, 0.07); HUB.haptic();
      }
      const lc = g.last_claim;
      if (lc && lc.seq > ui.lastClaim) {
        ui.lastClaim = lc.seq;
        if (!lc.ok) { sfx("bad"); HUB.toast(lc.uid === s.you ? "❌ False BINGO! Locked out for a few calls" : "❌ " + K().nameOf(s, lc.uid) + " made a false claim", 2400); }
      }
    }
    const letter = (n) => "BINGO"[Math.floor((n - 1) / 15)];
    $("#gdrecent").innerHTML = g.called.slice(-7, -1).reverse().map((n) => `<span class="gd-chip c${Math.floor((n - 1) / 15)}">${letter(n)}${n}</span>`).join("") || '<span class="gd-dim">Numbers appear here</span>';
    const el = $("#gdcard");
    if (card) {
      const win = g.reveal && g.reveal.line ? new Set(g.reveal.line.map((p) => p[0] * 5 + p[1])) : new Set();
      el.innerHTML = card.map((row, r) => row.map((n, c) => {
        const free = n === 0, on = free || marks.has(n), hot = !on && called.has(n);
        return `<button class="gd-cell ${on ? "on" : ""} ${hot ? "hot" : ""} ${win.has(r * 5 + c) ? "win" : ""}" ${free ? "" : `data-n="${n}"`}>${free ? "★" : n}</button>`;
      }).join("")).join("");
    } else {
      el.innerHTML = `<div class="gd-spec">👀 Watching — ${g.players.length} players<br>${g.players.map((p) => HUB.esc(K().nameOf(s, p.uid)) + " · " + p.marked + " marked").join("<br>")}</div>`;
    }
    const me = g.players.find((p) => p.uid === s.you);
    const btn = $("#gdbingo");
    btn.classList.toggle("hidden", !me);
    btn.disabled = s.status !== "playing" || !!(me && me.locked);
    btn.textContent = me && me.locked ? "⏳ Locked out…" : "🎉 BINGO!";
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).marked + " ✓", sub: "" }));
    K().setHint(g.reveal ? "🏆 " + K().nameOf(s, g.reveal.uid) + " got a line!" : `${g.called.length} / 75 called · tap called numbers, then press BINGO`);
  }

  /* =====================================================================  NIM */
  function buildNim(s) {
    K().newUI("nim", s, { lastSeq: 0, disp: s.game.heaps.slice(), sel: null });
    K().shell(s, `<div class="gd-nim"><div class="gd-heaps" id="gdheaps"></div><div class="gd-nimmsg" id="gdnimmsg"></div>
      <button class="gd-btn roll" id="gdtake" disabled>Take</button></div>`);
    $("#gdheaps").addEventListener("click", (e) => {
      const c = e.target.closest(".gd-coin"), s2 = room(), ui = HUB.S.ui;
      if (!c || !mineTurn(s2)) return;
      const h = +c.dataset.h, i = +c.dataset.i;
      ui.sel = { h, n: ui.disp[h] - i };
      HUB.haptic(); sfx("pop"); drawNim(s2);
    });
    $("#gdtake").addEventListener("click", () => { const s2 = room(), ui = HUB.S.ui; if (mineTurn(s2) && ui.sel) { HUB.send({ t: "take", heap: ui.sel.h, n: ui.sel.n }); ui.sel = null; HUB.haptic("medium"); } });
  }
  function drawNim(s, gone) {
    const ui = HUB.S.ui, el = $("#gdheaps"), max = Math.max(...s.game.heaps, ...ui.disp, 7);
    el.innerHTML = ui.disp.map((n, h) => {
      let coins = "";
      for (let i = 0; i < n; i++) {
        const sel = ui.sel && ui.sel.h === h && i >= n - ui.sel.n, g2 = gone && gone.h === h && i >= n - gone.n;
        coins += `<button class="gd-coin ${sel ? "sel" : ""} ${g2 ? "gone" : ""}" data-h="${h}" data-i="${i}" style="--k:${i}"></button>`;
      }
      return `<div class="gd-heap"><div class="gd-stack" style="min-height:${max * 30}px">${coins}</div><div class="gd-hn">${n}</div></div>`;
    }).join("");
    const take = $("#gdtake");
    take.disabled = !(ui.sel && mineTurn(s));
    take.textContent = ui.sel ? `Take ${ui.sel.n} from heap ${ui.sel.h + 1}` : "Tap coins to choose";
    take.classList.toggle("hidden", !playing(s));
  }
  async function applyNim(s) {
    const ui = HUB.S.ui, g = s.game, lm = g.last_move;
    if (ui.first) { ui.first = false; if (lm) ui.lastSeq = lm.seq; ui.disp = g.heaps.slice(); }
    else if (lm && lm.seq > ui.lastSeq) {
      ui.lastSeq = lm.seq; ui.sel = null;
      drawNim(s, { h: lm.heap, n: lm.n });
      for (let i = 0; i < lm.n; i++) { HUB.tone(300 + i * 60, 0.08, "triangle", 0.2); }
      HUB.haptic("medium");
      await HUB.sleep(520);
      ui.disp = g.heaps.slice();
    }
    ui.disp = g.heaps.slice();
    if (!mineTurn(s)) ui.sel = null;
    drawNim(s);
    $("#gdnimmsg").textContent = "Take any number of coins from ONE heap. Whoever takes the last coin wins!";
    K().updateBar(ui, s, () => ({ score: "" }));
    K().setHint(mineTurn(s) ? "Tap a coin: it and everything above it is taken" : K().turnHint(s));
    fx(ui, s);
  }

  /* =====================================================================  MANCALA */
  function buildMancala(s) {
    K().newUI("mancala", s, { lastSeq: 0, disp: s.game.board.slice(), busy: false, hl: -1 });
    K().shell(s, `<div class="gd-mancala"><div class="gd-mboard" id="gdmb"></div></div>`);
    $("#gdmb").addEventListener("click", (e) => {
      const p = e.target.closest(".gd-pit"), s2 = room(), ui = HUB.S.ui;
      if (!p || ui.busy || !mineTurn(s2)) return;
      const i = +p.dataset.i, idx = s2.game.players.findIndex((x) => x.uid === s2.you);
      if (i < idx * 7 || i > idx * 7 + 5 || !ui.disp[i]) return;
      HUB.send({ t: "sow", pit: i - idx * 7 }); HUB.haptic("medium");
    });
  }
  function stones(n, i) {
    if (n > 14) return `<span class="gd-many">${n}</span>`;
    let h = "";
    for (let k = 0; k < n; k++) {
      const a = (k * 137.5 + i * 40) * Math.PI / 180, r = Math.min(34, 8 + Math.sqrt(k) * 11);
      h += `<i style="left:${50 + Math.cos(a) * r * 0.9}%;top:${50 + Math.sin(a) * r * 0.9}%;--h:${(k * 53 + i * 17) % 360}"></i>`;
    }
    return h;
  }
  function drawMancala(s) {
    const ui = HUB.S.ui, g = s.game, idx = g.players.findIndex((p) => p.uid === s.you), flip = idx === 1;
    const top = flip ? [5, 4, 3, 2, 1, 0] : [12, 11, 10, 9, 8, 7], bot = flip ? [7, 8, 9, 10, 11, 12] : [0, 1, 2, 3, 4, 5];
    const lStore = flip ? 6 : 13, rStore = flip ? 13 : 6;
    const can = (i) => mineTurn(s) && !ui.busy && idx >= 0 && i >= idx * 7 && i <= idx * 7 + 5 && ui.disp[i] > 0;
    const pit = (i) => `<button class="gd-pit ${can(i) ? "can" : ""} ${ui.hl === i ? "hl" : ""}" data-i="${i}">${stones(ui.disp[i], i)}<b>${ui.disp[i]}</b></button>`;
    const store = (i) => `<div class="gd-store ${ui.hl === i ? "hl" : ""}" data-i="${i}">${stones(Math.min(ui.disp[i], 18), i)}<b>${ui.disp[i]}</b></div>`;
    $("#gdmb").innerHTML = `${store(lStore)}<div class="gd-rows"><div class="gd-prow">${top.map(pit).join("")}</div><div class="gd-prow">${bot.map(pit).join("")}</div></div>${store(rStore)}`;
  }
  async function applyMancala(s) {
    const ui = HUB.S.ui, g = s.game, lm = g.last_move;
    if (ui.first) { ui.first = false; if (lm) ui.lastSeq = lm.seq; ui.disp = g.board.slice(); drawMancala(s); }
    else if (lm && lm.seq > ui.lastSeq) {
      ui.lastSeq = lm.seq; ui.busy = true;
      ui.disp = lm.before.slice(); ui.disp[lm.pit] = 0; ui.hl = lm.pit; drawMancala(s); HUB.sfx.pop(); await HUB.sleep(260);
      for (const p of lm.path) {
        ui.disp[p]++; ui.hl = p; drawMancala(s);
        HUB.tone(420 + p * 25, 0.07, "triangle", 0.2); HUB.haptic();
        await HUB.sleep(300);
      }
      if (lm.capture) { sfx("capture"); ui.disp[lm.capture.from] = 0; ui.disp[lm.capture.to] = 0; ui.disp[lm.uid === g.players[0].uid ? 6 : 13] += lm.capture.n; ui.hl = lm.uid === g.players[0].uid ? 6 : 13; drawMancala(s); await HUB.sleep(500); }
      if (lm.extra) { sfx("good"); HUB.toast("Extra turn!", 1200); }
      ui.busy = false; ui.hl = -1;
    }
    ui.disp = g.board.slice(); ui.hl = -1; ui.busy = false;
    drawMancala(s);
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).score }));
    K().setHint(mineTurn(s) ? "Tap one of your pits to sow the stones" : K().turnHint(s));
    fx(ui, s);
  }

  /* =====================================================================  DOTS & BOXES */
  const GAP = 52, PAD = 20;
  function buildDots(s) {
    const n = s.game.n, W = PAD * 2 + GAP * n;
    K().newUI("dots", s, { lastSeq: 0, edges: {}, boxes: {} });
    let svg = `<svg viewBox="0 0 ${W} ${W}" class="gd-dsvg" id="gdsvg">`;
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) svg += `<rect class="gd-box" id="gdb${r}_${c}" x="${PAD + c * GAP + 4}" y="${PAD + r * GAP + 4}" width="${GAP - 8}" height="${GAP - 8}" rx="8"/><text class="gd-bt" id="gdt${r}_${c}" x="${PAD + c * GAP + GAP / 2}" y="${PAD + r * GAP + GAP / 2 + 7}"></text>`;
    for (let r = 0; r <= n; r++) for (let c = 0; c < n; c++) svg += `<line class="gd-edge" id="gdeh${r}_${c}" x1="${PAD + c * GAP}" y1="${PAD + r * GAP}" x2="${PAD + (c + 1) * GAP}" y2="${PAD + r * GAP}"/>`;
    for (let r = 0; r < n; r++) for (let c = 0; c <= n; c++) svg += `<line class="gd-edge" id="gdev${r}_${c}" x1="${PAD + c * GAP}" y1="${PAD + r * GAP}" x2="${PAD + c * GAP}" y2="${PAD + (r + 1) * GAP}"/>`;
    for (let r = 0; r <= n; r++) for (let c = 0; c < n; c++) svg += `<rect class="gd-hit" data-d="h" data-r="${r}" data-c="${c}" x="${PAD + c * GAP + 10}" y="${PAD + r * GAP - 14}" width="${GAP - 20}" height="28"/>`;
    for (let r = 0; r < n; r++) for (let c = 0; c <= n; c++) svg += `<rect class="gd-hit" data-d="v" data-r="${r}" data-c="${c}" x="${PAD + c * GAP - 14}" y="${PAD + r * GAP + 10}" width="28" height="${GAP - 20}"/>`;
    for (let r = 0; r <= n; r++) for (let c = 0; c <= n; c++) svg += `<circle class="gd-dot" cx="${PAD + c * GAP}" cy="${PAD + r * GAP}" r="5.5"/>`;
    K().shell(s, `<div class="gd-dots">${svg}</svg></div>`);
    $("#gdsvg").addEventListener("click", (e) => {
      const h = e.target.closest(".gd-hit"), s2 = room();
      if (!h || !mineTurn(s2)) return;
      if ($(`#gde${h.dataset.d}${h.dataset.r}_${h.dataset.c}`).dataset.own) return;
      HUB.send({ t: "line", d: h.dataset.d, r: +h.dataset.r, c: +h.dataset.c }); HUB.haptic("medium");
    });
  }
  function paintDots(s, freshMove) {
    const ui = HUB.S.ui, g = s.game, n = g.n;
    const set = (d, r, c, own) => {
      const el = $(`#gde${d}${r}_${c}`);
      if (!el || !own) return;
      const fresh = !el.dataset.own;
      el.dataset.own = own; el.style.stroke = pcol(s, own); el.classList.add("on");
      if (fresh && freshMove) { el.classList.remove("gd-draw"); void el.getBoundingClientRect(); el.classList.add("gd-draw"); }
    };
    for (let r = 0; r <= n; r++) for (let c = 0; c < n; c++) set("h", r, c, g.h[r][c]);
    for (let r = 0; r < n; r++) for (let c = 0; c <= n; c++) set("v", r, c, g.v[r][c]);
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) {
      const own = g.boxes[r][c], el = $(`#gdb${r}_${c}`), t = $(`#gdt${r}_${c}`);
      if (own && !el.dataset.own) {
        el.dataset.own = own; el.style.fill = pcol(s, own); el.classList.add("on");
        if (freshMove) { el.classList.add("gd-fill"); t.classList.add("gd-fill"); }
        t.textContent = (K().nameOf(s, own) || "?").trim().charAt(0).toUpperCase();
      }
    }
  }
  async function applyDots(s) {
    const ui = HUB.S.ui, g = s.game, lm = g.last_move;
    if (ui.first) { ui.first = false; if (lm) ui.lastSeq = lm.seq; paintDots(s, false); }
    else {
      const fresh = lm && lm.seq > ui.lastSeq;
      if (fresh) { ui.lastSeq = lm.seq; sfx("place"); HUB.haptic(); }
      paintDots(s, fresh);
      if (fresh && lm.boxes.length) { await HUB.sleep(120); sfx("good"); HUB.tone(880, 0.12, "triangle", 0.2); await HUB.sleep(300); }
    }
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).score + " ▣" }));
    K().setHint(mineTurn(s) ? "Draw a line. Close a box to go again!" : K().turnHint(s));
    fx(ui, s);
  }

  HUB.UI.pig = { build: buildPig, apply: applyPig };
  HUB.UI.liarsdice = { build: buildLiar, apply: applyLiar };
  HUB.UI.bingo = { build: buildBingo, apply: applyBingo };
  HUB.UI.nim = { build: buildNim, apply: applyNim };
  HUB.UI.mancala = { build: buildMancala, apply: applyMancala };
  HUB.UI.dots = { build: buildDots, apply: applyDots };
})();

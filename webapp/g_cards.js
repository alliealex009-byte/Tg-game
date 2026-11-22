/* Card games: UNO, Crazy Eights, Go Fish, Blackjack, Teen Patti. Renderers register in HUB.UI. */
(function () {
  "use strict";
  window.HUB = window.HUB || { UI: {} };
  const HUB = window.HUB;
  const $ = (s, r) => (r || document).querySelector(s);
  const SYM = { S: "♠", H: "♥", D: "♦", C: "♣" };
  const UCOL = { R: "red", G: "green", B: "blue", Y: "yellow" };
  const UCN = { R: "Red", G: "Green", B: "Blue", Y: "Yellow" };
  const K = () => HUB.kit;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const RORD = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"];

  /* ---------- card faces (pure CSS) ---------- */
  const U_SKIP = '<svg viewBox="0 0 24 24" class="usv"><circle cx="12" cy="12" r="8.5" fill="none" stroke="currentColor" stroke-width="3.4"/><path d="M6 18L18 6" stroke="currentColor" stroke-width="3.4" stroke-linecap="round"/></svg>';
  const U_REV = '<svg viewBox="0 0 24 24" class="usv"><path d="M4 9h13l-3.5-3.5M20 15H7l3.5 3.5" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  function unoVal(c) {
    if (c[0] === "W") return c === "W4" ? "+4" : "";
    const k = c.slice(1);
    return k === "S" ? U_SKIP : k === "R" ? U_REV : k === "D" ? "+2" : k;
  }
  function unoFace(c) {
    const col = c[0] === "W" ? "wild" : UCOL[c[0]];
    const v = unoVal(c), small = c[0] === "W" ? (c === "W4" ? "+4" : "★") : (c.slice(1) === "S" ? "⊘" : c.slice(1) === "R" ? "⇄" : v);
    const mid = c === "W" ? '<span class="wq"><u></u><u></u><u></u><u></u></span>' : `<b>${v}</b>`;
    return `<div class="gc-card uno ${col} ${c.length > 1 && /[SRD]/.test(c.slice(1)) || c === "W4" ? "sp" : ""}" data-c="${c}"><i class="tl">${small}</i><div class="oval">${mid}</div><i class="br">${small}</i></div>`;
  }
  function stdFace(c) {
    const r = c.slice(0, -1), s = c.slice(-1), red = s === "H" || s === "D";
    return `<div class="gc-card std ${red ? "red" : "blk"}" data-c="${c}"><i class="tl">${r}<br>${SYM[s]}</i><b>${SYM[s]}</b><i class="br">${r}<br>${SYM[s]}</i></div>`;
  }
  const face = (kind, c) => (kind === "uno" ? unoFace(c) : stdFace(c));
  const back = (n) => `<div class="gc-card back"${n != null ? ` data-n="${n}"` : ""}></div>`;

  /* ---------- flying card between two elements ---------- */
  async function fly(from, to, html, ms) {
    if (!from || !to) return;
    ms = ms || 300;
    const a = from.getBoundingClientRect(), b = to.getBoundingClientRect();
    const el = document.createElement("div");
    el.className = "gc-fly"; el.innerHTML = html;
    el.style.left = a.left + a.width / 2 - 28 + "px"; el.style.top = a.top + a.height / 2 - 42 + "px";
    document.body.appendChild(el);
    const dx = b.left + b.width / 2 - a.left - a.width / 2, dy = b.top + b.height / 2 - a.top - a.height / 2;
    const rot = (Math.random() * 20 - 10) | 0;
    from.style.visibility = "hidden";  // the card leaves its slot instead of being copied
    try {
      await el.animate([
        { transform: "translate(0,0) scale(1) rotate(0deg)" },
        { transform: `translate(${dx * 0.5}px,${dy * 0.5 - 18}px) scale(1.12) rotate(${rot / 2}deg)`, offset: 0.5 },
        { transform: `translate(${dx}px,${dy}px) scale(1) rotate(${rot}deg)` },
      ], { duration: ms, easing: "cubic-bezier(.3,.7,.3,1)", fill: "forwards" }).finished;
    } catch (e) { /* cancelled */ }
    el.remove();
    from.style.visibility = "";
  }
  const chipEl = (uid) => document.querySelector(`#screen-game .gc-opp[data-uid="${uid}"]`) || document.querySelector(`#screen-game .pchip[data-uid="${uid}"]`);

  /* ---------- shared scaffolding ---------- */
  function buildCommon(type, s, extraBody) {
    K().shell(s, `<div class="gc-table" id="gct"></div><div class="gc-log" id="gclog"></div><div class="gc-actions" id="gca"></div><div class="gc-hand" id="gch"></div>${extraBody || ""}`);
    const ui = K().newUI(type, s, { lastSeq: 0, hand: null });
    ui.busy = false;
    return ui;
  }
  function newEvents(ui, g) {
    const evs = g.log ? g.log : (g.event ? [g.event] : []);
    if (ui.first) { ui.first = false; ui.lastSeq = Math.max(0, ...evs.map((e) => e.seq)); return []; }
    const out = evs.filter((e) => e.seq > ui.lastSeq);
    if (out.length) ui.lastSeq = out[out.length - 1].seq;
    return out;
  }
  function renderHand(ui, s, g, kind, opts) {
    const box = $("#gch"); if (!box) return;
    const hand = g.hand || [];
    const mine = s.status === "playing" && g.turn === s.you;
    const play = new Set(opts && opts.playable || []);
    const key = hand.join(",") + "|" + mine + "|" + [...play].join(",");
    if (ui.handKey === key) return;
    ui.handKey = key;
    if (!K().iAmPlaying(s)) { box.innerHTML = '<div class="gc-spec">👁 Watching</div>'; return; }
    const UO = { R: 0, Y: 1, G: 2, B: 3, W: 4 };
    const unoKey = (c) => UO[c[0]] * 100 + (/\d/.test(c[1] || "") ? +c.slice(1) : 20 + c.charCodeAt(1) % 10);
    const sorted = kind === "gofish" ? hand.slice().sort((a, b) => RORD.indexOf(a.slice(0, -1)) - RORD.indexOf(b.slice(0, -1)))
      : kind === "uno" ? hand.slice().sort((a, b) => unoKey(a) - unoKey(b)) : hand;
    const cw = kind === "uno" ? 70 : 56;
    const n = sorted.length, step = n > 1 ? Math.min(cw + 6, (Math.min(window.innerWidth, 440) - 70 - cw) / (n - 1)) : 0;
    box.innerHTML = `<div class="gc-fan ${kind}" style="--ov:${(step - cw).toFixed(1)}px">` + sorted.map((c, i) => {
      const ok = !opts || !opts.playable || play.has(c), mid = (n - 1) / 2, d = i - mid;
      return `<div class="gc-slot ${mine && ok ? "can" : mine ? "no" : ""}" style="--i:${i};--rot:${(d * Math.min(2.2, 12 / Math.max(1, n))).toFixed(1)}deg;--dy:${(d * d * 0.25).toFixed(1)}px;z-index:${i}">${face(kind === "uno" ? "uno" : "std", c)}</div>`;
    }).join("") + "</div>";
  }

  function logLine(text) { const l = $("#gclog"); if (l) l.textContent = text || ""; }
  const nm = (s, uid) => (uid === s.you ? "You" : K().nameOf(s, uid));

  /* ---------- colour / suit picker ---------- */
  function picker(items, cb) {
    const m = document.createElement("div");
    m.className = "gc-modal";
    m.innerHTML = '<div class="gc-pick"><div class="gc-pt">Choose</div><div class="gc-pr">' +
      items.map((it) => `<button class="gc-pb ${it.cls}" data-v="${it.v}">${it.label}</button>`).join("") + "</div></div>";
    m.addEventListener("click", (e) => {
      const b = e.target.closest(".gc-pb");
      if (b) { m.remove(); cb(b.dataset.v); } else if (e.target === m) m.remove();
    });
    document.body.appendChild(m);
  }

  /* =====================================================================
     UNO + CRAZY EIGHTS (same table, different rules)
     ===================================================================== */
  function buildPile(type, s) {
    const ui = buildCommon(type, s);
    $("#gch").addEventListener("click", (e) => {
      const slot = e.target.closest(".gc-slot.can"); if (!slot) return;
      const c = slot.firstElementChild.dataset.c;
      const wild = type === "uno" ? c[0] === "W" : c.slice(0, -1) === "8";
      const go = (extra) => { HUB.send(Object.assign({ t: "play", card: c }, extra)); HUB.haptic(); };
      if (!wild) return go({});
      if (type === "uno") picker(["R", "G", "B", "Y"].map((x) => ({ v: x, cls: "u" + UCOL[x], label: UCN[x] })), (v) => go({ color: v }));
      else picker(["S", "H", "D", "C"].map((x) => ({ v: x, cls: x === "H" || x === "D" ? "sr" : "sb", label: SYM[x] })), (v) => go({ suit: v }));
    });
    $("#gca").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      HUB.send({ t: b.dataset.t }); HUB.haptic();
    });
    return ui;
  }

  async function applyPile(s) {
    const ui = HUB.S.ui, g = s.game, kind = ui.type;
    const evs = newEvents(ui, g);
    for (const ev of evs) {
      if (ev.kind === "play") {
        const src = ev.uid === s.you ? document.querySelector(`#gch [data-c="${ev.card}"]`) : chipEl(ev.uid);
        const html = ev.uid === s.you || true ? face(kind, ev.card) : back();
        await fly(src, $("#gc-pile"), html, 340);
        HUB.sfx.place();
        if (ev.victim && ev.n) { HUB.sfx.bad(); }
        logLine(`${nm(s, ev.uid)} played ${kind === "uno" ? cardName(ev.card) : ev.card.slice(0, -1) + SYM[ev.card.slice(-1)]}` +
          (ev.n ? ` → ${nm(s, ev.victim)} draws ${ev.n}` : ""));
      } else if (ev.kind === "draw") {
        await fly($("#gc-draw"), ev.uid === s.you ? $("#gch") : chipEl(ev.uid), back(), 300);
        HUB.sfx.deal();
        logLine(`${nm(s, ev.uid)} drew ${ev.n} card${ev.n > 1 ? "s" : ""}`);
      } else if (ev.kind === "uno") {
        HUB.sfx.good(); HUB.haptic("heavy"); logLine(`🔥 ${nm(s, ev.uid)} shouts UNO!`);
        const c = chipEl(ev.uid); if (c) { c.classList.add("gc-pulse"); setTimeout(() => c.classList.remove("gc-pulse"), 900); }
      } else if (ev.kind === "pass") logLine(`${nm(s, ev.uid)} passed`);
    }
    renderPileTable(ui, s, g, kind);
    const mine = s.status === "playing" && g.turn === s.you;
    renderHand(ui, s, g, kind === "uno" ? "uno" : "std", { playable: mine ? g.playable : [] });
    const acts = [];
    if (mine) {
      if (kind === "uno") {
        if (g.phase === "play") acts.push('<button class="btn primary" data-t="draw">Draw card</button>');
        else acts.push('<button class="btn" data-t="pass">Keep & pass</button>');
      } else {
        if (g.can_draw) acts.push(`<button class="btn primary" data-t="draw">Draw (${g.draws_left} left)</button>`);
        else if (!(g.playable || []).length) acts.push('<button class="btn" data-t="pass">Pass</button>');
      }
    }
    if (kind === "uno" && K().iAmPlaying(s) && (g.hand || []).length === 1 && s.status === "playing")
      acts.push('<button class="btn gold gc-unobtn" data-t="uno">UNO!</button>');
    $("#gca").innerHTML = acts.join("");
    K().updateBar(ui, s, (uid) => { const p = g.players.find((x) => x.uid === uid); return { score: p ? "🂠" + p.n : "" }; });
    K().setHint(!K().iAmPlaying(s) ? "👁 You are watching" : mine ? (kind === "uno" && g.phase === "drawn" ? "Play the drawn card or pass" : "👉 Your turn") : K().turnHint(s));
    K().turnFx(ui, s);
  }
  function cardName(c) {
    if (c === "W") return "Wild"; if (c === "W4") return "Wild +4";
    return UCN[c[0]] + " " + ({ S: "Skip", R: "Reverse", D: "+2" }[c.slice(1)] || c.slice(1));
  }
  function renderPileTable(ui, s, g, kind) {
    const cur = g.cur;
    const hist = ui.pileHist = ui.pileHist || [];
    if (hist[hist.length - 1] !== g.top) { hist.push(g.top); if (hist.length > 4) hist.shift(); }
    const rot = (c, i) => (((c.charCodeAt(0) * 7 + (c.charCodeAt(1) || 3) * 13 + i * 29) % 36) - 18);
    const stack = hist.map((c, i) => `<div class="gc-pcard" style="transform:rotate(${i === hist.length - 1 ? 0 : rot(c, i)}deg)">${face(kind, c)}</div>`).join("");
    const ind = kind === "uno" ? `<div class="gc-col ${UCOL[cur] || ""}" title="${UCN[cur] || ""}">${UCN[cur] || ""}</div><div class="gc-dir ${g.dir === 1 ? "" : "rev"}">↻</div>`
      : `<div class="gc-suit ${cur === "H" || cur === "D" ? "red" : ""}">${SYM[cur] || ""}</div>`;
    const opp = (g.players || []).filter((p) => p.uid !== s.you).map((p) => {
      const n = Math.min(p.n, 8), cls = p.uid === g.turn ? "act" : "";
      return `<div class="gc-opp ${cls}" data-uid="${p.uid}"><div class="gc-ofan">${Array.from({ length: n }, (_, i) => `<i style="--i:${i};--n:${n}"></i>`).join("")}</div><div class="gc-on">${esc(K().nameOf(s, p.uid)).slice(0, 9)} · <b>${p.n}</b>${p.n === 1 ? " 🔥" : ""}</div></div>`;
    }).join("");
    $("#gct").innerHTML = `<div class="gc-opps">${opp}</div><div class="gc-center"><div class="gc-deck" id="gc-draw">${back()}<span>${g.draw_count}</span></div>
      <div class="gc-pile glow-${UCOL[cur] || ""}" id="gc-pile">${stack}</div><div class="gc-ind">${ind}</div></div>`;
  }

  /* =====================================================================
     GO FISH
     ===================================================================== */
  function buildGoFish(s) {
    const ui = buildCommon("gofish", s);
    ui.rank = null;
    $("#gca").addEventListener("click", (e) => {
      const r = e.target.closest("[data-rank]"), t = e.target.closest("[data-target]");
      if (r) { ui.rank = r.dataset.rank; HUB.haptic(); HUB.sfx.pop(); return applyGoFish(HUB.S.room, true); }
      if (t && ui.rank) { HUB.send({ t: "ask", target: +t.dataset.target, rank: ui.rank }); ui.rank = null; HUB.haptic(); }
    });
    return ui;
  }
  async function applyGoFish(s, local) {
    const ui = HUB.S.ui, g = s.game;
    if (!local) {
      for (const ev of newEvents(ui, g)) {
        if (ev.kind === "ask") {
          const txt = `${nm(s, ev.uid)} asked ${nm(s, ev.target)} for ${ev.rank}s — ` + (ev.got ? `got ${ev.got}!` : ev.lucky ? "Go Fish… and caught one! 🍀" : "Go Fish 🐟");
          logLine(txt);
          if (ev.got) { await fly(chipEl(ev.target), chipEl(ev.uid), back(), 380); HUB.sfx.good(); } else { HUB.sfx.flip(); await sleep(250); }
          if (ev.books && ev.books.length) { HUB.sfx.cash(); HUB.haptic("heavy"); logLine(txt + "  📘 Book!"); }
        }
      }
    }
    const mine = s.status === "playing" && g.turn === s.you;
    $("#gct").innerHTML = `<div class="gc-center"><div class="gc-deck">${back()}<span>${g.draw_count}</span></div></div><div class="gc-books">` +
      g.players.map((p) => `<div class="gc-bk"><b>${esc(K().nameOf(s, p.uid))}</b> 📘 ${p.books.map((r) => `<em>${r}</em>`).join("") || "–"}</div>`).join("") + "</div>";
    ui.handKey = null;
    renderHand(ui, s, g, "gofish", { playable: null });
    let acts = "";
    if (mine) {
      const ranks = [...new Set((g.hand || []).map((c) => c.slice(0, -1)))].sort((a, b) => RORD.indexOf(a) - RORD.indexOf(b));
      acts = `<div class="gc-row">${ranks.map((r) => `<button class="btn sm ${ui.rank === r ? "primary" : ""}" data-rank="${r}">${r}</button>`).join("")}</div>`;
      acts += `<div class="gc-row">${(g.targets || []).map((u) => `<button class="btn sm gold" data-target="${u}" ${ui.rank ? "" : "disabled"}>Ask ${esc(K().nameOf(s, u))}</button>`).join("")}</div>`;
    }
    $("#gca").innerHTML = acts;
    K().updateBar(ui, s, (uid) => { const p = g.players.find((x) => x.uid === uid); return { score: p ? `🂠${p.n} 📘${p.books.length}` : "" }; });
    K().setHint(!K().iAmPlaying(s) ? "👁 You are watching" : mine ? (ui.rank ? "Now pick who to ask" : "Pick a rank you hold") : K().turnHint(s));
    if (!local) K().turnFx(ui, s);
  }
  const esc = (t) => HUB.esc(String(t == null ? "" : t));

  /* =====================================================================
     BLACKJACK
     ===================================================================== */
  function buildBJ(s) {
    const ui = buildCommon("blackjack", s);
    $("#gca").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      HUB.send(b.dataset.amount ? { t: "bet", amount: +b.dataset.amount } : { t: b.dataset.t });
      if (b.dataset.amount) HUB.sfx.chip(); HUB.haptic();
    });
    return ui;
  }
  const ST = { bet: "betting…", wait: "ready", play: "playing", stand: "stand", bust: "BUST", bj: "BLACKJACK!", out: "out" };
  async function applyBJ(s) {
    const ui = HUB.S.ui, g = s.game;
    for (const ev of newEvents(ui, g)) {
      if (ev.kind === "bet") HUB.sfx.chip();
      else if (ev.kind === "deal" || ev.kind === "dealer_hit") { HUB.sfx.deal(); await sleep(150); }
      else if (ev.kind === "hit" || ev.kind === "reveal") { HUB.sfx.flip(); await sleep(120); }
      else if (ev.kind === "bust") { HUB.sfx.bad(); HUB.haptic("heavy"); }
      else if (ev.kind === "result") {
        const me = ev.results && ev.results[s.you];
        if (me) { me.delta > 0 ? (HUB.sfx.cash(), HUB.haptic("heavy")) : me.delta < 0 ? HUB.sfx.bad() : HUB.sfx.pop(); }
        logLine(me ? `${me.outcome.toUpperCase()} ${me.delta > 0 ? "+" : ""}${me.delta}` : "Round over");
      }
    }
    const mine = s.status === "playing" && g.turn === s.you;
    const dealer = g.dealer.map((c) => (c ? stdFace(c) : back())).join("");
    $("#gct").innerHTML = `<div class="gc-dealer"><div class="gc-lbl">Dealer ${g.dealer_total != null ? "· " + g.dealer_total : ""}</div><div class="gc-cards">${dealer || '<span class="gc-dim">—</span>'}</div></div>
      <div class="gc-rnd">Round ${g.round}/${g.rounds}</div>` +
      g.players.map((p) => `<div class="gc-seat ${p.uid === s.you ? "me" : ""} ${g.turn === p.uid && g.phase === "play" ? "act" : ""}">
        <div class="gc-lbl">${esc(K().nameOf(s, p.uid))} · 💰${p.stack}${p.bet ? " · 🎰" + p.bet : ""} <em class="gc-st ${p.state}">${ST[p.state] || ""}${p.total ? " " + p.total : ""}</em></div>
        <div class="gc-cards">${p.hand.map(stdFace).join("")}</div></div>`).join("");
    const me = g.players.find((p) => p.uid === s.you);
    let acts = "";
    if (s.status === "playing" && me) {
      if (g.phase === "bet" && me.state === "bet") acts = g.bets.map((b) => `<button class="btn gold gc-chipbtn" data-amount="${b}">${b}</button>`).join("");
      else if (mine) acts = '<button class="btn primary" data-t="hit">Hit</button><button class="btn" data-t="stand">Stand</button>' +
        (g.can_double ? '<button class="btn gold" data-t="double">Double</button>' : "");
    }
    $("#gca").innerHTML = acts;
    $("#gch").innerHTML = "";
    K().updateBar(ui, s, (uid) => { const p = g.players.find((x) => x.uid === uid); return { score: p ? "💰" + p.stack : "" }; });
    K().setHint(!K().iAmPlaying(s) ? "👁 You are watching" : g.phase === "bet" ? (me && me.state === "bet" ? "Place your bet" : "Waiting for bets…") : mine ? "👉 Your move" : K().turnHint(s));
    K().turnFx(ui, s);
  }

  /* =====================================================================
     TEEN PATTI
     ===================================================================== */
  function buildTP(s) {
    const ui = buildCommon("teenpatti", s);
    $("#gca").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      const t = b.dataset.t;
      HUB.send(t === "raise" ? { t: "chaal", raise: true } : { t }); HUB.haptic();
      if (t === "chaal" || t === "raise") HUB.sfx.chip();
    });
    return ui;
  }
  async function applyTP(s) {
    const ui = HUB.S.ui, g = s.game;
    for (const ev of newEvents(ui, g)) {
      const who = nm(s, ev.uid);
      if (ev.kind === "deal") { HUB.sfx.deal(); logLine(`Round ${ev.round}: boot collected, cards dealt`); await sleep(250); }
      else if (ev.kind === "chaal" || ev.kind === "raise") { HUB.sfx.chip(); logLine(`${who} ${ev.kind === "raise" ? "raised" : "chaal"} ${ev.amount}`); }
      else if (ev.kind === "pack") { HUB.sfx.flip(); logLine(`${who} packed`); }
      else if (ev.kind === "see") { if (ev.uid === s.you) HUB.sfx.flip(); logLine(`${who} saw their cards`); }
      else if (ev.kind === "show") { HUB.sfx.good(); logLine(`${who} asked for a show!`); }
      else if (ev.kind === "round_end") {
        const win = ev.winners.includes(s.you);
        win ? (HUB.sfx.cash(), HUB.haptic("heavy")) : HUB.sfx.bad();
        logLine(`${ev.winners.map((u) => nm(s, u)).join(" & ")} won ${ev.pot}`);
      }
    }
    const mine = s.status === "playing" && g.turn === s.you;
    const lr = g.last_round, reveal = lr && lr.hands && Object.keys(lr.hands).length && !g.players.some((p) => p.n);
    const rows = g.players.map((p) => `<div class="gc-seat ${p.uid === s.you ? "me" : ""} ${g.turn === p.uid ? "act" : ""} ${p.state}">
      <div class="gc-lbl">${esc(K().nameOf(s, p.uid))} · 💰${p.stack} <em class="gc-st ${p.state}">${p.state}</em>${p.put ? " · in " + p.put : ""}</div>
      <div class="gc-cards">${p.n ? [0, 1, 2].map((i) => (p.uid === s.you && g.hand.length ? stdFace(g.hand[i]) : back())).join("") :
        (reveal && lr.hands[p.uid] ? lr.hands[p.uid].map(stdFace).join("") + `<em class="gc-st">${esc(lr.ranks[p.uid] || "")}</em>` : "")}</div></div>`).join("");
    $("#gct").innerHTML = `<div class="gc-pot"><div class="gc-potc">🪙 ${g.pot}</div><div class="gc-dim">stake ${g.stake} · round ${g.round}/${g.rounds}</div></div>${rows}`;
    let acts = "";
    if (K().iAmPlaying(s) && s.status === "playing") {
      const meRow = g.players.find((p) => p.uid === s.you);
      if (meRow && meRow.state === "blind") acts += '<button class="btn" data-t="see">👁 See cards</button>';
      if (mine) {
        if (g.cost != null) acts += `<button class="btn primary" data-t="chaal">Chaal ${g.cost}</button>`;
        if (g.raise_cost != null) acts += `<button class="btn gold" data-t="raise">Raise ${g.raise_cost}</button>`;
        acts += '<button class="btn danger" data-t="pack">Pack</button>';
        if (g.can_show) acts += '<button class="btn" data-t="show">Show</button>';
      }
    }
    $("#gca").innerHTML = acts;
    $("#gch").innerHTML = g.hand_rank ? `<div class="gc-spec">Your hand: <b>${esc(g.hand_rank)}</b></div>` : "";
    K().updateBar(ui, s, (uid) => { const p = g.players.find((x) => x.uid === uid); return { score: p ? "💰" + p.stack : "" }; });
    K().setHint(!K().iAmPlaying(s) ? "👁 You are watching" : mine ? "👉 Your turn" : K().turnHint(s));
    K().turnFx(ui, s);
  }

  HUB.UI.uno = { build: (s) => buildPile("uno", s), apply: applyPile };
  HUB.UI.crazy8 = { build: (s) => buildPile("crazy8", s), apply: applyPile };
  HUB.UI.gofish = { build: buildGoFish, apply: applyGoFish };
  HUB.UI.blackjack = { build: buildBJ, apply: applyBJ };
  HUB.UI.teenpatti = { build: buildTP, apply: applyTP };
})();

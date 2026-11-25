/* Football (2 players): snake-draft a squad of world stars, then play two halves of tactical attacks on an animated pitch,
   with half-time subs and a penalty shootout if tied. Pure canvas + DOM; all outcomes come from the server engine. */
(function () {
  "use strict";
  window.HUB = window.HUB || { UI: {} };
  const HUB = window.HUB;
  const $ = (s, r) => (r || document).querySelector(s);
  const K = () => HUB.kit;
  const sfx = (n) => { try { HUB.sfx[n](); } catch (e) { /* ignore */ } };
  const tone = (...a) => { try { HUB.tone(...a); } catch (e) { /* ignore */ } };
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const nm = (s, u) => (u === s.you ? "You" : K().nameOf(s, u));
  const playing = (s) => s.game.players.some((p) => p.uid === s.you);
  const raf = () => new Promise((r) => requestAnimationFrame(r));
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const ease = (t) => (t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
  const lerp = (a, b, t) => a + (b - a) * t;

  const ACT = { short: ["➡️", "Pass"], through: ["🎯", "Through ball"], dribble: ["🌀", "Dribble"], long: ["🚀", "Long ball"], cross: ["📐", "Cross"], shoot: ["🔥", "Shoot"] };
  const ZACT = { 0: ["short", "through", "dribble", "long"], 1: ["short", "through", "dribble", "long", "shoot"], 2: ["short", "through", "dribble", "cross", "shoot"] };
  const STANCE = { press: ["🏃", "Press"], hold: ["🧱", "Hold shape"], intercept: ["✋", "Intercept"], tackle: ["🦵", "Tackle"], drop: ["⬇️", "Drop deep"], mark: ["👤", "Man-mark"] };
  const ZONE = ["Own half", "Midfield", "Final third"];
  const ROLES = ["ALL", "GK", "DEF", "MID", "FWD"];
  const DIRL = { l: "Left", c: "Centre", r: "Right" };

  const PW = 340, PH = 220, X0 = 14, X1 = 326, Y0 = 10, Y1 = 210, MY = 110;
  const LANES = [-52, -18, 18, 52];
  const short = (n) => String(n || "").split(" ").slice(-1)[0].slice(0, 9);

  function pmap(g) {
    const m = {};
    (g.roster || []).forEach((p) => { m[p.id] = p; });
    Object.values(g.squads || {}).forEach((a) => a.forEach((p) => { m[p.id] = p; }));
    return m;
  }
  const right = (g) => g.players.some((p) => p.uid === HUB.S.room.you) ? HUB.S.room.you : g.players[0].uid;
  const pxOf = (g, team, p) => (team === right(g) ? X0 + p * (X1 - X0) : X0 + (1 - p) * (X1 - X0));

  /* ---------------- drawing ---------------- */
  function draw(ctx, s, st) {
    const g = s.game, R = pmap(g), me = right(g), opp = g.players.find((p) => p.uid !== me).uid;
    const grd = ctx.createLinearGradient(0, 0, 0, PH); grd.addColorStop(0, "#0b3d1f"); grd.addColorStop(1, "#0f5a2c"); ctx.fillStyle = grd; ctx.fillRect(0, 0, PW, PH);
    for (let i = 0; i < 12; i++) { ctx.fillStyle = i % 2 ? "#1b7a3a" : "#228b43"; ctx.fillRect(X0 + i * (X1 - X0) / 12, Y0, (X1 - X0) / 12 + 1, Y1 - Y0); }
    ctx.strokeStyle = "#ffffffcc"; ctx.lineWidth = 1.6; ctx.strokeRect(X0, Y0, X1 - X0, Y1 - Y0);
    ctx.beginPath(); ctx.moveTo((X0 + X1) / 2, Y0); ctx.lineTo((X0 + X1) / 2, Y1); ctx.stroke();
    ctx.beginPath(); ctx.arc((X0 + X1) / 2, MY, 26, 0, 7); ctx.stroke();
    [[X0, 1], [X1, -1]].forEach(([x, d]) => { ctx.strokeRect(d > 0 ? x : x - 46, MY - 48, 46, 96); ctx.strokeRect(d > 0 ? x : x - 16, MY - 22, 16, 44); ctx.fillStyle = "#ffffff55"; ctx.fillRect(d > 0 ? x - 8 : x, MY - 20, 8, 40); ctx.strokeStyle = "#fff"; ctx.strokeRect(d > 0 ? x - 8 : x, MY - 20, 8, 40); ctx.strokeStyle = "#ffffffcc"; });
    if (st.flash > 0) { ctx.fillStyle = `rgba(255,230,120,${st.flash * .35})`; ctx.fillRect(0, 0, PW, PH); }
    // crowd bob
    ctx.fillStyle = "#0d1b3a"; ctx.fillRect(0, 0, PW, Y0 - 1); ctx.fillRect(0, Y1 + 1, PW, PH - Y1);
    for (let i = 0; i < 40; i++) { const cx = 8 + i * 8.2, bob = st.crowd > 0 ? Math.abs(Math.sin(st.t * 11 + i)) * 3 : 0; ctx.fillStyle = ["#ef5350", "#ffd54f", "#42a5f5", "#fff"][i % 4]; ctx.beginPath(); ctx.arc(cx, 5 - bob, 2.2, 0, 7); ctx.fill(); ctx.beginPath(); ctx.arc(cx + 3, PH - 5 + bob * .5, 2.2, 0, 7); ctx.fill(); }
    // tokens
    const a = g.attack, lu = g.lineup || {}, bp = st.bp;
    const tok = (team, id, i, isGk) => {
      const p = R[id]; if (!p || p.off) return;
      let x, y;
      if (isGk) { x = pxOf(g, team, .04) + (team === me ? 6 : -6); y = MY + (st.gk && st.gk.team === team ? st.gk.dy : 0); if (st.gk && st.gk.team === team) x += (team === me ? 1 : -1) * st.gk.dx; }
      else {
        const att = a && a.team === team, base = [.22, .36, .5, .64][i % 4];
        const shift = (bp - .5) * (att ? .55 : .35) * (att ? 1 : 1);
        const prog = att ? clamp01(base + shift + .08) : clamp01((1 - base) * .98 - (bp - .5) * .45 + (att ? 0 : .02));
        x = pxOf(g, team, att ? prog : 1 - clamp01(.78 - base * .6 + (.5 - bp) * .0 + (bp - .5) * .4));
        y = MY + LANES[i % 4] + Math.sin(st.t * 2 + i * 1.7 + (team === me ? 0 : 2)) * 3;
        if (st.focus && st.focus.id === id) { x = st.focus.x; y = st.focus.y; }
      }
      ctx.fillStyle = "#0005"; ctx.beginPath(); ctx.ellipse(x + 1, y + 6, 7, 3, 0, 0, 7); ctx.fill();
      ctx.fillStyle = team === me ? "#1e88e5" : "#e53935"; ctx.beginPath(); ctx.arc(x, y, isGk ? 7.5 : 7, 0, 7); ctx.fill();
      ctx.lineWidth = 1.8; ctx.strokeStyle = isGk ? "#ffd54f" : "#fff"; ctx.stroke();
      if (a && a.holder === id) { ctx.strokeStyle = "#ffd24a"; ctx.lineWidth = 2.6; ctx.beginPath(); ctx.arc(x, y, 10.5, 0, 7); ctx.stroke(); st.hx = x; st.hy = y; }
      ctx.fillStyle = "#fff"; ctx.font = "bold 5.5px sans-serif"; ctx.textAlign = "center"; ctx.fillText((p.ovr || ""), x, y + 2);
      ctx.fillStyle = "#fffd"; ctx.font = "5.5px sans-serif"; ctx.fillText(short(p.name), x, y + 15);
      if (p.yc) { ctx.fillStyle = "#ffd600"; ctx.fillRect(x + 5, y - 11, 4, 6); }
      st.pos[id] = [x, y];
    };
    st.pos = {};
    [me, opp].forEach((u) => { const l = lu[u] || []; let i = 0; l.forEach((id) => { if (R[id] && R[id].role === "GK") tok(u, id, 0, true); else tok(u, id, i++, false); }); });
    const b = st.ball;
    if (b) { ctx.fillStyle = "#0007"; ctx.beginPath(); ctx.ellipse(b.x, b.y + 3, 4 - b.h * .02, 2, 0, 0, 7); ctx.fill(); ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(b.x, b.y - b.h, 3.6, 0, 7); ctx.fill(); ctx.strokeStyle = "#000"; ctx.lineWidth = .8; ctx.stroke(); }
    if (st.card) { ctx.fillStyle = st.card.kind === "red" ? "#e53935" : "#ffd600"; ctx.fillRect(PW / 2 - 9, MY - 16, 18, 26); }
  }
  const clamp01 = (v) => Math.max(.04, Math.min(.96, v));

  /* ---------------- build ---------------- */
  function build(s) {
    K().newUI("football", s, { lastSeq: -1, busy: false, q: [], sel: {}, tab: "ALL", st: { t: 0, crowd: 0, flash: 0, bp: .5, ball: null, gk: null, focus: null, card: null, pos: {} }, raf: 0 });
    K().shell(s, `<div class="fb-box">
      <div class="fb-tv" id="fbtv"></div>
      <div class="fb-fieldwrap"><canvas id="fbc" width="${PW * 2}" height="${PH * 2}"></canvas><div class="fb-banner" id="fbban"></div></div>
      <div class="fb-comm" id="fbcomm">Welcome to the match!</div>
      <div class="fb-panel" id="fbpanel"></div></div>`);
    const ui = HUB.S.ui, ctx = $("#fbc").getContext("2d"); ctx.scale(2, 2);
    ui.draw = () => { ctx.save(); draw(ctx, HUB.S.room, ui.st); ctx.restore(); };
    ui.draw();
    $("#fbpanel").onclick = onPanel;
  }
  const banner = (t, cls) => { const b = $("#fbban"); if (b) { b.textContent = t; b.className = "fb-banner show " + (cls || ""); } };
  const unbanner = () => { const b = $("#fbban"); if (b) b.className = "fb-banner"; };
  const say = (t) => { const c = $("#fbcomm"); if (c) c.textContent = t; };

  function tv(s) {
    const g = s.game, el = $("#fbtv"); if (!el) return;
    const [a, b] = g.players;
    const mm = g.stage === "pens" ? "PENS" : g.stage === "draft" ? "DRAFT" : g.stage === "done" ? "FT" : g.minute + "'";
    const sc = (u) => (g.stage === "pens" && g.pens ? `${g.players.find((p) => p.uid === u).score}<small> (${g.pens.goals[u]})</small>` : g.players.find((p) => p.uid === u).score);
    el.innerHTML = `<div class="fb-tvrow"><b>${esc(nm(s, a.uid))}</b><span class="fb-score">${sc(a.uid)} - ${sc(b.uid)}</span><b class="r">${esc(nm(s, b.uid))}</b></div>
      <div class="fb-tvsub"><span class="fb-clock">${mm}</span> ${g.stage === "play" || g.stage === "sub" ? `· ${g.half === 1 ? "1st" : "2nd"} half · attack ${Math.min(g.slot + 1, g.per_half)}/${g.per_half}` : ""}
      ${g.attack && g.stage === "play" ? `· <b>${esc(nm(s, g.attack.team))}</b> attack · ${ZONE[g.attack.zone]}${g.attack.counter ? " · ⚡ counter" : ""}${g.attack.opening ? " · 🎯 open play" : ""}` : ""}</div>`;
  }

  /* ---------------- panels ---------------- */
  const bar = (v, c) => `<span class="fb-bar ${c || ""}"><i style="--v:${Math.min(100, v)}%"></i></span>`;
  function card(p, cls, data) {
    const gk = p.role === "GK";
    return `<button class="fb-card ${cls || ""}" ${data || ""}><span class="fb-flag">${p.flag}</span><b>${esc(p.name)}</b><small>${p.role} · <u>${p.ovr}</u></small>
      ${gk ? `<span class="fb-r"><em>GK</em>${bar(p.gk, "b")}</span>` : `<span class="fb-r"><em>PAC</em>${bar(p.pac)}</span><span class="fb-r"><em>SHO</em>${bar(p.sho, "b")}</span><span class="fb-r"><em>PAS</em>${bar(p.pas)}</span><span class="fb-r"><em>DRI</em>${bar(p.dri, "b")}</span><span class="fb-r"><em>DEF</em>${bar(p.dfn)}</span>`}</button>`;
  }
  function mini(p, cls, data, extra) {
    return `<button class="fb-mini ${cls || ""}" ${data || ""} ${p.off ? "disabled" : ""}><span>${p.flag}</span><b>${esc(short(p.name))}</b><small>${p.role} ${p.ovr}${p.yc ? " 🟨" : ""}</small>${bar(p.stam, p.stam < 45 ? "low" : "")}${extra || ""}</button>`;
  }

  function panel(s) {
    const g = s.game, el = $("#fbpanel"), ui = HUB.S.ui; if (!el) return;
    const R = pmap(g), me = s.you, mine = playing(s), sel = ui.sel, pend = g.pending || [];
    const myTurn = mine && pend.includes(me) && !g.picked[me];
    const locked = mine && g.picked && g.picked[me] && g.stage !== "draft";
    if (g.stage === "done" || g.winner != null || g.draw) {
      const w = g.draw ? "🤝 Draw!" : g.winner === me ? "🏆 You win!" : mine ? `${esc(nm(s, g.winner))} wins` : `🏆 ${esc(nm(s, g.winner))} wins`;
      const [a, b] = g.players, S = g.stats;
      const row = (k, l) => `<tr><td>${S[a.uid][k]}</td><th>${l}</th><td>${S[b.uid][k]}</td></tr>`;
      el.innerHTML = `<div class="fb-result">${w}</div><div class="fb-final">${esc(nm(s, a.uid))} ${a.score} - ${b.score} ${esc(nm(s, b.uid))}${g.pens ? ` <small>(pens ${g.pens.goals[a.uid]}-${g.pens.goals[b.uid]})</small>` : ""}</div>
        <table class="fb-tbl">${row("shots", "Shots")}${row("on", "On target")}${row("corners", "Corners")}${row("fouls", "Fouls")}${row("yc", "Cards")}</table>`;
      return;
    }
    if (g.stage === "draft") {
      const order = g.draft.order, picker = order[g.draft.i], yours = picker === me && mine;
      const ssum = (u) => `<div class="fb-sq"><b>${esc(nm(s, u))}</b> ${(g.squads[u] || []).map((p) => `<span>${p.flag} ${esc(short(p.name))} <u>${p.ovr}</u></span>`).join("") || "<span>–</span>"}</div>`;
      const pool = (g.roster || []).filter((p) => g.pool.includes(p.id) && (ui.tab === "ALL" || p.role === ui.tab));
      el.innerHTML = `<div class="fb-h">${yours ? "👉 Your pick — build your squad (1 GK + 5 outfield)" : "⏳ " + esc(nm(s, picker)) + " is picking…"} <small>pick ${g.draft.i + 1}/${order.length}</small></div>
        ${ssum(g.players[0].uid)}${ssum(g.players[1].uid)}
        <div class="fb-tabs">${ROLES.map((r) => `<button data-tab="${r}" class="${ui.tab === r ? "on" : ""}">${r}</button>`).join("")}</div>
        <div class="fb-pool">${pool.map((p) => card(p, "", yours ? `data-pick="${p.id}"` : "disabled")).join("")}</div>`;
      return;
    }
    if (g.stage === "play" && g.attack) {
      const a = g.attack, att = a.team === me;
      if (!mine) { el.innerHTML = `<div class="fb-wait">👀 Watching · ${esc(nm(s, a.team))} attacking from ${ZONE[a.zone].toLowerCase()}</div>`; return; }
      if (locked) { el.innerHTML = `<div class="fb-wait">🔒 Locked in — waiting for ${esc(nm(s, g.players.find((p) => p.uid !== me).uid))}…</div>`; return; }
      if (att) {
        const acts = ZACT[a.zone], ids = g.lineup[me].filter((id) => R[id] && !R[id].off && (R[id].role !== "GK" || (a.zone === 0 && ["short", "long"].includes(sel.act))));
        el.innerHTML = `<div class="fb-h">⚔️ Attack from ${ZONE[a.zone]} — choose the move, then who does it</div>
          <div class="fb-opts">${acts.map((k) => `<button data-act="${k}" class="${sel.act === k ? "on" : ""}">${ACT[k][0]}<span>${ACT[k][1]}</span></button>`).join("")}</div>
          <div class="fb-minis">${ids.map((id) => mini(R[id], sel.who === id ? "on" : "", `data-who="${id}"`, a.holder === id ? "<s class=\"fb-ball\">⚽</s>" : "")).join("")}</div>
          <div class="fb-go"><button class="fb-primary" data-go="1" ${sel.act && sel.who ? "" : "disabled"}>Go! ⚡</button></div>`;
      } else {
        const ids = g.lineup[a.team].filter((id) => R[id] && R[id].role !== "GK" && !R[id].off);
        el.innerHTML = `<div class="fb-h">🛡️ Defend — pick a stance${sel.stance === "mark" ? " and the attacker to man-mark" : " (optionally mark one)"}</div>
          <div class="fb-opts">${Object.keys(STANCE).map((k) => `<button data-stance="${k}" class="${sel.stance === k ? "on" : ""}">${STANCE[k][0]}<span>${STANCE[k][1]}</span></button>`).join("")}</div>
          <div class="fb-minis">${ids.map((id) => mini(R[id], sel.mark === id ? "on" : "", `data-mark="${id}"`, a.holder === id ? "<s class=\"fb-ball\">⚽</s>" : "")).join("")}</div>
          <div class="fb-go"><button class="fb-primary" data-go="1" ${sel.stance && (sel.stance !== "mark" || sel.mark) ? "" : "disabled"}>Set defence 🛡️</button></div>`;
      }
      return;
    }
    if (g.stage === "sub") {
      if (!mine) { el.innerHTML = `<div class="fb-wait">⏸️ Half-time — teams are talking tactics</div>`; return; }
      if (locked) { el.innerHTML = `<div class="fb-wait">🔒 Locked in — waiting for the opponent…</div>`; return; }
      const bn = g.bench[me], ids = g.lineup[me].filter((id) => R[id] && R[id].role !== "GK" && !R[id].off);
      el.innerHTML = `<div class="fb-h">⏸️ Half-time: ${bn ? "swap a tired player for your fresh sub?" : "no substitute available"}</div>
        ${bn ? `<div class="fb-minis"><div class="fb-in">Bench ⬆️ ${mini(R[bn], "", "disabled")}</div>${ids.map((id) => mini(R[id], sel.out === id ? "on" : "", `data-out="${id}"`)).join("")}</div>` : ""}
        <div class="fb-go"><button class="fb-primary" data-sub="1" ${sel.out ? "" : "disabled"}>Substitute 🔁</button><button data-keep="1">Keep team ▶️</button></div>`;
      return;
    }
    if (g.stage === "pens" && g.pens) {
      const P = g.pens, sh = P.shooter, hist = P.history || [];
      const dots = (u) => hist.filter((h) => h.uid === u).map((h) => `<i class="${h.outcome === "goal" ? "g" : "m"}">${h.outcome === "goal" ? "⚽" : "✖"}</i>`).join("");
      const dd = `<div class="fb-pdots"><span>${esc(nm(s, g.players[0].uid))} ${dots(g.players[0].uid)}</span><span>${esc(nm(s, g.players[1].uid))} ${dots(g.players[1].uid)}</span></div>`;
      if (!mine) { el.innerHTML = dd + `<div class="fb-wait">👀 Penalty shootout</div>`; return; }
      if (locked) { el.innerHTML = dd + `<div class="fb-wait">🔒 Locked in…</div>`; return; }
      const taking = sh === me, name = R[P.order[sh][P.taken[sh] % P.order[sh].length]];
      el.innerHTML = dd + `<div class="fb-h">${taking ? "🥅 You take the penalty" + (name ? " — " + esc(name.name) : "") + ": pick your corner" : "🧤 Save it! Pick the way to dive"}</div>
        <div class="fb-opts l">${["l", "c", "r"].map((d) => `<button data-dir="${d}">${d === "l" ? "⬅️" : d === "c" ? "⬆️" : "➡️"}<span>${DIRL[d]}</span></button>`).join("")}</div>`;
      return;
    }
    el.innerHTML = `<div class="fb-wait">…</div>`;
  }

  function onPanel(e) {
    const s = HUB.S.room, ui = HUB.S.ui; if (!s || !playing(s) || ui.busy) return;
    const t = e.target.closest("button"); if (!t || t.disabled) return;
    const d = t.dataset, sel = ui.sel, g = s.game, a = g.attack;
    const send = (m) => { HUB.send(m); ui.sel = {}; HUB.haptic("medium"); sfx("pop"); };
    if (d.tab) { ui.tab = d.tab; return panel(s); }
    if (d.pick) return send({ t: "pick", id: d.pick });
    if (d.act) { sel.act = d.act; if (sel.who && g.lineup[s.you].length && !g.squads[s.you].find((p) => p.id === sel.who && p.role !== "GK") && !(a.zone === 0 && ["short", "long"].includes(d.act))) sel.who = null; sfx("pop"); return panel(s); }
    if (d.who) { sel.who = d.who; sfx("pop"); return panel(s); }
    if (d.stance) { sel.stance = d.stance; sfx("pop"); return panel(s); }
    if (d.mark) { sel.mark = sel.mark === d.mark && sel.stance !== "mark" ? null : d.mark; sfx("pop"); return panel(s); }
    if (d.go) { if (a.team === s.you) return send({ t: "act", act: sel.act, who: sel.who }); return send({ t: "def", stance: sel.stance, mark: sel.mark || null }); }
    if (d.out) { sel.out = d.out; return panel(s); }
    if (d.sub) return send({ t: "sub", out: sel.out });
    if (d.keep) return send({ t: "sub", out: null });
    if (d.dir) return send({ t: "dir", dir: d.dir });
  }

  /* ---------------- animation ---------------- */
  async function tween(ui, ms, fn) { const t0 = performance.now(); for (;;) { const k = Math.min(1, (performance.now() - t0) / ms); ui.st.t += .016; fn(ease(k), k); ui.draw(); if (k >= 1) break; await raf(); } }
  const goalXY = (g, defTeam, dir) => { const x = defTeam === right(g) ? X0 - 2 : X1 + 2; return [x, MY + (dir === "l" ? -16 : dir === "r" ? 16 : 0) * (defTeam === right(g) ? 1 : -1)]; };

  async function playShot(s, ev, sh) {
    const g = s.game, ui = HUB.S.ui, st = ui.st, R = pmap(g);
    const defTeam = ev.def != null ? ev.def : ev.att === g.players[0].uid ? g.players[1].uid : g.players[0].uid;
    const from = sh.__from || st.pos[sh.shooter] || [st.hx || PW / 2, st.hy || MY];
    const [gx, gy] = goalXY(g, defTeam, sh.dir);
    const dive = sh.outcome === "saved" ? sh.dir : ["l", "c", "r"].filter((d) => d !== sh.dir)[Math.random() * 2 | 0];
    const dv = dive === "l" ? -1 : dive === "r" ? 1 : 0;
    banner(ev.shots.length > 1 || sh.kind === "corner" ? "SHOT!" : "SHOOTS!"); sfx("turn");
    let tx = gx, ty = gy; if (sh.outcome === "off") { ty = gy + (Math.random() < .5 ? -34 : 34); } if (sh.outcome === "blocked") { tx = lerp(from[0], gx, .45); ty = lerp(from[1], gy, .45); }
    await tween(ui, 520, (k) => { st.ball = { x: lerp(from[0], tx, k), y: lerp(from[1], ty, k), h: Math.sin(k * Math.PI) * 6 }; st.gk = sh.outcome === "goal" || sh.outcome === "saved" ? { team: defTeam, dx: 0, dy: dv * 18 * (defTeam === right(g) ? 1 : -1) * k } : null; });
    if (sh.outcome === "goal") { banner("GOAL!!! ⚽", "big"); st.flash = 1; st.crowd = 2.4; sfx("win"); HUB.haptic("success"); if (HUB.confetti) HUB.confetti(48); for (let i = 0; i < 7; i++) tone(280 + Math.random() * 520, .14, "sawtooth", .05); say(`GOAL! ${R[sh.shooter] ? R[sh.shooter].name : ""} scores!`); }
    else if (sh.outcome === "saved") { banner("SAVED! 🧤", "save"); sfx("bad"); st.ball = { x: gx + (defTeam === right(g) ? 14 : -14), y: gy, h: 0 }; say(`${R[sh.keeper] ? R[sh.keeper].name : "Keeper"} with a great save!`); }
    else if (sh.outcome === "blocked") { banner("BLOCKED 🛡️", "save"); sfx("pop"); }
    else { banner("WIDE 💨"); sfx("pop"); }
    const end = performance.now() + (sh.outcome === "goal" ? 1700 : 900);
    while (performance.now() < end) { st.t += .016; st.flash = Math.max(0, st.flash - .02); st.crowd = Math.max(0, st.crowd - .016); ui.draw(); await raf(); }
    st.gk = null; st.flash = 0; unbanner();
  }

  async function playPhase(s, ev) {
    const g = s.game, ui = HUB.S.ui, st = ui.st, R = pmap(g);
    const W = R[ev.who], P0 = [0, 0.2, 0.5, 0.8][ev.zone + 1] || .5;
    const p0 = [.2, .5, .8][ev.zone], p1 = [.2, .5, .8][ev.zone2 != null ? ev.zone2 : ev.zone];
    st.bp = p0; ui.draw();
    const an = ACT[ev.act] ? ACT[ev.act][1] : "";
    say(`${W ? W.name : ""} ${an ? "→ " + an.toLowerCase() : ""} vs ${STANCE[ev.stance] ? STANCE[ev.stance][1].toLowerCase() : ""}${ev.mark && R[ev.mark] ? " (marking " + R[ev.mark].name + ")" : ""}`);
    banner(`${ACT[ev.act] ? ACT[ev.act][0] : ""} ${an}`.trim()); sfx("turn");
    await sleep(520);
    if (ev.act !== "shoot" || !ev.shots.length) {
      const a = [pxOf(g, ev.att, p0), MY + (Math.random() - .5) * 60], b = [pxOf(g, ev.att, ev.result === "lost" ? Math.max(.1, p0 - .12) : p1), MY + (Math.random() - .5) * 70];
      const hi = ev.act === "long" || ev.act === "cross" ? 18 : 5;
      if (ev.act === "dribble") {
        await tween(ui, 600, (k) => { st.ball = { x: lerp(a[0], b[0], k), y: lerp(a[1], b[1], k) + Math.sin(k * 14) * 2, h: 0 }; st.bp = lerp(p0, p1, k); });
      } else await tween(ui, ev.act === "long" ? 760 : 560, (k) => { st.ball = { x: lerp(a[0], b[0], k), y: lerp(a[1], b[1], k), h: Math.sin(k * Math.PI) * hi }; st.bp = lerp(p0, p1, k); });
    }
    if (ev.result === "adv" || ev.result === "open") { banner(ev.result === "open" ? "IN BEHIND! 🎯" : ev.zone2 > ev.zone ? "ADVANCING ➡️" : "KEEPS IT"); sfx("good"); }
    else if (ev.result === "lost") { banner(ev.counter ? "TURNOVER — COUNTER! ⚡" : "WON BACK 🛡️", "save"); sfx("bad"); }
    else if (ev.result === "wasted") banner("RUNS OUT OF IDEAS");
    if (ev.foul) { banner(ev.foul.kind === "pen" ? "PENALTY! 🟥" : "FOUL! 📣", "out"); sfx("bad"); HUB.haptic("heavy"); }
    if (ev.card) { st.card = ev.card; banner(ev.card.kind === "red" ? "RED CARD 🟥" : "YELLOW CARD 🟨", "out"); }
    if (ev.text) say(ev.text);
    await sleep(ev.shots.length ? 520 : 760);
    st.card = null;
    for (const sh of ev.shots || []) await playShot(s, ev, sh);
    if (ev.corner) { banner("CORNER 🚩"); await sleep(600); }
    unbanner(); st.ball = null; st.bp = .5; ui.draw();
  }

  async function playPen(s, ev) {
    const g = s.game, ui = HUB.S.ui, st = ui.st, R = pmap(g);
    const defTeam = g.players.find((p) => p.uid !== ev.uid).uid;
    const from = [pxOf(g, defTeam === right(g) ? right(g) : ev.uid, defTeam === right(g) ? .08 : .92) + (defTeam === right(g) ? 60 : -60), MY];
    st.bp = defTeam === right(g) ? .1 : .9;
    say(`${R[ev.pid] ? R[ev.pid].name : "Penalty taker"} steps up…`); banner("PENALTY 🥅"); sfx("turn");
    await sleep(600);
    await playShot(s, { att: ev.uid, def: defTeam, shots: [] }, { shooter: ev.pid, keeper: ev.keeper, kind: "penalty", outcome: ev.outcome, dir: ev.shot, __from: from });
    st.bp = .5; st.ball = null; ui.draw();
  }

  async function runQueue(s) {
    const ui = HUB.S.ui; if (ui.busy) return; ui.busy = true;
    try {
      while (ui.q.length) {
        const ev = ui.q.shift(), room = HUB.S.room; ui.st.bp = room.game.attack ? [.2, .5, .8][room.game.attack.zone] : .5; ui.draw();
        if (ev.type === "phase") await playPhase(room, ev);
        else if (ev.type === "pen") await playPen(room, ev);
        else if (ev.type === "pick") { sfx("good"); const p = pmap(room.game)[ev.pid]; if (p) say(`${nm(room, ev.uid)} signs ${p.flag} ${p.name}!`); }
        else if (ev.type === "kickoff") { banner("KICK OFF ⚽", "big"); say("The match is underway!"); sfx("win"); await sleep(1100); unbanner(); }
        else if (ev.type === "halftime") { banner("HALF TIME ⏸️", "big"); say("Pause for tactics and substitutions."); sfx("turn"); await sleep(1300); unbanner(); }
        else if (ev.type === "sub") { sfx("good"); say("Second half — fresh legs on the pitch."); banner("2ND HALF ▶️", "big"); await sleep(1000); unbanner(); }
        else if (ev.type === "fulltime") { banner("FULL TIME 🏁", "big"); sfx("turn"); await sleep(1200); unbanner(); }
        tv(HUB.S.room); if (ev.type !== "phase" && ev.type !== "pen" && ui.q.length === 0) panel(HUB.S.room);
      }
    } finally { ui.busy = false; }
    const room = HUB.S.room, g = room.game;
    tv(room); panel(room); finale(room);
  }
  function finale(s) {
    const ui = HUB.S.ui, g = s.game;
    if ((g.stage === "done" || g.winner != null || g.draw) && !ui.done) { ui.done = true; const w = g.winner === s.you; sfx(w ? "win" : g.draw ? "turn" : "bad"); if (w && HUB.confetti) HUB.confetti(70); say(g.draw ? "Full time: a draw!" : `${nm(s, g.winner)} win${g.winner === s.you ? "" : "s"} the match!`); }
  }

  /* ---------------- apply ---------------- */
  function apply(s) {
    const ui = HUB.S.ui, g = s.game;
    if (ui.first) { ui.first = false; ui.lastSeq = g.seq || 0; ui.st.bp = g.attack ? [.2, .5, .8][g.attack.zone] : .5; ui.draw(); }
    else {
      const fresh = (g.events || []).filter((e) => e.seq > ui.lastSeq);
      if (fresh.length) { ui.lastSeq = fresh[fresh.length - 1].seq; ui.q.push(...fresh); }
    }
    if (!ui.busy) { if (ui.q.length) runQueue(s); }
    if (!ui.busy) { tv(s); panel(s); finale(s); ui.st.bp = g.attack && g.stage === "play" ? [.2, .5, .8][g.attack.zone] : ui.st.bp; ui.draw(); }
    const barInfo = (uid) => ({ score: String((g.players.find((p) => p.uid === uid) || {}).score) });
    K().updateBar(ui, s, barInfo);
    K().setHint(g.stage === "done" ? "" : playing(s) ? ((g.pending || []).includes(s.you) && !g.picked[s.you] ? "👉 Your move" : "Waiting for opponent…") : "👀 Watching");
  }
  HUB.UI.football = { build, apply };
})();

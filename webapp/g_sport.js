/* Cricket (2 players): squad draft of world-class cricketers, then a ball-by-ball duel with a TV scoreboard and a top-down stadium. */
(function () {
  "use strict";
  window.HUB = window.HUB || { UI: {} };
  const HUB = window.HUB;
  const $ = (s, r) => (r || document).querySelector(s);
  const K = () => HUB.kit;
  const sfx = (n) => { try { HUB.sfx[n](); } catch (e) { /* ignore */ } };
  const tone = (...a) => { try { HUB.tone(...a); } catch (e) { /* ignore */ } };
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const nm = (s, u) => (u === s.you ? "You" : K().nameOf(s, u));
  const playing = (s) => s.game.players.some((p) => p.uid === s.you);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const rnd = (a, b) => a + Math.random() * (b - a);

  const DELIV = { yorker: ["🎯", "Yorker"], bouncer: ["⚡", "Bouncer"], length: ["📏", "Good length"], slower: ["🐢", "Slower ball"], inswing: ["↪️", "Inswinger"], outswing: ["↩️", "Outswinger"], offbreak: ["🌀", "Off-break"], legbreak: ["🔄", "Leg-break"], googly: ["🎭", "Googly"], flighted: ["🎈", "Flighted"] };
  const SHOT = { defend: ["🛡️", "Defend"], drive: ["🏏", "Drive"], cut: ["✂️", "Cut"], pull: ["💥", "Pull"], loft: ["🚀", "Loft"], sweep: ["🧹", "Sweep"], leave: ["🙅", "Leave"] };
  const FIELD = { attack: ["🔥", "Attacking"], balanced: ["⚖️", "Balanced"], defensive: ["🧱", "Defensive"] };
  const SIDE = { off: "Off", straight: "Straight", middle: "Middle", leg: "Leg" };
  const TYPE = { pace: "Pace", swing: "Swing", spin: "Spin" };

  /* ---------- stadium geometry (top-down), logical canvas 340 x 300 ---------- */
  const CW = 340, CH = 300, CXc = 170, CYc = 152, RX = 150, RY = 138, BX = 170, BY = 232, WX = 170, WY = 78;
  function ropeDist(ux, uy) {
    const ox = BX - CXc, oy = BY - CYc, a = (ux / RX) ** 2 + (uy / RY) ** 2, b = 2 * (ox * ux / RX ** 2 + oy * uy / RY ** 2), c = (ox / RX) ** 2 + (oy / RY) ** 2 - 1;
    return (-b + Math.sqrt(Math.max(0, b * b - 4 * a * c))) / (2 * a);
  }
  const FIELDS = {   // [angle deg from straight (+ off side), fraction of rope]
    attack: [[-70, .35], [-35, .3], [10, .3], [40, .35], [70, .4], [-110, .35], [140, .3], [0, .75]],
    balanced: [[-80, .55], [-40, .7], [-10, .85], [25, .85], [60, .7], [90, .55], [-125, .85], [150, .6]],
    defensive: [[-85, .9], [-50, .92], [-15, .93], [20, .93], [55, .92], [90, .9], [-125, .93], [150, .9]],
    pp: [[-60, .3], [60, .3], [-100, .9], [-60, .9], [-20, .9], [20, .9], [60, .9], [100, .9]],
  };
  const fpos = (set) => (FIELDS[set] || FIELDS.balanced).map(([deg, f]) => { const r = deg * Math.PI / 180, ux = Math.sin(r), uy = -Math.cos(r), R = ropeDist(ux, uy) * f; return [BX + ux * R, BY + uy * R]; });

  function drawStadium(ctx, st) {
    const g = ctx.createLinearGradient(0, 0, 0, CH); g.addColorStop(0, "#0d1b3a"); g.addColorStop(1, "#173766"); ctx.fillStyle = g; ctx.fillRect(0, 0, CW, CH);
    ctx.save(); ctx.beginPath(); ctx.ellipse(CXc, CYc, RX + 26, RY + 24, 0, 0, 7); ctx.ellipse(CXc, CYc, RX + 3, RY + 3, 0, 0, 7); ctx.clip("evenodd");
    ctx.fillStyle = "#2c3e50"; ctx.fillRect(0, 0, CW, CH);
    const cols = ["#ef5350", "#ffd54f", "#42a5f5", "#fff", "#66bb6a", "#ff8a65"];
    for (let i = 0; i < 200; i++) { const th = i * 0.0314 * 1.0, e = RX + 8 + (i % 3) * 7, f = RY + 8 + (i % 3) * 7; const bob = st.crowd > 0 ? Math.abs(Math.sin(st.t * 12 + i)) * 3 : 0; ctx.fillStyle = cols[i % 6]; ctx.beginPath(); ctx.arc(CXc + Math.cos(th * 6.28 / 6.28 * 5) * e * 1, CYc + Math.sin(th * 5) * f - bob, 2.2, 0, 7); ctx.fill(); }
    ctx.restore();
    ctx.lineWidth = 5; ctx.strokeStyle = "#e53935"; ctx.beginPath(); ctx.ellipse(CXc, CYc, RX + 2, RY + 2, 0, 0, 7); ctx.stroke();
    ctx.save(); ctx.beginPath(); ctx.ellipse(CXc, CYc, RX, RY, 0, 0, 7); ctx.clip();
    for (let i = 0; i < 12; i++) { ctx.fillStyle = i % 2 ? "#2e7d32" : "#388e3c"; ctx.fillRect(0, CYc - RY + i * (RY * 2 / 12), CW, RY * 2 / 12 + 1); }
    ctx.strokeStyle = "#ffffff44"; ctx.setLineDash([5, 6]); ctx.lineWidth = 1.5; ctx.beginPath(); ctx.ellipse(CXc, CYc, RX * .6, RY * .6, 0, 0, 7); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = "#d4b179"; ctx.beginPath(); ctx.roundRect(CXc - 16, WY - 18, 32, BY - WY + 44, 5); ctx.fill();
    ctx.strokeStyle = "#fff"; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(CXc - 22, WY + 6); ctx.lineTo(CXc + 22, WY + 6); ctx.moveTo(CXc - 22, BY - 8); ctx.lineTo(CXc + 22, BY - 8); ctx.stroke();
    ctx.restore();
    const dude = (x, y, col) => { ctx.fillStyle = "#0005"; ctx.beginPath(); ctx.ellipse(x + 2, y + 5, 7, 3.5, 0, 0, 7); ctx.fill(); ctx.fillStyle = col; ctx.beginPath(); ctx.roundRect(x - 5, y - 4, 10, 10, 3); ctx.fill(); ctx.fillStyle = "#ffcc80"; ctx.beginPath(); ctx.arc(x, y - 7, 4.2, 0, 7); ctx.fill(); ctx.fillStyle = "#0d47a1"; ctx.beginPath(); ctx.arc(x, y - 8.5, 4.2, Math.PI, 0); ctx.fill(); };
    // stumps
    [[WY - 12], [BY + 22]].forEach(([y], k) => { [-5, 0, 5].forEach((dx, i) => { ctx.fillStyle = "#fff8e1"; let ox = 0, oy = 0, rot = 0; if (k === 1 && st.stumps > 0) { ox = (i - 1) * st.stumps * 26; oy = -st.stumps * 24 - i * 3; rot = (i - 1) * st.stumps * 2.2; } ctx.save(); ctx.translate(CXc + dx + ox, y + oy); ctx.rotate(rot); ctx.fillRect(-1, -5, 2, 10); ctx.restore(); }); });
    st.field.forEach(([x, y], i) => { const f = st.catcher === i ? st.catchPos : null; dude(f ? f[0] : x, f ? f[1] : y, "#1e88e5"); });
    dude(CXc + 12, st.bowlerY, "#e53935");
    dude(CXc, BY + 38, "#fdd835");
    // ball
    const b = st.ball;
    if (b) { ctx.fillStyle = "#0006"; ctx.beginPath(); ctx.ellipse(b.x, b.y, b.r, b.r * .5, 0, 0, 7); ctx.fill(); ctx.fillStyle = "#c62828"; ctx.beginPath(); ctx.arc(b.x, b.y - b.h, b.r, 0, 7); ctx.fill(); if (b.trail) { ctx.strokeStyle = "#ffffff55"; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(BX, BY); ctx.lineTo(b.x, b.y - b.h * .5); ctx.stroke(); } }
    // batter
    ctx.fillStyle = "#0004"; ctx.beginPath(); ctx.ellipse(BX + 2, BY + 7, 10, 5, 0, 0, 7); ctx.fill();
    ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.roundRect(BX - 8, BY - 3, 16, 17, 4); ctx.fill(); ctx.fillStyle = "#e3f2fd"; ctx.fillRect(BX - 7, BY + 9, 5, 8); ctx.fillRect(BX + 2, BY + 9, 5, 8);
    ctx.fillStyle = "#1565c0"; ctx.beginPath(); ctx.arc(BX, BY - 8, 7, 0, 7); ctx.fill();
    ctx.save(); ctx.translate(BX + 8, BY + 2); ctx.rotate(st.swing > 0 ? -1.3 + (1 - st.swing) * 3 : -.5); ctx.fillStyle = "#e0b36a"; ctx.beginPath(); ctx.roundRect(-3, -36, 6, 34, 3); ctx.fill(); ctx.restore();
  }

  /* ---------- helpers on state ---------- */
  function roster(g) { const m = {}; (g.pool || []).forEach((p) => { m[p.id] = p; }); g.players.forEach((pl) => pl.squad.forEach((p) => { m[p.id] = p; })); return m; }
  const ovTxt = (b) => Math.floor(b / 6) + "." + (b % 6);
  const bar = (v) => `<i style="--v:${v}%"></i>`;
  function card(p, extra) {
    return `<button class="cx-card ${extra || ""}" data-pid="${p.id}"><span class="cx-flag">${p.flag}</span><b>${esc(p.short)}</b><small>${TYPE[p.type] || ""} · ${p.style === "aggressive" ? "Attacker" : "Anchor"}</small>
      <span class="cx-r"><em>BAT</em><span class="cx-bar">${bar(p.bat)}</span><u>${p.bat}</u></span><span class="cx-r"><em>BWL</em><span class="cx-bar b">${bar(p.bowl)}</span><u>${p.bowl}</u></span></button>`;
  }
  function comment(lb, R) {
    const bat = R[lb.batter] ? R[lb.batter].short : "Batter", bowl = R[lb.bowler] ? R[lb.bowler].short : "Bowler";
    const pick = (a) => a[Math.floor(Math.random() * a.length)];
    if (lb.extra === "wide") return pick([`Wide! ${bowl} strays down the leg side.`, "Wide called. One extra to the total."]);
    if (lb.extra === "noball") return pick(["No ball! Free hit coming up.", `${bowl} oversteps. No ball!`]);
    if (lb.wicket) { const k = lb.wicket.kind || lb.wicket; return ({ bowled: `BOWLED! ${bowl} rattles the stumps!`, caught: `CAUGHT! ${bat} holes out to the fielder.`, lbw: `LBW! Plumb in front, ${bat} has to go.`, stumped: `STUMPED! ${bat} is out of the crease.`, runout: `RUN OUT! Mix-up and ${bat} is short.` })[k] || `OUT! ${bat} departs.`; }
    if (lb.runs === 6) return pick([`SIX! ${bat} launches ${bowl} into the stands!`, `Massive hit by ${bat}, that's gone all the way!`, `${bat} goes downtown. Six!`]);
    if (lb.runs === 4) return pick([`FOUR! ${bat} finds the gap, races to the rope.`, `Cracking ${(lb.shot || "shot")} from ${bat}. Four!`, "Beats the fielders, the ball runs away for four."]);
    if (lb.runs === 0) return pick([`Dot ball. ${bowl} keeps it tight.`, `${bat} blocks it back to the bowler.`, "No run. Pressure building."]);
    return pick([`${lb.runs} run${lb.runs > 1 ? "s" : ""}, worked into the gap.`, `Quick ${lb.runs === 1 ? "single" : lb.runs + " runs"}. ${bat} keeps the board ticking.`]);
  }

  /* ---------- build ---------- */
  function build(s) {
    K().newUI("cricket", s, { lastSeq: 0, busy: false, sel: {}, tab: "all", st: { t: 0, crowd: 0, swing: 0, stumps: 0, bowlerY: WY, ball: null, field: fpos("balanced"), catcher: -1, catchPos: null }, raf: 0 });
    K().shell(s, `<div class="cx-box">
      <div class="cx-tv" id="cxtv"></div>
      <div class="cx-fieldwrap"><canvas id="cxc" width="${CW * 2}" height="${CH * 2}"></canvas><div class="cx-banner" id="cxban"></div></div>
      <div class="cx-comm" id="cxcomm">Welcome to the match!</div>
      <div class="cx-panel" id="cxpanel"></div>
      <button class="cx-sc-btn" id="cxscbtn">📋 Scorecard</button></div>`);
    const c = $("#cxc"), ui = HUB.S.ui, ctx = c.getContext("2d");
    ctx.scale(2, 2);
    ui.draw = () => { ctx.save(); drawStadium(ctx, ui.st); ctx.restore(); };
    ui.draw();
    $("#cxscbtn").onclick = () => showScore(HUB.S.room);
    $("#cxpanel").onclick = (e) => onPanel(e);
  }

  function setBanner(text, cls) { const b = $("#cxban"); if (!b) return; b.textContent = text; b.className = "cx-banner show " + (cls || ""); }
  function clearBanner() { const b = $("#cxban"); if (b) b.className = "cx-banner"; }

  /* ---------- scoreboard ---------- */
  function tv(s) {
    const g = s.game, inn = g.innings[g.inn_no - 1], el = $("#cxtv"); if (!el) return;
    const R = roster(g);
    if (!inn) { el.innerHTML = `<div class="cx-tvrow"><span>🏏 CRICKET</span><span>Draft your XI</span></div>`; return; }
    const batName = nm(s, inn.bat), bowlName = nm(s, inn.bowl);
    const st = R[inn.striker], ns = R[inn.non], bw = inn.bowler ? R[inn.bowler] : null;
    const bs = inn.bat_st[inn.striker] || { r: 0, b: 0 }, bn = inn.bat_st[inn.non] || { r: 0, b: 0 };
    const first = g.innings[0], prev = g.inn_no === 2 ? first : null;
    el.innerHTML = `<div class="cx-tvrow"><b>${esc(batName)}</b><span class="cx-score">${inn.runs}/${inn.wkts}</span><span>${ovTxt(inn.balls)}/${g.overs} ov</span><span class="cx-rr">RR ${inn.rr}</span></div>
      ${prev ? `<div class="cx-tvsub">Target <b>${inn.target}</b> · need <b>${inn.need}</b> off <b>${inn.balls_left}</b>${inn.balls_left ? " · RRR " + inn.rrr : ""}</div>` : `<div class="cx-tvsub">1st innings · ${g.overs} overs a side${g.pp ? " · ⚡ Powerplay" : ""}</div>`}
      <div class="cx-tvbats"><span class="on">🏏 ${st ? esc(st.short) : ""} ${bs.r}(${bs.b})*</span><span>${ns ? esc(ns.short) : ""} ${bn.r}(${bn.b})</span><span class="bw">⚾ ${bw ? esc(bw.short) : "—"} (${esc(bowlName)})</span></div>
      <div class="cx-over">${(inn.over || []).map((x) => `<i class="${x === "W" ? "w" : x === "6" || x === "4" ? "b" : ""}">${esc(x)}</i>`).join("")}</div>`;
  }

  /* ---------- panels ---------- */
  function panel(s) {
    const g = s.game, el = $("#cxpanel"), ui = HUB.S.ui; if (!el) return;
    const R = roster(g), me = s.you, mine = playing(s);
    if (s.status !== "playing" || g.phase === "done") {
      el.innerHTML = `<div class="cx-result">${g.draw ? "🤝 Match tied" : g.winner ? "🏆 " + esc(nm(s, g.winner)) + " " + esc(g.result_text) : esc(g.result_text || "Match over")}</div>`; return;
    }
    if (ui.busy) { el.innerHTML = `<div class="cx-wait">…</div>`; return; }
    const inn = g.innings[g.inn_no - 1];
    if (g.phase === "draft") {
      const my = g.players.find((p) => p.uid === me), opp = g.players.find((p) => p.uid !== me) || g.players[1];
      const squads = g.players.map((p) => `<div class="cx-squad"><b>${esc(nm(s, p.uid))}</b><span>${p.squad.map((x) => `${x.flag}${esc(x.short)}`).join(" · ") || "—"}</span></div>`).join("");
      if (mine && g.picker === me) {
        let pool = [...g.pool].sort((a, b) => (b.bat + b.bowl) - (a.bat + a.bowl));
        if (ui.tab === "bat") pool.sort((a, b) => b.bat - a.bat); if (ui.tab === "bowl") pool.sort((a, b) => b.bowl - a.bowl);
        el.innerHTML = `<div class="cx-h">Draft: pick player ${(my ? my.squad.length : 0) + 1} of ${g.team_size}</div>${squads}
          <div class="cx-tabs">${["all", "bat", "bowl"].map((t) => `<button data-tab="${t}" class="${ui.tab === t ? "on" : ""}">${{ all: "Best overall", bat: "Batters", bowl: "Bowlers" }[t]}</button>`).join("")}<button data-quick="1" class="q">⚡ Quick pick</button></div>
          <div class="cx-pool">${pool.map((p) => card(p)).join("")}</div>`;
      } else el.innerHTML = `<div class="cx-h">${mine ? esc(nm(s, g.picker)) + " is picking…" : "Squad draft in progress"}</div>${squads}`;
      return;
    }
    if (g.phase === "over") {
      if (mine && inn.bowl === me) {
        const sel = ui.sel;
        el.innerHTML = `<div class="cx-h">Over ${g.over_no}: choose your bowler & field</div>
          <div class="cx-pool small">${g.eligible.map((id) => card(R[id], sel.bowler === id ? "sel" : "")).join("")}</div>
          <div class="cx-opts">${["attack", "balanced", "defensive"].map((f) => `<button data-field="${f}" class="${(sel.field || "balanced") === f ? "on" : ""}" ${f === "defensive" && g.pp ? "disabled" : ""}>${FIELD[f][0]}<span>${FIELD[f][1]}</span></button>`).join("")}</div>
          <div class="cx-go"><button class="cx-primary" data-over="1" ${sel.bowler ? "" : "disabled"}>Bowl this over ▶</button><button data-quick="1">⚡ Auto</button></div>`;
      } else el.innerHTML = `<div class="cx-wait">${esc(nm(s, inn.bowl))} is choosing the bowler…</div>`;
      return;
    }
    if (g.phase === "ball") {
      const locked = mine && g.picked[me];
      if (mine && locked) { el.innerHTML = `<div class="cx-wait">🔒 Locked in. Waiting for ${esc(nm(s, me === inn.bat ? inn.bowl : inn.bat))}…</div>`; return; }
      if (mine && inn.bowl === me) {
        const sel = ui.sel, bw = R[inn.bowler];
        el.innerHTML = `<div class="cx-h">⚾ You bowl: ${esc(bw.short)} (${TYPE[bw.type]}) · ${FIELD[inn.field][1]} field</div>
          <div class="cx-opts d">${g.bowl_set.map((d) => `<button data-del="${d}" class="${sel.delivery === d ? "on" : ""}">${DELIV[d][0]}<span>${DELIV[d][1]}</span></button>`).join("")}</div>
          <div class="cx-opts l">${["off", "middle", "leg"].map((l) => `<button data-line="${l}" class="${sel.line === l ? "on" : ""}"><span>${SIDE[l]} stump</span></button>`).join("")}</div>
          <div class="cx-go"><button class="cx-primary" data-ball="1" ${sel.delivery && sel.line ? "" : "disabled"}>Bowl! ⚾</button><button data-quick="1">⚡ Auto</button></div>`;
      } else if (mine) {
        const sel = ui.sel, st = R[inn.striker];
        el.innerHTML = `<div class="cx-h">🏏 You bat: ${esc(st.short)} · aim the shot into the gaps</div>
          <div class="cx-opts s">${Object.keys(SHOT).map((k) => `<button data-shot="${k}" class="${sel.shot === k ? "on" : ""}">${SHOT[k][0]}<span>${SHOT[k][1]}</span></button>`).join("")}</div>
          ${sel.shot && !["defend", "leave"].includes(sel.shot) ? `<div class="cx-opts l">${["off", "straight", "leg"].map((d) => `<button data-dir="${d}" class="${sel.dir === d ? "on" : ""}"><span>${SIDE[d]} side</span></button>`).join("")}</div>` : ""}
          <div class="cx-go"><button class="cx-primary" data-play="1" ${sel.shot && (["defend", "leave"].includes(sel.shot) || sel.dir) ? "" : "disabled"}>Play shot! 🏏</button><button data-quick="1">⚡ Auto</button></div>`;
      } else el.innerHTML = `<div class="cx-wait">👀 Watching: ${esc(nm(s, inn.bowl))} bowling to ${esc(nm(s, inn.bat))}</div>`;
    }
  }
  function onPanel(e) {
    const s = HUB.S.room, ui = HUB.S.ui; if (!s || !playing(s) || ui.busy) return;
    const t = e.target.closest("button"); if (!t || t.disabled) return;
    const d = t.dataset, sel = ui.sel;
    const send = (m) => { HUB.send(m); ui.sel = {}; HUB.haptic("medium"); sfx("pop"); };
    if (d.tab) { ui.tab = d.tab; return panel(s); }
    if (d.quick) return send({ t: "quick" });
    if (d.pid) { if (s.game.phase === "draft") return send({ t: "pick", id: d.pid }); sel.bowler = d.pid; sfx("pop"); return panel(s); }
    if (d.field) { sel.field = d.field; return panel(s); }
    if (d.over) return send({ t: "over", bowler: sel.bowler, field: sel.field || "balanced" });
    if (d.del) { sel.delivery = d.del; sfx("pop"); return panel(s); }
    if (d.line) { sel.line = d.line; return panel(s); }
    if (d.ball) return send({ t: "ball", delivery: sel.delivery, line: sel.line });
    if (d.shot) { sel.shot = d.shot; if (["defend", "leave"].includes(d.shot)) sel.dir = "straight"; sfx("pop"); return panel(s); }
    if (d.dir) { sel.dir = d.dir; return panel(s); }
    if (d.play) return send({ t: "ball", shot: sel.shot, dir: sel.dir || "straight" });
  }

  function showScore(s) {
    const g = s.game, R = roster(g);
    const html = g.innings.map((inn, i) => `<h4>Innings ${i + 1}: ${esc(nm(s, inn.bat))} ${inn.runs}/${inn.wkts} (${ovTxt(inn.balls)} ov)</h4>
      <table class="cx-tbl"><tr><th>Batter</th><th>How out</th><th>R</th><th>B</th><th>4s</th><th>6s</th></tr>${inn.order.map((p) => { const b = inn.bat_st[p]; return `<tr><td>${esc(R[p].short)}</td><td>${esc(b.out || (b.b ? "not out" : "-"))}</td><td>${b.r}</td><td>${b.b}</td><td>${b.f}</td><td>${b.s}</td></tr>`; }).join("")}</table>
      <table class="cx-tbl"><tr><th>Bowler</th><th>O</th><th>R</th><th>W</th></tr>${Object.keys(inn.bowl_st).filter((p) => inn.bowl_st[p].b || inn.bowl_st[p].o).map((p) => { const b = inn.bowl_st[p]; return `<tr><td>${esc(R[p].short)}</td><td>${ovTxt(b.b)}</td><td>${b.r}</td><td>${b.w}</td></tr>`; }).join("")}</table>
      <small>Extras ${inn.extras}${inn.fow.length ? " · FOW " + inn.fow.map((f) => `${f.runs}-${f.wk} (${esc(R[f.pid].short)}, ${f.over})`).join(", ") : ""}</small>`).join("") || "<p>No innings yet.</p>";
    const sh = document.createElement("div"); sh.className = "cx-sheet";
    sh.innerHTML = `<div class="cx-sbox"><div class="cx-stitle"><b>📋 Scorecard</b><button id="cxsx">✕</button></div>${html}</div>`;
    document.body.appendChild(sh); sh.onclick = (e) => { if (e.target === sh || e.target.id === "cxsx") sh.remove(); };
  }

  /* ---------- ball animation ---------- */
  const raf = () => new Promise((r) => requestAnimationFrame(r));
  async function animateBall(s, lb) {
    const ui = HUB.S.ui, st = ui.st, g = s.game, R = roster(g);
    ui.busy = true; panel(s);
    st.field = fpos(lb.pp ? "pp" : lb.field); st.catcher = -1; st.stumps = 0; st.swing = 0;
    const lineX = { off: 6, middle: 0, leg: -6 }[lb.line] || 0;
    const dur = lb.delivery === "yorker" || lb.delivery === "bouncer" ? 520 : lb.delivery === "slower" || lb.delivery === "flighted" ? 900 : 700;
    let t0 = performance.now();
    $("#cxcomm").textContent = `${R[lb.bowler] ? R[lb.bowler].short : "Bowler"} runs in…`;
    // run-up and delivery
    tone(240, 0.06, "triangle", 0.08);
    for (;;) {
      const k = clamp((performance.now() - t0) / dur, 0, 1);
      st.bowlerY = WY + Math.sin(k * 3) * 6; st.t += 0.016;
      const y = WY + (BY - 8 - WY) * k, x = BX + lineX * (1 - k) + Math.sin(k * 5) * 2;
      const bounce = k < .62 ? Math.sin(k / .62 * Math.PI / 2) * 22 : Math.abs(Math.sin((k - .62) / .38 * Math.PI)) * 9;
      st.ball = { x, y, h: bounce, r: 2.6 + k * 2.2 };
      ui.draw(); if (k >= 1) break; await raf();
    }
    // shot
    const hit = !["beaten", "wide"].includes(lb.contact);
    st.swing = 1; sfx("hit"); tone(900, 0.04, "square", 0.22);
    const rad = (lb.ang || 0) * Math.PI / 180, ux = Math.sin(rad), uy = -Math.cos(rad), R0 = ropeDist(ux, uy), D = (lb.dist || 0) * R0;
    const kind = lb.wicket ? (lb.wicket.kind || lb.wicket) : null;
    if (kind === "bowled" || kind === "lbw") { st.stumps = kind === "bowled" ? 1 : 0; if (kind === "bowled") { sfx("bad"); tone(110, 0.4, "sawtooth", 0.25); } }
    if (hit) {
      const fd = 350 + D * 4, f0 = performance.now(); let caught = null;
      if (kind === "caught") { let best = 0, bd = 1e9; const ex = BX + ux * D, ey = BY + uy * D; st.field.forEach(([x, y], i) => { const dd = Math.hypot(x - ex, y - ey); if (dd < bd) { bd = dd; best = i; } }); caught = best; st.catcher = best; st.catchPos = null; }
      for (;;) {
        const k = clamp((performance.now() - f0) / fd, 0, 1), e = 1 - (1 - k) * (1 - k);
        st.swing = Math.max(0, 1 - k * 4);
        st.ball = { x: BX + ux * D * e, y: BY + uy * D * e, h: lb.air ? Math.sin(k * Math.PI) * (lb.runs === 6 ? 70 : 40) : Math.abs(Math.sin(k * 6)) * 4 * (1 - k), r: lb.runs === 6 && k > .6 ? 4.5 - (k - .6) * 6 : 4.5, trail: true };
        if (caught !== null) st.catchPos = [st.field[caught][0] + (BX + ux * D - st.field[caught][0]) * k, st.field[caught][1] + (BY + uy * D - st.field[caught][1]) * k];
        st.t += 0.016; ui.draw(); if (k >= 1) break; await raf();
      }
    } else { for (let i = 0; i < 18; i++) { st.swing = Math.max(0, 1 - i / 8); st.t += .016; ui.draw(); await raf(); } }
    st.ball = null; st.swing = 0;
    // result
    const label = lb.extra === "wide" ? "WIDE" : lb.extra === "noball" ? "NO BALL" : lb.wicket ? "OUT!" : lb.runs === 6 ? "SIX!" : lb.runs === 4 ? "FOUR!" : lb.runs === 0 ? "DOT" : lb.runs + (lb.runs === 1 ? " RUN" : " RUNS");
    setBanner(label, lb.wicket ? "out" : lb.runs >= 4 ? "big" : "");
    $("#cxcomm").textContent = comment(lb, R);
    if (lb.wicket) { sfx("bad"); HUB.haptic("heavy"); anim(document.querySelector(".cx-fieldwrap"), [{ transform: "translateX(0)" }, { transform: "translateX(-7px)" }, { transform: "translateX(6px)" }, { transform: "none" }], { duration: 420 }); }
    else if (lb.runs >= 4) { st.crowd = 1.6; sfx("win"); HUB.haptic("success"); if (HUB.confetti && lb.runs === 6) HUB.confetti(36); for (let i = 0; i < 6; i++) tone(300 + Math.random() * 500, 0.12, "sawtooth", 0.05); }
    else sfx(lb.runs ? "good" : "pop");
    if (lb.milestone) setTimeout(() => { setBanner(lb.milestone + " UP! 🎉", "big"); }, 900);
    const endT = performance.now() + (lb.wicket || lb.runs >= 4 ? 1500 : 900);
    while (performance.now() < endT) { st.t += .016; st.crowd = Math.max(0, st.crowd - .016); ui.draw(); await raf(); }
    st.stumps = 0; st.crowd = 0; st.bowlerY = WY; ui.draw(); clearBanner();
    ui.busy = false;
  }
  function anim(el, kf, o) { try { return el && el.animate ? el.animate(kf, o) : null; } catch (e) { return null; } }

  /* ---------- apply ---------- */
  function apply(s) {
    const ui = HUB.S.ui, g = s.game, lb = g.last_ball;
    if (ui.first) { ui.first = false; ui.lastSeq = lb ? lb.seq : 0; const inn = g.innings[g.inn_no - 1]; ui.st.field = fpos(inn ? (g.pp ? "pp" : inn.field) : "balanced"); ui.draw(); }
    else if (lb && lb.seq > ui.lastSeq) { ui.lastSeq = lb.seq; animateBall(s, lb).then(() => { tv(room()); panel(room()); K().updateBar(ui, room(), barInfo); }); }
    const ev = g.last_event;
    if (ev && ev.seq !== ui.lastEv) {
      ui.lastEv = ev.seq;
      if (ev.e === "toss") { $("#cxcomm").textContent = nm(s, ev.uid) + " bats first!"; setBanner("MATCH ON", "big"); sfx("turn"); setTimeout(clearBanner, 1400); }
      if (ev.e === "break") { setBanner("TARGET " + ev.target, "big"); sfx("win"); setTimeout(clearBanner, 1800); }
      if (ev.e === "end") { sfx(ev.winner === s.you ? "win" : "bad"); if (ev.winner === s.you && HUB.confetti) HUB.confetti(60); $("#cxcomm").textContent = ev.draw ? "What a finish: tied!" : nm(s, ev.winner) + " " + ev.text; }
    }
    function room() { return HUB.S.room; }
    function barInfo(uid) { const inn = g.innings.find((i) => i.bat === uid); return { score: inn ? inn.runs + "/" + inn.wkts : "" }; }
    const bx = $(".cx-box"); if (bx) bx.classList.toggle("draft", g.phase === "draft");
    if (!ui.busy) { tv(s); panel(s); }
    K().updateBar(ui, s, barInfo);
    K().setHint(g.phase === "done" ? "" : playing(s) ? (g.pending && g.pending.includes(s.you) ? "👉 Your move" : "Waiting for opponent…") : "👀 Watching");
  }
  HUB.UI.cricket = { build, apply };
})();

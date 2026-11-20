/* Renderers for the Arena group: Tank Duel, Car Racing, Dominoes, Word Duel. Registers { build, apply } in HUB.UI. */
(function () {
  "use strict";
  window.HUB = window.HUB || { UI: {} };
  const HUB = window.HUB;
  const $ = (s, r) => (r || document).querySelector(s);
  const K = () => HUB.kit;
  const room = () => HUB.S.room;
  const playing = (s) => s.game.players.some((p) => p.uid === s.you);
  const sfx = (n) => { try { HUB.sfx[n](); } catch (e) { /* ignore */ } };
  const esc = (t) => String(t).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  /* =============================== TANK DUEL =============================== */
  function terrain(g) {
    const pts = g.h.map((v, i) => `${i + 0.5},${20 - v}`).join(" ");
    return `0,20 ${pts} ${g.w},20`;
  }
  function tankSVG(g, s) {
    const gy = (x) => 20 - g.h[Math.max(0, Math.min(g.w - 1, Math.round(x)))];
    const tanks = g.players.map((p, i) => {
      const y = gy(p.x), col = i ? "#ea4335" : "#4285f4", d = i ? -1 : 1;
      return `<g class="tk" data-uid="${p.uid}" transform="translate(${p.x + 0.5},${y})"><rect x="-1.1" y="-1" width="2.2" height="1" rx=".3" fill="${col}"/><rect x="-.6" y="-1.5" width="1.2" height=".6" rx=".3" fill="${col}"/><line x1="0" y1="-1.3" x2="${d * 1.6}" y2="-2" stroke="${col}" stroke-width=".25"/></g>`;
    }).join("");
    return `<polygon points="${terrain(g)}" fill="#3b7d3a"/><polygon points="${terrain(g)}" fill="none" stroke="#2a5a2a" stroke-width=".15"/>${tanks}<circle id="tshell" r=".4" fill="#fbbc05" cx="-5" cy="-5"/><circle id="tboom" r="0" fill="#ff7043" opacity=".8" cx="-5" cy="-5"/>`;
  }
  function buildTank(s) {
    K().newUI("tank", s, { lastSeq: 0, busy: false });
    K().shell(s, `<div class="gx-box"><div class="gx-info"><span id="gxhp"></span><span id="gxwind"></span></div>
      <svg id="gxsky" class="gx-tank" viewBox="0 0 ${s.game.w} 20" preserveAspectRatio="none"></svg>
      <div class="gx-ctrl" id="gxctrl"><label>Angle <b id="gxav">45°</b><input id="gxa" type="range" min="10" max="80" value="45"></label>
      <label>Power <b id="gxpv">70</b><input id="gxp" type="range" min="20" max="100" value="70"></label>
      <button class="gx-fire" id="gxfire">🔥 FIRE</button></div></div>`);
    $("#gxa").oninput = () => { $("#gxav").textContent = $("#gxa").value + "°"; };
    $("#gxp").oninput = () => { $("#gxpv").textContent = $("#gxp").value; };
    $("#gxfire").onclick = () => {
      const s2 = room();
      if (!playing(s2) || s2.game.turn !== s2.you || HUB.S.ui.busy) return;
      HUB.send({ t: "fire", angle: +$("#gxa").value, power: +$("#gxp").value });
      HUB.haptic("medium"); sfx("pop");
    };
  }
  async function applyTank(s) {
    const ui = HUB.S.ui, g = s.game, ls = g.last_shot, svg = $("#gxsky");
    if (!svg) return;
    const draw = () => { svg.innerHTML = tankSVG(g, s); };
    if (ui.first) { ui.first = false; if (ls) ui.lastSeq = ls.seq; draw(); }
    else if (ls && ls.seq > ui.lastSeq) {
      ui.lastSeq = ls.seq; ui.busy = true;
      const prevSvg = svg.innerHTML;
      const sh = $("#tshell");
      sfx("place");
      const pts = ls.path;
      for (let i = 0; i < pts.length; i++) {
        if (sh) { sh.setAttribute("cx", pts[i][0] + 0.5); sh.setAttribute("cy", 20 - pts[i][1]); }
        await sleep(28);
      }
      const bm = $("#tboom");
      if (bm && ls.kind !== "out") {
        bm.setAttribute("cx", ls.impact[0] + 0.5); bm.setAttribute("cy", 20 - ls.impact[1]);
        sfx(Object.values(ls.dmg).some((d) => d > 0) ? "hit" : "miss"); HUB.haptic("heavy");
        bm.animate([{ r: 0.2, opacity: 0.9 }, { r: 3.2, opacity: 0 }], { duration: 450, easing: "ease-out" });
        bm.setAttribute("r", 0);
        await sleep(420);
      } else sfx("miss");
      draw(); ui.busy = false;
    } else if (!ui.busy) draw();
    $("#gxhp").innerHTML = g.players.map((p, i) => `<span style="color:${i ? "#ea4335" : "#4285f4"}">${p.uid === s.you ? "You" : esc(K().nameOf(s, p.uid))}: ${p.hp} HP</span>`).join(" · ");
    $("#gxwind").textContent = "🌬️ wind " + (g.wind > 0 ? "→ " : g.wind < 0 ? "← " : "") + Math.abs(g.wind);
    const mine = playing(s) && g.turn === s.you && s.status === "playing";
    $("#gxctrl").classList.toggle("hidden", !playing(s));
    $("#gxfire").disabled = !mine;
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).hp + "♥" }));
    K().setHint(playing(s) ? (mine ? "Set angle & power, then FIRE (shots always go toward your opponent)" : "Waiting for " + K().nameOf(s, g.turn) + "…") : "👀 Watching the battle");
  }

  /* =============================== CAR RACING =============================== */
  const GEAR = { cruise: ["🚗", "Cruise", "+2"], boost: ["🏎️", "Boost", "+3 · heat+1"], nitro: ["🚀", "Nitro", "+5 · heat+2"] };
  function buildRace(s) {
    K().newUI("race", s, { lastSeq: 0, locked: false });
    const g = s.game;
    K().shell(s, `<div class="gx-box"><div class="gx-track">${g.players.map((p, i) => `<div class="gx-lane" data-uid="${p.uid}"><div class="gx-oil">${g.oil.map((o) => `<i style="left:${(o / g.length) * 100}%">🛢️</i>`).join("")}</div><div class="gx-finish">🏁</div><div class="gx-car" style="left:0%">${["🚙", "🚕", "🏎️", "🚓"][i]}</div><div class="gx-heat"><i></i></div></div>`).join("")}</div>
      <div class="gx-msg" id="gxmsg">Pick a gear — everyone chooses at once!</div>
      <div class="gx-gears" id="gxgears">${Object.entries(GEAR).map(([k, v]) => `<button class="gx-g" data-g="${k}"><span>${v[0]}</span><b>${v[1]}</b><small>${v[2]}</small></button>`).join("")}</div></div>`);
    $("#gxgears").onclick = (e) => {
      const b = e.target.closest(".gx-g"), s2 = room(), ui = HUB.S.ui;
      if (!b || b.disabled || !playing(s2) || ui.locked) return;
      ui.locked = true; HUB.send({ t: "gear", gear: b.dataset.g }); HUB.haptic("medium"); sfx("pop");
      document.querySelectorAll(".gx-g").forEach((x) => x.classList.toggle("sel", x === b));
      $("#gxmsg").textContent = "Locked in " + b.dataset.g + " — waiting…";
    };
  }
  async function applyRace(s) {
    const ui = HUB.S.ui, g = s.game, lr = g.last_round;
    g.players.forEach((p) => {
      const lane = $(`.gx-lane[data-uid="${p.uid}"]`);
      if (!lane) return;
      lane.querySelector(".gx-car").style.left = `calc(${(p.pos / g.length) * 100}% - ${(p.pos / g.length) * 30}px)`;
      lane.querySelector(".gx-heat i").style.width = Math.min(100, p.heat * 25) + "%";
      lane.classList.toggle("me", p.uid === s.you);
      lane.classList.toggle("stall", p.stalled);
    });
    if (ui.first) { ui.first = false; if (lr) ui.lastSeq = lr.seq; }
    else if (lr && lr.seq > ui.lastSeq) {
      ui.lastSeq = lr.seq; ui.locked = false;
      sfx("roll"); HUB.haptic("light");
      const ev = lr.events.map((e) => `${e.uid === s.you ? "You" : K().nameOf(s, e.uid)} ${{ stall: "stalled 🥵", overheat: "overheated 🔥", oil: "hit oil 🛢️", bump: "got bumped 💥" }[e.e]}`);
      $("#gxmsg").textContent = ev.join(" · ") || "Round " + lr.round;
    }
    const me = playing(s), ok = me && s.status === "playing" && !g.picked[s.you];
    if (ok) { ui.locked = false; document.querySelectorAll(".gx-g").forEach((x) => x.classList.remove("sel")); }
    const mine = g.players.find((p) => p.uid === s.you);
    document.querySelectorAll(".gx-g").forEach((b) => { b.disabled = !ok || (mine && mine.stalled); });
    $("#gxgears").classList.toggle("hidden", !me);
    if (me && mine.stalled && ok) $("#gxmsg").textContent = "🥵 Engine stalled — you lose this round";
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).pos + "/" + g.length }));
    K().setHint(me ? (g.picked[s.you] ? "Waiting for other drivers…" : "Heat 4 = stall! Nitro is fast but hot") : "👀 Watching the race");
  }

  /* =============================== DOMINOES =============================== */
  const PIPS = { 0: [], 1: [4], 2: [0, 8], 3: [0, 4, 8], 4: [0, 2, 6, 8], 5: [0, 2, 4, 6, 8], 6: [0, 2, 3, 5, 6, 8] };
  const half = (n) => `<div class="dm-h">${[0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => `<i class="${PIPS[n].includes(i) ? "on" : ""}"></i>`).join("")}</div>`;
  const tileEl = (a, b, cls) => `<div class="dm-t ${cls || ""}" data-a="${a}" data-b="${b}">${half(a)}<span class="dm-sp"></span>${half(b)}</div>`;
  function buildDominoes(s) {
    K().newUI("dominoes", s, { lastSeq: 0, sel: null });
    K().shell(s, `<div class="gx-box"><div class="dm-info" id="dminfo"></div><div class="dm-chain" id="dmchain"></div>
      <div class="dm-acts" id="dmacts"></div><div class="dm-hand" id="dmhand"></div></div>`);
    $("#dmhand").onclick = (e) => {
      const t = e.target.closest(".dm-t"), s2 = room(), ui = HUB.S.ui;
      if (!t || !playing(s2) || s2.game.turn !== s2.you) return;
      const a = +t.dataset.a, b = +t.dataset.b;
      const opts = (s2.game.can || []).filter((c) => c.tile[0] === a && c.tile[1] === b);
      if (!opts.length) { HUB.toast && HUB.toast("That tile doesn't fit"); sfx("miss"); return; }
      if (opts.length === 1) { HUB.send({ t: "play", tile: [a, b], end: opts[0].end }); sfx("pop"); HUB.haptic("medium"); }
      else { ui.sel = [a, b]; applyDominoes(s2); }
    };
    $("#dmacts").onclick = (e) => {
      const b = e.target.closest("button"); if (!b) return;
      const ui = HUB.S.ui;
      if (b.dataset.end && ui.sel) { HUB.send({ t: "play", tile: ui.sel, end: b.dataset.end }); ui.sel = null; sfx("pop"); }
      else if (b.dataset.act) { HUB.send({ t: b.dataset.act }); sfx("pop"); }
    };
  }
  function applyDominoes(s) {
    const ui = HUB.S.ui, g = s.game, lm = g.last_move;
    $("#dmchain").innerHTML = g.chain.length ? g.chain.map(([a, b]) => tileEl(a, b, a === b ? "dbl" : "")).join("") : '<div class="dm-empty">Play any tile to start</div>';
    const ch = $("#dmchain"); ch.scrollLeft = ch.scrollWidth;
    const my = playing(s) && g.turn === s.you && s.status === "playing";
    const hand = g.hand || [];
    $("#dmhand").innerHTML = hand.map(([a, b]) => tileEl(a, b, my && (g.can || []).some((c) => c.tile[0] === a && c.tile[1] === b) ? "ok" : "")).join("");
    $("#dmhand").classList.toggle("hidden", !playing(s));
    let acts = "";
    if (my && ui.sel) acts = `<button data-end="L">◀ Left end</button><button data-end="R">Right end ▶</button>`;
    else if (my && !(g.can || []).length) acts = g.yard ? `<button data-act="draw">🂠 Draw (${g.yard} left)</button>` : `<button data-act="pass">Pass</button>`;
    if (!my) ui.sel = null;
    $("#dmacts").innerHTML = acts;
    $("#dminfo").textContent = "Boneyard: " + g.yard + " · " + Object.keys(g.counts).map((u) => `${+u === s.you ? "You" : K().nameOf(s, +u)} ${g.counts[u]}`).join(" · ");
    if (ui.first) { ui.first = false; if (lm) ui.lastSeq = lm.seq; }
    else if (lm && lm.seq > ui.lastSeq) { ui.lastSeq = lm.seq; sfx(lm.kind === "play" ? "place" : "pop"); HUB.haptic("light"); }
    K().turnFx(ui, s);
    K().updateBar(ui, s, (uid) => ({ score: (g.counts[uid] != null ? g.counts[uid] : "") + "🁣" }));
    K().setHint(playing(s) ? (my ? (ui.sel ? "Pick which end" : "Tap a glowing tile") : "Waiting for " + K().nameOf(s, g.turn) + "…") : "👀 Watching");
  }

  /* =============================== WORD DUEL =============================== */
  function buildWordle(s) {
    K().newUI("wordle", s, { lastSeq: 0, locked: false });
    K().shell(s, `<div class="gx-box"><div class="wd-grids" id="wdgrids"></div>
      <form class="wd-in" id="wdform" autocomplete="off"><input id="wdinp" maxlength="5" placeholder="5-letter word" autocapitalize="none" autocorrect="off" spellcheck="false"><button>Guess</button></form></div>`);
    $("#wdform").onsubmit = (e) => {
      e.preventDefault();
      const s2 = room(), v = $("#wdinp").value.trim().toLowerCase();
      if (!playing(s2) || HUB.S.ui.locked) return;
      if (!/^[a-z]{5}$/.test(v)) { HUB.toast && HUB.toast("Enter a 5-letter word"); return; }
      HUB.send({ t: "guess", word: v }); HUB.S.ui.locked = true; $("#wdinp").value = ""; sfx("pop"); HUB.haptic("medium");
    };
  }
  function applyWordle(s) {
    const ui = HUB.S.ui, g = s.game, lr = g.last_round;
    $("#wdgrids").innerHTML = g.players.map((p) => {
      const rows = [];
      for (let r = 0; r < g.rounds; r++) {
        const gu = p.guesses[r];
        rows.push(`<div class="wd-row">${[0, 1, 2, 3, 4].map((i) => `<span class="wd-c ${gu ? gu.fb[i] : ""}">${gu && gu.word ? gu.word[i].toUpperCase() : ""}</span>`).join("")}</div>`);
      }
      return `<div class="wd-g ${p.uid === s.you ? "me" : ""}"><div class="wd-n">${p.uid === s.you ? "You" : esc(K().nameOf(s, p.uid))}${g.picked[p.uid] ? " ✔" : ""}${p.solved ? " 🎉" : ""}</div>${rows.join("")}</div>`;
    }).join("");
    if (ui.first) { ui.first = false; if (lr) ui.lastSeq = lr.seq; }
    else if (lr && lr.seq > ui.lastSeq) { ui.lastSeq = lr.seq; ui.locked = false; sfx("place"); HUB.haptic("light"); }
    const me = playing(s), ok = me && s.status === "playing" && !g.picked[s.you] && !(g.players.find((p) => p.uid === s.you) || {}).solved;
    if (ok) ui.locked = false;
    $("#wdform").classList.toggle("hidden", !me);
    $("#wdinp").disabled = !ok;
    K().updateBar(ui, s, (uid) => ({ score: "R" + g.round + "/" + g.rounds }));
    K().setHint(me ? (ok ? "🟩 right spot · 🟨 wrong spot · ⬛ not in word" : "Waiting for the others…") : "👀 Watching");
    if (g.secret && s.status === "finished") K().setHint("The word was: " + g.secret.toUpperCase());
  }


  /* =============================== ADVENTURE QUEST =============================== */
  const QM = { attack: ["⚔️", "Attack", "9-15 dmg"], power: ["🔥", "Power", "22-30 · 2 mana"], heal: ["💚", "Heal", "+18 HP"], guard: ["🛡️", "Guard", "half dmg"] };
  function buildQuest(s) {
    K().newUI("quest", s, { lastSeq: 0, locked: false, floor: 0 });
    K().shell(s, `<div class="gx-box"><div class="qs-floor" id="qsfloor"></div>
      <div class="qs-boss"><div class="qs-bi" id="qsbi">👹</div><div class="gx-bar big"><i id="qsbhp"></i></div><div id="qsbt" class="qs-bt"></div></div>
      <div class="qs-party" id="qsparty"></div><div class="gx-msg" id="qsmsg">Pick your move — the party acts together!</div>
      <div class="gx-gears four" id="qsmoves">${Object.entries(QM).map(([k, v]) => `<button class="gx-g" data-m="${k}"><span>${v[0]}</span><b>${v[1]}</b><small>${v[2]}</small></button>`).join("")}</div></div>`);
    $("#qsmoves").onclick = (e) => {
      const b = e.target.closest(".gx-g"), s2 = room(), ui = HUB.S.ui;
      if (!b || b.disabled || !playing(s2) || ui.locked) return;
      ui.locked = true; HUB.send({ t: "act", move: b.dataset.m }); HUB.haptic("medium"); sfx("pop");
      document.querySelectorAll("#qsmoves .gx-g").forEach((x) => x.classList.toggle("sel", x === b));
      $("#qsmsg").textContent = "Locked in " + b.dataset.m + " — waiting for the party…";
    };
  }
  function applyQuest(s) {
    const ui = HUB.S.ui, g = s.game, lr = g.last_round, bs = g.boss;
    $("#qsfloor").textContent = `Floor ${g.floor}/${g.floors} · ${bs.name}`;
    $("#qsbi").textContent = bs.emoji;
    $("#qsbhp").style.width = (100 * bs.hp / bs.max) + "%";
    $("#qsbt").textContent = bs.hp + " / " + bs.max + " HP";
    $("#qsparty").innerHTML = g.players.map((p) => `<div class="qs-h ${p.down ? "down" : ""} ${p.uid === s.you ? "me" : ""} ${g.picked[p.uid] ? "pk" : ""}"><div>${p.down ? "💀" : "🧙"}</div><small>${p.uid === s.you ? "You" : esc(K().nameOf(s, p.uid))}</small><div class="gx-bar"><i style="width:${Math.min(100, p.hp / 70 * 100)}%"></i></div><small>${p.hp} HP · 💧${p.mana}</small></div>`).join("");
    if (ui.first) { ui.first = false; if (lr) ui.lastSeq = lr.seq; }
    else if (lr && lr.seq > ui.lastSeq) {
      ui.lastSeq = lr.seq; ui.locked = false;
      const dealt = Object.values(lr.dmg).reduce((a, b) => a + b, 0), hit = Object.entries(lr.hits).map(([u, d]) => `${+u === s.you ? "You" : K().nameOf(s, +u)} −${d}`);
      $("#qsmsg").textContent = `Party deals ${dealt}` + (hit.length ? " · Monster hits: " + hit.join(", ") : "") + (lr.events.includes("roar") ? " · 🗣️ ROAR!" : "") + (lr.next_floor != null ? " · ⬆️ Next floor!" : "");
      sfx(hit.length ? "hit" : "pop"); HUB.haptic(hit.length ? "heavy" : "light");
      $("#qsbi").animate([{ transform: "scale(1)" }, { transform: "scale(.85) rotate(-6deg)" }, { transform: "scale(1)" }], { duration: 300 });
    }
    const me = g.players.find((p) => p.uid === s.you), ok = !!me && !me.down && s.status === "playing" && !g.picked[s.you];
    if (ok) { ui.locked = false; document.querySelectorAll("#qsmoves .gx-g").forEach((x) => x.classList.remove("sel")); }
    document.querySelectorAll("#qsmoves .gx-g").forEach((b) => { b.disabled = !ok || (b.dataset.m === "power" && me.mana < 2); });
    $("#qsmoves").classList.toggle("hidden", !me);
    K().updateBar(ui, s, (uid) => { const p = g.players.find((x) => x.uid === uid); return { score: p.down ? "💀" : p.hp + "♥" }; });
    K().setHint(me ? (me.down ? "You are down — cheer on your party!" : "Co-op! Beat all 3 floors together. Guard when the monster roars") : "👀 Watching the quest");
  }

  /* =============================== CLICKRUSH =============================== */
  function buildClick(s) {
    K().newUI("clickrush", s, { sent: 0, t0: Date.now(), left: s.game.left });
    K().shell(s, `<div class="gx-box"><div class="cr-time" id="crtime">10.0</div><div class="cr-board" id="crboard"></div>
      <button class="cr-btn" id="crbtn">TAP!</button></div>`);
    const b = $("#crbtn");
    const tap = (e) => { e.preventDefault(); const s2 = room(); if (!playing(s2) || s2.status !== "playing") return; HUB.send({ t: "tap" }); sfx("pop"); b.animate([{ transform: "scale(.93)" }, { transform: "scale(1)" }], { duration: 90 }); };
    b.addEventListener("pointerdown", tap);
    const ui = HUB.S.ui;
    clearInterval(ui.tm);
    ui.tm = setInterval(() => {
      const el = $("#crtime"); if (!el) { clearInterval(ui.tm); return; }
      const l = Math.max(0, ui.left - (Date.now() - ui.t0) / 1000); el.textContent = l.toFixed(1);
    }, 100);
  }
  function applyClick(s) {
    const ui = HUB.S.ui, g = s.game;
    if (ui.first) { ui.first = false; ui.left = g.left; ui.t0 = Date.now(); }
    const max = Math.max(1, ...g.players.map((p) => p.taps));
    $("#crboard").innerHTML = g.players.map((p) => `<div class="cr-row ${p.uid === s.you ? "me" : ""}"><span>${p.uid === s.you ? "You" : esc(K().nameOf(s, p.uid))}</span><div class="gx-bar big"><i style="width:${100 * p.taps / max}%"></i></div><b>${p.taps}</b></div>`).join("");
    $("#crbtn").disabled = !playing(s) || s.status !== "playing";
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).taps + "👆" }));
    K().setHint(playing(s) ? "Tap as fast as you can for 10 seconds!" : "👀 Watching");
    if (s.status === "finished") clearInterval(ui.tm);
  }

  HUB.UI.quest = { build: buildQuest, apply: applyQuest };
  HUB.UI.clickrush = { build: buildClick, apply: applyClick };

  /* =============================== PARTYDROP =============================== */
  function buildDrop(s) {
    K().newUI("partydrop", s, { lastSeq: 0 });
    K().shell(s, `<div class="gx-box"><div class="gx-msg" id="pdmsg">Pass the bomb before it blows!</div><div class="pd-ring" id="pdring"></div></div>`);
    $("#pdring").onclick = (e) => {
      const el = e.target.closest(".pd-p"), s2 = room();
      if (!el || !playing(s2) || s2.game.holder !== s2.you || s2.status !== "playing") return;
      const to = +el.dataset.uid;
      if (to === s2.you || el.classList.contains("out")) return;
      HUB.send({ t: "pass", to }); sfx("pop"); HUB.haptic("medium");
    };
  }
  async function applyDrop(s) {
    const ui = HUB.S.ui, g = s.game, ev = g.last_event, n = g.players.length;
    $("#pdring").innerHTML = g.players.map((p, i) => {
      const a = (i / n) * 2 * Math.PI - Math.PI / 2, x = 50 + 38 * Math.cos(a), y = 50 + 38 * Math.sin(a);
      const nm = p.uid === s.you ? "You" : esc(K().nameOf(s, p.uid));
      return `<div class="pd-p ${p.out ? "out" : ""} ${p.uid === g.holder ? "hold" : ""} ${p.uid === s.you ? "me" : ""}" data-uid="${p.uid}" style="left:${x}%;top:${y}%"><span>${p.out ? "💥" : p.uid === g.holder ? "💣" : "🙂"}</span><small>${nm}</small></div>`;
    }).join("");
    if (ui.first) { ui.first = false; if (ev) ui.lastSeq = ev.seq; }
    else if (ev && ev.seq > ui.lastSeq) {
      ui.lastSeq = ev.seq;
      if (ev.boom) { sfx("hit"); HUB.haptic("heavy"); $("#pdmsg").textContent = "💥 BOOM! " + (ev.to === s.you ? "You're" : K().nameOf(s, ev.to) + " is") + " out!"; }
      else { sfx("place"); HUB.haptic("light"); $("#pdmsg").textContent = (ev.from === s.you ? "You" : K().nameOf(s, ev.from)) + " passed it to " + (ev.to === s.you ? "you" : K().nameOf(s, ev.to)); }
    }
    K().turnFx(ui, s);
    const mine = playing(s) && g.holder === s.you;
    if (mine && s.status === "playing") $("#pdmsg").textContent = "💣 You have the bomb — tap a player to pass it!";
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).out ? "💥" : "" }));
    K().setHint(playing(s) ? (mine ? "Quick! The fuse is short…" : "Waiting for " + K().nameOf(s, g.holder) + "…") : "👀 Watching");
  }

  /* =============================== CHATCLASH =============================== */
  function buildChat(s) {
    K().newUI("chatclash", s, { lastSeq: 0, round: 0 });
    K().shell(s, `<div class="gx-box"><div class="cc-round" id="ccround"></div><div class="cc-phrase" id="ccphrase"></div>
      <form class="wd-in" id="ccform" autocomplete="off"><input id="ccinp" placeholder="Type the phrase…" autocapitalize="none" autocorrect="off" spellcheck="false"><button>Send</button></form>
      <div class="cr-board" id="ccboard"></div></div>`);
    $("#ccform").onsubmit = (e) => {
      e.preventDefault();
      const v = $("#ccinp").value; if (!playing(room())) return;
      HUB.send({ t: "type", text: v }); $("#ccinp").focus();
    };
    $("#ccinp").addEventListener("input", () => {
      const ph = (room().game || {}).phrase || "", v = $("#ccinp").value.toLowerCase();
      $("#ccinp").classList.toggle("bad", !!v && !ph.startsWith(v));
    });
  }
  function applyChat(s) {
    const ui = HUB.S.ui, g = s.game, lr = g.last_round;
    if (ui.round !== g.round) { ui.round = g.round; const i = $("#ccinp"); if (i) { i.value = ""; i.classList.remove("bad"); if (playing(s) && s.status === "playing") i.focus(); } }
    $("#ccround").textContent = `Round ${g.round} · first to ${g.win}`;
    $("#ccphrase").textContent = g.phrase;
    $("#ccboard").innerHTML = g.players.map((p) => `<div class="cr-row ${p.uid === s.you ? "me" : ""}"><span>${p.uid === s.you ? "You" : esc(K().nameOf(s, p.uid))}</span><div class="gx-bar big"><i style="width:${100 * p.score / g.win}%"></i></div><b>${p.score}</b></div>`).join("");
    if (ui.first) { ui.first = false; if (lr) ui.lastSeq = lr.seq; }
    else if (lr && lr.seq > ui.lastSeq) { ui.lastSeq = lr.seq; sfx(lr.winner === s.you ? "win" : "place"); HUB.haptic("light"); HUB.toast && HUB.toast(lr.winner == null ? "Nobody finished!" : (lr.winner === s.you ? "You" : K().nameOf(s, lr.winner)) + " won the round"); }
    $("#ccform").classList.toggle("hidden", !playing(s));
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).score + "★" }));
    K().setHint(playing(s) ? "Type the phrase exactly — first one wins the round" : "👀 Watching");
  }

  /* =============================== PINGPLAY =============================== */
  function buildPing(s) {
    K().newUI("pingplay", s, { lastSeq: 0, round: 0, go: false, timer: null });
    K().shell(s, `<div class="gx-box"><div class="cc-round" id="pground"></div><button class="pg-pad" id="pgpad">Get ready…</button><div class="cr-board" id="pgboard"></div></div>`);
    $("#pgpad").addEventListener("pointerdown", (e) => {
      e.preventDefault(); const s2 = room(); if (!playing(s2) || s2.status !== "playing") return;
      HUB.send({ t: "tap" }); HUB.haptic("medium");
    });
  }
  function applyPing(s) {
    const ui = HUB.S.ui, g = s.game, lr = g.last_round, pad = $("#pgpad");
    $("#pground").textContent = `Round ${g.round} · first to ${g.win}`;
    $("#pgboard").innerHTML = g.players.map((p) => `<div class="cr-row ${p.uid === s.you ? "me" : ""}"><span>${p.uid === s.you ? "You" : esc(K().nameOf(s, p.uid))}${p.foul ? " ⛔" : ""}</span><div class="gx-bar big"><i style="width:${100 * p.score / g.win}%"></i></div><b>${p.score}</b></div>`).join("");
    if (ui.round !== g.round) {
      ui.round = g.round; ui.go = false; clearTimeout(ui.timer);
      pad.className = "pg-pad wait"; pad.textContent = "Wait for GREEN…";
      ui.timer = setTimeout(() => { ui.go = true; pad.className = "pg-pad go"; pad.textContent = "GO! TAP!"; sfx("turn"); HUB.haptic("heavy"); }, g.go_in * 1000);
    }
    const me = g.players.find((p) => p.uid === s.you);
    if (me && me.foul) { pad.className = "pg-pad foul"; pad.textContent = "Too early! ⛔"; }
    if (ui.first) { ui.first = false; if (lr) ui.lastSeq = lr.seq; }
    else if (lr && lr.seq > ui.lastSeq) {
      ui.lastSeq = lr.seq;
      if (lr.why !== "foul") { sfx(lr.winner === s.you ? "win" : "miss"); HUB.toast && HUB.toast(lr.winner == null ? "No winner this round" : (lr.winner === s.you ? "You" : K().nameOf(s, lr.winner)) + " was fastest!"); }
      else sfx("miss");
    }
    if (s.status === "finished") clearTimeout(ui.timer);
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).score + "★" }));
    K().setHint(playing(s) ? "Tap only AFTER it turns green — early taps are out" : "👀 Watching");
  }

  HUB.UI.partydrop = { build: buildDrop, apply: applyDrop };
  HUB.UI.chatclash = { build: buildChat, apply: applyChat };
  HUB.UI.pingplay = { build: buildPing, apply: applyPing };

  /* =============================== COINPULSE =============================== */
  function buildCoin(s) {
    K().newUI("coinpulse", s, { lastSeq: 0, locked: false });
    K().shell(s, `<div class="gx-box"><div class="cc-round" id="cpround"></div><div class="cp-pot" id="cppot"></div><div class="gx-msg" id="cpmsg">GRAB or WAIT — everyone picks at once</div>
      <div class="gx-gears" style="grid-template-columns:1fr 1fr" id="cpbtns"><button class="gx-g" data-p="grab"><span>🤑</span><b>GRAB</b><small>alone = whole pot · clash = −5</small></button><button class="gx-g" data-p="wait"><span>😌</span><b>WAIT</b><small>safe +2</small></button></div>
      <div class="cr-board" id="cpboard"></div></div>`);
    $("#cpbtns").onclick = (e) => {
      const b = e.target.closest(".gx-g"), s2 = room(), ui = HUB.S.ui;
      if (!b || b.disabled || !playing(s2) || ui.locked) return;
      ui.locked = true; HUB.send({ t: "pick", pick: b.dataset.p }); HUB.haptic("medium"); sfx("pop");
      document.querySelectorAll("#cpbtns .gx-g").forEach((x) => x.classList.toggle("sel", x === b));
    };
  }
  function applyCoin(s) {
    const ui = HUB.S.ui, g = s.game, lr = g.last_round;
    $("#cpround").textContent = `Round ${Math.min(g.round + 1, g.rounds)}/${g.rounds}`;
    $("#cppot").textContent = "🪙 Pot: " + g.pot;
    const max = Math.max(1, ...g.players.map((p) => Math.abs(p.score)));
    $("#cpboard").innerHTML = g.players.map((p) => `<div class="cr-row ${p.uid === s.you ? "me" : ""}"><span>${p.uid === s.you ? "You" : esc(K().nameOf(s, p.uid))}${g.picked[p.uid] ? " ✔" : ""}</span><div class="gx-bar big"><i style="width:${Math.max(0, 100 * p.score / max)}%"></i></div><b>${p.score}</b></div>`).join("");
    if (ui.first) { ui.first = false; if (lr) ui.lastSeq = lr.seq; }
    else if (lr && lr.seq > ui.lastSeq) {
      ui.lastSeq = lr.seq; ui.locked = false;
      const nm = (u) => (u === s.you ? "You" : K().nameOf(s, u));
      $("#cpmsg").textContent = lr.result === "take" ? `${nm(lr.taker)} grabbed the pot of ${lr.pot}!` : lr.result === "clash" ? "💥 Clash! Grabbers lose 5 — the pot carries over" : "Nobody grabbed — the pot grows";
      sfx(lr.result === "take" ? (lr.taker === s.you ? "win" : "hit") : "miss"); HUB.haptic("light");
    }
    const ok = playing(s) && s.status === "playing" && !g.picked[s.you];
    if (ok) { ui.locked = false; document.querySelectorAll("#cpbtns .gx-g").forEach((x) => x.classList.remove("sel")); }
    document.querySelectorAll("#cpbtns .gx-g").forEach((b) => { b.disabled = !ok; });
    $("#cpbtns").classList.toggle("hidden", !playing(s));
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).score + "🪙" }));
    K().setHint(playing(s) ? (g.picked[s.you] ? "Waiting for the others…" : "If two people grab, both lose 5. Bluff!") : "👀 Watching");
  }

  /* =============================== SQUADDUEL =============================== */
  const UN = { knight: ["⚔️", "Knight", "beats Archer"], archer: ["🏹", "Archer", "beats Mage"], mage: ["🔮", "Mage", "beats Knight"] };
  function buildSquad(s) {
    K().newUI("squadduel", s, { lastSeq: 0, locked: false });
    K().shell(s, `<div class="gx-box"><div class="cc-round" id="sqround"></div><div class="sq-clash" id="sqclash">⚔️ vs ⚔️</div><div class="gx-msg" id="sqmsg">Send a unit — both squads clash at once</div>
      <div class="gx-gears" id="sqhand"></div></div>`);
    $("#sqhand").onclick = (e) => {
      const b = e.target.closest(".gx-g"), s2 = room(), ui = HUB.S.ui;
      if (!b || b.disabled || !playing(s2) || ui.locked) return;
      ui.locked = true; HUB.send({ t: "send", unit: b.dataset.u }); HUB.haptic("medium"); sfx("pop");
      document.querySelectorAll("#sqhand .gx-g").forEach((x) => x.classList.toggle("sel", x === b));
    };
  }
  function applySquad(s) {
    const ui = HUB.S.ui, g = s.game, lr = g.last_round;
    $("#sqround").textContent = `Round ${Math.min(g.round + 1, g.total)}/${g.total} · ` + g.players.map((p) => `${p.uid === s.you ? "You" : K().nameOf(s, p.uid)} ${p.score}`).join(" — ");
    const cnt = {}; (g.hand || []).forEach((u) => { cnt[u] = (cnt[u] || 0) + 1; });
    $("#sqhand").innerHTML = Object.keys(UN).map((k) => `<button class="gx-g" data-u="${k}" ${cnt[k] ? "" : "disabled"}><span>${UN[k][0]}</span><b>${UN[k][1]} ×${cnt[k] || 0}</b><small>${UN[k][2]}</small></button>`).join("");
    if (ui.first) { ui.first = false; if (lr) ui.lastSeq = lr.seq; }
    else if (lr && lr.seq > ui.lastSeq) {
      ui.lastSeq = lr.seq; ui.locked = false;
      const us = g.players.map((p) => UN[lr.units[p.uid]][0]);
      $("#sqclash").textContent = us.join("  vs  ");
      $("#sqclash").animate([{ transform: "scale(.6)", opacity: 0 }, { transform: "scale(1.15)" }, { transform: "scale(1)" }], { duration: 350 });
      $("#sqmsg").textContent = lr.winner == null ? "Tie — both units fall" : (lr.winner === s.you ? "You" : K().nameOf(s, lr.winner)) + " won the clash!";
      sfx(lr.winner === s.you ? "win" : lr.winner == null ? "place" : "hit"); HUB.haptic("medium");
    }
    const ok = playing(s) && s.status === "playing" && !g.picked[s.you];
    if (ok) { ui.locked = false; }
    document.querySelectorAll("#sqhand .gx-g").forEach((b) => { if (!ok) b.disabled = true; });
    $("#sqhand").classList.toggle("hidden", !playing(s));
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).score + "★" }));
    K().setHint(playing(s) ? "⚔️ beats 🏹 · 🏹 beats 🔮 · 🔮 beats ⚔️ — watch your remaining units" : "👀 Watching");
  }

  /* =============================== TELEARENA =============================== */
  const TCOL = ["#4285f4", "#ea4335", "#fbbc05", "#34a853"];
  function buildTele(s) {
    K().newUI("telearena", s, { lastSeq: 0, locked: false });
    K().shell(s, `<div class="gx-box"><div class="ta-info" id="tainfo"></div><div class="ta-grid" id="tagrid"></div><div class="gx-msg" id="tamsg">Move, teleport or strike — all at once!</div>
      <div class="ta-pad" id="tapad"><span></span><button data-a="n">▲</button><span></span><button data-a="w">◀</button><button data-a="hit" class="hit">💥</button><button data-a="e">▶</button><span></span><button data-a="s">▼</button><button data-a="tp" class="tp">🌀</button></div></div>`);
    $("#tapad").onclick = (e) => {
      const b = e.target.closest("button"), s2 = room(), ui = HUB.S.ui;
      if (!b || b.disabled || !playing(s2) || ui.locked) return;
      ui.locked = true; HUB.send({ t: "act", a: b.dataset.a }); HUB.haptic("medium"); sfx("pop");
    };
  }
  function applyTele(s) {
    const ui = HUB.S.ui, g = s.game, lr = g.last_round, n = g.n;
    let cells = "";
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      const i = g.players.findIndex((p) => p.hp > 0 && p.x === x && p.y === y), p = g.players[i];
      cells += `<div class="ta-c ${(x + y) % 2 ? "alt" : ""}">${p ? `<b style="background:${TCOL[i]}" class="${p.uid === s.you ? "me" : ""}">${p.uid === s.you ? "★" : ""}</b>` : ""}</div>`;
    }
    $("#tagrid").style.gridTemplateColumns = `repeat(${n},1fr)`;
    $("#tagrid").innerHTML = cells;
    $("#tainfo").innerHTML = g.players.map((p, i) => `<span style="color:${TCOL[i]}">${p.uid === s.you ? "You" : esc(K().nameOf(s, p.uid))} ${"♥".repeat(p.hp) || "💀"}${g.picked[p.uid] ? " ✔" : ""}</span>`).join(" · ");
    if (ui.first) { ui.first = false; if (lr) ui.lastSeq = lr.seq; }
    else if (lr && lr.seq > ui.lastSeq) {
      ui.lastSeq = lr.seq; ui.locked = false;
      const hit = Object.entries(lr.hits);
      $("#tamsg").textContent = hit.length ? hit.map(([u, d]) => `${+u === s.you ? "You" : K().nameOf(s, +u)} −${d}`).join(", ") : (lr.events.some((e) => e.e === "tp") ? "🌀 Someone teleported!" : "Round " + lr.round);
      sfx(hit.length ? "hit" : "place"); HUB.haptic(hit.length ? "heavy" : "light");
    }
    const me = g.players.find((p) => p.uid === s.you), ok = !!me && me.hp > 0 && s.status === "playing" && !g.picked[s.you];
    if (ok) ui.locked = false;
    document.querySelectorAll("#tapad button").forEach((b) => { b.disabled = !ok || (b.dataset.a === "tp" && me.cool > 0); });
    $("#tapad").classList.toggle("hidden", !me);
    K().updateBar(ui, s, (uid) => ({ score: "♥".repeat(g.players.find((p) => p.uid === uid).hp) || "💀" }));
    K().setHint(me ? "💥 hits all 8 tiles around you · 🌀 teleports (recharges 2 rounds)" : "👀 Watching");
  }

  HUB.UI.coinpulse = { build: buildCoin, apply: applyCoin };
  HUB.UI.squadduel = { build: buildSquad, apply: applySquad };
  HUB.UI.telearena = { build: buildTele, apply: applyTele };
  HUB.UI.tank = { build: buildTank, apply: applyTank };
  HUB.UI.race = { build: buildRace, apply: applyRace };
  HUB.UI.dominoes = { build: buildDominoes, apply: applyDominoes };
  HUB.UI.wordle = { build: buildWordle, apply: applyWordle };
})();

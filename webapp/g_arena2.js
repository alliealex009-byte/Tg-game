/* Renderers for Poker Showdown, Yahtzee, Simon Duel and MathBlitz. */
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
  const nm = (s, u) => (u === s.you ? "You" : K().nameOf(s, u));

  /* =============================== POKER =============================== */
  const RK = "23456789TJQKA", SU = ["♠", "♥", "♦", "♣"];
  const card = (c) => (c ? `<div class="pk-c ${c[1] === 1 || c[1] === 2 ? "red" : ""}"><b>${RK[c[0]] === "T" ? "10" : RK[c[0]]}</b><i>${SU[c[1]]}</i></div>` : '<div class="pk-c back"></div>');
  function buildPoker(s) {
    K().newUI("poker", s, { lastSeq: 0, locked: false });
    K().shell(s, `<div class="gx-box"><div class="cc-round" id="pkinfo"></div><div class="pk-board" id="pkboard"></div><div class="cp-pot" id="pkpot"></div>
      <div class="gx-msg" id="pkmsg">Stay or fold — everyone decides at once</div><div class="pk-hole" id="pkhole"></div><div class="gx-msg" id="pkbest"></div>
      <div class="gx-gears" style="grid-template-columns:1fr 1fr" id="pkbtns"><button class="gx-g" data-d="stay"><span>✅</span><b>STAY</b><small id="pkcost"></small></button><button class="gx-g" data-d="fold"><span>🏳️</span><b>FOLD</b><small>keep your chips</small></button></div>
      <div class="cr-board" id="pkboardp"></div></div>`);
    $("#pkbtns").onclick = (e) => {
      const b = e.target.closest(".gx-g"), s2 = room(), ui = HUB.S.ui;
      if (!b || b.disabled || !playing(s2) || ui.locked) return;
      ui.locked = true; HUB.send({ t: "bet", do: b.dataset.d }); HUB.haptic("medium"); sfx(b.dataset.d === "stay" ? "chip" : "pop");
      document.querySelectorAll("#pkbtns .gx-g").forEach((x) => x.classList.toggle("sel", x === b));
    };
  }
  function applyPoker(s) {
    const ui = HUB.S.ui, g = s.game, ev = g.last_event;
    $("#pkinfo").textContent = `Hand ${g.hand}/${g.hands}`;
    $("#pkboard").innerHTML = [0, 1, 2, 3, 4].map((i) => card(g.board[i] || null).replace("back", g.board[i] ? "" : "back empty")).join("");
    $("#pkpot").textContent = "💰 Pot: " + g.pot;
    $("#pkhole").innerHTML = (g.mine || []).map(card).join("");
    $("#pkbest").textContent = g.best ? "Your hand: " + g.best : "";
    $("#pkcost").textContent = `pay ${g.stay}`;
    $("#pkboardp").innerHTML = g.players.map((p) => `<div class="cr-row ${p.uid === s.you ? "me" : ""} ${p.in ? "" : "fold"}"><span>${nm(s, p.uid)}${g.picked[p.uid] ? " ✔" : ""}</span><div class="gx-bar big"><i style="width:${Math.min(100, p.chips / 1.5)}%"></i></div><b>${p.chips}</b></div>`).join("");
    if (ui.first) { ui.first = false; if (ev) ui.lastSeq = ev.seq; }
    else if (ev && ev.seq > ui.lastSeq) {
      ui.lastSeq = ev.seq; ui.locked = false;
      if (ev.kind === "showdown") {
        const w = ev.winners.map((u) => nm(s, u)).join(" & ");
        $("#pkmsg").textContent = `${w} won ${ev.pot}` + (ev.early ? " (everyone else folded)" : " with " + ev.cats[ev.winners[0]]);
        sfx(ev.winners.includes(s.you) ? "win" : "hit"); HUB.haptic("medium");
      } else { sfx("flip"); if (ev.folded.length) $("#pkmsg").textContent = ev.folded.map((u) => nm(s, u)).join(", ") + " folded"; }
    }
    const me = g.players.find((p) => p.uid === s.you), ok = !!me && me.in && s.status === "playing" && !g.picked[s.you];
    if (ok) { ui.locked = false; document.querySelectorAll("#pkbtns .gx-g").forEach((x) => x.classList.remove("sel")); }
    document.querySelectorAll("#pkbtns .gx-g").forEach((b) => { b.disabled = !ok; });
    $("#pkbtns").classList.toggle("hidden", !me); $("#pkhole").classList.toggle("hidden", !me);
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).chips + "🪙" }));
    K().setHint(me ? (me.in ? "Stay costs " + g.stay + " chips each street. Best 5-card hand wins the pot" : "You folded — watch the showdown") : "👀 Watching");
  }

  /* =============================== YAHTZEE =============================== */
  const YC = { ones: "Ones", twos: "Twos", threes: "Threes", fours: "Fours", fives: "Fives", sixes: "Sixes", three: "3 of a kind", four: "4 of a kind", full: "Full house (25)", small: "Sm. straight (30)", large: "Lg. straight (40)", yahtzee: "YAHTZEE (50)", chance: "Chance" };
  const FACE = ["", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"];
  function buildYahtzee(s) {
    K().newUI("yahtzee", s, { lastSeq: 0, hold: [false, false, false, false, false], rolling: false });
    K().shell(s, `<div class="gx-box"><div class="yz-dice" id="yzdice"></div><button class="btn primary" id="yzroll">Roll</button><div class="gx-msg" id="yzmsg"></div><div class="yz-card" id="yzcard"></div></div>`);
    $("#yzdice").onclick = (e) => { const b = e.target.closest(".yz-d"), s2 = room(); if (!b || !playing(s2) || s2.game.turn !== s2.you || !s2.game.rolls || s2.game.rolls >= 3) return; const i = +b.dataset.i; HUB.S.ui.hold[i] = !HUB.S.ui.hold[i]; sfx("pop"); applyYahtzee(s2); };
    $("#yzroll").onclick = () => { const s2 = room(), ui = HUB.S.ui; if (!playing(s2) || s2.game.turn !== s2.you || s2.game.rolls >= 3) return; HUB.send({ t: "roll", hold: ui.hold }); sfx("roll"); HUB.haptic("light"); };
    $("#yzcard").onclick = (e) => { const r = e.target.closest("[data-cat]"), s2 = room(); if (!r || !r.classList.contains("open") || !playing(s2) || s2.game.turn !== s2.you || !s2.game.rolls) return; HUB.send({ t: "score", cat: r.dataset.cat }); sfx("place"); HUB.S.ui.hold = [false, false, false, false, false]; };
  }
  function applyYahtzee(s) {
    const ui = HUB.S.ui, g = s.game, lm = g.last_move, my = playing(s) && g.turn === s.you && s.status === "playing";
    if (ui.first) { ui.first = false; if (lm) ui.lastSeq = lm.seq; }
    else if (lm && lm.seq > ui.lastSeq) {
      ui.lastSeq = lm.seq;
      if (lm.kind === "roll") { sfx("roll"); if (lm.uid !== s.you) ui.hold = [false, false, false, false, false]; }
      else { sfx(lm.pts > 0 ? "good" : "miss"); ui.hold = [false, false, false, false, false]; $("#yzmsg").textContent = `${nm(s, lm.uid)} scored ${lm.pts} in ${YC[lm.cat]}`; }
    }
    if (!g.rolls) ui.hold = [false, false, false, false, false];
    $("#yzdice").innerHTML = g.dice.map((d, i) => `<button class="yz-d ${ui.hold[i] ? "held" : ""}" data-i="${i}">${d ? FACE[d] : "·"}</button>`).join("");
    $("#yzroll").textContent = g.rolls >= 3 ? "No rolls left — pick a row" : g.rolls ? `Re-roll unheld (${3 - g.rolls} left)` : "🎲 Roll";
    $("#yzroll").disabled = !my || g.rolls >= 3; $("#yzroll").classList.toggle("hidden", !playing(s));
    const used = (u, c) => g.players.find((p) => p.uid === u).card[c];
    $("#yzcard").innerHTML = `<div class="yz-r head"><span></span>${g.players.map((p) => `<b class="${p.uid === g.turn ? "cur" : ""}">${p.uid === s.you ? "You" : esc(K().nameOf(s, p.uid)).slice(0, 7)}</b>`).join("")}</div>` +
      Object.keys(YC).map((c) => `<div class="yz-r ${my && used(s.you, c) === undefined && g.rolls ? "open" : ""}" data-cat="${c}"><span>${YC[c]}</span>${g.players.map((p) => `<i>${p.card[c] !== undefined ? p.card[c] : (p.uid === g.turn && g.preview[c] !== undefined ? `<em>${g.preview[c]}</em>` : "")}</i>`).join("")}</div>`).join("") +
      `<div class="yz-r head"><span>Total</span>${g.players.map((p) => `<b>${p.total}</b>`).join("")}</div>`;
    K().turnFx(ui, s);
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).total + "pt" }));
    K().setHint(playing(s) ? (my ? (g.rolls ? "Tap dice to HOLD, re-roll, or tap a row to score" : "Roll the dice!") : "Waiting for " + K().nameOf(s, g.turn) + "…") : "👀 Watching");
  }

  /* =============================== SIMON =============================== */
  const SC = ["#ea4335", "#34a853", "#4285f4", "#fbbc05"], SF = [262, 330, 392, 523];
  function buildSimon(s) {
    K().newUI("simon", s, { round: 0, buf: [], showing: false, locked: false });
    K().shell(s, `<div class="gx-box"><div class="cc-round" id="smround"></div><div class="gx-msg" id="smmsg">Watch the sequence…</div><div class="sm-pads" id="smpads">${SC.map((c, i) => `<button class="sm-p" data-i="${i}" style="--c:${c}"></button>`).join("")}</div><div class="sm-dots" id="smdots"></div></div>`);
    $("#smpads").onclick = (e) => {
      const b = e.target.closest(".sm-p"), s2 = room(), ui = HUB.S.ui;
      if (!b || ui.showing || ui.locked || !playing(s2) || s2.status !== "playing") return;
      const me = s2.game.players.find((p) => p.uid === s2.you); if (!me || me.out || s2.game.picked[s2.you]) return;
      const i = +b.dataset.i; flash(i); ui.buf.push(i); $("#smdots").textContent = "●".repeat(ui.buf.length) + "○".repeat(Math.max(0, s2.game.round - ui.buf.length));
      if (ui.buf.length >= s2.game.round) { ui.locked = true; HUB.send({ t: "repeat", seq: ui.buf }); $("#smmsg").textContent = "Sent — waiting for the others…"; }
    };
  }
  function flash(i) { const b = document.querySelector(`.sm-p[data-i="${i}"]`); if (!b) return; b.classList.add("lit"); try { HUB.tone && HUB.tone(SF[i], 0.25, "sine", 0.25); } catch (e) { /* ignore */ } sfx("tick"); setTimeout(() => b.classList.remove("lit"), 300); }
  async function applySimon(s) {
    const ui = HUB.S.ui, g = s.game;
    $("#smround").textContent = `Round ${g.round} · ${g.players.filter((p) => !p.out).length} left` + g.players.map((p) => (p.out ? ` · ${nm(s, p.uid)} ❌` : "")).join("");
    const me = g.players.find((p) => p.uid === s.you);
    if (ui.round !== g.round && g.show) {
      ui.round = g.round; ui.buf = []; ui.locked = false; ui.showing = true; $("#smdots").textContent = "";
      $("#smmsg").textContent = me && !me.out ? "Watch the sequence…" : "👀 Watching";
      const my = ui.round;
      await sleep(500);
      for (const c of g.show) { if (HUB.S.ui !== ui || ui.round !== my) return; flash(c); await sleep(Math.max(320, 620 - g.round * 20)); }
      ui.showing = false;
      if (me && !me.out) $("#smmsg").textContent = "Your turn — repeat it! (" + g.round + " taps)";
    }
    if (g.last_round && g.last_round.failed.includes(s.you) && me && me.out) $("#smmsg").textContent = "❌ Wrong — you're out";
    $("#smpads").classList.toggle("dim", !me || me.out);
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).out ? "❌" : "" }));
    K().setHint(me ? "Remember the colour order and tap it back" : "👀 Watching");
  }

  /* =============================== MATHBLITZ =============================== */
  function buildMath(s) {
    K().newUI("mathblitz", s, { lastSeq: 0, round: 0 });
    K().shell(s, `<div class="gx-box"><div class="cc-round" id="mbround"></div><div class="cc-phrase mb-q" id="mbq"></div>
      <form class="wd-in" id="mbform" autocomplete="off"><input id="mbinp" type="text" inputmode="numeric" pattern="-?[0-9]*" placeholder="Answer"><button>Go</button></form><div class="cr-board" id="mbboard"></div></div>`);
    $("#mbform").onsubmit = (e) => {
      e.preventDefault(); const raw = $("#mbinp").value.trim(); if (!playing(room())) return;
      if (!/^-?\d+$/.test(raw)) { HUB.toast && HUB.toast("Enter a whole number"); return; }
      HUB.send({ t: "answer", value: parseInt(raw, 10) }); $("#mbinp").value = ""; $("#mbinp").focus();
    };
  }
  function applyMath(s) {
    const ui = HUB.S.ui, g = s.game, lr = g.last_round;
    if (ui.round !== g.round) { ui.round = g.round; const i = $("#mbinp"); if (i) { i.value = ""; if (playing(s) && s.status === "playing") i.focus(); } }
    $("#mbround").textContent = `Round ${g.round} · first to ${g.win}`;
    $("#mbq").textContent = g.q + " = ?";
    $("#mbboard").innerHTML = g.players.map((p) => `<div class="cr-row ${p.uid === s.you ? "me" : ""}"><span>${nm(s, p.uid)}</span><div class="gx-bar big"><i style="width:${100 * p.score / g.win}%"></i></div><b>${p.score}</b></div>`).join("");
    if (ui.first) { ui.first = false; if (lr) ui.lastSeq = lr.seq; }
    else if (lr && lr.seq > ui.lastSeq) { ui.lastSeq = lr.seq; sfx(lr.winner === s.you ? "win" : "place"); HUB.toast && HUB.toast((lr.winner == null ? "Nobody got it" : nm(s, lr.winner) + " solved it") + ` — ${lr.q} = ${lr.answer}`); }
    $("#mbform").classList.toggle("hidden", !playing(s));
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).score + "★" }));
    K().setHint(playing(s) ? "First correct answer wins the round — mind the order of operations!" : "👀 Watching");
  }


  /* =============================== WOULD YOU RATHER =============================== */
  function buildWyr(s) {
    K().newUI("wyr", s, { lastSeq: 0, locked: false });
    K().shell(s, `<div class="gx-box"><div class="cc-round" id="wyround"></div><div class="gx-msg" id="wymsg">Pick one — the bigger side scores!</div>
      <div class="wy-opts" id="wyopts"><button class="wy-o a" data-p="a"></button><div class="wy-or">OR</div><button class="wy-o b" data-p="b"></button></div><div class="cr-board" id="wyboard"></div></div>`);
    $("#wyopts").onclick = (e) => {
      const b = e.target.closest(".wy-o"), s2 = room(), ui = HUB.S.ui;
      if (!b || b.disabled || !playing(s2) || ui.locked) return;
      ui.locked = true; HUB.send({ t: "vote", pick: b.dataset.p }); HUB.haptic("medium"); sfx("pop");
      document.querySelectorAll(".wy-o").forEach((x) => x.classList.toggle("sel", x === b));
    };
  }
  function applyWyr(s) {
    const ui = HUB.S.ui, g = s.game, lr = g.last_round;
    $("#wyround").textContent = `Round ${Math.min(g.round + 1, g.rounds)}/${g.rounds}`;
    document.querySelector(".wy-o.a").textContent = g.q.a; document.querySelector(".wy-o.b").textContent = g.q.b;
    $("#wyboard").innerHTML = g.players.map((p) => `<div class="cr-row ${p.uid === s.you ? "me" : ""}"><span>${nm(s, p.uid)}${g.picked[p.uid] ? " ✔" : ""}</span><div class="gx-bar big"><i style="width:${100 * p.score / g.rounds}%"></i></div><b>${p.score}</b></div>`).join("");
    if (ui.first) { ui.first = false; if (lr) ui.lastSeq = lr.seq; }
    else if (lr && lr.seq > ui.lastSeq) {
      ui.lastSeq = lr.seq; ui.locked = false;
      const na = lr.a.length, nb = lr.b.length, mine = lr.a.includes(s.you) ? "a" : lr.b.includes(s.you) ? "b" : null;
      $("#wymsg").textContent = `${g.prev_q ? g.prev_q.a : "A"}: ${na} vs ${g.prev_q ? g.prev_q.b : "B"}: ${nb}` + (lr.win ? (mine === lr.win ? " — you're with the crowd! +1" : " — you were in the minority") : " — a tie, no points");
      sfx(mine && mine === lr.win ? "win" : "place"); HUB.haptic("light");
    }
    const ok = playing(s) && s.status === "playing" && !g.picked[s.you];
    if (ok) { ui.locked = false; document.querySelectorAll(".wy-o").forEach((x) => x.classList.remove("sel")); }
    document.querySelectorAll(".wy-o").forEach((b) => { b.disabled = !ok; });
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).score + "★" }));
    K().setHint(playing(s) ? (g.picked[s.you] ? "Waiting for the others…" : "Vote with the majority to score") : "👀 Watching");
  }

  /* =============================== GUESS THE NUMBER =============================== */
  function buildGuess(s) {
    K().newUI("guessnum", s, { lastSeq: 0 });
    K().shell(s, `<div class="gx-box"><div class="gn-range" id="gnrange"></div><div class="gn-bar"><i id="gnfill"></i></div><div class="gx-msg" id="gnmsg"></div>
      <form class="wd-in" id="gnform" autocomplete="off"><input id="gninp" type="text" inputmode="numeric" placeholder="Your guess"><button>Guess</button></form><div class="gn-hist" id="gnhist"></div></div>`);
    $("#gnform").onsubmit = (e) => {
      e.preventDefault(); const s2 = room(), v = $("#gninp").value.trim();
      if (!playing(s2) || s2.game.turn !== s2.you) { HUB.toast && HUB.toast("Wait for your turn"); return; }
      if (!/^\d+$/.test(v)) { HUB.toast && HUB.toast("Enter a whole number"); return; }
      HUB.send({ t: "guess", n: parseInt(v, 10) }); $("#gninp").value = ""; sfx("pop");
    };
  }
  function applyGuess(s) {
    const ui = HUB.S.ui, g = s.game, lm = g.last_move, my = playing(s) && g.turn === s.you && s.status === "playing";
    $("#gnrange").textContent = `It's between ${g.lo} and ${g.hi}`;
    $("#gnfill").style.cssText = `left:${(g.lo - 1) / g.range * 100}%;width:${(g.hi - g.lo + 1) / g.range * 100}%`;
    $("#gnhist").innerHTML = g.history.slice().reverse().map((h) => `<div class="gn-h ${h.hint}"><span>${nm(s, h.uid)}</span><b>${h.n}</b><em>${h.hint === "higher" ? "⬆️ higher" : h.hint === "lower" ? "⬇️ lower" : "🎯 correct!"}</em></div>`).join("");
    if (ui.first) { ui.first = false; if (lm) ui.lastSeq = lm.seq; }
    else if (lm && lm.seq > ui.lastSeq) { ui.lastSeq = lm.seq; sfx(lm.hint === "correct" ? "win" : "place"); HUB.haptic("light"); $("#gnmsg").textContent = `${nm(s, lm.uid)} guessed ${lm.n}: ${lm.hint}`; }
    if (g.secret != null) $("#gnmsg").textContent = "The number was " + g.secret;
    $("#gnform").classList.toggle("hidden", !playing(s)); $("#gninp").disabled = !my;
    if (my) $("#gninp").focus();
    K().turnFx(ui, s);
    K().updateBar(ui, s, () => ({}));
    K().setHint(playing(s) ? (my ? "Your turn — guess between " + g.lo + " and " + g.hi : "Waiting for " + K().nameOf(s, g.turn) + "…") : "👀 Watching");
  }

  /* =============================== EMOJIQUIZ =============================== */
  function buildEmoji(s) {
    K().newUI("emojiquiz", s, { lastSeq: 0, round: 0 });
    K().shell(s, `<div class="gx-box"><div class="cc-round" id="eqround"></div><div class="cc-phrase eq-q" id="eqq"></div>
      <form class="wd-in" id="eqform" autocomplete="off"><input id="eqinp" placeholder="Movie / word…" autocapitalize="none" autocorrect="off" spellcheck="false"><button>Send</button></form><div class="cr-board" id="eqboard"></div></div>`);
    $("#eqform").onsubmit = (e) => { e.preventDefault(); if (!playing(room())) return; HUB.send({ t: "answer", text: $("#eqinp").value }); $("#eqinp").focus(); };
  }
  function applyEmoji(s) {
    const ui = HUB.S.ui, g = s.game, lr = g.last_round;
    if (ui.round !== g.round) { ui.round = g.round; const i = $("#eqinp"); if (i) { i.value = ""; if (playing(s) && s.status === "playing") i.focus(); } }
    $("#eqround").textContent = `Round ${g.round} · first to ${g.win}`;
    $("#eqq").textContent = g.emoji;
    $("#eqboard").innerHTML = g.players.map((p) => `<div class="cr-row ${p.uid === s.you ? "me" : ""}"><span>${nm(s, p.uid)}</span><div class="gx-bar big"><i style="width:${100 * p.score / g.win}%"></i></div><b>${p.score}</b></div>`).join("");
    if (ui.first) { ui.first = false; if (lr) ui.lastSeq = lr.seq; }
    else if (lr && lr.seq > ui.lastSeq) { ui.lastSeq = lr.seq; sfx(lr.winner === s.you ? "win" : "place"); HUB.toast && HUB.toast((lr.winner == null ? "Nobody got it" : nm(s, lr.winner) + " got it") + ` — ${lr.emoji} = ${lr.answer}`); }
    $("#eqform").classList.toggle("hidden", !playing(s));
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).score + "★" }));
    K().setHint(playing(s) ? "Guess the movie, phrase or thing from the emojis" : "👀 Watching");
  }

  /* =============================== PENALTY SHOOTOUT =============================== */
  const DN = { l: 0, c: 1, r: 2 };
  function buildPenalty(s) {
    K().newUI("penalty", s, { lastSeq: 0, locked: false });
    K().shell(s, `<div class="gx-box"><div class="pn-score" id="pnscore"></div><div class="pn-goal" id="pngoal"><div class="pn-z" data-d="l"></div><div class="pn-z" data-d="c"></div><div class="pn-z" data-d="r"></div><div class="pn-ball" id="pnball">⚽</div><div class="pn-keep" id="pnkeep">🧤</div></div>
      <div class="gx-msg" id="pnmsg"></div><div class="pn-dots" id="pndots"></div></div>`);
    $("#pngoal").onclick = (e) => {
      const z = e.target.closest(".pn-z"), s2 = room(), ui = HUB.S.ui;
      if (!z || !playing(s2) || ui.locked || s2.status !== "playing" || s2.game.picked[s2.you]) return;
      ui.locked = true; HUB.send({ t: "dir", dir: z.dataset.d }); HUB.haptic("medium"); sfx("pop");
      document.querySelectorAll(".pn-z").forEach((x) => x.classList.toggle("sel", x === z));
    };
  }
  async function applyPenalty(s) {
    const ui = HUB.S.ui, g = s.game, lk = g.last_kick;
    const me = playing(s), shooting = me && g.shooter === s.you;
    $("#pnscore").innerHTML = g.players.map((p) => `<span class="${p.uid === s.you ? "me" : ""}">${nm(s, p.uid)} <b>${p.goals}</b></span>`).join(" — ");
    if (ui.first) { ui.first = false; if (lk) ui.lastSeq = lk.seq; }
    else if (lk && lk.seq > ui.lastSeq) {
      ui.lastSeq = lk.seq; ui.locked = false;
      const ball = $("#pnball"), keep = $("#pnkeep");
      const pos = (d) => 17 + DN[d] * 33;
      ball.style.left = pos(lk.shot) + "%"; ball.style.top = "30%"; keep.style.left = pos(lk.dive) + "%";
      sfx(lk.goal ? "win" : "hit"); HUB.haptic("heavy");
      $("#pnmsg").textContent = lk.goal ? "⚽ GOAL!" : "🧤 SAVED!";
      $("#pnmsg").animate([{ transform: "scale(.6)" }, { transform: "scale(1.2)" }, { transform: "scale(1)" }], { duration: 350 });
      await sleep(900);
      ball.style.left = "50%"; ball.style.top = "85%"; keep.style.left = "50%";
    }
    const mine = g.players.find((p) => p.uid === s.you);
    if (s.status === "playing") { const ok = me && !g.picked[s.you]; if (ok) { ui.locked = false; document.querySelectorAll(".pn-z").forEach((x) => x.classList.remove("sel")); } $("#pngoal").classList.toggle("dim", !ok); }
    $("#pndots").innerHTML = g.players.map((p) => `<div>${nm(s, p.uid)} ` + Array.from({ length: Math.max(g.kicks, p.taken) }, (_, i) => `<i class="${i < p.taken ? "t" : ""}"></i>`).join("") + "</div>").join("");
    if (!lk || lk.seq <= ui.lastSeq - 0) { /* message stays from the last kick */ }
    if (s.status === "playing" && me) $("#pnmsg").textContent = shooting ? "🎯 You SHOOT — pick a corner!" : "🧤 You're the KEEPER — guess where it goes!";
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).goals + "⚽" }));
    K().setHint(me ? "Same corner = saved. Mix it up!" : "👀 Watching the shootout");
  }

  HUB.UI.wyr = { build: buildWyr, apply: applyWyr };
  HUB.UI.guessnum = { build: buildGuess, apply: applyGuess };
  HUB.UI.emojiquiz = { build: buildEmoji, apply: applyEmoji };
  HUB.UI.penalty = { build: buildPenalty, apply: applyPenalty };

  /* =============================== SCRIBBLE =============================== */
  const CW = 680, CH = 560;
  function drawStrokes(cv, strokes) {
    const c = cv.getContext("2d"); c.fillStyle = "#fff"; c.fillRect(0, 0, CW, CH); c.lineCap = "round"; c.lineJoin = "round";
    strokes.forEach((st) => {
      c.strokeStyle = st.c; c.fillStyle = st.c; c.lineWidth = st.w * 2.2;
      const p = st.p; if (!p.length) return;
      if (p.length === 1) { c.beginPath(); c.arc(p[0][0] * CW, p[0][1] * CH, st.w * 1.1, 0, 7); c.fill(); return; }
      c.beginPath(); c.moveTo(p[0][0] * CW, p[0][1] * CH); for (let i = 1; i < p.length; i++) c.lineTo(p[i][0] * CW, p[i][1] * CH); c.stroke();
    });
  }
  function buildScribble(s) {
    K().newUI("scribble", s, { lastSeq: 0, turn: 0, color: "#111111", w: 4, sid: Math.floor(Math.random() * 1e6), buf: [], drawing: false, flushT: 0, t0: Date.now(), left: s.game.left, tm: 0, sent: 0 });
    K().shell(s, `<div class="gx-box"><div class="sc-top"><b id="scword"></b><span id="sctime"></span></div>
      <canvas id="sccv" class="sc-cv" width="${CW}" height="${CH}"></canvas>
      <div class="sc-tools hidden" id="sctools"></div>
      <form class="wd-in hidden" id="scform" autocomplete="off"><input id="scinp" placeholder="Type your guess…" autocapitalize="none" autocorrect="off" spellcheck="false"><button>Guess</button></form>
      <div class="sc-chat" id="scchat"></div><div class="cr-board" id="scboard"></div></div>`);
    const ui = HUB.S.ui, cv = $("#sccv");
    const pos = (e) => { const r = cv.getBoundingClientRect(); return [Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))]; };
    const flush = () => {
      if (!ui.buf.length) return;
      const chunk = ui.buf.splice(0, 60); HUB.send({ t: "stroke", id: ui.sid, p: chunk, c: ui.color, w: ui.w });
      if (ui.buf.length) flush();
    };
    const imDrawer = () => { const s2 = room(); return s2 && s2.game.drawer === s2.you && s2.status === "playing"; };
    cv.addEventListener("pointerdown", (e) => {
      if (!imDrawer()) return; e.preventDefault(); cv.setPointerCapture(e.pointerId);
      ui.drawing = true; ui.sid = (ui.sid + 1) % 1e9; const p = pos(e); ui.buf = [p]; ui.last = p;
      const c = cv.getContext("2d"); c.fillStyle = ui.color; c.beginPath(); c.arc(p[0] * CW, p[1] * CH, ui.w * 1.1, 0, 7); c.fill();
      clearInterval(ui.flushT); ui.flushT = setInterval(flush, 180);
    });
    cv.addEventListener("pointermove", (e) => {
      if (!ui.drawing) return; const p = pos(e), c = cv.getContext("2d");
      c.strokeStyle = ui.color; c.lineWidth = ui.w * 2.2; c.lineCap = "round"; c.beginPath(); c.moveTo(ui.last[0] * CW, ui.last[1] * CH); c.lineTo(p[0] * CW, p[1] * CH); c.stroke();
      ui.last = p; ui.buf.push(p);
    });
    const up = () => { if (!ui.drawing) return; ui.drawing = false; clearInterval(ui.flushT); flush(); };
    cv.addEventListener("pointerup", up); cv.addEventListener("pointercancel", up);
    $("#scform").onsubmit = (e) => { e.preventDefault(); const v = $("#scinp").value.trim(); if (!v) return; HUB.send({ t: "guess", text: v }); $("#scinp").value = ""; $("#scinp").focus(); };
    $("#sctools").onclick = (e) => {
      const b = e.target.closest("[data-a]"); if (!b || !imDrawer()) return;
      const a = b.dataset.a;
      if (a === "c") { ui.color = b.dataset.v; } else if (a === "w") { ui.w = +b.dataset.v; } else if (a === "undo") HUB.send({ t: "undo" }); else if (a === "clear") HUB.send({ t: "clear" });
      sfx("pop"); paintTools();
    };
    function paintTools() {
      const g = room().game;
      $("#sctools").innerHTML = g.colors.map((c) => `<i class="sc-c ${c === ui.color ? "sel" : ""}" data-a="c" data-v="${c}" style="background:${c}"></i>`).join("") +
        [2, 4, 6].map((w) => `<button class="sc-b ${w === ui.w ? "sel" : ""}" data-a="w" data-v="${w}">${w === 2 ? "·" : w === 4 ? "●" : "⬤"}</button>`).join("") + '<button class="sc-b" data-a="undo">↩️</button><button class="sc-b" data-a="clear">🗑️</button>';
    }
    ui.paintTools = paintTools;
    clearInterval(ui.tm);
    ui.tm = setInterval(() => { const el = $("#sctime"); if (!el) { clearInterval(ui.tm); return; } el.textContent = "⏱ " + Math.max(0, Math.ceil(ui.left - (Date.now() - ui.t0) / 1000)) + "s"; }, 250);
  }

  function applyScribble(s) {
    const ui = HUB.S.ui, g = s.game, lt = g.last_turn, cv = $("#sccv");
    if (!cv) return;
    const mineDraw = g.drawer === s.you, me = playing(s), got = g.guessed.includes(s.you);
    ui.left = g.left; ui.t0 = Date.now();
    if (!ui.drawing) drawStrokes(cv, g.strokes);
    $("#scword").textContent = g.word ? (mineDraw ? "✏️ Draw: " : "✅ ") + g.word.toUpperCase() : "_ ".repeat(g.len).trim() + `  (${g.len})`;
    $("#sctools").classList.toggle("hidden", !mineDraw || s.status !== "playing");
    if (mineDraw && s.status === "playing") ui.paintTools();
    $("#scform").classList.toggle("hidden", !me || mineDraw || got || s.status !== "playing");
    cv.classList.toggle("can", mineDraw);
    $("#scchat").innerHTML = g.chat.map((m) => m.ok ? `<div class="ok">✅ ${nm(s, m.uid)} guessed it!${m.pts ? " +" + m.pts : ""}</div>` : `<div><b>${nm(s, m.uid)}:</b> ${esc(m.text)}</div>`).join("");
    $("#scchat").scrollTop = 1e6;
    $("#scboard").innerHTML = g.players.map((p) => `<div class="cr-row ${p.uid === s.you ? "me" : ""}"><span>${p.uid === g.drawer ? "🎨 " : g.guessed.includes(p.uid) ? "✅ " : ""}${nm(s, p.uid)}</span><div class="gx-bar big"><i style="width:${Math.min(100, p.score / 4)}%"></i></div><b>${p.score}</b></div>`).join("");
    if (ui.first) { ui.first = false; if (lt) ui.lastSeq = lt.seq; }
    else if (lt && lt.seq > ui.lastSeq) { ui.lastSeq = lt.seq; sfx("place"); HUB.toast && HUB.toast(`The word was "${lt.word}"` + (lt.guessed.length ? "" : " — nobody guessed it")); }
    if (g.guessed.length && !ui.lastGuessed || (g.guessed.length > (ui.lastGuessed || 0))) sfx("good");
    ui.lastGuessed = g.guessed.length;
    K().turnFx(ui, s);
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).score + "pt" }));
    K().setHint(me ? (mineDraw ? "You're the artist — draw the word, no letters!" : got ? "You got it! Wait for the others" : `Guess the drawing · turn ${g.turn_no}/${g.turns}`) : "👀 Watching");
  }

  HUB.UI.scribble = { build: buildScribble, apply: applyScribble };
  HUB.UI.poker = { build: buildPoker, apply: applyPoker };
  HUB.UI.yahtzee = { build: buildYahtzee, apply: applyYahtzee };
  HUB.UI.simon = { build: buildSimon, apply: applySimon };
  HUB.UI.mathblitz = { build: buildMath, apply: applyMath };
})();

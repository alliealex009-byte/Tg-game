/* Renderers for Mafia, Hangman, Mastermind and Trivia. Each registers { build(state), apply(state) } in HUB.UI.
   Spectators (state.you not a player) get read-only views. CSS classes are prefixed gp-. */
(function () {
  "use strict";
  window.HUB = window.HUB || { UI: {} };
  const HUB = window.HUB;
  const $ = (s, r) => (r || document).querySelector(s);
  const K = () => HUB.kit;
  const sfx = (n) => { try { HUB.sfx[n](); } catch (e) { /* ignore */ } };
  const playing = (s) => s.game.players.some((p) => p.uid === s.you);
  const rp = (s, uid) => s.players.find((p) => p.uid === uid) || { uid, name: "Player" };
  const nm = (s, uid) => (uid === s.you ? "You" : rp(s, uid).name);
  const live = (ui) => HUB.S.ui === ui;

  /* countdown bar shared by phase-timed games */
  function clock(ui, sel) {
    if (ui.clk) return;
    ui.clk = setInterval(() => {
      if (!live(ui)) { clearInterval(ui.clk); return; }
      const el = $(sel);
      if (!el) return;
      const left = ui.deadline ? Math.max(0, (ui.deadline - performance.now()) / 1000) : 0;
      el.style.width = (ui.deadline ? Math.min(100, (100 * left) / (ui.turnSeconds || 15)) : 0) + "%";
      el.classList.toggle("low", left <= 5 && left > 0);
      const sec = Math.ceil(left);
      if (ui.deadline && sec <= 5 && sec > 0 && ui.tickSec !== sec && ui.ticking) { ui.tickSec = sec; sfx("tick"); }
    }, 120);
  }
  async function banner(text, ms, cls) {
    const b = document.createElement("div");
    b.className = "gp-banner " + (cls || "");
    b.innerHTML = text;
    document.body.appendChild(b);
    await HUB.sleep(ms || 1500);
    b.classList.add("out");
    await HUB.sleep(300);
    b.remove();
  }

  /* =====================================================================  MAFIA */
  const ROLE = {
    mafia: { e: "🔪", t: "Mafia", d: "Each night, choose a victim with your team. By day, blend in." },
    doctor: { e: "💉", t: "Doctor", d: "Each night, protect one player from the Mafia (not the same one twice in a row)." },
    detective: { e: "🔍", t: "Detective", d: "Each night, investigate one player to learn if they are Mafia." },
    villager: { e: "🏘️", t: "Villager", d: "Find the Mafia. Discuss in the chat, then vote." },
  };
  function buildMafia(s) {
    K().newUI("mafia", s, { lastSeq: 0, phaseKey: "", ticking: true });
    K().shell(s, `<div class="gp-mafia night" id="gpm">
      <div class="gp-sky"><span class="gp-orb" id="gporb">🌙</span></div>
      <div class="gp-phase" id="gpphase"></div>
      <div class="gp-time"><i id="gpclk"></i></div>
      <div class="gp-role" id="gprole"></div>
      <div class="gp-say" id="gpsay"></div>
      <div class="gp-tiles" id="gptiles"></div>
      <div class="gp-acts" id="gpacts"></div>
      <div class="gp-notes" id="gpnotes"></div></div>`);
    clock(HUB.S.ui, "#gpclk");
  }
  function roleCard(s, g) {
    const me = g.me, el = $("#gprole");
    if (!me) { el.innerHTML = '<div class="gp-spec">👁 You are watching</div>'; return; }
    const r = ROLE[me.role], ui = HUB.S.ui;
    const mates = me.mates.filter((u) => u !== s.you).map((u) => nm(s, u)).join(", ");
    el.innerHTML = `<div class="gp-card ${ui.flipped ? "flip" : ""}" id="gpcard"><div class="in">
      <div class="f front">🎭<small>Your role</small></div>
      <div class="f back"><b>${r.e} ${r.t}</b><small>${r.d}${mates ? "<br>Teammate: " + HUB.esc(mates) : ""}</small></div></div></div>`;
    if (!ui.flipped) setTimeout(() => { if (live(ui)) { ui.flipped = true; const c = $("#gpcard"); if (c) c.classList.add("flip"); sfx("flip"); } }, 700);
    $("#gpcard").addEventListener("click", () => { $("#gpcard").classList.toggle("flip"); });
  }
  function canTarget(s, g, p) {
    const me = g.me;
    if (!me || !me.alive || s.status !== "playing" || !p.alive) return false;
    if (g.phase === "night") {
      if (!me.pending) return false;
      if (me.role === "mafia") return !me.mates.includes(p.uid);
      if (me.role === "doctor") return p.uid !== me.can_save_not;
      if (me.role === "detective") return p.uid !== s.you;
      return false;
    }
    if (g.phase === "vote") return p.uid !== s.you;
    return false;
  }
  function mafiaTiles(s, g) {
    const me = g.me, votes = g.votes || {}, tally = {};
    Object.values(votes).forEach((t) => { tally[t] = (tally[t] || 0) + 1; });
    const maxv = Math.max(1, ...Object.values(tally));
    const picks = me && me.role === "mafia" ? Object.values(me.picks || {}) : [];
    $("#gptiles").innerHTML = g.players.map((p) => {
      const r = rp(s, p.uid), can = canTarget(s, g, p);
      const mine = me && (me.pick === p.uid || me.vote === p.uid);
      const role = p.role ? ROLE[p.role] : null;
      return `<button class="gp-tile ${p.alive ? "" : "dead"} ${can ? "can" : ""} ${mine ? "sel" : ""} ${p.uid === s.you ? "me" : ""}" data-uid="${p.uid}" ${can ? "" : "disabled"}>
        <div class="av"><div class="avatar">${HUB.avatarInner(r)}</div>${p.alive ? "" : '<i class="x">✖</i>'}</div>
        <b>${HUB.esc((r.name || "Player").slice(0, 10))}</b>
        <small>${role ? role.e + " " + role.t : p.alive ? (p.uid === s.you ? "you" : "alive") : "out"}</small>
        ${g.phase === "vote" && tally[p.uid] ? `<span class="gp-votes" style="--w:${(100 * tally[p.uid]) / maxv}%">${tally[p.uid]}</span>` : ""}
        ${picks.includes(p.uid) ? '<span class="gp-mark">🔪</span>' : ""}</button>`;
    }).join("");
    $("#gptiles").querySelectorAll(".gp-tile.can").forEach((b) => b.addEventListener("click", () => {
      const t = { mafia: "kill", doctor: "save", detective: "probe" }[me.role];
      HUB.send(g.phase === "vote" ? { t: "vote", target: +b.dataset.uid } : { t, target: +b.dataset.uid });
      HUB.haptic(); sfx("vote");
    }));
  }
  async function applyMafia(s) {
    const ui = HUB.S.ui, g = s.game, me = g.me, box = $("#gpm");
    const over = s.status === "finished" || g.phase === "over";
    ui.ticking = !over && me && me.alive;
    const key = g.phase + g.day;
    box.classList.toggle("night", g.phase === "night");
    box.classList.toggle("day", g.phase !== "night");
    $("#gporb").textContent = g.phase === "night" ? "🌙" : g.phase === "vote" ? "⚖️" : "☀️";
    $("#gpphase").textContent = over ? "🏁 Game over" : g.phase === "night" ? `🌙 Night ${g.day}` : g.phase === "day" ? `☀️ Day ${g.day} · discuss` : `🗳 Day ${g.day} · vote`;
    if (!ui.first && key !== ui.phaseKey && !over) { sfx(g.phase === "night" ? "night" : g.phase === "day" ? "day" : "vote"); }
    ui.phaseKey = key;
    if (ui.first) roleCard(s, g);
    const ev = g.last_event;
    if (ui.first) { ui.first = false; ui.lastSeq = ev ? ev.seq : 0; }
    else if (ev && ev.seq > ui.lastSeq) {
      ui.lastSeq = ev.seq;
      if (ev.kind === "dawn") {
        const who = ev.killed ? nm(s, ev.killed) : null;
        if (who) { dieAnim(ev.killed); sfx("hit"); HUB.haptic("heavy"); await banner(`☀️ Dawn<br>💀 <b>${HUB.esc(who)}</b> was killed<br><small>They were ${ROLE[ev.role].e} ${ROLE[ev.role].t}</small>`, 2200); }
        else { sfx("good"); await banner(ev.saved ? "☀️ Dawn<br>💉 The Doctor saved someone!<br><small>Nobody died</small>" : "☀️ Dawn<br>Nobody died tonight", 1800); }
      } else if (ev.kind === "vote") {
        if (ev.eliminated) { dieAnim(ev.eliminated); sfx("bad"); await banner(`🗳 <b>${HUB.esc(nm(s, ev.eliminated))}</b> was voted out<br><small>They were ${ROLE[ev.role].e} ${ROLE[ev.role].t}</small>`, 2200); }
        else await banner("🗳 No majority<br>Nobody is eliminated", 1600);
      } else if (ev.kind === "left") { await banner(`🚪 ${HUB.esc(nm(s, ev.uid))} left the game`, 1200); }
    }
    mafiaTiles(s, g);
    K().updateBar(ui, s, (uid) => { const p = g.players.find((x) => x.uid === uid); return { score: p && !p.alive ? "💀" : "" }; });
    const say = $("#gpsay"), acts = $("#gpacts");
    let msg = "", btns = "";
    if (over) {
      msg = g.win_team === "town" ? "🎉 Town wins! The Mafia are gone." : "🔪 The Mafia take over the town!";
    } else if (!me) msg = "Watching: roles stay hidden until the end.";
    else if (!me.alive) msg = "👻 You are out. Watch quietly — no spoilers in the chat!";
    else if (g.phase === "night") {
      msg = { mafia: me.pending ? "🔪 Choose who to eliminate" : "✅ Choice made — waiting for dawn", doctor: me.pending ? "💉 Choose who to protect tonight" : "✅ Protected — waiting for dawn",
        detective: me.pending ? "🔍 Choose who to investigate" : "✅ Investigated — waiting for dawn", villager: "😴 You sleep… wait for dawn" }[me.role];
    } else if (g.phase === "day") {
      msg = "💬 Discuss in the chat. Who is the Mafia?";
      btns = me.skipped ? `<span class="gp-wait">Ready ✓ (${g.skipped} ready)</span>` : '<button class="gp-btn" id="gpready">✅ Ready to vote</button>';
    } else {
      msg = me.vote === undefined || me.vote === null ? "🗳 Tap a player to vote them out" : me.vote === 0 ? "You skipped the vote" : `You voted for ${nm(s, me.vote)}`;
      btns = '<button class="gp-btn ghost" id="gpskip">Skip vote</button>';
    }
    say.textContent = msg; acts.innerHTML = btns;
    const rd = $("#gpready"); if (rd) rd.addEventListener("click", () => { HUB.send({ t: "skip" }); HUB.haptic(); });
    const sk = $("#gpskip"); if (sk) sk.addEventListener("click", () => { HUB.send({ t: "vote", target: 0 }); HUB.haptic(); });
    const pr = (me && me.probes || []).filter((p) => p.target);
    $("#gpnotes").innerHTML = pr.length ? "<b>🔍 Your findings</b>" + pr.map((p) => `<div>${HUB.esc(nm(s, p.target))}: ${p.team === "mafia" ? "🔪 <b>Mafia!</b>" : "✅ Town"}</div>`).join("") : "";
    K().setHint(over ? "" : "Use 💬 chat to talk during the day");
  }
  function dieAnim(uid) {
    const t = document.querySelector(`.gp-tile[data-uid="${uid}"]`);
    if (t) t.classList.add("dying");
  }

  /* =====================================================================  HANGMAN */
  const KEYS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"];
  function gallows(wrong) {
    const part = (i, svg) => `<g class="gp-part ${wrong >= i ? "on" : ""}">${svg}</g>`;
    return `<svg viewBox="0 0 160 190" class="gp-gal">
      <g stroke="#caa56a" stroke-width="6" stroke-linecap="round" fill="none"><path d="M20 180H100M40 180V15H115V35"/><path d="M40 55L60 15"/></g>
      <g stroke="#f3f3f3" stroke-width="5" stroke-linecap="round" fill="none">
      ${part(1, '<circle cx="115" cy="50" r="15" fill="#2a2a30"/><circle cx="110" cy="47" r="2" fill="#fff"/><circle cx="120" cy="47" r="2" fill="#fff"/>')}
      ${part(2, '<path d="M115 65V115"/>')}${part(3, '<path d="M115 80L92 100"/>')}${part(4, '<path d="M115 80L138 100"/>')}
      ${part(5, '<path d="M115 115L96 145"/>')}${part(6, '<path d="M115 115L134 145"/>')}</g></svg>`;
  }
  function buildHang(s) {
    K().newUI("hangman", s, { lastSeq: 0 });
    K().shell(s, `<div class="gp-hang"><div class="gp-meta"><span id="gphcat"></span><span id="gphround"></span><span id="gphwrong"></span></div>
      <div id="gphgal"></div><div class="gp-word" id="gphword"></div><div class="gp-kb" id="gphkb"></div></div>`);
    $("#gphkb").innerHTML = KEYS.map((r) => `<div>${r.split("").map((c) => `<button class="gp-key" data-l="${c}">${c}</button>`).join("")}</div>`).join("");
    $("#gphkb").addEventListener("click", (e) => {
      const b = e.target.closest(".gp-key"), s2 = HUB.S.room;
      if (!b || b.disabled || !s2 || s2.game.turn !== s2.you) return;
      HUB.send({ t: "guess", letter: b.dataset.l }); HUB.haptic();
    });
  }
  async function applyHang(s) {
    const ui = HUB.S.ui, g = s.game;
    const word = (mask) => { $("#gphword").innerHTML = mask.map((c) => `<span class="${c ? "on" : ""}">${c ? c.toUpperCase() : ""}</span>`).join(""); };
    const draw = () => {
      $("#gphcat").textContent = "📂 " + g.category; $("#gphround").textContent = `Word ${g.round}/${g.rounds}`;
      $("#gphwrong").textContent = `❌ ${g.wrong}/${g.max_wrong}`;
      $("#gphgal").innerHTML = gallows(g.wrong);
      word(g.mask);
      const inWord = new Set(g.mask.filter(Boolean));
      document.querySelectorAll(".gp-key").forEach((b) => {
        const used = g.guessed.includes(b.dataset.l);
        b.classList.toggle("used", used); b.classList.toggle("hit", used && inWord.has(b.dataset.l)); b.classList.toggle("miss", used && !inWord.has(b.dataset.l));
        b.disabled = used || !(s.status === "playing" && g.turn === s.you && playing(s));
      });
    };
    const lw = g.last_word, lg = g.last_guess;
    if (ui.first) {
      ui.first = false; ui.lastSeq = Math.max(lw ? lw.seq : 0, lg ? lg.seq : 0); draw();
    } else if ((lw && lw.seq > ui.lastSeq) || (lg && lg.seq > ui.lastSeq)) {
      const ended = lw && lw.seq > ui.lastSeq;
      if (lg && lg.seq > ui.lastSeq && (!ended || lg.seq < lw.seq)) {
        sfx(lg.hit ? "good" : "bad"); HUB.haptic(lg.hit ? "light" : "heavy");
        // show the previous board plus this guess so the letter pops before a new word replaces it
        if (!ended) { ui.lastSeq = lg.seq; draw(); const spans = document.querySelectorAll(".gp-word span.on"); spans.forEach((x) => { if (x.textContent === lg.letter.toUpperCase()) x.classList.add("pop"); }); }
      }
      if (ended) {
        ui.lastSeq = lw.seq;
        $("#gphword").innerHTML = lw.word.split("").map((c) => `<span class="on pop">${c.toUpperCase()}</span>`).join("");
        if (lg && lg.seq < lw.seq || !lg.hit) $("#gphgal").innerHTML = gallows(lw.solved_by ? g.wrong : g.max_wrong);
        sfx(lw.solved_by ? "win" : "lose");
        await banner(lw.solved_by ? `🎉 <b>${HUB.esc(nm(s, lw.solved_by))}</b> solved it!<br><small>${lw.word.toUpperCase()}</small>` : `💀 Out of guesses<br><small>The word was ${lw.word.toUpperCase()}</small>`, 1900);
        if (s.status !== "finished") draw();
      }
    } else draw();
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).score }));
    K().setHint(s.status !== "playing" ? "" : g.turn === s.you ? "Pick a letter — a correct one lets you go again" : K().turnHint(s));
    K().turnFx(ui, s);
  }

  /* =====================================================================  MASTERMIND */
  const MC = ["#ef5350", "#ffa726", "#ffee58", "#66bb6a", "#42a5f5", "#ab47bc"];
  const peg = (c) => `<i class="gp-dot" style="background:${c === null || c === undefined ? "transparent" : MC[c]}"></i>`;
  function fb(b, w) {
    let h = "";
    for (let i = 0; i < 4; i++) h += `<i class="gp-fb ${i < b ? "b" : i < b + w ? "w" : ""}"></i>`;
    return `<span class="gp-fbs">${h}</span>`;
  }
  function buildMind(s) {
    K().newUI("mastermind", s, { lastSeq: 0, cur: [null, null, null, null] });
    K().shell(s, `<div class="gp-mind"><div class="gp-secret" id="gpmsec"></div><div class="gp-boards" id="gpmb"></div>
      <div class="gp-guess" id="gpmcur"></div><div class="gp-pal" id="gpmpal">${MC.map((c, i) => `<button class="gp-pc" data-c="${i}" style="background:${c}"></button>`).join("")}</div>
      <div class="gp-acts"><button class="gp-btn ghost" id="gpmclr">Clear</button><button class="gp-btn" id="gpmok">Guess</button></div></div>`);
    const ui = HUB.S.ui;
    $("#gpmpal").addEventListener("click", (e) => {
      const b = e.target.closest(".gp-pc"); if (!b) return;
      const i = ui.cur.indexOf(null); if (i < 0) return;
      ui.cur[i] = +b.dataset.c; sfx("pop"); drawCur();
    });
    $("#gpmcur").addEventListener("click", (e) => { const d = e.target.closest("[data-i]"); if (d) { ui.cur[+d.dataset.i] = null; drawCur(); } });
    $("#gpmclr").addEventListener("click", () => { ui.cur = [null, null, null, null]; drawCur(); });
    $("#gpmok").addEventListener("click", () => {
      const s2 = HUB.S.room;
      if (!s2 || s2.game.turn !== s2.you || ui.cur.includes(null)) return;
      HUB.send({ t: "guess", code: ui.cur.slice() }); ui.cur = [null, null, null, null]; HUB.haptic("medium"); drawCur();
    });
    function drawCur() {
      $("#gpmcur").innerHTML = ui.cur.map((c, i) => `<button class="gp-slot ${c === null ? "" : "on"}" data-i="${i}" style="background:${c === null ? "#2a2a30" : MC[c]}"></button>`).join("");
      const s2 = HUB.S.room, my = s2 && s2.status === "playing" && s2.game.turn === s2.you;
      $("#gpmok").disabled = !my || ui.cur.includes(null);
    }
    ui.drawCur = drawCur; drawCur();
  }
  async function applyMind(s) {
    const ui = HUB.S.ui, g = s.game;
    const view = playing(s) ? g.players : g.players;
    const col = (p, label) => {
      let rows = "";
      for (let i = 0; i < g.max; i++) {
        const gu = p.guesses[i];
        rows += `<div class="gp-row ${gu ? "" : "empty"} ${gu && i === p.guesses.length - 1 && g.last_guess && g.last_guess.uid === p.uid ? "new" : ""}">
          <span class="n">${i + 1}</span>${(gu ? gu.code : [null, null, null, null]).map(peg).join("")}${gu ? fb(gu.black, gu.white) : ""}</div>`;
      }
      return `<div class="gp-col ${g.turn === p.uid ? "turn" : ""}"><h5>${label}</h5>${rows}</div>`;
    };
    const lg = g.last_guess;
    const fresh = !ui.first && lg && lg.seq > ui.lastSeq;
    $("#gpmb").innerHTML = view.map((p) => col(p, HUB.esc(p.uid === s.you ? "You" : nm(s, p.uid)))).join("");
    $("#gpmsec").innerHTML = g.secret ? "Secret: " + g.secret.map(peg).join("") : "";
    if (ui.first) { ui.first = false; ui.lastSeq = lg ? lg.seq : 0; }
    else if (fresh) {
      ui.lastSeq = lg.seq;
      for (let i = 0; i < lg.black; i++) { sfx("good"); await HUB.sleep(110); }
      for (let i = 0; i < lg.white; i++) { sfx("tick"); await HUB.sleep(110); }
      if (!lg.black && !lg.white) sfx("miss");
      HUB.haptic();
    }
    ui.drawCur();
    const my = s.status === "playing" && g.turn === s.you;
    document.querySelectorAll(".gp-pc").forEach((b) => { b.disabled = !my; });
    $("#gpmcur").classList.toggle("hidden", !playing(s)); $("#gpmpal").classList.toggle("hidden", !playing(s));
    document.querySelector(".gp-mind .gp-acts").classList.toggle("hidden", !playing(s));
    K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).guesses.length + "/" + g.max }));
    K().setHint(my ? "Build a 4-colour code, then Guess" : K().turnHint(s));
    K().turnFx(ui, s);
  }

  /* =====================================================================  TRIVIA */
  function buildTrivia(s) {
    K().newUI("trivia", s, { lastSeq: 0, q: 0, ticking: true });
    K().shell(s, `<div class="gp-trv"><div class="gp-meta"><span id="gptcat"></span><span id="gptq"></span></div>
      <div class="gp-time"><i id="gptclk"></i></div><div class="gp-qtext" id="gptext"></div><div class="gp-opts" id="gptopts"></div>
      <div class="gp-ans" id="gptans"></div></div>`);
    clock(HUB.S.ui, "#gptclk");
    $("#gptopts").addEventListener("click", (e) => {
      const b = e.target.closest(".gp-opt"), s2 = HUB.S.room;
      if (!b || b.disabled || !s2) return;
      HUB.send({ t: "answer", choice: +b.dataset.i }); HUB.haptic(); sfx("pop");
      document.querySelectorAll(".gp-opt").forEach((x) => { x.disabled = true; x.classList.toggle("mine", x === b); });
    });
  }
  async function applyTrivia(s) {
    const ui = HUB.S.ui, g = s.game, can = playing(s) && s.status === "playing" && g.phase === "ask" && g.my_pick === null && !g.players.find((p) => p.uid === s.you).left;
    ui.ticking = g.phase === "ask" && playing(s);
    if (g.q !== ui.q) {
      ui.q = g.q;
      $("#gptcat").textContent = "📂 " + g.category; $("#gptq").textContent = `Question ${g.q}/${g.total}`;
      $("#gptext").textContent = g.question;
      $("#gptopts").innerHTML = g.options.map((o, i) => `<button class="gp-opt" data-i="${i}"><b>${"ABCD"[i]}</b>${HUB.esc(o)}</button>`).join("");
      $("#gptans").innerHTML = "";
      if (!ui.first) sfx("turn");
    }
    const opts = document.querySelectorAll(".gp-opt");
    opts.forEach((b, i) => { if (g.phase === "ask") { b.disabled = !can; b.classList.toggle("mine", g.my_pick === i); } });
    const rv = g.reveal;
    if (rv && rv.q === g.q - 1) {
      const fresh = rv.seq > ui.lastSeq;
      opts.forEach((b, i) => {
        b.disabled = true; b.classList.remove("mine");
        b.classList.toggle("right", i === rv.correct);
        b.classList.toggle("wrong", i !== rv.correct && Object.values(rv.picks).includes(i) && (g.my_pick === i || !playing(s)));
        if (g.my_pick === i && i !== rv.correct) b.classList.add("wrong");
        if (i !== rv.correct && !b.classList.contains("wrong")) b.classList.add("dim");
      });
      $("#gptans").innerHTML = g.players.map((p) => {
        const gain = rv.gained[String(p.uid)] || 0;
        return `<span class="gp-chip ${gain ? "ok" : "no"}">${HUB.esc(nm(s, p.uid))} ${gain ? "+" + gain : "✖"}</span>`;
      }).join("");
      if (fresh && !ui.first) {
        ui.lastSeq = rv.seq;
        const mine = rv.gained[String(s.you)];
        if (playing(s)) { sfx(mine ? "good" : "bad"); HUB.haptic(mine ? "light" : "heavy"); } else sfx("pop");
        document.querySelectorAll(".gp-chip.ok").forEach((c) => c.classList.add("pop"));
      }
    } else if (g.phase === "ask") {
      $("#gptans").innerHTML = g.players.map((p) => `<span class="gp-chip ${p.answered ? "ok" : ""}">${HUB.esc(nm(s, p.uid))} ${p.answered ? "✓" : "…"}</span>`).join("");
    }
    if (ui.first) { ui.first = false; if (rv) ui.lastSeq = rv.seq; }
    K().updateBar(ui, s, (uid) => { const p = g.players.find((x) => x.uid === uid); return { score: p.score, sub: p.streak > 1 ? "🔥 x" + p.streak : "" }; });
    K().setHint(g.phase === "ask" ? (g.my_pick !== null && g.my_pick !== undefined ? "Locked in ✓ waiting for others" : playing(s) ? "Answer fast — speed scores!" : "Watching") : "");
  }

  HUB.UI.mafia = { build: buildMafia, apply: applyMafia };
  HUB.UI.hangman = { build: buildHang, apply: applyHang };
  HUB.UI.mastermind = { build: buildMind, apply: applyMind };
  HUB.UI.trivia = { build: buildTrivia, apply: applyTrivia };
})();

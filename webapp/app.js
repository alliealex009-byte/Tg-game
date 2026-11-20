/* Telegram mini app client: home, lobby, Ludo board, Tic-Tac-Toe. No build step, no dependencies. */
(function () {
  "use strict";
  window.HUB = window.HUB || { UI: {} };
  const tg = window.Telegram && window.Telegram.WebApp;
  const B = window.LudoBoard;
  const PCT = 100 / 15;
  const params = new URLSearchParams(location.search);
  const $ = (s, r) => (r || document).querySelector(s);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const S = {
    initData: "", me: null, cfg: null, ws: null, code: null, room: null, lastV: 0, bet: 0,
    closing: false, retry: 0, ui: null, queue: Promise.resolve(), chatLog: [],
    sound: localStorage.getItem("snd") !== "0", timer: null, ping: null,
  };

  /* ---------------- helpers ---------------- */
  let toastT;
  function toast(msg, ms) {
    const t = $("#toast");
    t.textContent = msg;
    t.classList.remove("hidden");
    clearTimeout(toastT);
    toastT = setTimeout(() => t.classList.add("hidden"), ms || 2400);
  }
  function showScreen(name) {
    document.querySelectorAll(".screen").forEach((s) => s.classList.toggle("active", s.id === "screen-" + name));
  }
  function fatal(msg) {
    showScreen("loading");
    $("#loading-msg").textContent = msg;
    $("#screen-loading .spinner").style.display = "none";
  }
  function haptic(kind) { try { tg.HapticFeedback.impactOccurred(kind || "light"); } catch (e) { /* not in Telegram */ } }
  function tgBack(show) { if (tg && tg.BackButton) { show ? tg.BackButton.show() : tg.BackButton.hide(); } }
  function avatarInner(p) {
    if (!p) return "?";
    if (p.is_bot) return "🤖";
    const ini = esc((p.name || "?").trim().slice(0, 1).toUpperCase() || "?");
    const img = p.photo ? `<img src="${esc(p.photo)}" referrerpolicy="no-referrer" onerror="this.remove()">` : "";
    return ini + img;
  }
  function handle(p) { return p.is_bot ? p.name : "@" + (p.username || p.name); }

  function getInitData() {
    if (tg && tg.initData) return tg.initData;
    const dev = params.get("dev"); // only works when the server runs with DEV_MODE=1
    if (dev) {
      let h = 0;
      for (const ch of dev) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
      return "dev:" + ((h % 900000) + 100000) + ":" + dev;
    }
    return "";
  }

  async function api(path, opts) {
    opts = opts || {};
    const r = await fetch(path, {
      method: opts.method || "GET",
      headers: { "Content-Type": "application/json", "X-Init-Data": S.initData },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || "Request failed");
    return data;
  }

  /* ---------------- sound ---------------- */
  let actx, master, noiseBuf;
  function audio() {
    if (!actx) {
      try {
        actx = new (window.AudioContext || window.webkitAudioContext)();
        master = actx.createGain(); master.gain.value = 0.9; master.connect(actx.destination);
        noiseBuf = actx.createBuffer(1, actx.sampleRate, actx.sampleRate);
        const d = noiseBuf.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
      } catch (e) { actx = null; }
    }
    if (actx && actx.state === "suspended") { try { actx.resume(); } catch (e) { /* ignore */ } }
    return actx;
  }
  function unlockAudio() {
    const c = audio(); if (!c) return;
    try { const o = c.createOscillator(), g = c.createGain(); g.gain.value = 0.0001; o.connect(g); g.connect(c.destination); o.start(); o.stop(c.currentTime + 0.01); } catch (e) { /* ignore */ }
  }
  ["pointerdown", "touchend", "click", "keydown"].forEach((ev) => document.addEventListener(ev, unlockAudio, { passive: true }));
  document.addEventListener("visibilitychange", () => { if (!document.hidden) audio(); });
  function tone(freq, dur, type, vol, when, slideTo) {
    if (!S.sound) return;
    const c = audio(); if (!c) return;
    try {
      const o = c.createOscillator(), g = c.createGain(), t = c.currentTime + (when || 0), v = vol || 0.2;
      o.type = type || "sine"; o.frequency.setValueAtTime(freq, t);
      if (slideTo) o.frequency.exponentialRampToValueAtTime(slideTo, t + dur);
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(v, t + 0.01);
      g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      o.connect(g); g.connect(master); o.start(t); o.stop(t + dur + 0.03);
    } catch (e) { /* audio blocked */ }
  }
  function noise(dur, vol, when, freq) {
    if (!S.sound) return;
    const c = audio(); if (!c || !noiseBuf) return;
    try {
      const src = c.createBufferSource(), f = c.createBiquadFilter(), g = c.createGain(), t = c.currentTime + (when || 0);
      src.buffer = noiseBuf; f.type = "bandpass"; f.frequency.value = freq || 1800; f.Q.value = 0.9;
      g.gain.setValueAtTime(vol || 0.2, t); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      src.connect(f); f.connect(g); g.connect(master); src.start(t); src.stop(t + dur + 0.02);
    } catch (e) { /* ignore */ }
  }
  const sfx = {
    roll() { for (let i = 0; i < 7; i++) { noise(0.05, 0.35, i * 0.07, 1400 + Math.random() * 1800); tone(180 + Math.random() * 120, 0.04, "square", 0.05, i * 0.07); } tone(240, 0.12, "triangle", 0.22, 0.52); },
    step() { tone(520, 0.07, "triangle", 0.2); },
    capture() { tone(260, 0.3, "sawtooth", 0.22, 0, 70); noise(0.18, 0.3, 0, 600); },
    win() { [523, 659, 784, 1046, 1318].forEach((f, i) => tone(f, 0.28, "triangle", 0.25, i * 0.12)); tone(1046, 0.6, "sine", 0.18, 0.62); },
    lose() { [392, 330, 262].forEach((f, i) => tone(f, 0.3, "sine", 0.22, i * 0.18)); },
    draw() { tone(440, 0.2, "sine", 0.2); tone(440, 0.25, "sine", 0.2, 0.22); },
    pop() { tone(700, 0.09, "sine", 0.22, 0, 1000); },
    place() { tone(180, 0.1, "sine", 0.35, 0, 90); noise(0.04, 0.2, 0, 2500); },
    drop() { tone(420, 0.25, "sine", 0.2, 0, 160); tone(120, 0.12, "sine", 0.3, 0.22); },
    flip() { noise(0.07, 0.25, 0, 3500); tone(900, 0.05, "triangle", 0.1); },
    deal() { noise(0.09, 0.3, 0, 4200); tone(300, 0.04, "triangle", 0.08); },
    chip() { tone(1500, 0.05, "square", 0.08); tone(2000, 0.07, "square", 0.06, 0.04); },
    hit() { tone(140, 0.18, "sine", 0.35, 0, 60); noise(0.1, 0.35, 0, 900); },
    miss() { noise(0.25, 0.25, 0, 500); tone(300, 0.25, "sine", 0.1, 0, 180); },
    good() { tone(660, 0.1, "triangle", 0.22); tone(880, 0.16, "triangle", 0.22, 0.09); },
    bad() { tone(200, 0.22, "sawtooth", 0.18, 0, 120); },
    turn() { tone(880, 0.12, "sine", 0.2); tone(1175, 0.14, "sine", 0.18, 0.1); },
    tick() { tone(1000, 0.03, "square", 0.08); },
    night() { tone(220, 0.6, "sine", 0.22, 0, 110); tone(330, 0.6, "sine", 0.12, 0.05, 165); },
    day() { tone(523, 0.2, "triangle", 0.2); tone(659, 0.2, "triangle", 0.2, 0.15); tone(784, 0.3, "triangle", 0.2, 0.3); },
    vote() { tone(500, 0.06, "square", 0.12); tone(750, 0.1, "square", 0.12, 0.07); },
    cash() { [1318, 1568, 2093].forEach((f, i) => tone(f, 0.12, "triangle", 0.15, i * 0.06)); },
  };

  /* ---------- quiet background ambience for a few games (never Ludo or Carrom) ---------- */
  const AMBIENT = { chess: "calm", checkers: "calm", gomoku: "calm", reversi: "calm", mancala: "calm", dominoes: "calm", wordle: "calm", uttt: "calm",
    tank: "wind", race: "engine", telearena: "dark", quest: "dark", mafia: "dark" };
  let amb = null;
  function ambStop() {
    if (!amb) return;
    const a = amb; amb = null;
    try { a.g.gain.cancelScheduledValues(0); a.g.gain.setTargetAtTime(0.0001, a.c.currentTime, 0.25); setTimeout(() => { a.nodes.forEach((n) => { try { n.stop(); } catch (e) { /* ignore */ } }); try { a.g.disconnect(); } catch (e) { /* ignore */ } }, 900); } catch (e) { /* ignore */ }
  }
  function ambStart(kind) {
    if (!S.sound) return ambStop();
    if (amb && amb.kind === kind) return;
    ambStop();
    const c = audio(); if (!c) return;
    try {
      const g = c.createGain(); g.gain.value = 0.0001; g.connect(master);
      const nodes = [], lfo = c.createOscillator(), lg = c.createGain(); lfo.frequency.value = 0.15; lg.gain.value = 0.35; lfo.connect(lg); nodes.push(lfo);
      const mk = (type, f) => { const o = c.createOscillator(); o.type = type; o.frequency.value = f; nodes.push(o); return o; };
      let vol = 0.03;
      if (kind === "calm" || kind === "dark") {
        const f = kind === "calm" ? [110, 164.8, 220.4] : [98, 116.5, 147];
        f.forEach((hz) => { const o = mk("sine", hz), og = c.createGain(); og.gain.value = 0.33; o.connect(og); og.connect(g); lg.connect(og.gain); });
        if (kind === "dark") vol = 0.035;
      } else if (kind === "wind") {
        const src = c.createBufferSource(), f = c.createBiquadFilter(), fg = c.createGain(); src.buffer = noiseBuf; src.loop = true; f.type = "lowpass"; f.frequency.value = 420; fg.gain.value = 0.7;
        src.connect(f); f.connect(fg); fg.connect(g); lg.connect(fg.gain); nodes.push(src); vol = 0.05;
      } else if (kind === "engine") {
        const o = mk("sawtooth", 62), o2 = mk("sawtooth", 63.5), f = c.createBiquadFilter(), fg = c.createGain(); f.type = "lowpass"; f.frequency.value = 180; fg.gain.value = 0.5;
        o.connect(f); o2.connect(f); f.connect(fg); fg.connect(g); lg.connect(fg.gain); vol = 0.03;
      }
      nodes.forEach((n) => n.start());
      g.gain.setTargetAtTime(vol, c.currentTime, 0.8);
      amb = { kind, g, c, nodes };
    } catch (e) { amb = null; }
  }
  sfx.ambient = (gameType, playing) => { const k = AMBIENT[gameType]; if (k && playing) ambStart(k); else ambStop(); };
  sfx.ambientOff = ambStop;
  document.addEventListener("visibilitychange", () => { if (document.hidden) ambStop(); });

  /* dice tumble: cycles random faces with a spin, then settles on the real value */
  const PIPS = { 1: [4], 2: [0, 8], 3: [0, 4, 8], 4: [0, 2, 6, 8], 5: [0, 2, 4, 6, 8], 6: [0, 2, 3, 5, 6, 8] };
  // cube faces: front=1 back=6 right=2 left=5 top=3 bottom=4 (opposite faces add up to 7)
  const FACE = { 1: ["", 1], 6: ["rotateY(180deg)", 6], 2: ["rotateY(90deg)", 2], 5: ["rotateY(-90deg)", 5], 3: ["rotateX(90deg)", 3], 4: ["rotateX(-90deg)", 4] };
  const SHOW = { 1: [0, 0], 6: [0, 180], 2: [0, -90], 5: [0, 90], 3: [-90, 0], 4: [90, 0] };  // [rotateX, rotateY] that bring a face to the front
  async function tumble(el, value, ms) {
    if (!el) return;
    ms = ms || 1100;
    sfx.roll();
    const S = Math.max(28, Math.round(el.clientWidth || 44)), h = S / 2;
    el.style.overflow = "visible"; el.style.zIndex = "40";
    el.innerHTML = `<div class="d3scene" style="width:${S}px;height:${S}px"><div class="d3cube" style="width:${S}px;height:${S}px">` +
      Object.values(FACE).map(([t, v]) => `<div class="d3face" style="transform:${t} translateZ(${h}px)">${[0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => `<i class="${PIPS[v].includes(i) ? "on" : ""}"></i>`).join("")}</div>`).join("") + "</div></div>";
    const scene = el.firstChild, cube = scene.firstChild;
    const [fx, fy] = SHOW[value];
    const r = () => (Math.random() * 2 - 1);
    const ax = (n) => Math.round(n * 360 + r() * 40), sgn = Math.random() < 0.5 ? 1 : -1;
    let a1 = null, a2 = null;
    try {
      a1 = cube.animate([
        { transform: `rotateX(${Math.round(r() * 90)}deg) rotateY(${Math.round(r() * 90)}deg) rotateZ(${Math.round(r() * 40)}deg)` },
        { transform: `rotateX(${ax(1) * sgn}deg) rotateY(${ax(1)}deg) rotateZ(${Math.round(r() * 60)}deg)`, offset: 0.35 },
        { transform: `rotateX(${ax(2) * sgn}deg) rotateY(${ax(2)}deg) rotateZ(${Math.round(r() * 60)}deg)`, offset: 0.7 },
        { transform: `rotateX(${fx + 360 * 3 * sgn}deg) rotateY(${fy + 360 * 2}deg) rotateZ(0deg)` },
      ], { duration: ms, easing: "cubic-bezier(.2,.7,.25,1)", fill: "forwards" });
      a2 = scene.animate([
        { transform: "translateY(0) scale(1)", filter: "drop-shadow(0 2px 2px #0007)" },
        { transform: "translateY(-45%) scale(2.2)", filter: "drop-shadow(0 18px 8px #0006)", offset: 0.28 },
        { transform: "translateY(-5%) scale(1.7)", filter: "drop-shadow(0 8px 5px #0006)", offset: 0.5 },
        { transform: "translateY(-26%) scale(1.9)", filter: "drop-shadow(0 12px 6px #0006)", offset: 0.72 },
        { transform: "translateY(0) scale(1.15)", filter: "drop-shadow(0 3px 3px #0007)", offset: 0.9 },
        { transform: "translateY(0) scale(1)", filter: "drop-shadow(0 2px 2px #0007)" },
      ], { duration: ms, easing: "ease-in-out", fill: "forwards" });
    } catch (e) { /* no WAAPI */ }
    // a soft clack when the dice lands
    setTimeout(() => sfx.place(), Math.round(ms * 0.5));
    setTimeout(() => sfx.place(), Math.round(ms * 0.72));
    if (a1) { try { await a1.finished; } catch (e) { /* cancelled */ } }
    el.innerHTML = diceHTML(value);   // identical flat face, so the rest of the UI stays consistent
    el.style.zIndex = "";
    const d = el.querySelector(".dice");
    if (d) d.animate([{ transform: "scale(1.15)" }, { transform: "scale(.97)" }, { transform: "scale(1)" }], { duration: 200, easing: "ease-out" });
  }

  /* confetti burst */
  function confetti(n) {
    const box = document.createElement("div"); box.className = "confetti";
    const cols = ["#ff5a5a", "#ffd24a", "#4ade80", "#4aa8ff", "#c084fc", "#fff"];
    for (let i = 0; i < (n || 70); i++) {
      const c = document.createElement("i");
      c.style.left = Math.random() * 100 + "%";
      c.style.background = cols[i % cols.length];
      c.style.animationDelay = Math.random() * 0.6 + "s";
      c.style.animationDuration = 1.8 + Math.random() * 1.4 + "s";
      c.style.setProperty("--dx", (Math.random() * 120 - 60) + "px");
      c.style.transform = "rotate(" + Math.random() * 360 + "deg)";
      box.appendChild(c);
    }
    document.body.appendChild(box);
    setTimeout(() => box.remove(), 4000);
  }

  /* ---------------- socket ---------------- */
  function send(obj) { if (S.ws && S.ws.readyState === 1) S.ws.send(JSON.stringify(obj)); }
  function setConn(ok) { $("#conn").classList.toggle("hidden", ok); }

  function openSocket(code) {
    closeSocket();
    S.closing = false;
    const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
    S.ws = ws;
    ws.onopen = () => {
      S.retry = 0; setConn(true);
      ws.send(JSON.stringify({ t: "join", room: code, initData: S.initData }));
      clearInterval(S.ping);
      S.ping = setInterval(() => send({ t: "ping" }), 25000);
    };
    ws.onmessage = (ev) => {
      let m; try { m = JSON.parse(ev.data); } catch (e) { return; }
      onMessage(m);
    };
    ws.onclose = () => {
      clearInterval(S.ping);
      if (S.closing || S.ws !== ws) return;
      setConn(false);
      S.retry++;
      setTimeout(() => { if (!S.closing && S.code === code) openSocket(code); }, Math.min(5000, 700 * S.retry));
    };
  }
  document.addEventListener("visibilitychange", () => {
    if (document.hidden || !S.code || S.closing) return;
    if (!S.ws || S.ws.readyState > 1) { S.retry = 0; openSocket(S.code); }
    else if (S.ws.readyState === 1) send({ t: "ping" });
  });
  function closeSocket() {
    S.closing = true;
    clearInterval(S.ping);
    if (S.ws) { try { S.ws.close(); } catch (e) { /* already closed */ } }
    S.ws = null;
    setConn(true);
  }

  function onMessage(m) {
    if (m.t === "state") return onState(m);
    if (m.t === "chat") return addChat(m);
    if (m.t === "react") return HUB.onReact && HUB.onReact(m);
    if (m.t === "toast") return toast(m.msg);
    if (m.t === "error") {
      toast(/not found|expired/i.test(m.msg || "") ? "This room has closed. Start a new game from the menu 👇" : m.msg);
      if (m.fatal) showHome();
    }
  }

  function joinRoom(code) {
    S.code = code; S.lastV = 0; S.ui = null; S.chatLog = []; S.room = null;
    showScreen("loading");
    $("#loading-msg").textContent = "Joining room " + code + "…";
    $("#screen-loading .spinner").style.display = "";
    openSocket(code);
  }

  function leaveRoom() {
    send({ t: "leave" });
    showHome();
  }
  function askLeave() {
    const s = S.room;
    const playing = s && s.status === "playing" && s.players.some((p) => p.uid === s.you && !p.left);
    if (!playing) return leaveRoom();
    const msg = s.bet ? "Leave the game? You will lose your " + s.bet + "-coin bet." : "Leave the game? You will forfeit.";
    if (tg && tg.showConfirm) tg.showConfirm(msg, (ok) => ok && leaveRoom());
    else if (window.confirm(msg)) leaveRoom();
  }

  /* ---------------- home ---------------- */
  function showHome() {
    closeSocket();
    S.room = null; S.code = null; S.ui = null; S.queue = Promise.resolve();
    clearInterval(S.timer);
    $("#result").classList.add("hidden");
    $("#chat").classList.add("hidden");
    showScreen("home");
    tgBack(false);
    try { if (HUB.onHome) HUB.onHome(); } catch (e) { /* ignore */ }
    renderHome();
    api("/api/me", { method: "POST" }).then((r) => { S.me = r.user; S.isAdmin = !!r.is_admin; updateCoins(); }).catch(() => {});
    api("/api/leaderboard").then(renderLeaderboard).catch(() => {});
  }
  function updateCoins() { const c = $("#coins"); if (c && S.me) c.textContent = "💰 " + S.me.coins; }

  function renderHome() {
    const m = S.me, cfg = S.cfg;
    $("#screen-home").innerHTML = `
    <div class="home">
      <div class="me">
        <div class="av" style="width:46px;height:46px"><div class="avatar">${avatarInner(m)}</div></div>
        <div><div class="nm">${esc(m.name)}</div><div class="un">@${esc(m.username)}</div></div>
        <div class="coins" id="coins">💰 ${m.coins}</div>
      </div>
      <div class="card"><button class="btn gold block" id="daily">🎁 Claim daily bonus (+${cfg.daily})</button></div>
      <div class="card"><h3>Entry bet</h3>
        <div class="chips">${cfg.bets.map((b) => `<button class="chip ${b === S.bet ? "on" : ""}" data-bet="${b}">${b ? b : "Free"}</button>`).join("")}</div>
        <div style="color:var(--muted);font-size:12px;margin-top:8px">Winner takes the pot (house keeps ${cfg.rake}%). Coins are virtual.</div>
      </div>
      <div class="homeSec"><button class="btn gold" id="h-arcade">🕹 Arcade · earn coins</button>${S.isAdmin ? '<button class="btn" id="h-owner">👑 Owner</button>' : ""}</div>
      <div class="card"><h3>Multiplayer games <span style="color:var(--muted);font-weight:400">(${Object.keys(cfg.games).length})</span></h3>
        <div class="cats" id="cats">${["All", ...new Set(Object.values(cfg.games).map((g) => g.cat || "Classic"))].map((c) => `<button class="chip ${c === (S.cat || "All") ? "on" : ""}" data-cat="${c}">${c}</button>`).join("")}</div>
        <div class="games">${Object.entries(cfg.games).filter(([, g]) => (S.cat || "All") === "All" || (g.cat || "Classic") === S.cat).map(([k, g]) => `
          <button class="gcard" data-game="${k}"><span class="inf" data-info="${k}">ⓘ</span><div class="em">${g.emoji}</div><div class="t">${esc(g.title)}</div>
          <div class="s">${g.min === g.max ? g.min : g.min + "-" + g.max} players</div></button>`).join("")}</div>
      </div>
      <div class="card"><h3>Join with a code</h3>
        <form class="joinrow" id="joinform"><input id="joincode" maxlength="8" placeholder="ROOM CODE" autocomplete="off"><button class="btn primary">Join</button></form>
      </div>
      <div class="card"><h3>Top players</h3><ul class="lb" id="lb"><li><span class="rk">…</span></li></ul></div>
      <div class="credits">🎮 <b>GAMELY</b> · Game Hub Bot<br>👑 Owner: ${esc(cfg.owner.name)} (<a href="https://t.me/${esc(cfg.owner.username)}">@${esc(cfg.owner.username)}</a>)<br>🤖 Sister bot: <a href="https://t.me/${esc(cfg.sister)}">@${esc(cfg.sister)}</a><br><span style="opacity:.6">v${esc(cfg.version || "")}</span></div>
    </div>`;
    const root = $("#screen-home");
    root.querySelectorAll(".chip[data-bet]").forEach((c) => c.addEventListener("click", () => {
      S.bet = +c.dataset.bet;
      root.querySelectorAll(".chip[data-bet]").forEach((x) => x.classList.toggle("on", x === c));
    }));
    root.querySelectorAll("[data-cat]").forEach((c) => c.addEventListener("click", () => { S.cat = c.dataset.cat; renderHome(); api("/api/leaderboard").then(renderLeaderboard).catch(() => {}); }));
    const ar = $("#h-arcade"); if (ar) ar.addEventListener("click", () => HUB.openArcade());
    const ow = $("#h-owner"); if (ow) ow.addEventListener("click", () => HUB.openOwner());
    root.querySelectorAll(".gcard").forEach((c) => c.addEventListener("click", async (ev) => {
      if (ev.target.dataset.info) { ev.stopPropagation(); return HUB.showHowto(ev.target.dataset.info); }
      try {
        const r = await api("/api/room", { method: "POST", body: { game: c.dataset.game, bet: S.bet } });
        joinRoom(r.code);
      } catch (e) { toast(e.message); }
    }));
    $("#daily").addEventListener("click", async () => {
      try {
        const r = await api("/api/daily", { method: "POST" });
        if (r.claimed) { toast("🎁 +" + r.bonus + " coins!"); S.me.coins = r.coins; updateCoins(); sfx.win(); }
        else toast("Next bonus in " + Math.ceil(r.wait / 3600) + "h");
      } catch (e) { toast(e.message); }
    });
    $("#joinform").addEventListener("submit", (e) => {
      e.preventDefault();
      const c = $("#joincode").value.trim().toUpperCase();
      if (/^[0-9A-F]{8}$/.test(c)) joinRoom(c); else toast("Enter the 8-character room code");
    });
  }
  function renderLeaderboard(r) {
    const ul = $("#lb");
    if (!ul) return;
    if (!r.rows.length) { ul.innerHTML = '<li><span class="rk"></span><span style="color:var(--muted)">No games yet, be the first!</span></li>'; return; }
    ul.innerHTML = r.rows.map((x, i) => `<li><span class="rk">${i + 1}</span>
      <div class="av sm-av" style="width:30px;height:30px"><div class="avatar">${avatarInner(x)}</div></div>
      <span>${esc(x.name)}</span><span class="w">${x.wins} 🏆</span></li>`).join("");
  }

  /* ---------------- lobby ---------------- */
  function shareLink(code) {
    const c = S.cfg;
    if (c.bot && c.app) return "https://t.me/" + c.bot + "/" + c.app + "?startapp=" + code;
    if (c.bot) return "https://t.me/" + c.bot + "?start=join_" + code;
    return location.origin + "/?room=" + code;
  }
  function share(code, title) {
    const msgs = [
      `🎮 Join my ${title} game! Room ${code}`,
      `🔥 Think you can beat me at ${title}? Room ${code} is waiting!`,
      `🏆 ${title} time! Tap the link and join room ${code}`,
      `💰 Free coins + ${title} with friends. Room ${code}, come play!`,
      `⚡ Quick! ${title} is about to start. Room ${code}`,
    ];
    const m = document.createElement("div"); m.className = "xmodal";
    m.innerHTML = '<div class="xcard"><h3>📤 Send an invite</h3><div class="xlist">' + msgs.map((t, i) => `<button class="xitem" data-i="${i}"><span>${esc(t)}</span></button>`).join("") + "</div></div>";
    m.addEventListener("click", (e) => {
      const b = e.target.closest("[data-i]");
      if (b) {
        const u = "https://t.me/share/url?url=" + encodeURIComponent(shareLink(code)) + "&text=" + encodeURIComponent(msgs[+b.dataset.i]);
        if (tg && tg.openTelegramLink) tg.openTelegramLink(u); else window.open(u, "_blank");
      }
      if (b || e.target === m) m.remove();
    });
    document.body.appendChild(m);
  }

  function renderLobby(s) {
    showScreen("lobby");
    const isHost = s.host === s.you, inRoom = s.players.some((p) => p.uid === s.you);
    const rows = s.players.map((p, i) => `
      <div class="prow2"><span class="n">${i + 1}.</span>
        <div class="av"><div class="avatar">${avatarInner(p)}</div></div>
        <div><div class="nm">${esc(p.name)}${p.uid === s.host ? '<span class="hostb">👑 HOST</span>' : ""}</div>
        <div class="un">${p.is_bot ? "Computer" : "@" + esc(p.username || "")}</div></div>
        ${p.is_bot && isHost ? `<button class="btn sm x" data-rm="${p.uid}">✕</button>` : ""}
      </div>`);
    for (let i = s.players.length; i < s.max_players; i++) rows.push(`<div class="prow2 empty"><span class="n">${i + 1}.</span><div class="av"><div class="avatar">＋</div></div><div class="un">Waiting for player…</div></div>`);
    const canStart = isHost && s.players.length >= s.min_players;
    $("#screen-lobby").innerHTML = `
    <div class="lobby">
      <h2>${s.emoji} ${esc(s.title)} Lobby</h2>
      <div class="wait">${!inRoom ? "You are watching. Take a seat if there is one free" : isHost ? "You are the host. Start when everyone is in." : "Waiting for Host to start…"}</div>
      <div class="codebox"><span class="code">${s.code}</span>
        <button class="btn sm" id="copy">Copy</button><button class="btn sm" id="share">Share</button></div>
      <div style="color:var(--gold);font-weight:700;margin-bottom:12px">${s.bet ? "💰 Bet: " + s.bet + " coins each" : "Free game"}</div>
      <div class="plist">${rows.join("")}</div>
      ${canStart ? '<button class="btn primary block start" id="start">▶ START GAME</button>' : ""}
      ${isHost && !s.bet && s.players.length < s.max_players ? '<button class="btn block" id="addbot" style="margin-bottom:10px">🤖 Add computer player</button>' : ""}
      ${!inRoom && s.players.length < s.max_players ? '<button class="btn primary block" id="sit" style="margin-bottom:10px">🪑 Take a seat</button>' : ""}
      ${s.watching ? `<div class="wait">👁 ${s.watching} watching</div>` : ""}
      <button class="btn block" id="howto" style="margin-bottom:10px">❓ How to play</button>
      <button class="btn block" id="leave">Leave room</button>
    </div>`;
    const root = $("#screen-lobby");
    const on = (sel, fn) => { const el = root.querySelector(sel); if (el) el.addEventListener("click", fn); };
    on("#copy", () => { try { navigator.clipboard.writeText(s.code); toast("Code copied"); } catch (e) { toast(s.code); } });
    on("#share", () => share(s.code, s.title));
    on("#start", () => send({ t: "start" }));
    on("#addbot", () => send({ t: "add_bot" }));
    on("#sit", () => send({ t: "sit" }));
    on("#howto", () => HUB.showHowto(s.game_type));
    on("#leave", leaveRoom);
    root.querySelectorAll("[data-rm]").forEach((b) => b.addEventListener("click", () => send({ t: "remove_bot", uid: +b.dataset.rm })));
  }

  /* ---------------- state pipeline ---------------- */
  function onState(s) {
    if (s.v < S.lastV) return;
    S.lastV = s.v;
    S.room = s;
    S.queue = S.queue.then(() => process(s)).catch((e) => console.error(e));
    try { if (HUB.afterState) HUB.afterState(s); } catch (e) { console.error(e); }
  }

  async function process(s) {
    if (S.code !== s.code) return;
    const me = s.players.find((p) => p.uid === s.you);
    if (me && S.me) { S.me.coins = me.coins; }
    if (s.status === "lobby") {
      clearInterval(S.timer);
      S.ui = null;
      $("#result").classList.add("hidden");
      renderLobby(s);
      tgBack(true);
      return;
    }
    if (!HUB.UI[s.game_type]) { toast("Please reload the app to play this game"); return; }
    if (!S.ui || S.ui.code !== s.code || S.ui.type !== s.game_type) buildGame(s);
    showScreen("game");
    tgBack(true);
    S.ui.deadline = s.time_left != null ? performance.now() + s.time_left * 1000 : null;
    S.ui.turnSeconds = s.turn_seconds;
    await HUB.UI[s.game_type].apply(s);
    if (s.status === "finished") { await sleep(450); showResult(s); }
    else $("#result").classList.add("hidden");
  }

  function topbarHTML(code) {
    return `<div class="topbar"><button class="ibtn" id="b-snd">${S.sound ? "🔊" : "🔇"}</button>
      <button class="ibtn" id="b-exit">🚪</button><div class="roomtag">ROOM: ${code}</div>
      <button class="ibtn" id="b-chat">💬</button></div>`;
  }
  function bindTopbar() {
    $("#b-snd").addEventListener("click", (e) => {
      S.sound = !S.sound; localStorage.setItem("snd", S.sound ? "1" : "0");
      e.currentTarget.textContent = S.sound ? "🔊" : "🔇";
      if (!S.sound) ambStop();
      else if (S.room) sfx.ambient(S.room.game_type, S.room.status === "playing");
    });
    $("#b-exit").addEventListener("click", askLeave);
    $("#b-chat").addEventListener("click", () => { $("#chat").classList.remove("hidden"); renderChat(); });
  }

  function buildGame(s) {
    clearInterval(S.timer);
    HUB.UI[s.game_type].build(s);
    bindTopbar();
    S.timer = setInterval(tickTimer, 250);
  }

  function tickTimer() {
    const ui = S.ui, s = S.room;
    if (!ui || !s || !s.game) return;
    for (const uid in ui.rings) ui.rings[uid].style.setProperty("--p", "0deg");
    if (s.status !== "playing" || !ui.deadline) return;
    const frac = Math.max(0, ui.deadline - performance.now()) / (ui.turnSeconds * 1000);
    const ring = ui.rings[s.game.turn];
    if (ring) ring.style.setProperty("--p", frac * 360 + "deg");
    const left = Math.ceil(frac * ui.turnSeconds);
    if (s.game.turn === s.you && left <= 5 && left > 0 && ui.lastTick !== left) { ui.lastTick = left; sfx.tick(); haptic(); }
  }

  /* ---------------- Ludo ---------------- */
  function diceHTML(v) {
    const on = { 1: [4], 2: [0, 8], 3: [0, 4, 8], 4: [0, 2, 6, 8], 5: [0, 2, 4, 6, 8], 6: [0, 2, 3, 5, 6, 8] }[v] || [];
    let h = '<div class="dice">';
    for (let i = 0; i < 9; i++) h += "<i" + (on.includes(i) ? ' class="on"' : "") + "></i>";
    return h + "</div>";
  }

  function drawBoard(board) {
    const mk = (cls, r, c, w, h) => {
      const d = document.createElement("div");
      d.className = cls;
      d.style.left = c * PCT + "%"; d.style.top = r * PCT + "%";
      if (w) { d.style.width = w * PCT + "%"; d.style.height = h * PCT + "%"; }
      board.append(d);
      return d;
    };
    B.YARD_ORIGIN.forEach((o, seat) => { mk("yard c" + seat, o[0], o[1], 6, 6).innerHTML = '<div class="yard-in"></div>'; });
    B.PATH.forEach((rc, i) => {
      const si = B.START.indexOf(i);
      const d = mk("cell" + (si >= 0 ? " c" + si + " start" : ""), rc[0], rc[1]);
      if (B.SAFE.has(i)) d.innerHTML = '<i class="star">★</i>';
    });
    B.HOMECOL.forEach((cells, seat) => cells.forEach((rc) => mk("cell hc c" + seat, rc[0], rc[1])));
    mk("center-box", 6, 6, 3, 3).innerHTML =
      '<svg viewBox="0 0 3 3" width="100%" height="100%"><polygon points="0,0 1.5,1.5 0,3" fill="var(--c0)"/>' +
      '<polygon points="0,0 3,0 1.5,1.5" fill="var(--c1)"/><polygon points="3,0 3,3 1.5,1.5" fill="var(--c2)"/>' +
      '<polygon points="0,3 3,3 1.5,1.5" fill="var(--c3)"/></svg>';
  }

  function buildLudo(s) {
    const g = s.game, mine = g.players.find((p) => p.uid === s.you);
    const rot = mine ? (3 - mine.seat + 4) % 4 : 0; // rotate so my colour sits bottom-left
    const ui = (S.ui = {
      type: "ludo", code: s.code, rot, pos: {}, dice: {}, lastRollSeq: 0, lastMoveSeq: 0, first: true,
      tokenEls: {}, panelEls: {}, rings: {}, players: g.players, deadline: null, turnSeconds: s.turn_seconds, prevTurn: null, resultShown: false,
    });
    const root = $("#screen-game");
    root.innerHTML = topbarHTML(s.code) + `<div class="stage">
      <div class="prow"><div class="pslot" data-slot="0"></div><div class="pslot" data-slot="1"></div></div>
      <div class="boardbox"><div class="board" id="board"></div></div>
      <div class="prow"><div class="pslot" data-slot="3"></div><div class="pslot" data-slot="2"></div></div></div>`;
    const board = $("#board");
    board.style.transform = "rotate(" + rot * 90 + "deg)";
    board.style.setProperty("--unrot", -rot * 90 + "deg");
    drawBoard(board);
    for (let seat = 0; seat < 4; seat++) {
      const slot = (seat + rot) % 4;
      const el = document.createElement("div");
      el.className = "panel empty c" + seat + (slot === 1 || slot === 2 ? " rev" : "");
      el.innerHTML = '<div class="tag coin"></div><div class="pill"><div class="ring"><div class="avatar"></div></div><div class="dicebox"></div></div>' +
        '<div class="tag name"></div><div class="dots"><i></i><i></i><i></i><i></i></div><div class="badge hidden"></div>';
      root.querySelector('.pslot[data-slot="' + slot + '"]').append(el);
      ui.panelEls[seat] = el;
    }
    for (const p of g.players) {
      ui.pos[p.uid] = p.tokens.slice();
      for (let i = 0; i < 4; i++) {
        const t = document.createElement("div");
        t.className = "token t" + p.seat;
        t.innerHTML = '<div class="pin"></div>';
        t.dataset.i = i;
        board.append(t);
        ui.tokenEls[p.uid + ":" + i] = t;
      }
    }
    board.addEventListener("click", (e) => {
      const t = e.target.closest(".token.movable");
      if (t) { send({ t: "move", token: +t.dataset.i }); haptic(); }
    });
    root.addEventListener("click", (e) => {
      if (e.target.closest(".dicebox.rollable")) { send({ t: "roll" }); haptic("medium"); }
    });
  }

  const OFFS = [[-0.2, -0.2], [0.2, -0.2], [-0.2, 0.2], [0.2, 0.2]];
  function renderTokens() {
    const ui = S.ui, groups = {};
    for (const p of ui.players) {
      ui.pos[p.uid].forEach((pos, i) => {
        const el = ui.tokenEls[p.uid + ":" + i];
        el.style.display = p.left ? "none" : "";
        if (p.left) return;
        const rc = B.tokenCell(p.seat, i, pos);
        const k = pos < 0 ? "y" + p.seat + i : rc[0] + "," + rc[1];
        (groups[k] = groups[k] || []).push([el, rc, pos]);
      });
    }
    for (const k in groups) {
      const arr = groups[k];
      arr.forEach(([el, rc, pos], idx) => {
        const off = arr.length > 1 ? OFFS[idx % 4] : [0, 0];
        el.style.left = rc[1] * PCT + "%"; el.style.top = rc[0] * PCT + "%";
        el.style.setProperty("--dx", off[0]); el.style.setProperty("--dy", off[1]);
        el.style.setProperty("--s", arr.length > 1 ? 0.72 : pos === 56 ? 0.8 : 1);
        el.style.zIndex = 3 + idx;
      });
    }
  }

  async function animateMove(m) {
    const arr = S.ui.pos[m.uid];
    if (!arr) return;
    if (m.from === -1) { arr[m.token] = m.to; renderTokens(); sfx.pop(); await sleep(260); }
    else {
      for (let p = m.from + 1; p <= m.to; p++) { arr[m.token] = p; renderTokens(); sfx.step(); await sleep(150); }
    }
    if (m.captured.length) {
      for (const c of m.captured) if (S.ui.pos[c.uid]) S.ui.pos[c.uid][c.token] = -1;
      renderTokens(); sfx.capture(); haptic("heavy");
      await sleep(350);
    }
  }

  function updateLudoPanels(s, shakeUid) {
    const ui = S.ui, g = s.game, letters = ["R", "G", "Y", "B"];
    const byUid = {}; s.players.forEach((p) => { byUid[p.uid] = p; });
    ui.rings = {};
    for (let seat = 0; seat < 4; seat++) {
      const el = ui.panelEls[seat], gp = g.players.find((p) => p.seat === seat);
      const av = el.querySelector(".avatar"), dbx = el.querySelector(".dicebox");
      const nameTag = el.querySelector(".name"), coinTag = el.querySelector(".coin"), badge = el.querySelector(".badge");
      if (!gp) {
        el.classList.add("empty");
        av.textContent = letters[seat]; dbx.className = "dicebox"; dbx.innerHTML = "";
        nameTag.textContent = ""; coinTag.textContent = ""; badge.classList.add("hidden");
        continue;
      }
      const rp = byUid[gp.uid] || {};
      el.classList.remove("empty");
      el.classList.toggle("left", gp.left);
      el.classList.toggle("turn", s.status === "playing" && g.turn === gp.uid);
      const key = gp.uid + "|" + (rp.photo || "");
      if (av.dataset.k !== key) { av.innerHTML = avatarInner(rp); av.dataset.k = key; }
      nameTag.textContent = handle(rp);
      nameTag.classList.toggle("you", gp.uid === s.you);
      coinTag.textContent = rp.is_bot ? "" : "💰 " + rp.coins;
      const home = (ui.pos[gp.uid] || []).filter((x) => x === 56).length;
      el.querySelectorAll(".dots i").forEach((d, i) => d.classList.toggle("on", i < home));
      const rollable = s.status === "playing" && g.turn === gp.uid && gp.uid === s.you && g.phase === "roll";
      dbx.className = "dicebox" + (rollable ? " rollable" : "") + (shakeUid === gp.uid ? " rolling" : "");
      if (rollable) dbx.textContent = "🎲";
      else dbx.innerHTML = ui.dice[gp.uid] ? diceHTML(ui.dice[gp.uid]) : "";
      const label = gp.left ? "LEFT" : rp.afk ? "AFK" : rp.online === false ? "OFFLINE" : "";
      badge.textContent = label; badge.classList.toggle("hidden", !label);
      ui.rings[gp.uid] = el.querySelector(".ring");
    }
  }

  async function applyLudo(s) {
    const ui = S.ui, g = s.game;
    ui.players = g.players;
    if (ui.first) {
      ui.first = false;
      for (const p of g.players) ui.pos[p.uid] = p.tokens.slice();
      if (g.last_roll) { ui.lastRollSeq = g.last_roll.seq; ui.dice[g.last_roll.uid] = g.last_roll.value; }
      if (g.last_move) ui.lastMoveSeq = g.last_move.seq;
    } else {
      if (g.last_roll && g.last_roll.seq > ui.lastRollSeq) {
        ui.lastRollSeq = g.last_roll.seq;
        ui.dice[g.last_roll.uid] = g.last_roll.value;
        renderTokens(); updateLudoPanels(s);
        const seat = (g.players.find((p) => p.uid === g.last_roll.uid) || {}).seat;
        const dbx = ui.panelEls[seat] && ui.panelEls[seat].querySelector(".dicebox");
        await tumble(dbx, g.last_roll.value, 1100);
        await sleep(120);
      }
      if (g.last_move && g.last_move.seq > ui.lastMoveSeq) {
        ui.lastMoveSeq = g.last_move.seq;
        await animateMove(g.last_move);
      }
      for (const p of g.players) ui.pos[p.uid] = p.tokens.slice();
    }
    renderTokens();
    updateLudoPanels(s);
    const canMove = s.status === "playing" && g.turn === s.you && g.phase === "move";
    for (const key in ui.tokenEls) {
      const [uid, i] = key.split(":");
      ui.tokenEls[key].classList.toggle("movable", canMove && +uid === s.you && g.movable.includes(+i));
    }
    if (g.turn === s.you && ui.prevTurn !== s.you && s.status === "playing") { sfx.turn(); haptic(); }
    ui.prevTurn = g.turn;
  }

  /* ---------------- Tic-Tac-Toe ---------------- */
  function buildTTT(s) {
    const g = s.game, order = g.players.map((p) => p.uid);
    const bottom = order.includes(s.you) ? s.you : order[0];
    const top = order.find((u) => u !== bottom);
    S.ui = { type: "tictactoe", code: s.code, top, bottom, rings: {}, deadline: null, turnSeconds: s.turn_seconds, lastMoveSeq: 0, first: true, prevTurn: null, resultShown: false };
    const pill = (id) => `<div class="panel" id="${id}"><div class="pill"><div class="ring"><div class="avatar"></div></div>
      <div style="flex:1;text-align:left;min-width:0"><div class="tag name" style="display:inline-block"></div><div class="tag coin" style="display:block;margin-top:3px;background:none;padding:0 10px"></div></div>
      <div class="markchip"></div></div></div>`;
    $("#screen-game").innerHTML = topbarHTML(s.code) + `<div class="ttt">${pill("tp-top")}
      <div class="ttt-board" id="tb">${[0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => `<button class="tcell" data-i="${i}"></button>`).join("")}</div>
      ${pill("tp-bot")}</div>`;
    $("#tb").addEventListener("click", (e) => {
      const c = e.target.closest(".tcell.can");
      if (c) { send({ t: "place", cell: +c.dataset.i }); haptic(); }
    });
  }

  function applyTTT(s) {
    const ui = S.ui, g = s.game, byUid = {};
    s.players.forEach((p) => { byUid[p.uid] = p; });
    ui.rings = {};
    [["#tp-top", ui.top], ["#tp-bot", ui.bottom]].forEach(([sel, uid]) => {
      const el = $(sel), rp = byUid[uid] || {}, gp = g.players.find((p) => p.uid === uid) || {};
      el.className = "panel " + (gp.mark === "X" ? "c3" : "c0") + (s.status === "playing" && g.turn === uid ? " turn" : "");
      const av = el.querySelector(".avatar"), key = uid + "|" + (rp.photo || "");
      if (av.dataset.k !== key) { av.innerHTML = avatarInner(rp); av.dataset.k = key; }
      const nm = el.querySelector(".name");
      nm.textContent = handle(rp); nm.classList.toggle("you", uid === s.you);
      el.querySelector(".coin").textContent = rp.is_bot ? "" : "💰 " + rp.coins + (rp.afk ? "  · AFK" : "");
      el.querySelector(".markchip").textContent = gp.mark || "";
      el.querySelector(".markchip").style.color = gp.mark === "X" ? "var(--c3)" : "var(--c0)";
      ui.rings[uid] = el.querySelector(".ring");
    });
    const myTurn = s.status === "playing" && g.turn === s.you;
    $("#tb").querySelectorAll(".tcell").forEach((c, i) => {
      const v = g.board[i];
      c.textContent = v;
      const fresh = v && c.dataset.v !== v;
      c.dataset.v = v || "";
      c.className = "tcell" + (v ? " " + v : "") + (fresh && !ui.first ? " new" : "") + (!v && myTurn ? " can" : "") + (g.line && g.line.includes(i) ? " win" : "");
    });
    if (!ui.first && g.last_move && g.last_move.seq > ui.lastMoveSeq) { sfx.place(); haptic(); }
    ui.first = false;
    if (g.last_move) ui.lastMoveSeq = g.last_move.seq;
    if (myTurn && ui.prevTurn !== s.you) { sfx.turn(); haptic(); }
    ui.prevTurn = g.turn;
  }

  /* ---------------- result ---------------- */
  function showResult(s) {
    const ui = S.ui;
    if (!ui || ui.resultShown) { $("#result").classList.remove("hidden"); return; }
    ui.resultShown = true;
    const r = s.result || {}, byUid = {};
    s.players.forEach((p) => { byUid[p.uid] = p; });
    const played = s.players.some((p) => p.uid === s.you && !p.left);
    let title, sub = "", amt = "";
    if (r.draw) { title = "🤝 Draw"; sub = s.bet ? "Bets refunded" : ""; sfx.draw(); }
    else if (r.winner === s.you) {
      title = "🏆 You won!";
      if (s.bet) amt = `<div class="amt win">+${r.prize} coins</div>`;
      sub = s.bet && r.rake ? "House fee: " + r.rake : "";
      sfx.win(); confetti();
    } else if (r.winners && r.winners.includes(s.you)) {
      title = "🏆 You won!"; if (s.bet) amt = `<div class="amt win">+${r.share} coins</div>`; sfx.win(); confetti();
    } else {
      if (played) sfx.lose();
      const w = byUid[r.winner];
      title = w ? esc(w.name) + " won" : "Game over";
      if (played && s.bet) amt = `<div class="amt lose">-${s.bet} coins</div>`;
    }
    const o = $("#result");
    o.innerHTML = `<div class="rbox"><h2>${title}</h2>${amt}<div class="sub">${sub}</div>
      ${played ? '<button class="btn primary" id="r-again">🔁 Rematch</button>' : ""}
      <button class="btn" id="r-home">Home</button></div>`;
    o.classList.remove("hidden");
    const again = $("#r-again");
    if (again) again.addEventListener("click", () => send({ t: "rematch" }));
    $("#r-home").addEventListener("click", leaveRoom);
  }

  /* ---------------- chat ---------------- */
  const QUICK = ["👍", "😂", "😮", "😡", "GG", "Nice!", "Hurry up!"];
  function renderChat() {
    $("#chat-list").innerHTML = S.chatLog.map((m) => `<div class="m"><b>${esc(m.name)}:</b> ${esc(m.text)}</div>`).join("") || '<div style="color:var(--muted)">No messages yet</div>';
    const l = $("#chat-list"); l.scrollTop = l.scrollHeight;
  }
  function addChat(m) {
    S.chatLog = S.chatLog.concat(m).slice(-40);
    const open = !$("#chat").classList.contains("hidden");
    if (open) renderChat();
    else if (Date.now() / 1000 - m.ts < 8) { toast(m.name + ": " + m.text, 2600); sfx.pop(); }
  }

  /* ---------------- boot ---------------- */
  async function boot() {
    if (tg) {
      tg.ready(); tg.expand();
      try { if (tg.disableVerticalSwipes) tg.disableVerticalSwipes(); } catch (e) { /* old client */ }
      try { tg.setHeaderColor("#1b1b1d"); tg.setBackgroundColor("#1b1b1d"); } catch (e) { /* old client */ }
      if (tg.BackButton) tg.BackButton.onClick(() => { if (S.room) askLeave(); });
    }
    $("#chat-close").addEventListener("click", () => $("#chat").classList.add("hidden"));
    $("#chat-quick").innerHTML = QUICK.map((q) => `<button type="button">${q}</button>`).join("");
    $("#chat-quick").addEventListener("click", (e) => { if (e.target.tagName === "BUTTON") send({ t: "chat", text: e.target.textContent }); });
    $("#chat-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const i = $("#chat-input");
      if (i.value.trim()) send({ t: "chat", text: i.value });
      i.value = "";
    });
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden && S.code && (!S.ws || S.ws.readyState > 1)) openSocket(S.code);
    });

    S.initData = getInitData();
    if (!S.initData) return fatal("Please open this game from Telegram.");
    try {
      S.cfg = await api("/api/config");
      const me = await api("/api/me", { method: "POST" });
      S.me = me.user; S.isAdmin = !!me.is_admin;
    } catch (e) { return fatal(e.message || "Could not connect to the server"); }

    const sp = (tg && tg.initDataUnsafe && tg.initDataUnsafe.start_param) || params.get("room") || params.get("startapp") || "";
    if (/^[0-9a-fA-F]{8}$/.test(sp)) joinRoom(sp.toUpperCase());
    else { showHome(); if (params.get("owner") && S.isAdmin) HUB.openOwner(); }
  }
  Object.assign(window.HUB, { api, tg, refreshHome: () => renderHome(), S, send, esc, sleep, sfx, haptic, avatarInner, handle, topbarHTML, diceHTML, toast, tumble, confetti, tone, noise });
  window.HUB.UI.ludo = { build: buildLudo, apply: applyLudo };
  window.HUB.UI.tictactoe = { build: buildTTT, apply: applyTTT };
  boot();
})();

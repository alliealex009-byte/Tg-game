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
  let actx;
  function beep(freq, dur, type, vol, when) {
    if (!S.sound) return;
    try {
      actx = actx || new (window.AudioContext || window.webkitAudioContext)();
      const o = actx.createOscillator(), g = actx.createGain();
      o.type = type || "sine"; o.frequency.value = freq;
      o.connect(g); g.connect(actx.destination);
      const t = actx.currentTime + (when || 0), v = vol || 0.05;
      g.gain.setValueAtTime(v, t);
      g.gain.exponentialRampToValueAtTime(0.0001, t + (dur || 0.08));
      o.start(t); o.stop(t + (dur || 0.08) + 0.02);
    } catch (e) { /* audio blocked */ }
  }
  const sfx = {
    roll() { [300, 380, 460, 540].forEach((f, i) => beep(f, 0.05, "square", 0.03, i * 0.07)); },
    step() { beep(520, 0.04, "triangle", 0.05); },
    capture() { beep(190, 0.25, "sawtooth", 0.06); },
    win() { [523, 659, 784, 1046].forEach((f, i) => beep(f, 0.2, "triangle", 0.07, i * 0.14)); },
    pop() { beep(660, 0.07, "sine", 0.05); },
    turn() { beep(880, 0.1, "sine", 0.05); },
  };

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
    if (m.t === "error") {
      toast(m.msg);
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
    renderHome();
    api("/api/me", { method: "POST" }).then((r) => { S.me = r.user; updateCoins(); }).catch(() => {});
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
      <div class="card"><h3>Play</h3>
        <div class="games">${Object.entries(cfg.games).map(([k, g]) => `
          <button class="gcard" data-game="${k}"><div class="em">${g.emoji}</div><div class="t">${esc(g.title)}</div>
          <div class="s">${g.min === g.max ? g.min : g.min + "-" + g.max} players</div></button>`).join("")}</div>
      </div>
      <div class="card"><h3>Join with a code</h3>
        <form class="joinrow" id="joinform"><input id="joincode" maxlength="8" placeholder="ROOM CODE" autocomplete="off"><button class="btn primary">Join</button></form>
      </div>
      <div class="card"><h3>Top players</h3><ul class="lb" id="lb"><li><span class="rk">…</span></li></ul></div>
    </div>`;
    const root = $("#screen-home");
    root.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => {
      S.bet = +c.dataset.bet;
      root.querySelectorAll(".chip").forEach((x) => x.classList.toggle("on", x === c));
    }));
    root.querySelectorAll(".gcard").forEach((c) => c.addEventListener("click", async () => {
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
    const u = "https://t.me/share/url?url=" + encodeURIComponent(shareLink(code)) + "&text=" + encodeURIComponent("Join my " + title + " game! Room " + code);
    if (tg && tg.openTelegramLink) tg.openTelegramLink(u); else window.open(u, "_blank");
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
      <div class="wait">${!inRoom ? "Room is full or already started — you are watching" : isHost ? "You are the host. Start when everyone is in." : "Waiting for Host to start…"}</div>
      <div class="codebox"><span class="code">${s.code}</span>
        <button class="btn sm" id="copy">Copy</button><button class="btn sm" id="share">Share</button></div>
      <div style="color:var(--gold);font-weight:700;margin-bottom:12px">${s.bet ? "💰 Bet: " + s.bet + " coins each" : "Free game"}</div>
      <div class="plist">${rows.join("")}</div>
      ${canStart ? '<button class="btn primary block start" id="start">▶ START GAME</button>' : ""}
      ${isHost && !s.bet && s.players.length < s.max_players ? '<button class="btn block" id="addbot" style="margin-bottom:10px">🤖 Add computer player</button>' : ""}
      <button class="btn block" id="leave">Leave room</button>
    </div>`;
    const root = $("#screen-lobby");
    const on = (sel, fn) => { const el = root.querySelector(sel); if (el) el.addEventListener("click", fn); };
    on("#copy", () => { try { navigator.clipboard.writeText(s.code); toast("Code copied"); } catch (e) { toast(s.code); } });
    on("#share", () => share(s.code, s.title));
    on("#start", () => send({ t: "start" }));
    on("#addbot", () => send({ t: "add_bot" }));
    on("#leave", leaveRoom);
    root.querySelectorAll("[data-rm]").forEach((b) => b.addEventListener("click", () => send({ t: "remove_bot", uid: +b.dataset.rm })));
  }

  /* ---------------- state pipeline ---------------- */
  function onState(s) {
    if (s.v < S.lastV) return;
    S.lastV = s.v;
    S.room = s;
    S.queue = S.queue.then(() => process(s)).catch((e) => console.error(e));
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
        renderTokens(); updateLudoPanels(s, g.last_roll.uid);
        sfx.roll();
        await sleep(550);
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
      c.className = "tcell" + (v ? " " + v : "") + (!v && myTurn ? " can" : "") + (g.line && g.line.includes(i) ? " win" : "");
    });
    if (!ui.first && g.last_move && g.last_move.seq > ui.lastMoveSeq) { sfx.pop(); }
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
    if (r.draw) { title = "🤝 Draw"; sub = s.bet ? "Bets refunded" : ""; }
    else if (r.winner === s.you) {
      title = "🏆 You won!";
      if (s.bet) amt = `<div class="amt win">+${r.prize} coins</div>`;
      sub = s.bet && r.rake ? "House fee: " + r.rake : "";
      sfx.win();
    } else {
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
      S.me = (await api("/api/me", { method: "POST" })).user;
    } catch (e) { return fatal(e.message || "Could not connect to the server"); }

    const sp = (tg && tg.initDataUnsafe && tg.initDataUnsafe.start_param) || params.get("room") || params.get("startapp") || "";
    if (/^[0-9a-fA-F]{8}$/.test(sp)) joinRoom(sp.toUpperCase()); else showHome();
  }
  Object.assign(window.HUB, { S, send, esc, sleep, sfx, haptic, avatarInner, handle, topbarHTML, diceHTML, toast });
  window.HUB.UI.ludo = { build: buildLudo, apply: applyLudo };
  window.HUB.UI.tictactoe = { build: buildTTT, apply: applyTTT };
  boot();
})();

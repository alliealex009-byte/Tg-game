/* Extras: floating dock (watchers, emoji reactions, how-to), owner panel screen, arcade menu. */
(function () {
  const HUB = window.HUB;
  const $ = (s) => document.querySelector(s);
  const EMOJI = ["😂", "🔥", "👏", "😮", "😡", "❤️", "👍", "😭", "🎉", "🤯", "💀", "🙏"];
  let dock = null, tray = false;

  let trayTimer = 0, lastReact = 0;
  function setTray(on) {
    tray = !!on;
    const t = $("#xtray"); if (!t) return;
    t.classList.toggle("hidden", !tray);
    clearTimeout(trayTimer);
    if (tray) {
      [...t.children].forEach((b, i) => { b.style.animationDelay = i * 22 + "ms"; });
      trayTimer = setTimeout(() => setTray(false), 6000);     // never leave it covering the game
    }
  }
  function ensureDock() {
    if (dock) return dock;
    dock = document.createElement("div");
    dock.id = "xdock";
    dock.innerHTML = `<button class="xd" id="xd-watch" title="Watching">👁 <b id="xd-n">0</b></button>
      <button class="xd" id="xd-react" title="Reactions">😀</button>
      <button class="xd" id="xd-help" title="How to play">❓</button>
      <div id="xtray" class="hidden">${EMOJI.map((e) => `<button type="button" data-e="${e}">${e}</button>`).join("")}</div>`;
    document.body.appendChild(dock);
    dock.addEventListener("click", (ev) => {
      const b = ev.target.closest("button"); if (!b) return;
      const s = HUB.S.room;
      if (b.dataset.e) {
        const now = Date.now();
        if (now - lastReact > 450) { lastReact = now; HUB.send({ t: "react", e: b.dataset.e }); HUB.haptic(); }
        setTray(false);                                         // close right after sending
        return;
      }
      if (b.id === "xd-react") setTray(!tray);
      else if (b.id === "xd-help" && s) showHowto(s.game_type);
      else if (b.id === "xd-watch" && s) {
        const names = (s.watchers || []).map((w) => w.name).join(", ");
        HUB.toast(s.watching ? "👁 Watching: " + names : "Nobody is watching yet");
      }
    });
    // tap anywhere else (the game, the background) closes the tray
    document.addEventListener("pointerdown", (ev) => { if (tray && !ev.target.closest("#xdock")) setTray(false); }, true);
    return dock;
  }

  HUB.afterState = function (s) {
    ensureDock();
    try { HUB.sfx.ambient(s.game_type, s.status === "playing"); } catch (e) { /* ignore */ }
    document.body.classList.add("in-room");
    dock.classList.add("on");
    $("#xd-n").textContent = s.watching || 0;
    $("#xd-watch").classList.toggle("hot", (s.watching || 0) > 0);
    // spectator banner
    let sb = $("#xspec");
    if (s.spectator && s.status !== "lobby") {
      if (!sb) { sb = document.createElement("div"); sb.id = "xspec"; document.body.appendChild(sb); }
      sb.textContent = "👁 You are watching this game";
    } else if (sb) sb.remove();
  };
  HUB.onHome = function () {
    try { HUB.sfx.ambientOff(); } catch (e) { /* ignore */ }
    if (dock) dock.classList.remove("on");
    document.body.classList.remove("in-room");
    const sb = $("#xspec"); if (sb) sb.remove();
    setTray(false);
  };

  HUB.onReact = function (m) {
    const el = document.createElement("div");
    el.className = "xfloat";
    el.innerHTML = `<span class="xe">${m.e}</span><span class="xn">${HUB.esc(String(m.name || "").slice(0, 12))}</span>`;
    el.style.left = 12 + Math.random() * 68 + "%";
    document.body.appendChild(el);
    const sway = (Math.random() * 60 - 30);
    el.animate([
      { transform: "translate(0,0) scale(.4)", opacity: 0 },
      { transform: `translate(${sway / 2}px,-18vh) scale(1.25)`, opacity: 1, offset: 0.2 },
      { transform: `translate(${-sway}px,-45vh) scale(1)`, opacity: 1, offset: 0.7 },
      { transform: `translate(${sway}px,-62vh) scale(.9)`, opacity: 0 },
    ], { duration: 2400, easing: "ease-out" }).finished.then(() => el.remove(), () => el.remove());
    HUB.sfx.pop();
  };

  /* ---------- how to play ---------- */
  function showHowto(key) {
    const cfg = HUB.S.cfg || {}, tips = (cfg.howto || {})[key] || (cfg.arcade_tips && cfg.arcade_tips[key] ? [cfg.arcade_tips[key]] : ["Have fun!"]);
    const g = (cfg.games || {})[key] || {};
    const m = document.createElement("div");
    m.className = "xmodal";
    m.innerHTML = `<div class="xcard"><h3>${g.emoji || "🎮"} ${HUB.esc(g.title || key)} — how to play</h3>
      <ol>${tips.map((t) => `<li>${HUB.esc(t)}</li>`).join("")}</ol><button class="btn primary block">Got it</button></div>`;
    m.addEventListener("click", (e) => { if (e.target === m || e.target.tagName === "BUTTON") m.remove(); });
    document.body.appendChild(m);
  }
  HUB.showHowto = showHowto;

  /* ---------- full screen overlay helper ---------- */
  function overlay(title, html, back) {
    let o = $("#xscreen");
    if (o) o.remove();
    o = document.createElement("div");
    o.id = "xscreen";
    o.innerHTML = `<div class="xhead"><button class="ibtn" id="xback">⬅️</button><b>${title}</b><span></span></div><div class="xbody">${html}</div>`;
    document.body.appendChild(o);
    $("#xback").addEventListener("click", () => { if (back) { if (HUB.stopArcade) HUB.stopArcade(); back(); } else closeOverlay(); });
    if (HUB.tg && HUB.tg.BackButton) { HUB.tg.BackButton.show(); }
    return o;
  }
  function closeOverlay() {
    const o = $("#xscreen"); if (o) o.remove();
    if (HUB.stopArcade) HUB.stopArcade();
    if (HUB.tg && HUB.tg.BackButton && !HUB.S.room) HUB.tg.BackButton.hide();
    if (!HUB.S.room) { try { HUB.refreshHome(); } catch (e) { /* ignore */ } }
  }
  HUB.overlay = overlay; HUB.closeOverlay = closeOverlay;

  /* ---------- owner panel ---------- */
  HUB.openOwner = async function () {
    const o = overlay("👑 Owner panel", '<div class="xcardp" id="ow-stats">Loading…</div>');
    const post = (path, body) => HUB.api(path, { method: "POST", body: body || {} });
    const body = o.querySelector(".xbody");
    async function load() {
      try {
        const st = await post("/api/owner/stats");
        body.innerHTML = `
        <div class="xcardp"><h4>📊 Stats</h4>
          <div class="xgrid"><div><b>${st.users}</b><span>users</span></div><div><b>${st.new_today}</b><span>new today</span></div>
          <div><b>${st.chats}</b><span>groups</span></div><div><b>${st.matches}</b><span>matches</span></div>
          <div><b>${st.live_rooms}</b><span>live rooms</span></div><div><b>${st.online}</b><span>online</span></div></div></div>
        <div class="xcardp"><h4>📢 Broadcast</h4>
          <textarea id="ow-text" maxlength="3500" rows="4" placeholder="Message (HTML allowed: &lt;b&gt;bold&lt;/b&gt;)"></textarea>
          <div class="xrow"><select id="ow-target"><option value="users">All users (DM)</option><option value="groups">All groups</option><option value="all">Everyone</option></select>
          <button class="btn primary" id="ow-send">Send</button></div></div>
        <div class="xcardp"><h4>👤 Player tools</h4>
          <input id="ow-uid" inputmode="numeric" placeholder="Telegram user id">
          <input id="ow-amt" inputmode="numeric" placeholder="Coins (+/-)">
          <div class="xrow"><button class="btn" data-a="info">Info</button><button class="btn" data-a="coins">Give coins</button>
          <button class="btn" data-a="ban">Ban</button><button class="btn" data-a="unban">Unban</button></div>
          <div id="ow-out" class="xout"></div></div>`;
        $("#ow-send").addEventListener("click", async () => {
          const text = $("#ow-text").value.trim(); if (!text) return HUB.toast("Write a message first");
          const tgt = $("#ow-target").value;
          if (!confirm("Send to " + tgt + "?")) return;
          try { const r = await post("/api/owner/broadcast", { text, target: tgt }); HUB.toast("Queued for " + r.queued + " chats"); $("#ow-text").value = ""; } catch (e) { HUB.toast(e.message); }
        });
        body.querySelectorAll("[data-a]").forEach((b) => b.addEventListener("click", async () => {
          const uid = parseInt($("#ow-uid").value, 10), a = b.dataset.a;
          if (!uid) return HUB.toast("Enter a user id");
          const payload = { uid, action: a };
          if (a === "coins") payload.amount = parseInt($("#ow-amt").value, 10);
          try {
            const r = await post("/api/owner/user", payload);
            $("#ow-out").textContent = `${r.name} (@${r.username}) · 💰${r.coins} · 🎮${r.games} · 🏆${r.wins}${r.banned ? " · 🚫 banned" : ""}`;
          } catch (e) { HUB.toast(e.message); }
        }));
      } catch (e) { body.innerHTML = '<div class="xcardp">' + HUB.esc(e.message) + "</div>"; }
    }
    load();
  };

  /* ---------- arcade menu ---------- */
  const ARCADE = [
    { k: "bricks", e: "🧱", t: "Break Bricks", d: "Classic brick breaker" },
    { k: "tapverse", e: "🪙", t: "TapVerse", d: "Tap to earn, upgrade power" },
    { k: "quickdrop", e: "☄️", t: "QuickDrop", d: "Catch coins, dodge bombs" },
    { k: "gridpop", e: "🔷", t: "GridPop", d: "Pop colour groups" },
    { k: "pocketfarm", e: "🌱", t: "PocketFarm", d: "Idle farm that grows" },
    { k: "byteblock", e: "🟦", t: "ByteBlock", d: "Slide & merge number blocks" },
    { k: "tiledash", e: "⚡", t: "TileDash", d: "Hit the lit tiles fast" },
    { k: "neonslice", e: "🍉", t: "NeonSlice", d: "Slice orbs, avoid bombs" },
    { k: "minttap", e: "🎯", t: "MintTap", d: "Stop the bar in the green zone" },
    { k: "turbocoin", e: "🚀", t: "TurboCoin", d: "10-second turbo tap burst" },
    { k: "sprout", e: "🌳", t: "IdleSprout", d: "A tree that earns while you sleep" },
    { k: "paws", e: "🐾", t: "PixelPaws", d: "Care for a pet, earn treats" },
    { k: "world", e: "🏘️", t: "TinyWorld", d: "Build a tiny town" },
    { k: "realm", e: "🏰", t: "MiniRealm", d: "Send heroes on missions" },
    { k: "snake", e: "🐍", t: "Snake", d: "Swipe to eat apples, grow longer" },
    { k: "flap", e: "🐤", t: "Flappy Wing", d: "Tap to fly through the pipes" },
    { k: "galaxy", e: "🚀", t: "Galaxy Shooter", d: "Drag your ship, blast aliens" },
    { k: "stack", e: "🏗️", t: "Stack Tower", d: "Drop blocks, build high" },
    { k: "roadrush", e: "🏎️", t: "Road Rush", d: "Dodge traffic, grab coins" },
    { k: "mole", e: "🔨", t: "Whack-a-Mole", d: "Whack moles, avoid bombs" },
  ];
  HUB.openArcade = function () {
    const o = overlay("🕹 Arcade", `<p class="xnote">Solo games that pay coins (daily cap applies). Anti-cheat runs on the server.</p>
      <div class="xlist">${ARCADE.map((a) => `<button class="xitem" data-k="${a.k}"><span class="xem">${a.e}</span><span><b>${a.t}</b><small>${a.d}</small></span><i>▶</i></button>`).join("")}</div>`);
    o.querySelectorAll(".xitem").forEach((b) => b.addEventListener("click", () => {
      const k = b.dataset.k;
      if (HUB.arcadeGames && HUB.arcadeGames[k]) HUB.arcadeGames[k]();
      else HUB.toast("Reload the app to play");
    }));
  };
})();

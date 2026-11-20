/* Idle / pet games: IdleSprout, PixelPaws, TinyWorld, MiniRealm. State lives on the server (app/idle.py). */
(function () {
  const HUB = window.HUB, A = HUB.arc, games = A.games;
  const $ = (s) => document.querySelector(s);
  const fmt = (s) => (s >= 3600 ? Math.floor(s / 3600) + "h " + Math.floor((s % 3600) / 60) + "m" : s >= 60 ? Math.floor(s / 60) + "m " + (s % 60) + "s" : s + "s");

  function idleGame(key, title, html, draw) {
    return async function () {
      HUB.overlay2(title, `<div class="xarc idl" id="idl">${html}</div>`);
      let st;
      const call = async (action, arg) => {
        try { st = await A.post("/api/idle/" + key, action ? { action, arg } : {}); if (action) { HUB.sfx.chip(); if (HUB.S.me) HUB.S.me.coins = st.coins; } paint(); }
        catch (e) { HUB.toast(e.message); HUB.sfx.miss(); }
      };
      const paint = () => { if (st && $("#idl")) { $("#idcoins").textContent = "💰 " + st.coins; draw(st, call); } };
      await call();
      A.timer(setInterval(() => { if (st && $("#idl")) call(); }, 15000));
    };
  }
  const head = '<div class="tvc" id="idcoins"></div>';

  games.sprout = idleGame("sprout", "🌳 IdleSprout", head + '<div class="id-big" id="idt"></div><div class="xnote" id="idn"></div><button class="btn primary" id="idc"></button><button class="btn" id="idu"></button>',
    (st, call) => {
      $("#idt").textContent = ["🌱", "🌱", "🌿", "🌿", "🪴", "🌳", "🌳", "🌲", "🌲", "🎄", "🎄"][st.lvl] || "🌳";
      $("#idn").textContent = `Level ${st.lvl} · ${st.rate} coins/hour · stores up to ${st.cap_h}h${st.full ? " (FULL!)" : ""}`;
      $("#idc").textContent = `Collect ${st.ready} 🪙`; $("#idc").disabled = st.ready < 1; $("#idc").onclick = () => call("collect");
      $("#idu").textContent = st.up_cost ? `Upgrade · ${st.up_cost} 🪙` : "Max level"; $("#idu").disabled = !st.up_cost; $("#idu").onclick = () => call("upgrade");
    });

  games.paws = idleGame("paws", "🐾 PixelPaws", head + '<div class="id-big" id="idt"></div><div class="xnote" id="idn"></div><div class="gx-bar big" style="width:min(260px,90%)"><i id="idxp"></i></div><div class="idrow"><button class="btn" id="idf"></button><button class="btn" id="idp"></button></div><button class="btn primary" id="idc"></button>',
    (st, call) => {
      $("#idt").textContent = st.mood === "happy" ? ["🐱", "🐱", "😸", "😸", "🐯", "🐯", "🦁", "🦁", "🐉"][st.lvl] : "😿";
      $("#idn").textContent = `Level ${st.lvl} · ${st.mood === "happy" ? "Happy" : "Needs food & play!"}`;
      $("#idxp").style.width = (st.xp / st.next_xp) * 100 + "%";
      $("#idf").textContent = st.feed_cd ? `🍖 Feed (${fmt(st.feed_cd)})` : `🍖 Feed · ${st.feed_cost} 🪙`; $("#idf").disabled = !!st.feed_cd; $("#idf").onclick = () => call("feed");
      $("#idp").textContent = st.play_cd ? `🎾 Play (${fmt(st.play_cd)})` : "🎾 Play"; $("#idp").disabled = !!st.play_cd; $("#idp").onclick = () => call("play");
      $("#idc").textContent = st.claim_cd ? `Treasure in ${fmt(st.claim_cd)}` : `Collect ${st.claim_reward} 🪙`; $("#idc").disabled = !!st.claim_cd; $("#idc").onclick = () => call("claim");
    });

  const EMO = { house: "🏠", farm: "🌾", mill: "🏭", tower: "🏯" };
  games.world = idleGame("world", "🏘️ TinyWorld", head + '<div class="idw" id="idg"></div><div class="xnote" id="idn"></div><div class="idrow" id="idb"></div><button class="btn primary" id="idc"></button>',
    (st, call) => {
      const sel = A.worldSel || "house";
      $("#idg").innerHTML = st.slots.map((b, i) => `<button class="idp ${b ? "full" : ""}" data-i="${i}">${b ? EMO[b] : "＋"}</button>`).join("");
      $("#idg").onclick = (e) => { const b = e.target.closest(".idp"); if (b && !b.classList.contains("full")) call("build", { idx: +b.dataset.i, type: A.worldSel || "house" }); };
      $("#idb").innerHTML = Object.entries(st.build).map(([k, v]) => `<button class="btn ${k === sel ? "primary" : ""}" data-k="${k}">${EMO[k]} ${v.cost}🪙<small>+${v.rate}/h</small></button>`).join("");
      $("#idb").onclick = (e) => { const b = e.target.closest("button"); if (b) { A.worldSel = b.dataset.k; draw0(); } };
      const draw0 = () => { $("#idb").querySelectorAll("button").forEach((x) => x.classList.toggle("primary", x.dataset.k === (A.worldSel || "house"))); };
      $("#idn").textContent = `Town earns ${st.rate} coins/hour · stores up to ${st.cap_h}h · tap ＋ to build the selected building`;
      $("#idc").textContent = `Collect ${st.ready} 🪙`; $("#idc").disabled = st.ready < 1; $("#idc").onclick = () => call("collect");
    });

  const MEM = { scout: ["🔭", "Scout"], raid: ["🗡️", "Raid"], siege: ["🏰", "Siege"] };
  games.realm = idleGame("realm", "🏰 MiniRealm", head + '<div class="id-big">🛡️</div><div class="xnote" id="idn"></div><div id="idm" class="idrow"></div><button class="btn primary" id="idc"></button>',
    (st, call) => {
      $("#idn").textContent = `Hero level ${st.lvl} · ${st.xp} XP · higher level = bigger rewards`;
      const m = st.mission;
      $("#idm").innerHTML = Object.entries(st.missions).map(([k, v]) => `<button class="btn" data-k="${k}" ${m ? "disabled" : ""}>${MEM[k][0]} ${MEM[k][1]}<small>${fmt(v.secs)} · ${v.reward}🪙 · ${v.chance}% win</small></button>`).join("");
      $("#idm").onclick = (e) => { const b = e.target.closest("button"); if (b && !b.disabled) call("start", b.dataset.k); };
      $("#idc").style.display = m ? "" : "none";
      if (m) { $("#idc").textContent = m.done ? "Heroes are back — claim!" : `Out on a ${m.id}… ${fmt(m.left)}`; $("#idc").disabled = !m.done; $("#idc").onclick = () => call("claim"); }
    });
})();

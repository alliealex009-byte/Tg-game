/* Renderer for Boxing (action group). Registers { build, apply } in HUB.UI. Spectators get a read-only view. */
(function () {
  "use strict";
  window.HUB = window.HUB || { UI: {} };
  const HUB = window.HUB;
  const $ = (s, r) => (r || document).querySelector(s);
  const K = () => HUB.kit;
  const room = () => HUB.S.room;
  const playing = (s) => s.game.players.some((p) => p.uid === s.you);
  const COST = { jab: 5, hook: 12, uppercut: 20, block: 0, dodge: 8 };
  const ICON = { jab: "👊", hook: "🥊", uppercut: "💥", block: "🛡️", dodge: "💨" };
  const sfx = (n) => { try { HUB.sfx[n](); } catch (e) { /* ignore */ } };

  function buildBoxing(s) {
    K().newUI("boxing", s, { lastSeq: 0, locked: false, round: 0 });
    const f = (p, i) => `<div class="ga-f" data-uid="${p.uid}"><div class="ga-glove" id="gaglove${i}">🥊</div>
      <div class="ga-bars"><div class="ga-hp"><i></i></div><div class="ga-st"><i></i></div></div><div class="ga-kd"></div></div>`;
    K().shell(s, `<div class="ga-box"><div class="ga-round" id="garound"></div>
      <div class="ga-ring">${s.game.players.map(f).join('<div class="ga-vs">VS</div>')}</div>
      <div class="ga-msg" id="gamsg">Pick your move!</div>
      <div class="ga-moves" id="gamoves">${Object.keys(COST).map((m) =>
        `<button class="ga-mv" data-m="${m}"><span>${ICON[m]}</span><b>${m}</b><small>${COST[m] ? "⚡" + COST[m] : "free"}</small></button>`).join("")}</div></div>`);
    $("#gamoves").addEventListener("click", (e) => {
      const b = e.target.closest(".ga-mv"), s2 = room(), ui = HUB.S.ui;
      if (!b || b.disabled || !playing(s2) || ui.locked || s2.status !== "playing") return;
      ui.locked = true;
      HUB.send({ t: "move", move: b.dataset.m });
      HUB.haptic("medium"); sfx("pop");
      document.querySelectorAll(".ga-mv").forEach((x) => x.classList.toggle("sel", x === b));
      $("#gamsg").textContent = "Locked in " + b.dataset.m + " — waiting…";
    });
  }
  function describe(s, le) {
    const [a, b] = s.game.players.map((p) => p.uid);
    const nm = (u) => (u === s.you ? "You" : K().nameOf(s, u));
    const parts = [];
    [[a, b], [b, a]].forEach(([x, y]) => {
      const d = le.dmg[y];
      if (d) parts.push(`${nm(x)} ${le.moves[x]} → ${d} dmg`);
      else if (le.moves[x] in { jab: 1, hook: 1, uppercut: 1 }) parts.push(`${nm(x)}'s ${le.moves[x]} missed`);
    });
    return parts.join(" · ") || "Both fighters circle…";
  }
  async function applyBoxing(s) {
    const ui = HUB.S.ui, g = s.game, le = g.last_exchange;
    const ps = g.players;
    document.querySelectorAll(".ga-f").forEach((el, i) => {
      const p = ps[i];
      el.querySelector(".ga-hp i").style.width = p.hp + "%";
      el.querySelector(".ga-st i").style.width = p.stamina + "%";
      el.querySelector(".ga-kd").textContent = (p.kd ? "KD ×" + p.kd + "  " : "") + "R " + p.rounds;
      el.classList.toggle("me", p.uid === s.you);
      el.classList.toggle("picked", !!g.picked[p.uid]);
    });
    $("#garound").textContent = `ROUND ${g.round}/${g.rounds} · exchange ${Math.min(g.exch + 1, g.exchanges)}/${g.exchanges}`;
    const mine = ps.find((p) => p.uid === s.you), me = !!mine;
    if (ui.first) { ui.first = false; if (le) ui.lastSeq = le.seq; }
    else if (le && le.seq > ui.lastSeq) {
      ui.lastSeq = le.seq; ui.locked = false;
      const gl = ps.map((p, i) => $("#gaglove" + i));
      ps.forEach((p, i) => {
        const hit = le.dmg[ps[1 - i].uid] > 0;   // this fighter's punch landed
        gl[i].textContent = ICON[le.moves[p.uid]];
        gl[i].animate([{ transform: "translateX(0) scale(1)" }, { transform: `translateX(${i ? -26 : 26}px) scale(1.4)` }, { transform: "translateX(0) scale(1)" }], { duration: 380, easing: "ease-out" });
        if (hit) { const t = $(`.ga-f[data-uid="${ps[1 - i].uid}"]`); t.animate([{ transform: "translateX(0)" }, { transform: "translateX(-7px)" }, { transform: "translateX(7px)" }, { transform: "translateX(0)" }], { duration: 300 }); }
      });
      const any = Object.values(le.dmg).some((d) => d > 0);
      sfx(any ? "hit" : "miss"); HUB.haptic(any ? "heavy" : "light");
      $("#gamsg").textContent = describe(s, le);
      if (le.knockdown != null) { $("#gamsg").textContent = "💫 KNOCKDOWN! " + (le.ko ? "KO!" : "Count " + le.count); HUB.confetti && le.ko && HUB.confetti(); }
      if (le.round_end) { await HUB.sleep(600); $("#gamsg").textContent = "🔔 End of round"; }
    }
    const ok = me && s.status === "playing" && !g.picked[s.you];
    if (ok) ui.locked = false;
    document.querySelectorAll(".ga-mv").forEach((b) => {
      b.disabled = !ok || COST[b.dataset.m] > mine.stamina;
      if (ok) b.classList.remove("sel");
    });
    $("#gamoves").classList.toggle("hidden", !me);
    if (ok && ui.round !== g.round + "/" + g.exch) { ui.round = g.round + "/" + g.exch; if (le) {} }
    K().updateBar(ui, s, (uid) => { const p = ps.find((x) => x.uid === uid); return { score: "R" + p.rounds }; });
    K().setHint(me ? (g.picked[s.you] ? "Waiting for your opponent…" : "Choose a move — both fighters pick at once") : "👀 Watching the fight");
  }
  HUB.UI.boxing = { build: buildBoxing, apply: applyBoxing };
})();

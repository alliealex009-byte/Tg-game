/* FX layer for Teen Patti + Crazy Eights. Loads after g_cards.js; wraps apply() and only adds effects on top. */
(function () {
  "use strict";
  const HUB = window.HUB; if (!HUB || !HUB.UI) return;
  const $ = (s, r) => (r || document).querySelector(s), $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const RM = () => { try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { return false; } };
  const tone = (...a) => { try { HUB.tone && HUB.tone(...a); } catch (e) { /* audio */ } };
  const sfx = (n) => { try { HUB.sfx && HUB.sfx[n] && HUB.sfx[n](); } catch (e) { /* audio */ } };
  const safe = (f) => { try { f(); } catch (e) { /* fx must never break the game */ } };
  const anim = (el, frames, o) => { if (!el || !el.animate || RM()) return null; try { return el.animate(frames, Object.assign({ easing: "ease-out" }, o)); } catch (e) { return null; } };
  const ctr = (el) => { const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; };

  function events(ui, g) {
    const evs = g.log ? g.log : (g.event ? [g.event] : []);
    const mx = evs.reduce((m, e) => Math.max(m, e.seq || 0), 0);
    if (ui.fxSeq == null) { ui.fxSeq = mx; return []; }
    const out = evs.filter((e) => e.seq > ui.fxSeq); ui.fxSeq = Math.max(ui.fxSeq, mx); return out;
  }
  function toss(from, to, n, color) {
    if (RM() || !from || !to) return;
    const a = ctr(from), b = ctr(to);
    for (let i = 0; i < n; i++) setTimeout(() => safe(() => {
      const c = document.createElement("i"); c.className = "fx-chip"; if (color) c.style.filter = color;
      c.style.left = a.x + "px"; c.style.top = a.y + "px"; document.body.appendChild(c);
      const dx = b.x - a.x + (Math.random() * 16 - 8), dy = b.y - a.y, arc = -40 - Math.random() * 30;
      const an = anim(c, [{ transform: "translate(0,0) scale(.8)", opacity: 1 },
        { transform: `translate(${dx * 0.5}px,${dy * 0.5 + arc}px) scale(1.15) rotate(180deg)`, offset: 0.5 },
        { transform: `translate(${dx}px,${dy}px) scale(.9) rotate(360deg)`, opacity: 1 }], { duration: 340, easing: "cubic-bezier(.3,.7,.4,1)" });
      const done = () => { c.remove(); tone(2200 + Math.random() * 600, 0.06, "square", 0.05); };
      if (an) an.onfinish = done; else c.remove();
    }), i * 70);
  }
  function countUp(el, from, to, pre) {
    if (!el || from === to || RM()) return;
    const t0 = performance.now(), ms = 420;
    const step = (t) => { const k = Math.min(1, (t - t0) / ms); el.textContent = pre + Math.round(from + (to - from) * k); if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
    anim(el, [{ transform: "scale(1.25)" }, { transform: "scale(1)" }], { duration: 420 });
  }
  function flipCards(root, sel) {
    $$(sel || ".gc-card", root).forEach((c, i) => anim(c, [{ transform: "perspective(400px) rotateY(90deg)", opacity: 0.2 }, { transform: "perspective(400px) rotateY(0)", opacity: 1 }], { duration: 320, delay: i * 60, easing: "cubic-bezier(.2,.8,.3,1)" }));
  }
  function banner(text, red) {
    if (RM()) return;
    const b = document.createElement("div"); b.className = "fx-banner" + (red ? " red" : ""); b.textContent = text; document.body.appendChild(b);
    const an = anim(b, [{ opacity: 0, transform: "translate(-50%,-50%) scale(.5)" }, { opacity: 1, transform: "translate(-50%,-50%) scale(1.1)", offset: 0.3 },
      { opacity: 1, transform: "translate(-50%,-50%) scale(1)", offset: 0.75 }, { opacity: 0, transform: "translate(-50%,-80%) scale(1)" }], { duration: 560 });
    if (an) an.onfinish = () => b.remove(); else b.remove();
  }
  const shake = (el) => anim(el, [{ transform: "translateX(0)" }, { transform: "translateX(-6px)" }, { transform: "translateX(6px)" }, { transform: "translateX(-4px)" }, { transform: "translateX(3px)" }, { transform: "none" }], { duration: 420 });

  /* ---------------- Teen Patti ---------------- */
  const TP = HUB.UI.teenpatti;
  if (TP && TP.apply) {
    const orig = TP.apply;
    TP.apply = function (s) {
      let snap = null, evs = [];
      const ui = HUB.S && HUB.S.ui;
      safe(() => {
        const g = s.game;
        snap = { pot: ui.fxPot, st: ui.fxSt || {} };
        evs = ui ? events(ui, g) : [];
      });
      const r = orig.apply(this, arguments);
      const after = () => safe(() => {
        if (!ui || !snap) return;
        const g = s.game, seats = $$("#gct .gc-seat"), idx = (u) => g.players.findIndex((p) => p.uid === u);
        const potEl = $("#gct .gc-potc");
        const potTo = (u) => toss(seats[idx(u)], potEl, 3);
        for (const ev of evs) {
          if (ev.kind === "chaal" || ev.kind === "raise") { potTo(ev.uid); if (ev.kind === "raise") tone(900, 0.12, "triangle", 0.1, 0.2, 1400); }
          else if (ev.kind === "deal") { g.players.forEach((p, i) => toss(seats[i], potEl, 1)); }
          else if (ev.kind === "see") { if (ev.uid === s.you) { flipCards($("#gch")); flipCards(seats[idx(ev.uid)], ".gc-card"); } tone(700, 0.08, "triangle", 0.1); }
          else if (ev.kind === "show") { flipCards($("#gct"), ".gc-card.std"); tone(500, 0.3, "sawtooth", 0.1, 0, 900); }
          else if (ev.kind === "pack") {
            const st = seats[idx(ev.uid)];
            anim(st, [{ opacity: 1, filter: "none", transform: "scale(1.03)" }, { opacity: 0.4, transform: "translateX(-12px)", offset: 0.6 }, { opacity: 0.55 }], { duration: 450 });
            tone(300, 0.25, "sine", 0.12, 0, 120);
          } else if (ev.kind === "round_end") {
            const w = ev.winners && ev.winners[0], ws = w != null && seats[idx(w)];
            if (potEl && ws) for (let i = 0; i < 6; i++) setTimeout(() => safe(() => toss(potEl, ws, 1)), i * 60);
            flipCards($("#gct"), ".gc-card.std");
            if (ev.winners && ev.winners.includes(s.you) && s.status !== "finished" && HUB.confetti && !RM()) HUB.confetti(36);
            [1046, 1318, 1568].forEach((f, i) => tone(f, 0.14, "triangle", 0.12, 0.25 + i * 0.07));
          }
        }
        if (potEl && snap.pot != null && snap.pot !== g.pot) countUp(potEl, snap.pot, g.pot, "🪙 ");
        const st = {};
        g.players.forEach((p, i) => {
          st[p.uid] = p.state;
          if (snap.st[p.uid] && snap.st[p.uid] !== p.state && p.state !== "pack") {
            const em = $(".gc-st", seats[i]); anim(em, [{ transform: "scale(.4)", opacity: 0 }, { transform: "scale(1.5)", offset: 0.6, opacity: 1 }, { transform: "scale(1)" }], { duration: 380 });
          }
        });
        ui.fxSt = st; ui.fxPot = g.pot;
      });
      // orig is async (awaits event pacing) - run effects once DOM is rendered
      if (r && r.then) return r.then((v) => { after(); return v; }); after(); return r;
    };
  }

  /* ---------------- Crazy Eights ---------------- */
  const C8 = HUB.UI.crazy8;
  if (C8 && C8.apply) {
    const orig = C8.apply;
    C8.apply = function (s) {
      let evs = [], prevCur = null, ui = HUB.S && HUB.S.ui;
      safe(() => { evs = ui ? events(ui, s.game) : []; prevCur = ui && ui.fxCur; });
      const r = orig.apply(this, arguments);
      const after = () => safe(() => {
        if (!ui) return;
        const g = s.game, SYM = { S: "♠", H: "♥", D: "♦", C: "♣" };
        const oppEl = (u) => document.querySelector(`#gct .gc-opp[data-uid="${u}"]`);
        for (const ev of evs) {
          if (ev.kind === "play" && ev.card && ev.card.slice(0, -1) === "8" && prevCur != null) {
            const red = g.cur === "H" || g.cur === "D";
            banner("Suit: " + (SYM[g.cur] || g.cur), red); tone(600, 0.18, "triangle", 0.14, 0, 1200); tone(900, 0.2, "triangle", 0.12, 0.12, 1500);
            anim($("#gct .gc-suit"), [{ transform: "scale(2.2) rotate(-30deg)" }, { transform: "scale(1)" }], { duration: 480, easing: "cubic-bezier(.3,1.6,.5,1)" });
          } else if (ev.kind === "draw") {
            const d = $("#gc-draw"); anim(d, [{ transform: "translateY(0)" }, { transform: "translateY(5px) scale(.96)" }, { transform: "none" }], { duration: 260 });
            for (let i = 1; i < Math.min(ev.n || 1, 3); i++) setTimeout(() => safe(() => {
              const to = ev.uid === s.you ? $("#gch") : oppEl(ev.uid), from = $("#gc-draw");
              if (!to || !from || RM()) return; const a = ctr(from), b = ctr(to), c = document.createElement("div");
              c.className = "gc-card back fx-ghost"; c.style.left = a.x - 28 + "px"; c.style.top = a.y - 42 + "px"; document.body.appendChild(c);
              const an = anim(c, [{ transform: "translate(0,0)" }, { transform: `translate(${b.x - a.x}px,${b.y - a.y}px) scale(.8)`, opacity: 0.2 }], { duration: 300 });
              if (an) an.onfinish = () => c.remove(); else c.remove(); sfx("deal");
            }), i * 110);
          }
          if (ev.victim && ev.n) { const v = ev.victim === s.you ? $("#gch") : oppEl(ev.victim); shake(v); tone(160, 0.25, "sawtooth", 0.15, 0, 70); if (ev.victim === s.you) HUB.haptic && HUB.haptic("heavy"); }
        }
        ui.fxCur = g.cur;
        // last-card warning
        const last = ui.fxLast || {};
        (g.players || []).forEach((p) => {
          if (p.n === 1 && !last[p.uid]) {
            const el = p.uid === s.you ? $("#gch") : oppEl(p.uid); if (el && !RM()) { el.classList.add("fx-last"); setTimeout(() => el.classList.remove("fx-last"), 1300); }
            tone(988, 0.1, "square", 0.08); tone(988, 0.1, "square", 0.08, 0.16);
          }
          last[p.uid] = p.n === 1;
        });
        ui.fxLast = last;
      });
      if (r && r.then) return r.then((v) => { after(); return v; }); after(); return r;
    };
  }
})();

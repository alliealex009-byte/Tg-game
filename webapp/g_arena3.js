/* Hand Cricket (gully cricket) and Bluff (Cheat). */
(function () {
  "use strict";
  window.HUB = window.HUB || { UI: {} };
  const HUB = window.HUB;
  const $ = (s, r) => (r || document).querySelector(s);
  const K = () => HUB.kit;
  const room = () => HUB.S.room;
  const playing = (s) => s.game.players.some((p) => p.uid === s.you);
  const sfx = (n) => { try { HUB.sfx[n](); } catch (e) { /* ignore */ } };
  const tone = (...a) => { try { HUB.tone(...a); } catch (e) { /* ignore */ } };
  const esc = (t) => String(t).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const nm = (s, u) => (u === s.you ? "You" : K().nameOf(s, u));
  const anim = (el, kf, o) => { try { return el && el.animate ? el.animate(kf, o) : null; } catch (e) { return null; } };

  /* ================================ HAND CRICKET ================================ */
  const HAND = ["", "☝️", "✌️", "🤟", "🖖", "🖐️", "👍"];
  const CALL = { 4: "FOUR!", 6: "SIXER!" };
  function buildCricket(s) {
    K().newUI("cricket", s, { lastSeq: 0, locked: false, busy: false });
    K().shell(s, `<div class="hc-box">
      <div class="hc-board"><div class="hc-bat" id="hcbat"></div><div class="hc-sc" id="hcsc"></div><div class="hc-need" id="hcneed"></div></div>
      <div class="hc-stadium" id="hcstad"><div class="hc-crowd"></div><div class="hc-pitch"><div class="hc-stumps" id="hcst"><i></i><i></i><i></i><b class="b1"></b><b class="b2"></b></div></div>
        <div class="hc-ball" id="hcball">🏏</div><div class="hc-call" id="hccall"></div>
        <div class="hc-hands"><div class="hc-hand l" id="hcL"><span>✊</span><small id="hcLn"></small></div><div class="hc-hand r" id="hcR"><span>✊</span><small id="hcRn"></small></div></div></div>
      <div class="hc-balls" id="hcballs"></div>
      <div class="gx-msg" id="hcmsg"></div>
      <div class="hc-pad" id="hcpad">${[1, 2, 3, 4, 5, 6].map((n) => `<button data-n="${n}"><span>${HAND[n]}</span><b>${n}</b></button>`).join("")}</div></div>`);
    $("#hcpad").onclick = (e) => {
      const b = e.target.closest("button"), s2 = room(), ui = HUB.S.ui;
      if (!b || b.disabled || !playing(s2) || ui.locked || ui.busy || s2.status !== "playing" || s2.game.picked[s2.you]) return;
      ui.locked = true; HUB.send({ t: "num", n: +b.dataset.n }); HUB.haptic("medium"); sfx("pop");
      document.querySelectorAll("#hcpad button").forEach((x) => x.classList.toggle("sel", x === b));
      $("#hcmsg").textContent = "Locked " + b.dataset.n + " — waiting…";
    };
  }
  async function revealBall(s, lb) {
    const ui = HUB.S.ui, bat = lb.batter === s.you ? "You" : nm(s, lb.batter);
    ui.busy = true;
    const L = $("#hcL"), R = $("#hcR");
    // "1-2-3 GO": both fists shake, then the fingers show
    L.firstElementChild.textContent = R.firstElementChild.textContent = "✊";
    $("#hcLn").textContent = $("#hcRn").textContent = "";
    for (let i = 0; i < 3; i++) {
      anim(L, [{ transform: "translateY(0)" }, { transform: "translateY(-18px)" }, { transform: "none" }], { duration: 230 });
      anim(R, [{ transform: "translateY(0)" }, { transform: "translateY(-18px)" }, { transform: "none" }], { duration: 230 });
      tone(300 + i * 80, 0.08, "square", 0.12);
      await sleep(250);
    }
    L.firstElementChild.textContent = HAND[lb.bowl]; R.firstElementChild.textContent = HAND[lb.bat];
    $("#hcLn").textContent = lb.bowl; $("#hcRn").textContent = lb.bat;
    anim(L, [{ transform: "scale(.6)" }, { transform: "scale(1.25)" }, { transform: "none" }], { duration: 300 });
    anim(R, [{ transform: "scale(.6)" }, { transform: "scale(1.25)" }, { transform: "none" }], { duration: 300 });
    sfx("hit");
    const call = $("#hccall"), stad = $("#hcstad"), ball = $("#hcball");
    if (lb.out) {
      stad.classList.add("out"); call.textContent = "OUT!"; call.className = "hc-call show out";
      document.querySelectorAll("#hcst i").forEach((st, i) => anim(st, [{ transform: "none" }, { transform: `translate(${(i - 1) * 26}px,-40px) rotate(${(i - 1) * 70}deg)`, opacity: 0.2 }], { duration: 600, fill: "forwards", easing: "ease-out" }));
      document.querySelectorAll("#hcst b").forEach((b, i) => anim(b, [{ transform: "none" }, { transform: `translate(${(i ? 1 : -1) * 50}px,-70px) rotate(${(i ? 1 : -1) * 220}deg)`, opacity: 0 }], { duration: 700, fill: "forwards" }));
      anim(stad, [{ transform: "translate(0,0)" }, { transform: "translate(-8px,3px)" }, { transform: "translate(7px,-3px)" }, { transform: "translate(-4px,2px)" }, { transform: "none" }], { duration: 480 });
      sfx("bad"); tone(120, 0.5, "sawtooth", 0.25, 0, 40); HUB.haptic("heavy");
      $("#hcmsg").textContent = `${bat} is OUT! Both showed ${lb.bat}`;
    } else {
      const big = lb.runs >= 4;
      call.textContent = CALL[lb.runs] || "+" + lb.runs; call.className = "hc-call show " + (big ? "big" : "");
      const dx = (Math.random() - 0.5) * 120, h = big ? (lb.runs === 6 ? 230 : 120) : 60 + lb.runs * 10;
      ball.style.opacity = 1;
      anim(ball, [{ transform: "translate(0,0) scale(1)", opacity: 1 }, { transform: `translate(${dx * 0.6}px,-${h}px) scale(${big ? 1.6 : 1.2}) rotate(360deg)`, opacity: 1, offset: 0.5 }, { transform: `translate(${dx}px,${big ? -30 : 10}px) scale(.7) rotate(720deg)`, opacity: lb.runs === 6 ? 0 : 1 }], { duration: big ? 900 : 650, easing: "ease-out" });
      if (big) { sfx("win"); HUB.haptic("heavy"); if (lb.runs === 6 && HUB.confetti) HUB.confetti(40); stad.classList.add("roar"); }
      else sfx(lb.runs >= 2 ? "good" : "place");
      $("#hcmsg").textContent = `${bat} scored ${lb.runs}`;
    }
    await sleep(lb.out ? 1100 : 900);
    stad.classList.remove("out", "roar"); call.className = "hc-call"; call.textContent = "";
    document.querySelectorAll("#hcst i,#hcst b").forEach((x) => { x.getAnimations && x.getAnimations().forEach((a) => a.cancel()); });
    L.firstElementChild.textContent = R.firstElementChild.textContent = "✊"; $("#hcLn").textContent = $("#hcRn").textContent = "";
    ui.busy = false;
  }
  function applyCricket(s) {
    const ui = HUB.S.ui, g = s.game, lb = g.last_ball, me = playing(s);
    const bt = g.players.find((p) => p.uid === g.batter), ru = bt.runs;
    $("#hcbat").innerHTML = `🏏 <b>${esc(nm(s, g.batter))}</b> batting <small>${esc(nm(s, g.bowler))} bowling</small>`;
    $("#hcsc").innerHTML = `<b>${ru}</b>/${g.wkts} <small>${g.balls}/${g.total_balls} balls</small>`;
    $("#hcneed").textContent = g.target == null ? `Innings 1 — set a big target!` : `Target ${g.target + 1} · need ${Math.max(0, g.target + 1 - ru)} off ${g.total_balls - g.balls} balls`;
    $("#hcballs").innerHTML = g.history.map((h) => `<i class="${h === "W" ? "w" : h >= 4 ? "f" : ""}">${h}</i>`).join("");
    if (ui.first) { ui.first = false; if (lb) ui.lastSeq = lb.seq; }
    else if (lb && lb.seq > ui.lastSeq) {
      ui.lastSeq = lb.seq; ui.locked = false;
      revealBall(s, lb).then(() => { if (lb.innings_over) { const m = $("#hcmsg"); if (m) m.textContent = `Innings break! Target is ${g.target + 1}`; sfx("turn"); } });
    }
    const ok = me && s.status === "playing" && !g.picked[s.you];
    if (ok && !ui.busy) { ui.locked = false; document.querySelectorAll("#hcpad button").forEach((x) => x.classList.remove("sel")); if (!$("#hcmsg").textContent.startsWith("Innings")) $("#hcmsg").textContent = g.batter === s.you ? "🏏 You BAT — pick a number, don't match the bowler!" : "🎯 You BOWL — guess the batter's number!"; }
    document.querySelectorAll("#hcpad button").forEach((b) => { b.disabled = !ok; });
    $("#hcpad").classList.toggle("hidden", !me);
    K().updateBar(ui, s, (uid) => ({ score: "🏏" + g.players.find((p) => p.uid === uid).runs }));
    K().setHint(me ? "Same number = OUT!" : "👀 Watching the match");
  }
  HUB.UI.cricket = { build: buildCricket, apply: applyCricket };

  /* ==================================== BLUFF ==================================== */
  const SUIT = { S: "♠", H: "♥", D: "♦", C: "♣" };
  const face = (c, cls) => `<div class="bl-c ${"HD".includes(c.slice(-1)) ? "red" : ""} ${cls || ""}" data-c="${c}" data-s="${SUIT[c.slice(-1)]}"><b>${c.slice(0, -1)}</b><i>${SUIT[c.slice(-1)]}</i></div>`;
  const RN = { A: "Aces", 2: "2s", 3: "3s", 4: "4s", 5: "5s", 6: "6s", 7: "7s", 8: "8s", 9: "9s", 10: "10s", J: "Jacks", Q: "Queens", K: "Kings" };
  function buildBluff(s) {
    K().newUI("bluff", s, { lastSeq: 0, sel: new Set(), busy: false });
    K().shell(s, `<div class="bl-box"><div class="bl-opps" id="blopps"></div>
      <div class="bl-table"><div class="bl-pile" id="blpile"><div class="bl-pcards" id="blpc"></div><span id="blcnt"></span></div><div class="bl-rank" id="blrank"></div></div>
      <div class="bl-claim" id="blclaim"></div><div class="bl-reveal" id="blrev"></div>
      <div class="bl-btns" id="blbtns"></div><div class="bl-hand" id="blhand"></div></div>`);
    $("#blhand").onclick = (e) => {
      const c = e.target.closest(".bl-c"), s2 = room(), ui = HUB.S.ui;
      if (!c || !isMyPlay(s2)) return;
      const k = c.dataset.c;
      if (ui.sel.has(k)) ui.sel.delete(k); else if (ui.sel.size < 4) ui.sel.add(k); else return;
      sfx("flip"); paintHand(s2);
    };
    $("#blbtns").onclick = (e) => {
      const b = e.target.closest("button"), s2 = room(), ui = HUB.S.ui;
      if (!b || b.disabled) return;
      const t = b.dataset.t;
      if (t === "play") { if (!ui.sel.size) return; HUB.send({ t: "play", cards: [...ui.sel] }); ui.sel.clear(); sfx("deal"); }
      else HUB.send({ t }); HUB.haptic("medium");
    };
  }
  const isMyPlay = (s) => playing(s) && s.status === "playing" && !s.game.claim && s.game.active === s.you;
  const isMyCall = (s) => playing(s) && s.status === "playing" && s.game.claim && s.game.claim.uid !== s.you && !s.game.passed.includes(s.you);
  function paintHand(s) {
    const ui = HUB.S.ui, g = s.game, hand = g.hand || [], can = isMyPlay(s);
    [...ui.sel].forEach((c) => { if (!hand.includes(c)) ui.sel.delete(c); });
    $("#blhand").innerHTML = `<div class="bl-fan">` + hand.map((c, i) => `<div class="bl-slot ${ui.sel.has(c) ? "up" : ""} ${can ? "can" : ""}" style="z-index:${i}">${face(c)}</div>`).join("") + "</div>";
    paintBtns(s);
  }
  function paintBtns(s) {
    const ui = HUB.S.ui, g = s.game, b = $("#blbtns");
    if (isMyPlay(s)) b.innerHTML = `<button class="btn primary" data-t="play" ${ui.sel.size ? "" : "disabled"}>Claim ${ui.sel.size || "…"} × ${RN[g.rank]}</button>`;
    else if (isMyCall(s)) b.innerHTML = `<button class="btn danger" data-t="bluff">🚨 BLUFF!</button><button class="btn" data-t="pass">✅ Believe</button>`;
    else b.innerHTML = "";
  }
  async function showReveal(s, ev) {
    const ui = HUB.S.ui, box = $("#blrev"); ui.busy = true;
    box.innerHTML = `<div class="bl-rcards">${ev.cards.map((c) => face(c, "flip")).join("")}</div><div class="bl-verdict ${ev.liar ? "liar" : "honest"}">${ev.liar ? "🤥 LIAR!" : "😇 HONEST!"}</div><div class="bl-sub">${esc(nm(s, ev.loser))} picks up ${ev.taken} cards</div>`;
    box.classList.add("show"); sfx("flip"); await sleep(450);
    sfx(ev.liar ? "win" : "bad"); HUB.haptic("heavy"); anim($(".bl-verdict", box), [{ transform: "scale(.3) rotate(-12deg)", opacity: 0 }, { transform: "scale(1.25) rotate(4deg)", opacity: 1 }, { transform: "none" }], { duration: 420 });
    anim(document.body, [{ transform: "translateX(0)" }, { transform: "translateX(-5px)" }, { transform: "translateX(5px)" }, { transform: "none" }], { duration: 300 });
    await sleep(1700); box.classList.remove("show"); box.innerHTML = ""; ui.busy = false;
  }
  function applyBluff(s) {
    const ui = HUB.S.ui, g = s.game, ev = g.last_event, me = playing(s);
    $("#blopps").innerHTML = g.players.filter((p) => p.uid !== s.you).map((p) => {
      const n = Math.min(p.n, 8);
      return `<div class="bl-opp ${p.uid === g.turn ? "act" : ""}"><div class="bl-ofan">${Array.from({ length: n }, (_, i) => `<i style="--i:${i};--n:${n}"></i>`).join("")}</div><div class="bl-on">${esc(nm(s, p.uid)).slice(0, 9)} · <b>${p.n}</b>${p.n <= 2 ? " 🔥" : ""}</div></div>`;
    }).join("");
    $("#blcnt").textContent = g.pile;
    $("#blpc").innerHTML = Array.from({ length: Math.min(6, Math.ceil(g.pile / 4)) }, (_, i) => `<div class="bl-c back" style="transform:rotate(${(i * 37) % 40 - 20}deg) translate(${(i * 5) % 14 - 7}px,${(i * 3) % 8}px)"></div>`).join("");
    $("#blrank").innerHTML = `Next rank: <b>${RN[g.rank]}</b>`;
    $("#blclaim").innerHTML = g.claim ? `<b>${esc(nm(s, g.claim.uid))}</b> claims <b>${g.claim.n} × ${RN[g.claim.rank]}</b> 🃏` : (g.turn ? `${esc(nm(s, g.turn))} to play…` : "");
    if (ui.first) { ui.first = false; if (ev) ui.lastSeq = ev.seq; }
    else if (ev && ev.seq > ui.lastSeq) {
      ui.lastSeq = ev.seq;
      if (ev.e === "claim") { sfx("deal"); anim($("#blpile"), [{ transform: "scale(1)" }, { transform: "scale(1.12)" }, { transform: "none" }], { duration: 260 }); }
      else if (ev.e === "bluff") showReveal(s, ev);
      else if (ev.e === "accept") sfx("place");
    }
    if (g.turn === s.you && me && s.status === "playing") { if (ui.turnSeq !== (ev && ev.seq)) { ui.turnSeq = ev && ev.seq; sfx("turn"); } }
    paintHand(s);
    $("#blhand").classList.toggle("hidden", !me);
    K().updateBar(ui, s, (uid) => ({ score: "🂠" + g.players.find((p) => p.uid === uid).n }));
    K().setHint(me ? (isMyPlay(s) ? `Pick 1-4 cards and claim they are ${RN[g.rank]} — lie if you must!` : isMyCall(s) ? "Do you believe it? Call BLUFF to check!" : "Waiting…") : "👀 Watching");
  }
  HUB.UI.bluff = { build: buildBluff, apply: applyBluff };

  /* ================================ COIN FLIP / DICE DUEL (betting) ================================ */
  const DIE = ["", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"];
  function buildDuel(kind) {
    return function (s) {
      K().newUI(kind, s, { lastSeq: 0, myPick: null, busy: false });
      const coin = kind === "coinduel";
      K().shell(s, `<div class="du-box"><div class="du-round" id="duround"></div>
        <div class="du-stage" id="dustage">${coin ? '<div class="du-coin" id="ducoin"><b>H</b></div><div class="du-coin two" id="ducoin2"><b>T</b></div>' : '<div class="du-die" id="dudie1">🎲</div><div class="du-vs">VS</div><div class="du-die" id="dudie2">🎲</div>'}</div>
        <div class="du-msg" id="dumsg"></div>
        <div class="du-pad" id="dupad">${coin ? '<button data-s="heads">🪙<b>HEADS</b></button><button data-s="tails">🪙<b>TAILS</b></button>' : '<button data-r="1" class="roll">🎲<b>ROLL</b></button>'}</div></div>`);
      $("#dupad").onclick = (e) => {
        const b = e.target.closest("button"), s2 = room(), ui = HUB.S.ui;
        if (!b || b.disabled || ui.busy || !playing(s2) || s2.status !== "playing" || s2.game.picked[s2.you]) return;
        ui.myPick = b.dataset.s || "roll";
        HUB.send(coin ? { t: "call", side: b.dataset.s } : { t: "roll" }); HUB.haptic("medium"); sfx("pop");
        document.querySelectorAll("#dupad button").forEach((x) => x.classList.toggle("sel", x === b));
        $("#dumsg").textContent = "Locked in — waiting for your opponent…";
      };
    };
  }
  async function duelReveal(s, lr, coin) {
    const ui = HUB.S.ui; ui.busy = true;
    const ids = s.game.players.map((p) => p.uid), me = ids.includes(s.you);
    const mine = me ? s.you : ids[0], other = ids.find((u) => u !== mine);
    const msg = $("#dumsg");
    msg.textContent = coin ? "Flipping…" : "Rolling…";
    if (coin) {
      const c = $("#ducoin");
      c.querySelector("b").textContent = "?";
      anim(c, [{ transform: "translateY(0) rotateY(0)" }, { transform: "translateY(-120px) rotateY(900deg)" }, { transform: "translateY(0) rotateY(1800deg)" }], { duration: 1100, easing: "ease-out" });
      for (let i = 0; i < 5; i++) { tone(500 + i * 70, 0.06, "triangle", 0.1); await sleep(200); }
      c.querySelector("b").textContent = lr.coin === "heads" ? "H" : "T"; c.classList.toggle("tails", lr.coin === "tails");
      sfx("hit");
      msg.textContent = `It's ${lr.coin.toUpperCase()}! You called ${lr.picks[mine]}, ${nm(s, other)} called ${lr.picks[other]}.`;
    } else {
      const d1 = $("#dudie1"), d2 = $("#dudie2");
      for (let i = 0; i < 8; i++) {
        d1.textContent = DIE[1 + Math.floor(Math.random() * 6)]; d2.textContent = DIE[1 + Math.floor(Math.random() * 6)];
        anim(d1, [{ transform: "rotate(-25deg)" }, { transform: "rotate(25deg)" }], { duration: 110 }); anim(d2, [{ transform: "rotate(25deg)" }, { transform: "rotate(-25deg)" }], { duration: 110 });
        tone(280 + i * 30, 0.05, "square", 0.08); await sleep(120);
      }
      d1.textContent = DIE[lr.dice[mine]]; d2.textContent = DIE[lr.dice[other]];
      anim(d1, [{ transform: "scale(1.5)" }, { transform: "none" }], { duration: 300 }); anim(d2, [{ transform: "scale(1.5)" }, { transform: "none" }], { duration: 300 });
      sfx("hit");
    }
    const v = lr.winner == null ? "🤝 Tie — go again" : lr.winner === s.you ? "🎉 You win the round!" : (me ? nm(s, lr.winner) + " wins the round" : nm(s, lr.winner) + " wins the round");
    msg.textContent += " " + v; msg.classList.add("pulse");
    if (lr.winner === s.you) { sfx("win"); HUB.haptic("success"); }
    await sleep(1500); msg.classList.remove("pulse"); ui.busy = false;
    document.querySelectorAll("#dupad button").forEach((x) => x.classList.remove("sel"));
  }
  function applyDuel(coin) {
    return function (s) {
      const ui = HUB.S.ui, g = s.game, lr = g.last_round, me = playing(s);
      $("#duround").textContent = `Round ${Math.min(g.round, 9)} · first to ${g.win_score} wins`;
      if (ui.first) { ui.first = false; if (lr) ui.lastSeq = lr.seq; }
      else if (lr && lr.seq > ui.lastSeq) { ui.lastSeq = lr.seq; duelReveal(s, lr, coin); }
      const ok = me && s.status === "playing" && !g.picked[s.you];
      if (ok && !ui.busy) { $("#dumsg").textContent = coin ? "Call it: heads or tails?" : "Tap ROLL — highest die wins the round!"; }
      document.querySelectorAll("#dupad button").forEach((b) => { b.disabled = !ok; });
      $("#dupad").classList.toggle("hidden", !me);
      K().updateBar(ui, s, (uid) => ({ score: g.players.find((p) => p.uid === uid).score + "/" + g.win_score }));
      K().setHint(me ? "Server-side flip: nobody can cheat" : "👀 Watching the duel");
    };
  }
  HUB.UI.coinduel = { build: buildDuel("coinduel"), apply: applyDuel(true) };
  HUB.UI.diceduel = { build: buildDuel("diceduel"), apply: applyDuel(false) };
})();

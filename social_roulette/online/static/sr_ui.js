/* Social Roulette — pure visual layer. No WebSocket, no bootstrap, no load-time
 * side effects. render() draws the BOARD (seats laid out in TURN ORDER); #controls
 * (verb bar + tap-to-target) are owned by index.html glue.
 *   SRUI.render(root, view) / setTargets / clearTargets
 *   SRUI.playEvents(root, events, view)   slow, labelled cascade, then settle
 *   SRUI.setup(root, view) / decoder / toast(root, text, hold) / announce(root, e) */
(function (global) {
  "use strict";
  const bit = () => (Math.random() < 0.5 ? "0" : "1");
  const el = (root, id) => root.querySelector("#" + id);
  let _skip = false, _tt = null;
  const wait = (ms) => new Promise((res) => (_skip || ms <= 0 ? res() : setTimeout(res, ms)));

  function decoder(node, text, opts) {
    opts = opts || {};
    const dur = opts.dur || 750, cursor = opts.cursor !== false;
    const n = text.length, t0 = performance.now(), rt = [];
    [...Array(n).keys()].filter((i) => text[i] !== " ")
      .forEach((i, k, arr) => (rt[i] = k / arr.length));
    node.classList.add("fx");
    return new Promise((resolve) => {
      (function tick(t) {
        const p = (t - t0) / dur; let html = "", edge = true;
        for (let i = 0; i < n; i++) {
          if (text[i] === " ") { html += " "; continue; }
          if (p >= rt[i] + 0.05) html += text[i];
          else if (cursor && edge) { html += '<span class="cur">█</span>'; edge = false; }
          else html += '<span class="n">' + bit() + "</span>";
        }
        node.innerHTML = html;
        if (p < 1.15) requestAnimationFrame(tick);
        else { node.textContent = text; resolve(); }
      })(t0);
    });
  }

  function seatPos(n, i) {
    const th = (-90 + i * (360 / n)) * (Math.PI / 180);
    return { left: 50 + 40 * Math.cos(th), top: 50 + 40 * Math.sin(th), deg: -90 + i * (360 / n) };
  }
  const form = (team) => (team === "RED" ? "filled" : "hollow");

  /* turn-dot glides to `seat`'s RING position (order index → adjacent seats advance in order) */
  function dotTo(root, order, seat) {
    const arm = el(root, "dotarm"), i = order.indexOf(seat);
    if (arm && i >= 0) arm.style.transform = "rotate(" + seatPos(order.length, i).deg + "deg)";
  }

  function render(root, v) {
    const order = v.order || v.players.map((p) => p.id), n = order.length;
    el(root, "seats").innerHTML = v.players.map((p) => {
      const pos = seatPos(n, order.indexOf(p.id));
      const cls = ["seat", p.id === v.current ? "current" : "", p.id === v.you ? "me" : "", p.alive ? "" : "dead"].join(" ").trim();
      const pips = Array.from({ length: Math.max(0, p.lives) }, () => "<i></i>").join("");
      const imm = (p.immune_from || []).map((c) => `<span class="immtag">P${c}<b>M</b></span>`).join("");
      return `<div class="${cls}" data-seat="${p.id}" style="left:${pos.left}%;top:${pos.top}%">
        <div class="imm">${imm}</div>
        <div class="badge"><div class="form ${form(p.team)}"></div><div class="x">✕</div></div>
        <div class="name">P${p.id}</div><div class="pips">${pips}</div>
        ${p.handcuffed ? '<div class="held">HELD</div>' : ""}</div>`;
    }).join("");
    dotTo(root, order, v.current);
    const items = Object.entries(v.your_hand || {}).filter(([, c]) => c > 0);
    el(root, "hand").innerHTML = items.length
      ? items.map(([t, c]) => `<div class="card"><div class="t">${t}</div><div class="c">${c}</div></div>`).join("")
      : '<div class="card empty">NO ITEMS</div>';
    el(root, "peek").textContent = v.peek && v.peek !== "unknown" ? `NEXT SHELL: ${v.peek.toUpperCase()}` : "";
    const turn = el(root, "turn"), label = v.winner != null ? "" : (v.current === v.you ? "YOUR TURN" : `P${v.current}'S TURN`);
    if (turn.dataset.label !== label) { turn.dataset.label = label; if (label) decoder(turn, label, { dur: 620 }); else turn.textContent = ""; }
  }

  function clearTargets(root) { root.querySelectorAll(".seat.selectable").forEach((s) => s.classList.remove("selectable")); }
  function setTargets(root, ids) {
    clearTargets(root);
    ids.forEach((id) => { const s = root.querySelector(`.seat[data-seat="${id}"]`); if (s) s.classList.add("selectable"); });
  }

  /* JS-timed toast so each message can HOLD for a chosen duration (announce = 5s) */
  function toast(root, text, hold) {
    const t = el(root, "toast");
    clearTimeout(_tt);
    t.style.transition = "none"; t.style.opacity = "1";
    decoder(t, text, { dur: 440 });
    _tt = setTimeout(() => { t.style.transition = "opacity .6s"; t.style.opacity = "0"; }, hold || 1500);
  }
  const announce = (root, e) => toast(root, `${e.total} SHELLS · ${e.live} LIVE`, 5000);

  /* SLOW, LABELLED, IN-ORDER cascade so a human can follow who did what after their shot */
  const DUR = { shot: 1500, item: 1200, elimination: 1400, reload: 1700, flip: 1200, announce: 5000 };
  const BEAT = 450;
  async function playEvents(root, events, endView) {
    _skip = false; events = events || [];
    const order = (endView && endView.order) || (endView && endView.players.map((p) => p.id)) || [0, 1, 2, 3, 4];
    for (const e of events) {
      if (e.type === "announce" || e.type === "reload") { toast(root, `${e.total} SHELLS · ${e.live} LIVE`, DUR.announce); await wait(DUR.announce); }
      else if (e.type === "shot") {
        dotTo(root, order, e.actor); await wait(340);              // dot glides to the shooter first
        const live = e.shell === "LIVE", center = el(root, "center");
        const tgt = e.actor === e.target ? "SELF" : `P${e.target}`;
        toast(root, `P${e.actor} → ${tgt} · ${live ? "BANG" : "CLICK"}`, DUR.shot);
        if (live) {
          const f = el(root, "flash"); f.classList.remove("bang"); void f.offsetWidth; f.classList.add("bang");
          center.classList.remove("recoil"); void center.offsetWidth; center.classList.add("recoil");
        } else { center.classList.remove("shudder"); void center.offsetWidth; center.classList.add("shudder"); }
        await wait(DUR.shot);
      }
      else if (e.type === "item") {
        dotTo(root, order, e.actor);
        toast(root, `P${e.actor} · ${e.item}${e.target != null ? " → P" + e.target : ""}`, DUR.item);
        await wait(DUR.item);
      }
      else if (e.type === "elimination") {
        const s = root.querySelector(`.seat[data-seat="${e.target}"]`); if (s) s.classList.add("dying");
        toast(root, `P${e.target} OUT`, DUR.elimination); await wait(DUR.elimination);
      }
      else if (e.type === "flip") { toast(root, `P${e.actor} FLIP P${e.target}`, DUR.flip); await wait(DUR.flip); }
      await wait(BEAT);
    }
    if (endView) render(root, endView);
  }

  async function setup(root, v) {
    const table = el(root, "table"); table.style.opacity = "0";
    render(root, v);
    const seats = [...root.querySelectorAll(".seat")], cards = [...root.querySelectorAll("#hand .card")];
    const dial = el(root, "dial"), arm = el(root, "dotarm");
    [...seats, ...cards, dial, arm].forEach((n) => n && (n.style.opacity = "0"));
    const turn = el(root, "turn");
    table.style.transition = "opacity .4s"; table.style.opacity = "1";
    await decoder(turn, "ASSIGNING TEAMS", { dur: 520 });
    for (const s of seats) { s.style.transition = "opacity .25s"; s.style.opacity = "1"; await wait(90); }
    await decoder(turn, "LOADING CHAMBER", { dur: 520 });
    [dial, arm].forEach((x) => x && (x.style.transition = "opacity .4s", x.style.opacity = "1"));
    await wait(340);
    await decoder(turn, "DEALING", { dur: 420 });
    for (const c of cards) { c.style.transition = "opacity .2s"; c.style.opacity = "1"; await wait(110); }
    await wait(160); turn.dataset.label = ""; render(root, v);
  }

  global.SRUI = { render, setTargets, clearTargets, playEvents, setup, decoder, toast, announce, skip: () => (_skip = true), seatPos };
  if (typeof module !== "undefined" && module.exports) module.exports = global.SRUI;
})(typeof window !== "undefined" ? window : globalThis);

/* Social Roulette — pure visual layer. No WebSocket, no bootstrap, no load-time
 * side effects. render() draws the BOARD; #controls (verb bar + tap-to-target)
 * are owned by index.html glue.
 *   SRUI.render(root, view)               redraw board
 *   SRUI.setTargets(root, ids)/clearTargets(root)
 *   SRUI.playEvents(root, events, view)   animate deltas (slow, labelled), settle
 *   SRUI.setup(root, view)                opening animation
 *   SRUI.decoder(el, text, opts)/toast(root, text)/announce(root, e) */
(function (global) {
  "use strict";
  const bit = () => (Math.random() < 0.5 ? "0" : "1");
  const el = (root, id) => root.querySelector("#" + id);
  let _skip = false;
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

  /* the central turn-dot glides to `seat`'s angle (replaces the old barrel arrow) */
  function dotTo(root, n, seat) {
    const arm = el(root, "dotarm");
    if (arm) arm.style.transform = "rotate(" + seatPos(n, seat).deg + "deg)";
  }

  function render(root, v) {
    const n = v.players.length;
    el(root, "seats").innerHTML = v.players.map((p) => {
      const pos = seatPos(n, p.id);
      const cls = ["seat", p.id === v.current ? "current" : "", p.id === v.you ? "me" : "", p.alive ? "" : "dead"].join(" ").trim();
      const pips = Array.from({ length: Math.max(0, p.lives) }, () => "<i></i>").join("");
      // immunity markers above the head: "P3M" over P1 = P3 put immunity on P1 (P1 can't shoot P3)
      const imm = (p.immune_from || []).map((c) => `<span class="immtag">P${c}<b>M</b></span>`).join("");
      return `<div class="${cls}" data-seat="${p.id}" style="left:${pos.left}%;top:${pos.top}%">
        <div class="imm">${imm}</div>
        <div class="badge"><div class="form ${form(p.team)}"></div><div class="x">✕</div></div>
        <div class="name">P${p.id}</div><div class="pips">${pips}</div>
        ${p.handcuffed ? '<div class="held">HELD</div>' : ""}</div>`;
    }).join("");
    dotTo(root, n, v.current);
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

  function toast(root, text) {
    const t = el(root, "toast");
    t.classList.remove("show"); void t.offsetWidth; t.classList.add("show");
    decoder(t, text, { dur: 440 });
  }
  const announce = (root, e) => toast(root, `${e.total} SHELLS · ${e.live} LIVE`);

  /* SLOW, LABELLED cascade so a human can read who shot whom (user: "make it slower") */
  const DUR = { shot: 850, elimination: 720, reload: 900, flip: 650, announce: 1100 };
  const BEAT = 150;
  async function playEvents(root, events, endView) {
    _skip = false; events = events || [];
    const n = (endView && endView.players.length) || root.querySelectorAll(".seat").length || 5;
    for (const e of events) {
      if (e.type === "announce" || e.type === "reload") { announce(root, e); await wait(DUR.announce); }
      else if (e.type === "shot") {
        dotTo(root, n, e.actor); await wait(260);                 // dot glides to the acting player first
        const live = e.shell === "LIVE", center = el(root, "center");
        const tgt = e.actor === e.target ? "SELF" : `P${e.target}`;
        toast(root, `P${e.actor} → ${tgt} · ${live ? "BANG" : "CLICK"}`);
        if (live) {
          const f = el(root, "flash"); f.classList.remove("bang"); void f.offsetWidth; f.classList.add("bang");
          center.classList.remove("recoil"); void center.offsetWidth; center.classList.add("recoil");
        } else { center.classList.remove("shudder"); void center.offsetWidth; center.classList.add("shudder"); }
        await wait(DUR.shot);
      }
      else if (e.type === "elimination") {
        const s = root.querySelector(`.seat[data-seat="${e.target}"]`); if (s) s.classList.add("dying");
        toast(root, `P${e.target} OUT`); await wait(DUR.elimination);
      }
      else if (e.type === "flip") { toast(root, `FLIP P${e.target}`); await wait(DUR.flip); }
      await wait(BEAT);                                            // a readable beat between actions
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
    await decoder(turn, "ASSIGNING TEAMS", { dur: 500 });
    for (const s of seats) { s.style.transition = "opacity .25s"; s.style.opacity = "1"; await wait(80); }
    await decoder(turn, "LOADING CHAMBER", { dur: 500 });
    [dial, arm].forEach((x) => x && (x.style.transition = "opacity .4s", x.style.opacity = "1"));
    await wait(320);
    await decoder(turn, "DEALING", { dur: 400 });
    for (const c of cards) { c.style.transition = "opacity .2s"; c.style.opacity = "1"; await wait(100); }
    await wait(140); turn.dataset.label = ""; render(root, v);
  }

  global.SRUI = { render, setTargets, clearTargets, playEvents, setup, decoder, toast, announce, skip: () => (_skip = true), seatPos };
  if (typeof module !== "undefined" && module.exports) module.exports = global.SRUI;
})(typeof window !== "undefined" ? window : globalThis);

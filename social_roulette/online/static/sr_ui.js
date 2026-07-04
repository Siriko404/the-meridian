/* Social Roulette — pure visual layer. No WebSocket, no bootstrap, no load-time
 * side effects. render() draws the BOARD only (seats/gun/hand/peek/turn); the
 * #controls (verb bar + tap-to-target) are owned by index.html glue, because
 * targeting is interaction state, not a function of the view.
 *   SRUI.render(root, view)               redraw board
 *   SRUI.setTargets(root, ids) / clearTargets(root)   highlight tappable seats
 *   SRUI.playEvents(root, events, view)   animate deltas, then settle board
 *   SRUI.setup(root, view)                opening animation
 *   SRUI.decoder(el, text, opts) / toast(root, text) */
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
  function barrelTo(root, n, seat) {
    const b = el(root, "barrel"); if (b) b.style.transform = "rotate(" + seatPos(n, seat).deg + "deg)";
  }

  /* draw the BOARD (never #controls) */
  function render(root, v) {
    const n = v.players.length;
    el(root, "seats").innerHTML = v.players.map((p) => {
      const pos = seatPos(n, p.id);
      const cls = ["seat", p.id === v.current ? "current" : "", p.id === v.you ? "me" : "", p.alive ? "" : "dead"].join(" ").trim();
      const pips = Array.from({ length: Math.max(0, p.lives) }, () => "<i></i>").join("");
      return `<div class="${cls}" data-seat="${p.id}" style="left:${pos.left}%;top:${pos.top}%">
        <div class="badge"><div class="form ${form(p.team)}"></div><div class="x">✕</div></div>
        <div class="name">P${p.id}</div><div class="pips">${pips}</div>
        ${p.handcuffed ? '<div class="held">HELD</div>' : ""}</div>`;
    }).join("");
    barrelTo(root, n, v.current);
    const total = v.chamber.total || 0, fired = v.chamber.fired || 0;
    let holes = "";
    for (let i = 0; i < total; i++) {
      const th = (-90 + i * (360 / total)) * (Math.PI / 180);
      holes += `<div class="hole ${i < fired ? "fired" : ""}" style="left:${50 + 40 * Math.cos(th)}%;top:${50 + 40 * Math.sin(th)}%"></div>`;
    }
    el(root, "cylinder").innerHTML = holes;
    el(root, "readout").textContent = `${fired}/${total} · ${v.chamber.live} LIVE`;
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

  async function toast(root, text) {
    const t = el(root, "toast");
    t.classList.remove("show"); void t.offsetWidth; t.classList.add("show");
    decoder(t, text, { dur: 460 });
  }

  const DUR = { shot: 460, elimination: 520, reload: 520, flip: 320 };
  async function playEvents(root, events, endView) {
    _skip = false; events = events || [];
    const n = (endView && endView.players.length) || root.querySelectorAll(".seat").length || 5;
    const want = events.filter((e) => DUR[e.type]).reduce((s, e) => s + DUR[e.type], 0);
    const speed = want > 2800 ? 2800 / want : 1;
    for (const e of events) {
      if (e.type === "shot") {
        barrelTo(root, n, e.actor); await wait(120 * speed);
        const live = e.shell === "LIVE", center = el(root, "center");
        if (live) {
          const f = el(root, "flash"); f.classList.remove("bang"); void f.offsetWidth; f.classList.add("bang");
          center.classList.remove("recoil"); void center.offsetWidth; center.classList.add("recoil");
        } else { center.classList.remove("shudder"); void center.offsetWidth; center.classList.add("shudder"); }
        await wait((live ? 340 : 300) * speed);
      } else if (e.type === "elimination") {
        const s = root.querySelector(`.seat[data-seat="${e.target}"]`); if (s) s.classList.add("dying");
        toast(root, `P${e.target} OUT`); await wait(DUR.elimination * speed);
      } else if (e.type === "reload") { toast(root, "RELOAD"); await wait(DUR.reload * speed); }
      else if (e.type === "flip") { toast(root, `FLIP P${e.target}`); await wait(DUR.flip * speed); }
    }
    if (endView) render(root, endView);
  }

  async function setup(root, v) {
    const table = el(root, "table"); table.style.opacity = "0";
    render(root, v);
    const seats = [...root.querySelectorAll(".seat")], holes = [...root.querySelectorAll("#cylinder .hole")], cards = [...root.querySelectorAll("#hand .card")];
    [...seats, ...holes, ...cards].forEach((n) => (n.style.opacity = "0"));
    const turn = el(root, "turn");
    table.style.transition = "opacity .4s"; table.style.opacity = "1";
    await decoder(turn, "ASSIGNING TEAMS", { dur: 500 });
    for (const s of seats) { s.style.transition = "opacity .25s"; s.style.opacity = "1"; await wait(80); }
    await decoder(turn, "LOADING CHAMBER", { dur: 500 });
    for (const h of holes) { h.style.transition = "opacity .1s"; h.style.opacity = "1"; await wait(55); }
    await decoder(turn, "DEALING", { dur: 400 });
    for (const c of cards) { c.style.transition = "opacity .2s"; c.style.opacity = "1"; await wait(100); }
    await wait(140); turn.dataset.label = ""; render(root, v);
  }

  global.SRUI = { render, setTargets, clearTargets, playEvents, setup, decoder, toast, skip: () => (_skip = true), seatPos };
  if (typeof module !== "undefined" && module.exports) module.exports = global.SRUI;
})(typeof window !== "undefined" ? window : globalThis);

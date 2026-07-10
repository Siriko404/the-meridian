/* DEV-ONLY monkey driver — loaded by index.html ONLY with ?bot=1 (never in normal play).
 * Auto-joins (?code=&tag=), host-starts (?start=1), then plays the thread UI semantically:
 * armed rows ("trow"), seat targets ("tgt"), pick-cancel/abort/back, and the dock hubs.
 * Posts canvas frames + console errors to the _devcap sink so Claude can review the run. */
(function () {
  "use strict";
  const P = new URLSearchParams(location.search);
  if (!P.get("bot")) return;
  const $ = (id) => document.getElementById(id);
  const TAG = (P.get("tag") || "ZZ").toUpperCase();
  const SINK = "http://localhost:8017/cap";
  const errs = [];
  window.addEventListener("error", (e) => errs.push(e.message + " @ " + e.filename + ":" + e.lineno));
  const post = (body) => fetch(SINK, { method: "POST",
    headers: { "content-type": "application/json" }, body: JSON.stringify(body) }).catch(() => {});

  localStorage.removeItem("meridian_token");                   // always a fresh seat
  setTimeout(() => {                                           // join
    $("name").value = TAG[0]; $("lastinit").value = TAG[1] || "Z";
    $("code").value = P.get("code") || "BOTGAME";
    $("enterbtn").click();
  }, 800);
  if (P.get("start")) {
    const t0 = Date.now();
    const iv = setInterval(() => {                             // host: wait for the 2nd human, then start
      const b = $("startbtn");
      const two = document.querySelectorAll("#members .member").length >= 2;
      if (b && b.style.display !== "none" && (two || Date.now() - t0 > 15000)) {
        clearInterval(iv); b.click();
      }
    }, 500);
  }

  setInterval(() => {                                          // headless tabs: rAF is DEAD — pump the loop
    const g = window.__game;
    if (g && g.loop && performance.now() - g.loop.now > 100) g.loop.step(performance.now());
  }, 33);

  const rand = (a) => a[(Math.random() * a.length) | 0];
  setInterval(() => {                                          // the monkey
    const s = window.__scene;
    if (!s || !s.built) return;
    const rows = [], meta = [];
    s.children.list.forEach((o) => {
      if (!o.input || !o.input.enabled || !o.visible) return;
      if (o.name === "trow" || o.name === "tgt") rows.push(o);
      else if (o.name === "tcxl" || o.name === "tabort" || o.name === "tback") meta.push(o);
    });
    if (rows.length && Math.random() < 0.88) rand(rows).emit("pointerdown");
    else if (meta.length && Math.random() < 0.4) rand(meta).emit("pointerdown");
    else if (!s._thread) {
      const r = Math.random();
      if (r < 0.75 && s.onAction) s.onAction();                // YOUR MOVE / respond
      else if (r < 0.88 && s.onLedger) s.onLedger();
      else if (s.onKit) s.onKit();
    }
  }, 650);

  /* film as 3x2 CONTACT SHEETS (like the capture rig) — not a hail of single frames */
  const TW = 390, TH = 844, COLS = 3, ROWS = 2, PER = COLS * ROWS;
  let shots = 0, page = 0, fill = 0, sheet = null, sctx = null;
  const flush = () => {
    if (!sctx) return;
    post({ name: TAG + "_live_s" + (++page), img: sheet.toDataURL("image/jpeg", 0.8) });
    sheet = null; sctx = null; fill = 0;
  };
  setInterval(() => {
    const c = document.querySelector("canvas");
    if (!c || shots >= 60) return;
    if (!sctx) {
      sheet = document.createElement("canvas");
      sheet.width = TW * COLS; sheet.height = TH * ROWS;
      sctx = sheet.getContext("2d");
      sctx.fillStyle = "#222"; sctx.fillRect(0, 0, sheet.width, sheet.height);
    }
    const k = fill++, x = (k % COLS) * TW, y = ((k / COLS) | 0) * TH;
    sctx.drawImage(c, 0, 0, c.width, c.height, x, y, TW, TH);
    sctx.fillStyle = "#0f0"; sctx.font = "bold 22px monospace";
    sctx.fillText(String(++shots), x + 6, y + 24);
    if (shots % PER === 0) flush();
  }, 4000);
  setInterval(flush, 40000);                                   // partial sheet safety-flush
  setInterval(() => post({ name: TAG + "_errors",
    txt: errs.length ? errs.join("\n") : "NO ERRORS · shots=" + shots }), 15000);
})();

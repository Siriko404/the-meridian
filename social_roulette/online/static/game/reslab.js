/* RESLAB — the sharpness A/B the user locks FROM HIS PHONE.
 * The 390×844 canvas stretched over a 3× phone screen is what mushed the text
 * (friend's report, 2026-07-11). Each variant renders the SAME busy screen at a
 * different backing resolution: the canvas grows to W*DPR × H*DPR and the camera
 * zooms by DPR, so every layout coordinate stays untouched. Marching ants + the
 * burning band supply real render load; the FPS meter tells the truth.
 * Variants: DPR 1 (today) · 2 · 3 · DEVICE (exact ratio) — each in CANVAS or WEBGL. */
(function () {
  "use strict";
  const Q = new URLSearchParams(location.search);
  const DEV = window.devicePixelRatio || 1;
  const DPR = Q.get("dpr") === "dev" ? DEV : Math.max(1, parseInt(Q.get("dpr") || "1", 10) || 1);
  const GL = !!Q.get("webgl");

  /* switcher bar */
  const bar = document.getElementById("bar");
  const opts = [["1", "1×"], ["2", "2×"], ["3", "3×"], ["dev", "DEV " + DEV.toFixed(2) + "×"]];
  opts.forEach(([v, label]) => {
    const a = document.createElement("a");
    a.textContent = label;
    a.href = "?dpr=" + v + (GL ? "&webgl=1" : "");
    if ((Q.get("dpr") || "1") === v) a.className = "on";
    bar.appendChild(a);
  });
  const g = document.createElement("a");
  g.textContent = GL ? "WEBGL" : "CANVAS";
  g.href = "?dpr=" + (Q.get("dpr") || "1") + (GL ? "" : "&webgl=1");
  g.style.marginLeft = "10px";
  bar.appendChild(g);

  /* text sharpness must follow the backing store: every scene text hardcodes
   * setResolution(2) — clamp it up to DPR here, without touching scene.js */
  const origRes = Phaser.GameObjects.Text.prototype.setResolution;
  Phaser.GameObjects.Text.prototype.setResolution = function (r) {
    return origRes.call(this, Math.max(r || 1, DPR));
  };

  const BASE = () => ({
    you: 0, order: [0, 1, 2, 3, 4], current: 3, winner: null, gen: 1,
    phase: "decision", phase_ends_at: null, server_now: 0, bonus: false, extra_turn: false,
    poison_armed: false, teams_active: true, flipback_discount: false,
    use_counts: {}, use_limit: 5, feed: [],
    players: [
      { id: 0, team: "RED",  cover: 3, alive: true, shaken: false, immune_from: [] },
      { id: 1, team: "BLUE", cover: 3, alive: true, shaken: false, immune_from: [] },
      { id: 2, team: "RED",  cover: 2, alive: true, shaken: true,  immune_from: [3] },
      { id: 3, team: "BLUE", cover: 3, alive: true, shaken: false, immune_from: [] },
      { id: 4, team: "RED",  cover: 1, alive: true, shaken: false, immune_from: [] },
    ],
    your_hand: { MAGNET: 1, GEIGER: 1, PASSPORT: 1 },
    your_specials: { WARRANT: 1, DRAGNET: 1, HANDLER: 1 },
    item_counts: { MAGNET: 3, SHAKEDOWN: 2, GEIGER: 2, POISON: 1, PASSPORT: 3, TERMS: 2 },
    special_counts: { WARRANT: 5, DRAGNET: 4, HANDLER: 5 },
    scan: { live: 1, of: 2 },
  });
  const ROSTER = { "0": "you" };
  const ORDER = ["MAGNET", "SHAKEDOWN", "GEIGER", "POISON", "PASSPORT", "TERMS"];

  /* the SAME dense screen every variant shows: kit sheet (small subs), crumb,
   * red ants marching on every seat, band burning — worst-case text + motion */
  function sample(s) {
    s.render(BASE(), ROSTER);
    let secs = 22;
    s.setBand({ phase: "decision", secs, name: THEME.seatName(3, ROSTER), invert: true });
    s.time.addEvent({ delay: 1000, loop: true, callback: () => {
      secs = secs > 0 ? secs - 1 : 22;
      s.setBand({ phase: "decision", secs, name: THEME.seatName(3, ROSTER), invert: true });
    } });
    s.seatGlow([0, 1, 2, 4], true, null, 0xc8102e);          // constant motion = honest FPS
    const th = s.openThread({ mode: "fade", anim: "decode", title: "RESLAB · DPR " +
      (Q.get("dpr") || "1") + " · " + (GL ? "WEBGL" : "CANVAS") });
    const rows = ORDER.map((en) => ({ label: THEME.ITEMS[en].name, badge: "×1",
      sub: THEME.ITEMS[en].blurb, bright: true }));
    rows.push({ dot: true }, { label: "SPECIALS", badge: "×3",
      sub: "ONE-SHOT POWERS — NOT CURRENCY, NEVER FINED", bright: true });
    th.list("KIT", "YOUR KIT · 3/" + THEME.MAX_TOTAL, rows);
  }

  /* FPS meter — rolling second */
  const hud = document.getElementById("hud");
  let frames = 0, t0 = performance.now();
  function meter() {
    frames++;
    const now = performance.now();
    if (now - t0 >= 1000) {
      hud.textContent = "DPR " + (Q.get("dpr") || "1") + " · " + (GL ? "WEBGL" : "CANVAS") +
        " · " + frames + " FPS · screen " + Math.round(390 * DEV) + "px wide";
      frames = 0; t0 = now;
    }
    requestAnimationFrame(meter);
  }
  requestAnimationFrame(meter);

  SCENE.ready = (s) => {
    window.__scene = s;
    const cam = s.cameras.main;
    if (DPR !== 1) { cam.setZoom(DPR); cam.centerOn(SCENE.W / 2, SCENE.H / 2); }
    sample(s);
    console.log("RESLAB OK · dpr=" + DPR + " gl=" + GL);
  };
  new Phaser.Game({
    type: GL ? Phaser.AUTO : Phaser.CANVAS, parent: "stage",
    width: Math.round(SCENE.W * DPR), height: Math.round(SCENE.H * DPR),
    backgroundColor: "#000000", pixelArt: true,
    scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
    scene: SCENE.TableScene,
  });
})();

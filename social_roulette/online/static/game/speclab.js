/* SPECLAB — every step of WARRANT / DRAGNET / HANDLER, from every chair.
 * Sheets replicate main.js row structures VERBATIM so what you ratify here is
 * what ships. Tap = next step. window.__lab.go(n) jumps (screenshot rig).
 * View: http://127.0.0.1:8000/static/game/speclab.html */
(function () {
  "use strict";
  const hud = document.getElementById("hud");
  const BASE = () => ({
    you: 0, order: [0, 1, 2, 3, 4], current: 0, winner: null, gen: 1,
    phase: "talk", phase_ends_at: null, server_now: 0, bonus: false, extra_turn: false,
    poison_armed: false, teams_active: true, flipback_discount: false,
    use_counts: {}, use_limit: 5, feed: [],
    players: [
      { id: 0, team: "RED",  cover: 3, alive: true, shaken: false, immune_from: [] },
      { id: 1, team: "BLUE", cover: 3, alive: true, shaken: false, immune_from: [] },
      { id: 2, team: "RED",  cover: 2, alive: true, shaken: false, immune_from: [3] },
      { id: 3, team: "BLUE", cover: 3, alive: true, shaken: false, immune_from: [] },
      { id: 4, team: "RED",  cover: 1, alive: true, shaken: false, immune_from: [] },
    ],
    your_hand: { MAGNET: 1, GEIGER: 1, PASSPORT: 1 },
    your_specials: { WARRANT: 1, DRAGNET: 1, HANDLER: 1 },
    item_counts: { MAGNET: 3, SHAKEDOWN: 2, GEIGER: 2, POISON: 1, PASSPORT: 3, TERMS: 2 },
    special_counts: { WARRANT: 5, DRAGNET: 4, HANDLER: 5 },
    scan: null,
  });
  const ROSTER = { "0": "you" };
  const ORDER = ["MAGNET", "SHAKEDOWN", "GEIGER", "POISON", "PASSPORT", "TERMS"];
  const iname = (en) => THEME.ITEMS[en].name;
  const wait = (s, ms) => new Promise((r) => s.time.delayedCall(ms, r));

  function openTh(s, title, abortLabel) {
    return s.openThread({ mode: "fade", anim: "decode", title, abortLabel: abortLabel || "✕ ABORT" });
  }

  /* ---- the KIT sheet exactly as main.js builds it (items + specials section) ---- */
  function kitSheet(s, v) {
    const th = openTh(s, "YOUR MOVE");
    const rows = ORDER.map((en) => {
      const n = (v.your_hand || {})[en] || 0;
      const ok = n > 0;
      return { en, label: iname(en), badge: "×" + n,
        sub: THEME.ITEMS[en].blurb, bright: ok, dim: !ok };
    });
    rows.push({ dot: true },
      { label: "SPECIALS", badge: "×3", sub: "ONE-SHOT POWERS — NOT CURRENCY, NEVER FINED",
        bright: true });
    th.list("KIT", "YOUR KIT · 3/" + THEME.MAX_TOTAL, rows);
    return th;
  }
  function specialsSheet(s) {
    const th = openTh(s, "YOUR MOVE");
    const rows = ["WARRANT", "DRAGNET", "HANDLER"].map((k) => ({
      label: THEME.SPECIALS[k].name, badge: "×1", sub: THEME.SPECIALS[k].blurb,
      bright: k !== "HANDLER", dim: false }));
    th.list("SP", "CALLS TO A HIGHER POWER", rows);
    return th;
  }

  const STEPS = [
    /* ================= WARRANT ================= */
    ["W1 · ACTOR — kit menu, specials section", async (s) => {
      kitSheet(s, BASE());
      await hold(s);
      s.closeThread();
    }],
    ["W1b · ACTOR — the SPECIALS page", async (s) => {
      specialsSheet(s);
      await hold(s);
      s.closeThread();
    }],
    ["W2 · ACTOR — pick a player to search", async (s) => {
      const th = openTh(s, "YOUR MOVE");
      th.pickSeat("item", [1, 2, 3, 4], "WARRANT — TAP A PLAYER");
      await hold(s);
      s.closeThread();
    }],
    ["W3 · ACTOR — confirm the search", async (s) => {
      const th = openTh(s, "YOUR MOVE");
      th.list("GO", "CONFIRM — SEARCH " + THEME.seatName(2, ROSTER), [
        { info: true, label: THEME.SPECIALS.WARRANT.blurb },
        { dot: true },
        { label: "✓ EXECUTE", bright: true }, { label: "✕ STAND DOWN", down: true }]);
      await hold(s);
      s.closeThread();
    }],
    ["W4 · ACTOR — the take sheet (their FULL kit)", async (s) => {
      const th = openTh(s, "WARRANT");
      const rows = [{ info: true, label: "SEARCHING " + THEME.seatName(2, ROSTER) + " — TAKE ONE" }, { dot: true }];
      [["POISON", 2], ["TERMS", 1]].forEach(([en, c]) =>
        rows.push({ label: iname(en), badge: "×" + c, bright: true, sub: THEME.ITEMS[en].blurb }));
      [["DRAGNET", 1], ["HANDLER", 1]].forEach(([k, c]) =>
        rows.push({ label: THEME.SPECIALS[k].name, badge: "×" + c, bright: true, sub: THEME.SPECIALS[k].blurb }));
      rows.push({ dot: true }, { label: "TAKE NOTHING", down: true, sub: "WALK AWAY" });
      th.list("TAKE", "", rows);
      await hold(s);
      s.closeThread();
    }],
    ["W5 · VICTIM — searched (anonymous)", (s) =>
      CHOREO.play(s, [{ type: "searched", taken: "POISON" }], BASE(), BASE(), ROSTER)],
    ["W6 · TABLE — sees NOTHING (board unchanged)", async (s) => {
      s.render(BASE(), ROSTER);
      s.setBand({ phase: "talk", secs: 41, name: THEME.seatName(2, ROSTER),
        note: "" });
      await hold(s);
    }],
    /* ================= DRAGNET ================= */
    ["D1 · ACTOR — confirm the dragnet", async (s) => {
      const th = openTh(s, "YOUR MOVE");
      th.list("GO", "CONFIRM — CALL A DRAGNET", [
        { info: true, label: THEME.SPECIALS.DRAGNET.blurb },
        { dot: true },
        { label: "✓ EXECUTE", bright: true }, { label: "✕ STAND DOWN", down: true }]);
      await hold(s);
      s.closeThread();
    }],
    ["D2 · ACTOR — the report", async (s) => {
      const th = openTh(s, "DRAGNET REPORT", "✕ CLOSE");
      const rows = [{ info: true, label: "EVERY KIT ON THE TRAIN — SPECIALS STAY DARK" }, { dot: true }];
      const rep = { 1: "MAGNET×1 · TERMS×2", 2: "POISON×2 · TERMS×1", 3: "EMPTY-HANDED", 4: "PASSPORT×3" };
      Object.entries(rep).forEach(([pid, inv]) => {
        rows.push({ label: THEME.seatName(+pid, ROSTER), still: true, bright: true });
        rows.push({ info: true, label: inv, tight: true });
      });
      th.list("i", "", rows);
      await hold(s);
      s.closeThread();
    }],
    ["D3 · TABLE — only the ledger moved", async (s) => {
      const th = openTh(s, "LEDGER", "✕ CLOSE");
      const v = BASE(); v.special_counts.DRAGNET = 4;
      const rows = [];
      ORDER.forEach((en) => {
        const live = (v.item_counts || {})[en] || 0;
        rows.push({ split: [iname(en) + " ×" + live, "5 TO USE"] });
      });
      rows.push({ dot: true });
      ["WARRANT", "DRAGNET", "HANDLER"].forEach((k) => {
        rows.push({ split: [THEME.SPECIALS[k].name + " ×" + v.special_counts[k], "NO LIMIT"] });
      });
      th.list("i", "", rows);
      await hold(s);
      s.closeThread();
    }],
    /* ================= HANDLER ================= */
    ["H1 · HOLDER — SEIZE button during their decision", async (s) => {
      const v = BASE(); v.current = 3;
      s.render(v, ROSTER);
      s.setBand({ phase: "decision", secs: 22, name: THEME.seatName(3, ROSTER), invert: true });
      s.setSeize(true, () => {});
      await hold(s);
      s.setSeize(false);
    }],
    ["H2 · ALL — a bot takes aim (5s window)", async (s) => {
      const v = BASE(); v.current = 3;
      s.render(v, ROSTER);
      for (let t = 5; t >= 0; t--) {
        s.setBand({ phase: "aiming", secs: t, name: THEME.seatName(3, ROSTER),
          note: THEME.seatName(3, ROSTER) + " IS TAKING AIM…", invert: true });
        await wait(s, 320);
      }
      s.setSeize(false);
    }],
    ["H3 · HOLDER — their shot, your call", async (s) => {
      const th = openTh(s, "HANDLER");
      th.pickSeat("shoot", [0, 2, 3, 4], "THEIR SHOT — TAP THE TARGET");
      await hold(s);
      s.closeThread(); s.clearTargets();
    }],
    ["H4 · VICTIM — a higher power (anonymous)", async (s) => {
      const v = BASE();
      s.render(v, ROSTER);
      s.setBand({ phase: "decision", secs: 18, name: "YOUR TURN · " + THEME.seatName(0, ROSTER),
        note: "YOUR HANDS MOVE ON THEIR OWN — THE SHOT IS NOT YOURS", invert: true });
      await CHOREO.play(s, [{ type: "ridden" }], v, v, ROSTER);
    }],
    ["H5 · VICTIM — SHOOT locked in the move sheet", async (s) => {
      const th = openTh(s, "YOUR MOVE");
      th.list("MOVE", "", [
        { label: "SHOOT", dim: true, sub: "YOUR HANDS MOVE ON THEIR OWN" },
        { label: "FLIP", flip: true, sub: "BUY A CHANGE OF LOYALTY" },
        { label: "ITEM", kit: true, sub: "OPEN YOUR KIT" }]);
      await hold(s);
      s.closeThread();
    }],
    ["H6 · TABLE — the shot reads as the victim's own", (s) =>
      CHOREO.play(s, [{ type: "shot", actor: 3, target: 1, bullet: "LIVE", damage: 1, killed: false }],
        BASE(), BASE(), ROSTER)],
  ];

  function hold(s) {                                   // park until the next tap (or __lab.go)
    return new Promise((r) => { holdRelease = r; });
  }
  let holdRelease = null;

  let scene = null, i = 0, running = false;
  async function runStep(n) {
    if (!scene || running) return;
    running = true;
    i = ((n % STEPS.length) + STEPS.length) % STEPS.length;
    const [label, run] = STEPS[i];
    hud.textContent = (i + 1) + "/" + STEPS.length + " · " + label;
    try { await run(scene); } catch (err) { hud.textContent = "ERR " + label + ": " + err.message; console.error(err); }
    scene.render(BASE(), ROSTER);
    scene.setBand({ phase: "talk", secs: 60, name: "SPECLAB" });
    running = false;
  }
  SCENE.ready = (s) => {
    scene = s; window.__scene = s;
    s.render(BASE(), ROSTER);
    s.setBand({ phase: "talk", secs: 60, name: "SPECLAB" });
    console.log("SPECLAB OK · " + STEPS.length + " steps");
  };
  new Phaser.Game({ type: Phaser.CANVAS, parent: "stage", width: SCENE.W, height: SCENE.H,
    backgroundColor: "#000000", pixelArt: true,
    scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH }, scene: SCENE.TableScene });

  document.addEventListener("pointerdown", () => {
    if (holdRelease) { const r = holdRelease; holdRelease = null; r(); return; }
    if (running) { CHOREO.skip(); return; }
    runStep(i + (scene && hud.textContent.startsWith("TAP") ? 0 : 1));
  }, true);
  window.__lab = { go: (n) => { if (holdRelease) { const r = holdRelease; holdRelease = null; r(); }
                                setTimeout(() => runStep(n), 80); },
                   next: () => window.__lab.go(i + 1) };
})();

/* CHOREO — the moment catalog (spec §7). Pure sequencing over scene primitives.
 * Skippable: CHOREO.skip() flips a flag; every wait routes through it (v1 behavior). */
(function (global) {
  "use strict";
  let _skip = false;
  function bind(scene) {
    _skip = false;
    scene.w = (ms) => new Promise((r) => {
      if (_skip || ms <= 0) { r(); return; }
      scene.time.delayedCall(ms, r);
    });
  }
  const nm = (id, roster) => THEME.seatName(id, roster);
  const iname = (en) => THEME.itemName(en);

  /* ---------- setup ceremony: M1 coin, plates stamp, M2+M3 load, M4 deal, M5 first turn ---------- */
  async function setup(scene, view, roster, announce) {
    bind(scene);
    scene.render(view, roster);
    view.order.forEach((id) => { const s = scene.seats.get(id);
      [s.plate, s.nameT].forEach((o) => o.setScale(0)); });
    // M1 — coin flip lands on the extra-seat agency (odd split is derivable from the view)
    const counts = {};
    view.players.forEach((p) => { counts[p.team] = (counts[p.team] || 0) + 1; });
    const odd = Object.keys(counts).sort((a, b) => counts[b] - counts[a])[0];
    await coinFlip(scene, odd);
    for (const id of view.order) {                            // plates stamp in, 120ms stagger
      const s = scene.seats.get(id);
      scene.tweens.add({ targets: [s.plate, s.nameT], scaleX: 1, scaleY: 1, duration: 160, ease: "Back.easeOut" });
      await scene.w(120);
    }
    if (announce) {                                           // M2 dice ceremony + M3 announce
      await scene.diceCeremony(announce.total, announce.live, { keepDim: true });
      await scene.announceHold(announce.total, announce.live);
    }
    await deal(scene, view);                                  // M4
    await scene.dialTo(view.current, false);                  // M5 first heavy click
    scene.render(view, roster);
  }

  async function coinFlip(scene, oddTeam) {
    scene.dim(true);                                          // dark overlay for the coin (review)
    const tm = THEME.TEAMS[oddTeam] || THEME.TEAMS.RED;
    const cap = scene.add.text(SCENE.W / 2, 160, "", { fontFamily: "'Times New Roman','Times',Georgia,serif",
      fontSize: "24px", color: "#ffffff", fontStyle: "bold", stroke: "#000000", strokeThickness: 6 })
      .setOrigin(0.5).setResolution(2).setDepth(18);
    const capIn = scene.decode(cap, "THE ODD SEAT…", 420);    // decode-in while the coin spins
    const c = scene.add.circle(SCENE.W / 2, 210, 24, 0xffffff).setStrokeStyle(3, 0xffffff, 1).setDepth(18);
    for (let k = 0; k < 6; k++) {
      await new Promise((r) => scene.tweens.add({ targets: c, scaleX: 0.06, duration: 90, yoyo: true,
        onYoyo: () => c.setFillStyle(k % 2 ? 0xffffff : 0x000000), onComplete: r }));
    }
    await capIn;
    c.setFillStyle(tm.plate);
    const t = scene.add.text(SCENE.W / 2, 258, "", { fontFamily: "'Times New Roman','Times',Georgia,serif",
      fontSize: "26px", color: "#ffffff", fontStyle: "bold", stroke: "#000000", strokeThickness: 6 })
      .setOrigin(0.5).setResolution(2).setDepth(18);
    await scene.decode(t, tm.name + " +1 SEAT", 460);
    await scene.w(1100);
    await Promise.all([scene.decodeOut(cap, 420), scene.decodeOut(t, 420),
      new Promise((r) => scene.tweens.add({ targets: c, alpha: 0, duration: 350, onComplete: r }))]);
    c.destroy(); t.destroy(); cap.destroy();                  // await cleanup — no leak
    scene.dim(false);
  }

  async function quickTumble(scene, x, y) {                   // M4's per-seat 3 quick d6 tumbles
    const t = scene.add.text(x, y - 52, "", { fontFamily: "Consolas,monospace", fontSize: "20px",
      color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2).setDepth(15);
    for (let k = 0; k < 3; k++) { t.setText("⚀⚁⚂⚃⚄⚅"[(Math.random() * 6) | 0]); await scene.w(60); }
    t.destroy();
  }

  async function deal(scene, view) {                          // tightened: ceremony budget (was 9.4s)
    const c = { x: SCENE.CX, y: SCENE.CY };
    for (const id of view.order) {
      const p = view.players.find((q) => q.id === id);
      if (!p || !p.alive) continue;
      await quickTumble(scene, scene.seatXY(id).x, scene.seatXY(id).y);
      if (id === view.you) {                                  // your icons fly into KIT, names revealed
        for (const [en, cnt] of Object.entries(view.your_hand || {}))
          for (let k = 0; k < cnt; k++)
            scene.iconFly(THEME.ITEMS[en].icon, c, scene.kitXY(), iname(en)), await scene.w(320);
      } else {
        for (let k = 0; k < 3; k++) scene.cardBack(c, id);    // 3 card-backs fan, no await between
        await scene.w(260);
      }
    }
    await scene.w(600);                                       // last flights land before first turn
  }

  /* ---------- the live cascade ---------- */
  async function play(scene, events, prev, view, roster) {
    bind(scene);
    let sawElim = false, lastBeer = null;
    /* live state — each beat mutates a working copy of the PREV view and repaints the
     * affected seat AT the beat: lives/chips/cuffs never wait for the end-of-cascade settle */
    const work = {};
    if (prev && prev.players) prev.players.forEach((p) => {
      work[p.id] = Object.assign({}, p, { immune_from: (p.immune_from || []).slice() });
    });
    const ctx = prev ? { teams_active: prev.teams_active, current: view.current,
      winner: view.winner } : view;
    const paint = (id) => { if (work[id]) scene.paintSeat(work[id], ctx, roster, true); };
    for (const e of events || []) {
      if (e.type === "announce") {
        await scene.diceCeremony(e.total, e.live, { keepDim: true });
        await scene.announceHold(e.total, e.live);
      } else if (e.type === "reload") {
        await scene.diceCeremony(e.total, e.live, { fast: true, honor: sawElim, keepDim: true });
        await scene.announceHold(e.total, e.live);
        if (lastBeer != null && lastBeer === view.current && view.winner == null)
          await scene.toast("STILL YOUR SHOT", 1400);         // C3 after a MAGNET-emptied reload
      } else if (e.type === "shot") {
        await scene.dialTo(e.actor, true);                    // M12 overwind + lock
        await scene.w(400);                                   // tension hold
        if (e.shell === "LIVE") {
          scene.flashWhite(); scene.shake();
          scene.seatRecoil(e.target);
          scene.pipShatter(e.target, e.damage || 1);
          scene.floatText(e.target, "−" + (e.damage || 1), true);
          if (work[e.target]) {                               // pips drop AT impact
            work[e.target].lives = Math.max(0, work[e.target].lives - (e.damage || 1));
            paint(e.target);
          }
          await scene.w(1000);
        } else {
          scene.tweens.add({ targets: scene.center, angle: "+=3", yoyo: true, repeat: 3, duration: 40 });
          scene.floatText(e.actor, "CLICK", false);
          await scene.w(800);
          if (e.actor === e.target && view.bonus && view.current === e.actor && view.winner == null)
            await scene.stampSeat(e.actor, "BONUS TURN", false);                 // M13
        }
        scene.setSawChip(false); lastBeer = null;
      } else if (e.type === "elimination") {
        sawElim = true;
        if (work[e.target]) { work[e.target].alive = false; work[e.target].lives = 0; }
        Object.values(work).forEach((w) => {                  // their DIRT dissolves with them
          w.immune_from = w.immune_from.filter((c) => c !== e.target); });
        await deathBeat(scene, e.target, roster);             // M14
      } else if (e.type === "item") {
        if (e.item === "BEER") lastBeer = e.actor;
        await scene.dialTo(e.actor);                          // the arrow OWNS every beat's actor
        if (e.item === "HANDCUFFS" && work[e.target] != null) {
          work[e.target].handcuffed = true; paint(e.target);  // SEDATED chip lands with the beat
        } else if (e.item === "IMMUNITY" && work[e.target] != null) {
          work[e.target].immune_from.push(e.actor); paint(e.target);
        } else if (e.item === "CIGARETTES" && work[e.actor] != null) {
          work[e.actor].lives = Math.min(work[e.actor].lives + 1, THEME.MAX_LIVES);
          paint(e.actor);
        }
        await itemBeat(scene, e, view, roster);
      } else if (e.type === "flip") {
        await scene.dialTo(e.actor);
        const fp = view.players.find((q) => q.id === e.target);
        if (fp && work[e.target]) work[e.target].team = fp.team;   // later repaints keep the new color
        await flipBeat(scene, e, view, roster);               // M25
      } else if (e.type === "fine") {
        await scene.dialTo(e.actor);
        await scene.stampSeat(e.actor, "FINED", false);       // M9 — publicly anonymous (D14)
        await scene.crumbleCard(e.actor);
      } else if (e.type === "draw") {
        await drawBeat(scene, e, view, roster);               // M17
      } else if (e.type === "skip") {
        if (work[e.target]) { work[e.target].handcuffed = false; paint(e.target); }
        await scene.skipBeat(e.target, roster);               // M23 beat
      } else if (e.type === "trade" || e.type === "gift") {
        await scene.dialTo(e.actor);                          // trades are legal ONLY on the actor's
        await tradeBeat(scene, e, prev, view, roster);        // turn (engine) — show it (M26)
      } else if (e.type === "trade_private") {
        await scene.toast(e.kind === "cancelled"
          ? "TRADE CANCELLED — A PARTY LACKED THE GOODS" : "OFFER DECLINED", 1800);
      }
      await scene.w(300);
    }
    /* derived beats (prev→end view diffs) */
    if (prev && prev.teams_active && !view.teams_active && view.winner == null) {
      await scene.toast("AGENCIES DISSOLVED · FREE FOR ALL", 2200);              // M27
      scene.equalizePlates();
    }
    for (const en of Object.keys(THEME.ITEMS)) {                                 // M24 cap crossings
      const was = prev ? (prev.use_counts || {})[en] || 0 : 0;
      const now = (view.use_counts || {})[en] || 0;
      if (now >= view.use_limit && was < view.use_limit)
        await scene.toast(iname(en) + " EXHAUSTED — TABLE LIMIT", 1600);
    }
    if (view.extra_turn && view.winner == null)
      await scene.toast("EXTRA TURN · " + nm(view.current, roster), 1500);       // M15
    scene.render(view, roster);
    if (view.winner != null) await scene.winnerScene(view.winner, roster);       // M28
  }

  async function deathBeat(scene, id, roster) {
    const s = scene.seats.get(id); if (!s) return;
    s.tile.setVisible(false); s.broken.setVisible(true);                         // frame breaks apart
    scene.tweens.add({ targets: s.face, alpha: 0.35, duration: 650 });           // faces SACRED: alpha only
    s.pips.forEach((p) => p.setVisible(false));
    s.plate.setFillStyle(0x000000);
    s.chipT.setText("");                                                          // a corpse wears no chips
    s.nameT.setColor("#666666").setStroke("#000000", 6); s.strike.setVisible(true);
    await scene.stampSeat(id, "BURNED", true);                                   // red — danger list
    const dead = "DIRT·" + nm(id, roster).slice(0, 6);                           // a12: only THEIR placed
    scene.seats.forEach((t) => {                                                 // BLACKMAIL dissolves;
      t.chipT.setText(t.chipT.text.split("\n").filter((c) => c !== dead).join("\n"));
    });                                                                          // SEDATED chips stay
    await scene.w(400);
  }

  async function itemBeat(scene, e, view, roster) {
    const who = nm(e.actor, roster), it = e.item;
    const icon = THEME.ITEMS[it] ? THEME.ITEMS[it].icon : 0;
    if (it === "CIGARETTES") {                                                   // M18 PASSPORT
      if (e.actor === view.you) await scene.iconFly(icon, scene.kitXY(), e.actor);  // spend from YOUR kit
      scene.floatText(e.actor, "+1 COVER", false);
      await scene.w(700);
    } else if (it === "MAGNIFIER") {                                             // M19 SPYCAM
      await scene.iconFly(icon, e.actor, { x: SCENE.CX, y: SCENE.CY - 90 });
      scene.flashWhite();                                                        // shutter blink
      await scene.toast(who + " USED A SPYCAM", 1400);
    } else if (it === "SAW") {                                                   // M20 POISON
      scene.setSawChip(true);
      await scene.toast(who + " · ×2 ARMED", 1500);
    } else if (it === "BEER") {                                                  // M22 MAGNET
      await scene.shellEject();
      await scene.toast("SHELL EJECTED", 1100);
    } else if (it === "HANDCUFFS") {                                             // M23 place
      await scene.iconFly(icon, e.actor, e.target);
      await scene.toast(nm(e.target, roster) + " SEDATED", 1300);
    } else if (it === "IMMUNITY") {                                             // M21 BLACKMAIL
      await scene.iconFly(THEME.ICON.envelope, e.actor, e.target);
      await scene.toast(who + (who === "YOU" ? " HAVE" : " HAS") + " DIRT ON " + nm(e.target, roster), 1500);
    }
  }

  async function flipBeat(scene, e, view, roster) {                              // M25 — polarity snaps
    const s = scene.seats.get(e.target);
    const p = view.players.find((q) => q.id === e.target);
    if (s && p && view.teams_active) {
      const tm = THEME.TEAMS[p.team] || THEME.TEAMS.RED;                         // endView team
      s.plate.setFillStyle(tm.plate);
      s.nameT.setColor(tm.text).setStroke(tm.text === "#000000" ? "#ffffff" : "#000000", 6);
      s.plate.setStrokeStyle(tm.tk, 0xffffff, 0.95); s.tile.setStrokeStyle(tm.tk, 0xffffff, 1);
      scene.tweens.add({ targets: [s.plate, s.nameT], scaleX: { from: 0, to: 1 }, duration: 220 });
    }
    await scene.toast(e.actor === e.target
      ? nm(e.actor, roster) + " SWITCHED SIDES"                                  // flip-back (self)
      : nm(e.actor, roster) + " TURNED " + nm(e.target, roster), 1700);
  }

  async function drawBeat(scene, e, view, roster) {                              // M17
    if (e.you) {
      const recv = {};                                                           // count-aware diff
      (e.you.received || []).forEach((n) => { recv[n] = (recv[n] || 0) + 1; });
      for (const n of e.you.attempted || []) {
        const icon = THEME.ITEMS[n] ? THEME.ITEMS[n].icon : 0;
        if ((recv[n] || 0) > 0) {
          recv[n]--;
          await scene.iconFly(icon, { x: SCENE.CX, y: SCENE.CY }, scene.kitXY(), iname(n));
        } else {                                                                 // over-cap bounce: "FULL"
          const k = scene.kitXY();
          await scene.iconFly(icon, { x: SCENE.CX, y: SCENE.CY }, { x: k.x - 40, y: k.y - 40 });
          scene.floatAt({ x: k.x - 40, y: k.y - 50 }, "FULL", false);            // at the KIT, not the seat
          await scene.w(350);
        }
      }
    } else {                                                                     // public copy: no data
      view.players.filter((p) => p.alive && p.id !== view.you)
        .forEach((p) => scene.cardBack({ x: SCENE.CX, y: SCENE.CY }, p.id));
      await scene.toast("RESUPPLY", 1100);
    }
  }

  async function tradeBeat(scene, e, prev, view, roster) {                       // M26 + bot gift
    const parties = view.you === e.actor || view.you === e.target;
    if (e.items && parties) {                                                    // real items — parties only
      for (const n of e.items.give || [])
        await scene.iconFly(THEME.ITEMS[n].icon, e.actor, e.target, iname(n));
      for (const n of e.items.want || [])
        await scene.iconFly(THEME.ITEMS[n].icon, e.target, e.actor, iname(n));
    } else if (e.type === "gift" && parties && view.you === e.target && prev) {
      await scene.cardBack(e.actor, e.target);                                   // enrich via hand diff
      for (const [n, c] of Object.entries(view.your_hand || {})) {
        const gained = c - ((prev.your_hand || {})[n] || 0);
        for (let k = 0; k < gained; k++)
          await scene.iconFly(THEME.ITEMS[n].icon, e.actor, scene.kitXY(), iname(n));
      }
    } else {                                                                     // public: ONE per direction
      await scene.cardBack(e.actor, e.target);
      if (e.type === "trade") await scene.cardBack(e.target, e.actor);
    }
    await scene.toast(e.type === "gift"
      ? nm(e.actor, roster) + " PASSED SOMETHING TO " + nm(e.target, roster)
      : nm(e.actor, roster) + " AND " + nm(e.target, roster) + " MADE AN EXCHANGE", 1500);
  }

  const CHOREO = { setup, play, skip: () => { _skip = true; } };
  global.CHOREO = CHOREO;
  if (typeof module !== "undefined" && module.exports) module.exports = CHOREO;
})(typeof window !== "undefined" ? window : globalThis);

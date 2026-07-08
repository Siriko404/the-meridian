/* TableScene — the dining car (spec §6.2). Layout is PARAMETRIC in seat count (D15).
 * Team = polarity (locked): RED=bloc A white plate/black text/4px · BLUE=black/white/2px.
 * Turn = stroke brightness, never weight. Red 0xc8102e = DANGER ONLY (spec §8 list).
 * The center dial is a SEAT dial — one bore per seat, never tracks shells (a11). */
(function (global) {
  "use strict";
  const W = 390, H = 844, RED = 0xc8102e, WHITE = 0xffffff;
  const MONO = "Consolas,monospace";
  const CX = 195, CY = 430, RX = 142, RY = 150;      // arc (spike-proven); drop CY if KIT collides
  const SCENE = { ready: null };
  const style = (size, color, extra) => Object.assign(
    { fontFamily: MONO, fontSize: size + "px", color: color || "#ffffff", fontStyle: "bold" }, extra || {});

  class TableScene extends Phaser.Scene {
    preload() {
      this.load.spritesheet("faces", "/static/game/assets/portraits/Noir-portraits/36x36-bw-portraits-no-background.png",
        { frameWidth: 36, frameHeight: 36 });
      this.load.spritesheet("icons", "/static/game/assets/Mystery_Icons.png", { frameWidth: 16, frameHeight: 16 });
    }

    create() {
      this.w = (ms) => new Promise((r) => this.time.delayedCall(ms, r));  // choreo swaps in skippable wait
      this.seats = new Map();
      this.built = false;
      this._brackets = []; this._glows = [];
      this.onKit = null; this.onLedger = null; this.onPhone = null;

      // ---- STATUS BAND (destination-board) ----
      this.bandBg = this.add.rectangle(W / 2, 35, W, 70, 0x000000).setDepth(5);
      this.bandLine1 = this.add.text(W / 2, 22, "", style(22)).setOrigin(0.5).setResolution(2).setDepth(6).setLetterSpacing(3);
      this.bandLine2 = this.add.text(W / 2, 50, "", style(14, "#aaaaaa")).setOrigin(0.5).setResolution(2).setDepth(6).setLetterSpacing(2);
      this.bandCode = this.add.text(W - 6, 4, "", style(13, "#777777")).setOrigin(1, 0).setResolution(2).setDepth(6);
      this.add.line(0, 0, 12, 70, W - 12, 70, WHITE, 0.5).setOrigin(0).setDepth(6);
      this.bandNote = this.add.text(W / 2, 84, "", style(13, "#cccccc")).setOrigin(0.5).setResolution(2).setDepth(6).setLetterSpacing(1);

      // ---- LEDGER icon (small, by the band — below the note line so M27b never overlaps) ----
      const lb = this.add.container(24, 128).setDepth(6);
      lb.add(this.add.rectangle(0, 0, 36, 30).setStrokeStyle(1, WHITE, 0.7).setInteractive()
        .on("pointerdown", () => this.onLedger && this.onLedger()));
      lb.add(this.add.text(0, 0, "LEDG", style(13)).setOrigin(0.5).setResolution(2));

      // ---- DOCK ----
      this.add.line(0, 0, 12, 700, W - 12, 700, WHITE, 0.5).setOrigin(0).setDepth(6);
      this.peekChip = this.add.container(62, 726).setDepth(6).setVisible(false);
      this.peekBg = this.add.rectangle(0, 0, 108, 26, 0x000000).setStrokeStyle(2, WHITE, 0.9);
      this.peekT = this.add.text(0, 0, "", style(13)).setOrigin(0.5).setResolution(2);
      this.peekChip.add([this.peekBg, this.peekT]);
      this.strip = this.add.container(0, 0).setDepth(7);      // ACTION STRIP: filled by setStrip()
      // KIT icon (briefcase, icon-gated tray — standing principle)
      const kx = W - 46, ky = 786;
      this._kitXY = { x: kx, y: ky };
      this.add.rectangle(kx, ky + 6, 64, 64).setStrokeStyle(2, WHITE, 0.9).setDepth(6).setInteractive()
        .on("pointerdown", () => this.onKit && this.onKit());
      this.add.image(kx, ky, "icons", THEME.ICON.briefcase).setScale(2.6).setDepth(6);
      this.kitBadge = this.add.text(kx, ky + 22, "KIT", style(13)).setOrigin(0.5).setResolution(2).setDepth(6);
      // chat ticker + phone icon
      this.ticker = this.add.text(10, 833, "", style(13, "#bbbbbb")).setOrigin(0, 0.5).setResolution(2).setDepth(6);
      this.add.image(W - 20, 833, "icons", THEME.ICON.phone).setScale(1.8).setDepth(6)
        .setInteractive().on("pointerdown", () => this.onPhone && this.onPhone());

      this.center = null;                                     // dial container, built with the seats
      if (SCENE.ready) SCENE.ready(this);
    }

    /* ================= layout (parametric N) ================= */
    seatAngle(i, n) { return -Math.PI / 2 + i * (Math.PI * 2 / n); }
    seatXY(id) { const s = this.seats.get(id); return { x: s.x, y: s.y }; }
    kitXY() { return this._kitXY; }

    layout(order) {
      const n = order.length;
      order.forEach((id, i) => {
        const a = this.seatAngle(i, n);
        const x = CX + RX * Math.cos(a), y = CY + RY * Math.sin(a);
        const tile = this.add.rectangle(x, y, 78, 78, 0x000000).setStrokeStyle(2, WHITE, 0.55);
        const broken = this.add.graphics().setVisible(false);  // death frame (M14)
        [[-39, -39, 1, 1], [39, -39, -1, 1], [-39, 39, 1, -1], [39, 39, -1, -1]].forEach(([dx, dy, sx, sy]) => {
          broken.lineStyle(3, WHITE, 0.8);
          broken.lineBetween(x + dx + sx * 4, y + dy + sy * 4, x + dx + sx * 16, y + dy + sy * 4);
          broken.lineBetween(x + dx + sx * 4, y + dy + sy * 4, x + dx + sx * 4, y + dy + sy * 16);
        });
        const face = this.add.image(x, y, "faces", id % 12).setScale(2); // faces SACRED — no tint ever
        const plate = this.add.rectangle(x, y + 53, 62, 22, 0xffffff).setStrokeStyle(2, WHITE, 0.95);
        const nameT = this.add.text(x, y + 53, "", style(14, "#000000")).setOrigin(0.5).setResolution(2);
        const strike = this.add.line(0, 0, x - 26, y + 53, x + 26, y + 53, WHITE, 0.9).setOrigin(0).setVisible(false);
        const pips = [];
        for (let k = 0; k < THEME.MAX_LIVES; k++)
          pips.push(this.add.image(x - 32 + k * 16, y + 74, "icons", THEME.ICON.heart).setScale(1.2).setVisible(false));
        const chipT = this.add.text(x, y - 52, "", style(13)).setOrigin(0.5).setResolution(2)
          .setBackgroundColor("#000000");
        const stamp = this.add.text(x, y, "", style(16, "#ffffff")).setOrigin(0.5).setResolution(2)
          .setAngle(-12).setDepth(8).setVisible(false).setBackgroundColor("#000000");
        this.seats.set(id, { id, x, y, i, tile, broken, face, plate, nameT, strike, pips, chipT, stamp, tk: 2 });
      });
      this.buildDial(n);
      this.built = true;
    }

    buildDial(n) {                                            // spike's fluted cylinder, parametric bores
      this.center = this.add.container(CX, CY).setDepth(4);
      const cg = this.add.graphics();
      const BORE_D = 30, BORE_R = 10, BULGE_R = 17, FLUTE_R = 5, FLUTE_D = 44;
      const pts = [];
      const P = (r, cxx, cyy, a) => pts.push({ x: cxx + r * Math.cos(a), y: cyy + r * Math.sin(a) });
      const stepDeg = 360 / n;
      for (let i = 0; i < n; i++) {
        const a0 = (-90 + i * stepDeg) * Math.PI / 180;
        const bx = BORE_D * Math.cos(a0), by = BORE_D * Math.sin(a0);
        for (let k = -6; k <= 6; k++) P(BULGE_R, bx, by, a0 + k * 0.16);
        const am = a0 + (stepDeg / 2) * Math.PI / 180;
        const fx = FLUTE_D * Math.cos(am), fy = FLUTE_D * Math.sin(am);
        for (let k = 5; k >= -5; k--) P(FLUTE_R, fx, fy, am + k * 0.14 + Math.PI);
      }
      cg.fillStyle(0x000000, 1).lineStyle(3, WHITE, 0.95);
      cg.beginPath(); cg.moveTo(pts[0].x, pts[0].y);
      pts.forEach((p) => cg.lineTo(p.x, p.y));
      cg.closePath(); cg.fillPath(); cg.strokePath();
      for (let i = 0; i < n; i++) {
        const a = (-90 + i * stepDeg) * Math.PI / 180;
        cg.lineStyle(2, WHITE, 0.9).strokeCircle(BORE_D * Math.cos(a), BORE_D * Math.sin(a), BORE_R);
      }
      cg.fillStyle(0xffffff, 0.25).fillCircle(0, 0, 7);
      cg.lineStyle(2, WHITE, 0.7).strokeCircle(0, 0, 7);
      const chambered = this.add.circle(0, -BORE_D, BORE_R - 3, WHITE);
      this.center.add([cg, chambered]);
      // ×2 ARMED chip, pinned at the dial while POISON is live (M20 — red: danger)
      this.sawChip = this.add.text(CX, CY + 64, "×2 ARMED", style(13, "#c8102e")).setOrigin(0.5)
        .setResolution(2).setDepth(8).setBackgroundColor("#000000").setVisible(false);
    }

    /* ================= settle render ================= */
    render(view, roster) {
      if (!this.built) this.layout(view.order);
      const eq = !view.teams_active;                          // M27: agencies dissolved — equalize
      view.players.forEach((p) => {
        const s = this.seats.get(p.id); if (!s) return;
        const tm = THEME.TEAMS[p.team] || THEME.TEAMS.RED;
        const tk = eq ? 3 : tm.tk, plate = eq ? 0x000000 : tm.plate, txt = eq ? "#ffffff" : tm.text;
        s.tk = tk;
        s.nameT.setText(THEME.seatName(p.id, roster)).setColor(p.alive ? txt : "#666666");
        s.plate.setFillStyle(p.alive ? plate : 0x000000);
        s.plate.setStrokeStyle(tk, WHITE, 0.95);
        s.pips.forEach((pp, k) => pp.setVisible(p.alive && k < p.lives));
        const chips = [];
        (p.immune_from || []).forEach((c) => chips.push("BLACKMAIL·" + THEME.seatName(c, roster)));
        if (p.handcuffed) chips.push("SEDATED");
        s.chipT.setText(chips.join("  "));
        const active = p.alive && p.id === view.current && view.winner == null;
        s.tile.setStrokeStyle(tk, WHITE, active ? 1 : 0.55);
        s.face.setScale(active ? 2.3 : 2);
        if (!p.alive) {                                       // M14 end-state (the beat itself is choreo)
          s.tile.setVisible(false); s.broken.setVisible(true);
          s.face.setAlpha(0.35);                              // whole-object fade — pixels untouched
          s.strike.setVisible(true);
          s.stamp.setText("BURNED").setColor("#c8102e").setVisible(true);
        } else {
          s.tile.setVisible(true); s.broken.setVisible(false);
          s.face.setAlpha(1); s.strike.setVisible(false);
          if (s.stamp.text === "BURNED") s.stamp.setVisible(false);
        }
      });
      if (view.winner == null) this.dialTo(view.current, false);
      this.setPeek(view.peek);
      this.setSawChip(!!view.saw_active);
      this.bandCode.setText(this._code || "");
    }

    /* ================= band ================= */
    setBand(o) {                                              // o = {phase,secs,name,bonus,note,invert}
      const inv = !!o.invert;                                 // M8: DECISION inverts the band (pressure)
      this.bandBg.setFillStyle(inv ? 0xffffff : 0x000000);
      const fg = inv ? "#000000" : "#ffffff";
      let l1 = "";
      if (o.phase === "talk") l1 = "TALK · " + fmt(o.secs);
      else if (o.phase === "decision") l1 = (o.bonus ? "BONUS · " : "DECISION · ") + fmt(o.secs);
      else if (o.phase != null) l1 = String(o.phase);
      const red = o.phase === "decision" && o.secs != null && o.secs <= 5;   // M8: final 5s digits red
      this.bandLine1.setText(l1).setColor(red ? "#c8102e" : fg);
      if (o.phase === "decision" && o.secs != null && o.secs <= 10 && this._lastTick !== (o.secs | 0)) {
        this._lastTick = o.secs | 0;                          // M8: final-10s tick pulse
        this.tweens.add({ targets: this.bandLine1, scale: { from: 1.12, to: 1 }, duration: 180 });
      }
      this.bandLine2.setText(o.name || "").setColor(inv ? "#333333" : "#aaaaaa");
      this.bandNote.setText(o.note || "");
    }
    setCode(code) { this._code = code; this.bandCode.setText(code || ""); }
    setTicker(s) { this.ticker.setText(s.length > 44 ? s.slice(0, 43) + "…" : s); }

    /* ================= primitives (all waits via this.w — skippable) ================= */
    decode(txtObj, str, dur) {                                // v1 terminal decoder, ported
      return new Promise((resolve) => {
        const n = str.length, t0 = this.time.now, rt = [];
        const idx = [...Array(n).keys()].filter((i) => str[i] !== " ");
        idx.forEach((i, k) => (rt[i] = k / idx.length));
        const ev = this.time.addEvent({ delay: 33, loop: true, callback: () => {
          const p = (this.time.now - t0) / (dur || 750);
          let out = "";
          for (let i = 0; i < n; i++) {
            if (str[i] === " ") { out += " "; continue; }
            out += p >= rt[i] + 0.05 ? str[i] : (Math.random() < 0.5 ? "0" : "1");
          }
          txtObj.setText(out);
          if (p >= 1.15) { txtObj.setText(str); ev.remove(); resolve(); }
        } });
      });
    }
    async toast(str, hold) {
      if (!this._toast) this._toast = this.add.text(W / 2, 116, "", style(17)).setOrigin(0.5)
        .setResolution(2).setDepth(9).setBackgroundColor("#000000").setLetterSpacing(2);
      this._toast.setAlpha(1);
      await this.decode(this._toast, str, 440);
      await this.w(hold || 1400);
      this.tweens.add({ targets: this._toast, alpha: 0, duration: 500 });
    }
    flashWhite() {
      const f = this.add.rectangle(W / 2, H / 2, W, H, 0xffffff).setDepth(20);
      this.time.delayedCall(60, () => f.destroy());
    }
    shake() { this.cameras.main.shake(140, 0.012); }
    seatRecoil(id) {
      const s = this.seats.get(id); if (!s) return;
      const parts = [s.tile, s.face, s.plate, s.nameT];
      this.tweens.add({ targets: parts, x: "+=7", yoyo: true, repeat: 2, duration: 45 });
    }
    pipShatter(id, nDamage) {                                 // M12 — red particles (danger)
      const s = this.seats.get(id); if (!s) return;
      for (let k = 0; k < 10 * (nDamage || 1); k++) {
        const px = s.x - 32 + Math.random() * 64, py = s.y + 74;
        const dot = this.add.rectangle(px, py, 3, 3, RED).setDepth(15);
        this.tweens.add({ targets: dot, x: px + (Math.random() - 0.5) * 90, y: py + 30 + Math.random() * 60,
          alpha: 0, duration: 550 + Math.random() * 250, onComplete: () => dot.destroy() });
      }
    }
    floatText(id, str, red) {
      const s = this.seats.get(id); if (!s) return;
      const t = this.add.text(s.x, s.y - 30, str, style(20, red ? "#c8102e" : "#ffffff")).setOrigin(0.5)
        .setResolution(2).setDepth(15);
      this.tweens.add({ targets: t, y: s.y - 80, alpha: 0, duration: 950, onComplete: () => t.destroy() });
    }
    async stampSeat(id, str, red) {
      const s = this.seats.get(id); if (!s) return;
      s.stamp.setText(str).setColor(red ? "#c8102e" : "#ffffff").setVisible(true).setScale(1.6).setAlpha(0);
      this.tweens.add({ targets: s.stamp, scale: 1, alpha: 1, duration: 190, ease: "Back.easeOut" });
      await this.w(900);
      if (str !== "BURNED") { this.tweens.add({ targets: s.stamp, alpha: 0, duration: 400 }); await this.w(400);
        s.stamp.setVisible(false).setAlpha(1); }
    }
    _pt(p) { return typeof p === "object" ? p : this.seatXY(p); }
    async cardBack(from, to) {                                // ONE generic card-back (D16/M9/M26)
      const a = this._pt(from), b = this._pt(to);
      const c = this.add.rectangle(a.x, a.y, 22, 30, 0x000000).setStrokeStyle(2, WHITE, 0.95).setDepth(15);
      const dot = this.add.rectangle(a.x, a.y, 6, 6, 0xffffff).setDepth(16);
      await new Promise((r) => this.tweens.add({ targets: [c, dot], x: b.x, y: b.y, duration: 550,
        ease: "Quad.easeInOut", onComplete: r }));
      this.tweens.add({ targets: [c, dot], alpha: 0, scale: 0.4, duration: 250,
        onComplete: () => { c.destroy(); dot.destroy(); } });
    }
    async crumbleCard(id) {                                   // M9: fine — card falls + crumbles
      const s = this.seats.get(id); if (!s) return;
      const c = this.add.rectangle(s.x, s.y, 22, 30, 0x000000).setStrokeStyle(2, WHITE, 0.95).setDepth(15);
      await new Promise((r) => this.tweens.add({ targets: c, y: s.y + 70, angle: 50, duration: 480,
        ease: "Quad.easeIn", onComplete: r }));
      for (let k = 0; k < 8; k++) {
        const d = this.add.rectangle(c.x, c.y, 3, 3, 0xffffff).setDepth(15);
        this.tweens.add({ targets: d, x: c.x + (Math.random() - 0.5) * 50, y: c.y + Math.random() * 30,
          alpha: 0, duration: 450, onComplete: () => d.destroy() });
      }
      c.destroy();
    }
    async iconFly(idx, from, to, label) {
      const a = this._pt(from), b = this._pt(to);
      const ic = this.add.image(a.x, a.y, "icons", idx).setScale(2.4).setDepth(15);
      const t = label ? this.add.text(a.x, a.y + 20, label, style(13)).setOrigin(0.5).setResolution(2).setDepth(15) : null;
      await new Promise((r) => this.tweens.add({ targets: t ? [ic, t] : ic, x: b.x, y: b.y, duration: 550,
        ease: "Quad.easeInOut", onComplete: r }));
      this.tweens.add({ targets: t ? [ic, t] : ic, alpha: 0, duration: 260,
        onComplete: () => { ic.destroy(); if (t) t.destroy(); } });
    }
    dialTo(id, overwind) {
      const s = this.seats.get(id); if (!s || !this.center) return Promise.resolve();
      const n = this.seats.size, deg = s.i * (360 / n);
      if (!overwind) { this.tweens.add({ targets: this.center, angle: deg, duration: 420, ease: "Back.easeOut" });
        return this.w(430); }
      return new Promise((r) => this.tweens.add({ targets: this.center, angle: deg + 8, duration: 300,
        ease: "Quad.easeIn", onComplete: () => this.tweens.add({ targets: this.center, angle: deg,
          duration: 120, onComplete: r }) }));
    }
    async shellEject() {                                      // M22: from the dial's CENTER AXIS (a11)
      const sh = this.add.rectangle(CX, CY, 8, 18, 0xffffff).setDepth(15);
      await new Promise((r) => this.tweens.add({ targets: sh, x: W + 40, y: CY - 160, angle: 260,
        duration: 600, ease: "Quad.easeOut", onComplete: r }));
      sh.destroy();
    }
    setPeek(v) {                                              // M19 — own view only; red only when LIVE
      const known = v && v !== "unknown";
      this.peekChip.setVisible(!!known);
      if (known) {
        const live = v === "LIVE";
        this.peekT.setText("NEXT: " + v).setColor(live ? "#c8102e" : "#ffffff");
        this.peekBg.setStrokeStyle(2, live ? RED : WHITE, 0.95);
      }
    }
    setSawChip(on) { if (this.sawChip) this.sawChip.setVisible(!!on); }
    equalizePlates() {                                        // M27 — team semantics visibly end
      this.seats.forEach((s) => { s.plate.setFillStyle(0x000000); s.nameT.setColor("#ffffff");
        s.plate.setStrokeStyle(3, WHITE, 0.95); s.tile.setStrokeStyle(3, WHITE, 0.55); s.tk = 3; });
    }

    /* ---- dice ceremony (M2 full / M16 fast) — counters + transient loading cylinder ---- */
    async diceCeremony(total, live, opts) {
      opts = opts || {};
      const sp = opts.fast ? 0.5 : 1;
      if (opts.honor) await this.toast("IN THEIR HONOR", 900 * sp);
      const rolls = DICE.synthDice(total, live);
      const layer = this.add.container(0, 0).setDepth(18);
      const cnt = { t: 0, l: 0 };
      const tT = this.add.text(100, 150, "TOTAL 0", style(16)).setOrigin(0.5).setResolution(2);
      const lT = this.add.text(290, 150, "LIVE 0", style(16)).setOrigin(0.5).setResolution(2);
      layer.add([tT, lT]);
      const die = (x) => { const g = this.add.graphics(); layer.add(g); return { g, x, y: 300, v: 1 }; };
      const d1 = die(160), d2 = die(230);
      const drawDie = (d) => {
        d.g.clear().fillStyle(0x000000).lineStyle(2, WHITE, 0.95);
        d.g.fillRect(d.x - 17, d.y - 17, 34, 34).strokeRect(d.x - 17, d.y - 17, 34, 34);
        const pip = (px, py) => d.g.fillStyle(0xffffff).fillCircle(d.x + px * 9, d.y + py * 9, 3);
        const P = { 1: [[0, 0]], 2: [[-1, -1], [1, 1]], 3: [[-1, -1], [0, 0], [1, 1]],
          4: [[-1, -1], [1, -1], [-1, 1], [1, 1]], 5: [[-1, -1], [1, -1], [0, 0], [-1, 1], [1, 1]],
          6: [[-1, -1], [1, -1], [-1, 0], [1, 0], [-1, 1], [1, 1]] };
        P[d.v].forEach(([px, py]) => pip(px, py));
      };
      for (const [h, l] of rolls) {
        for (let k = 0; k < 5; k++) {                          // tumble
          d1.v = 1 + ((Math.random() * 6) | 0); d2.v = 1 + ((Math.random() * 6) | 0);
          drawDie(d1); drawDie(d2); await this.w(70 * sp);
        }
        d1.v = h; d2.v = l; drawDie(d1); drawDie(d2);
        await this.w(260 * sp);
        cnt.t += h; cnt.l += l;                                // hi flies to TOTAL, lo to LIVE
        const fh = this.add.text(d1.x, d1.y, String(h), style(18)).setOrigin(0.5).setResolution(2); layer.add(fh);
        const fl = this.add.text(d2.x, d2.y, String(l), style(18)).setOrigin(0.5).setResolution(2); layer.add(fl);
        this.tweens.add({ targets: fh, x: 100, y: 150, alpha: 0, duration: 380 * sp,
          onComplete: () => { fh.destroy(); tT.setText("TOTAL " + cnt.t); } });
        this.tweens.add({ targets: fl, x: 290, y: 150, alpha: 0, duration: 380 * sp,
          onComplete: () => { fl.destroy(); lT.setText("LIVE " + cnt.l); } });
        await this.w(420 * sp);
      }
      tT.setText("TOTAL " + total); lT.setText("LIVE " + live);
      const seal = this.add.text(W / 2, 218, "30–70% · SEALED", style(15)).setOrigin(0.5)
        .setResolution(2).setBackgroundColor("#000000"); layer.add(seal);
      await this.w(650 * sp);
      // transient loading-cylinder: bores fill one-by-one, spin-shuffle decelerates, fade (a11-safe)
      const lc = this.add.container(CX, CY - 140).setDepth(18); layer.add(lc);
      const lg = this.add.graphics(); lc.add(lg);
      lg.lineStyle(2, WHITE, 0.9).strokeCircle(0, 0, 46);
      const bores = Math.min(total, 16), per = Math.max(30, 900 / bores) * sp;
      for (let i = 0; i < bores; i++) {
        const a = -Math.PI / 2 + i * (Math.PI * 2 / bores);
        lg.fillStyle(0xffffff, 0.9).fillCircle(34 * Math.cos(a), 34 * Math.sin(a), 4);
        await this.w(per);
      }
      await new Promise((r) => this.tweens.add({ targets: lc, angle: 900, duration: 1100 * sp,
        ease: "Cubic.easeOut", onComplete: r }));
      await new Promise((r) => this.tweens.add({ targets: layer, alpha: 0, duration: 350,
        onComplete: () => { layer.destroy(); r(); } }));
    }
    async announceHold(total, live) {                          // M3 — once, 5s, then never again (#3b=A)
      const t = this.add.text(W / 2, 200, total + " SHELLS · " + live + " LIVE", style(24)).setOrigin(0.5)
        .setResolution(2).setDepth(19).setBackgroundColor("#000000").setLetterSpacing(3);
      await this.decode(t, total + " SHELLS · " + live + " LIVE", 600);
      await this.w(5000);
      this.tweens.add({ targets: t, alpha: 0, duration: 400, onComplete: () => t.destroy() });
    }

    /* ---- targeting + glow ---- */
    setTargets(ids, onTap) {                                   // M11 — RED corner brackets (danger)
      this.clearTargets();
      ids.forEach((id) => {
        const s = this.seats.get(id); if (!s) return;
        const g = this.add.graphics().setDepth(12);
        [[-44, -44, 1, 1], [44, -44, -1, 1], [-44, 44, 1, -1], [44, 44, -1, -1]].forEach(([dx, dy, sx, sy]) => {
          g.lineStyle(3, RED, 1);
          g.lineBetween(s.x + dx, s.y + dy, s.x + dx + sx * 14, s.y + dy);
          g.lineBetween(s.x + dx, s.y + dy, s.x + dx, s.y + dy + sy * 14);
        });
        const hit = this.add.rectangle(s.x, s.y, 88, 88, 0xffffff, 0.001).setDepth(12).setInteractive()
          .on("pointerdown", () => onTap && onTap(id));
        this._brackets.push(g, hit);
      });
    }
    clearTargets() { this._brackets.forEach((o) => o.destroy()); this._brackets = []; }
    seatGlow(ids, on, onTap) {                                 // M26 — tradable teammates glow.
      this._glows.forEach((o) => { o.tween.stop(); o.g.destroy(); if (o.hit) o.hit.destroy(); });
      this._glows = [];                                        // WHITE glow + tap — never red (trade ≠ danger)
      if (!on) return;
      ids.forEach((id) => {
        const s = this.seats.get(id); if (!s) return;
        const g = this.add.rectangle(s.x, s.y, 90, 90).setStrokeStyle(3, WHITE, 0.9).setDepth(11);
        const tween = this.tweens.add({ targets: g, alpha: { from: 0.9, to: 0.25 }, yoyo: true,
          repeat: -1, duration: 520 });
        let hit = null;
        if (onTap) hit = this.add.rectangle(s.x, s.y, 90, 90, 0xffffff, 0.001).setDepth(11)
          .setInteractive().on("pointerdown", () => onTap(id));
        this._glows.push({ g, tween, hit });
      });
    }
    async skipBeat(id, roster) {                               // M23 — the invisible skip becomes a beat
      await this.dialTo(id, false);
      await this.stampSeat(id, "SKIPPED", false);
      const s = this.seats.get(id);
      if (s && s.chipT.text.includes("SEDATED"))
        s.chipT.setText(s.chipT.text.replace("SEDATED", "").trim());
    }
    async winnerScene(id, roster) {                            // M28
      this.add.rectangle(W / 2, H / 2, W, H, 0x000000, 0.82).setDepth(24);
      this.add.image(W / 2, 330, "faces", id % 12).setScale(6).setDepth(25);
      this.add.text(W / 2, 470, "LAST AGENT STANDING", style(18)).setOrigin(0.5).setResolution(2)
        .setDepth(25).setLetterSpacing(4);
      const t2 = this.add.text(W / 2, 505, "", style(26)).setOrigin(0.5)
        .setResolution(2).setDepth(25).setLetterSpacing(6);
      this.add.text(W / 2, 810, THEME.CREDITS, style(13, "#888888")).setOrigin(0.5).setResolution(2).setDepth(25);
      await this.decode(t2, THEME.seatName(id, roster), 700);
    }

    /* ---- ACTION STRIP: verb buttons drawn on demand (used from Task 7) ---- */
    setStrip(defs) {                                           // defs = [{label, onTap, wide}]
      this.strip.removeAll(true);
      if (!defs || !defs.length) return;
      let x = 130;
      defs.forEach((d) => {
        const w = d.wide ? 116 : 82;
        const r = this.add.rectangle(x + w / 2, 760, w, 44, 0x000000).setStrokeStyle(2, WHITE, 0.95)
          .setInteractive().on("pointerdown", () => d.onTap && d.onTap());
        const t = this.add.text(x + w / 2, 760, d.label, style(14)).setOrigin(0.5).setResolution(2);
        this.strip.add([r, t]);
        x += w + 8;
      });
    }
  }

  function fmt(secs) {
    if (secs == null) return "";
    const s = Math.ceil(secs);
    return "0:" + String(Math.max(0, s)).padStart(2, "0");
  }

  SCENE.TableScene = TableScene; SCENE.W = W; SCENE.H = H; SCENE.RED = RED; SCENE.WHITE = WHITE;
  SCENE.CX = CX; SCENE.CY = CY;
  global.SCENE = SCENE;
})(typeof window !== "undefined" ? window : globalThis);

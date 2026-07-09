/* TableScene — the dining car (spec §6.2). Layout is PARAMETRIC in seat count (D15).
 * Team = polarity (locked): RED=bloc A white plate/black text/4px · BLUE=black/white/2px.
 * Turn = stroke brightness, never weight. Red 0xc8102e = DANGER ONLY (spec §8 list).
 * The center dial is a SEAT dial — one bore per seat, never tracks shells (a11). */
(function (global) {
  "use strict";
  const W = 390, H = 844, RED = 0xc8102e, WHITE = 0xffffff;
  const SERIF = "'Times New Roman','Times',Georgia,serif";   // 1-bit-crisp serif (setResolution 2)
  const CX = 195, CY = 430, RX = 142, RY = 150;      // arc (spike-proven); drop CY if KIT collides
  const SCENE = { ready: null };
  const FS = 1.5;                                     // global size bump — mobile readability
  const style = (size, color, extra) => {             // INVERSE outline: white text/black rim, black text/white rim
    const c = color || "#ffffff";
    return Object.assign({ fontFamily: SERIF, fontSize: Math.round(size * FS) + "px", color: c,
      fontStyle: "bold", stroke: c === "#000000" ? "#ffffff" : "#000000", strokeThickness: 6 }, extra || {});
  };

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
      this.onKit = null; this.onLedger = null; this.onPhone = null; this.onAction = null;

      // ---- BURNING TIMER BAR (white = talk 60s, red = decision 30s; seconds centered) ----
      const BARX = 18, BARW = W - 36, BARY = 34, BARH = 40;
      this._bar = { x: BARX, y: BARY, w: BARW };
      this.barFill = this.add.rectangle(BARX, BARY, BARW, BARH, WHITE).setOrigin(0, 0.5).setDepth(5).setVisible(false);
      this.barFrame = this.add.rectangle(W / 2, BARY, BARW, BARH).setStrokeStyle(2, WHITE, 0.4).setDepth(6).setVisible(false);
      // burn-through digits: two layers masked at the fill edge — the burn INVERTS them pixel by pixel
      const secStyle = (col) => style(20, col, { strokeThickness: 0 });
      this.barSecs = this.add.text(W / 2, BARY, "", secStyle("#ffffff")).setOrigin(0.5)
        .setResolution(2).setDepth(7).setLetterSpacing(1).setVisible(false);      // over the VOID
      this.barSecsD = this.add.text(W / 2, BARY, "", secStyle("#000000")).setOrigin(0.5)
        .setResolution(2).setDepth(7).setLetterSpacing(1).setVisible(false);      // over the FILL
      this._mFillG = this.make.graphics({ add: false });
      this._mEmptyG = this.make.graphics({ add: false });
      this.barSecsD.setMask(this._mFillG.createGeometryMask());
      this.barSecs.setMask(this._mEmptyG.createGeometryMask());
      this.bandLine2 = this.add.text(W / 2, BARY + 34, "", style(13, "#aaaaaa")).setOrigin(0.5).setResolution(2).setDepth(6).setLetterSpacing(2);
      this.bandCode = this.add.text(W - 6, 2, "", style(11, "#777777")).setOrigin(1, 0).setResolution(2).setDepth(7);
      this.bandNote = this.add.text(W / 2, BARY + 54, "", style(12, "#cccccc", { align: "center",
        wordWrap: { width: W - 24 } })).setOrigin(0.5, 0).setResolution(2).setDepth(6).setLetterSpacing(1);

      // ---- DOCK: three circular hubs (the dial idiom) + a chat ticker row ----
      this.add.line(0, 0, 12, 700, W - 12, 700, WHITE, 0.5).setOrigin(0).setDepth(6);
      this.peekChip = this.add.container(W / 2, 716).setDepth(6).setVisible(false);
      this.peekBg = this.add.rectangle(0, 0, 108, 24, 0x000000).setStrokeStyle(2, WHITE, 0.9);
      this.peekT = this.add.text(0, 0, "", style(12)).setOrigin(0.5).setResolution(2);
      this.peekChip.add([this.peekBg, this.peekT]);
      this.strip = this.add.container(0, 0).setDepth(7);      // legacy anchor (unused by the dial UI)
      const hy = 776, kx = W - 52, lx = 52;
      this._kitXY = { x: kx, y: hy };
      const hub = (x, r, cb) => this.add.circle(x, hy, r, 0x000000).setStrokeStyle(2, WHITE, 0.9)
        .setDepth(6).setInteractive().on("pointerdown", cb);
      hub(lx, 30, () => this.onLedger && this.onLedger());
      this.add.text(lx, hy, "≣", style(20)).setOrigin(0.5).setResolution(2).setDepth(6);   // the ledger glyph
      this.actionHub = hub(W / 2, 38, () => this.onAction && this.onAction());
      this.actionT = this.add.text(W / 2, hy, "· · ·", style(12, "#888888", { align: "center" }))
        .setOrigin(0.5).setResolution(2).setDepth(7);
      hub(kx, 30, () => this.onKit && this.onKit());
      this.add.image(kx, hy, "icons", THEME.ICON.briefcase).setScale(2).setDepth(6);
      // chat = the ticker row itself (tap to open the sheet)
      this.ticker = this.add.text(W / 2, 831, "· · ·", style(12, "#888888")).setOrigin(0.5).setResolution(2).setDepth(6);
      this.add.rectangle(W / 2, 831, W - 8, 22, 0xffffff, 0.001).setDepth(6)
        .setInteractive().on("pointerdown", () => this.onPhone && this.onPhone());

      this.center = null;                                     // dial container, built with the seats
      SCENE.instance = this;                                  // live-scene handle (debug/testing)
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
        const plate = this.add.rectangle(x, y + 54, 82, 24, 0xffffff).setStrokeStyle(2, WHITE, 0.95);
        const nameT = this.add.text(x, y + 54, "", style(11, "#000000")).setOrigin(0.5).setResolution(2);
        const strike = this.add.line(0, 0, x - 26, y + 53, x + 26, y + 53, WHITE, 0.9).setOrigin(0).setVisible(false);
        const pips = [];
        for (let k = 0; k < THEME.MAX_LIVES; k++)
          pips.push(this.add.image(x - 32 + k * 16, y + 78, "icons", THEME.ICON.heart).setVisible(false));
        const chipT = this.add.text(x, y + 88, "", style(13, "#ffffff", { align: "center" }))
          .setOrigin(0.5, 0).setResolution(2).setBackgroundColor("#000000");   // grows DOWN, under the pips
        const stamp = this.add.text(x, y, "", style(16, "#ffffff")).setOrigin(0.5).setResolution(2)
          .setAngle(-12).setDepth(8).setVisible(false).setBackgroundColor("#000000").setName("stamp");
        this.seats.set(id, { id, x, y, i, tile, broken, face, plate, nameT, strike, pips, chipT, stamp, tk: 2 });
      });
      this.buildDial(n);
      this.built = true;
    }

    buildDial() {                                             // cylinder dial REMOVED (review); turn = active-seat frame.
      this.center = this.add.container(CX, CY).setDepth(4);   // empty anchor kept for POISON/MAGNET effects
      // ×2 ARMED chip, shown at table center while POISON is live (M20 — red: danger)
      this.sawChip = this.add.text(CX, CY, "×2 ARMED", style(13, "#c8102e")).setOrigin(0.5)
        .setResolution(2).setDepth(8).setBackgroundColor("#000000").setVisible(false);
    }

    dim(on) {                                                 // OPAQUE overlay: board fully hidden, event owns the stage
      if (!this._dim) this._dim = this.add.rectangle(W / 2, H / 2, W, H, 0x000000, 1).setVisible(false);
      this._dim.setDepth(16).setVisible(!!on);
      if (on) this.children.bringToTop(this._dim);
    }

    /* ================= settle render ================= */
    render(view, roster) {
      if (!this.built) this.layout(view.order);
      if (this._arrow) this._arrow.setVisible(false);         // re-shown by _arrowTo for the active seat
      const eq = !view.teams_active;                          // M27: agencies dissolved — equalize
      view.players.forEach((p) => {
        const s = this.seats.get(p.id); if (!s) return;
        const tm = THEME.TEAMS[p.team] || THEME.TEAMS.RED;
        const tk = eq ? 3 : tm.tk, plate = eq ? 0x000000 : tm.plate, txt = eq ? "#ffffff" : tm.text;
        s.tk = tk;
        const nm = THEME.seatName(p.id, roster);
        const nc = p.alive ? txt : "#666666";
        s.nameT.setText(nm).setColor(nc)
          .setStroke(nc === "#000000" ? "#ffffff" : "#000000", 6)   // stroke must FLIP with the color
          .setFontSize(nm.length <= 4 ? 18 : 15);             // monogram initials read BIG (spy plate)
        s.plate.setFillStyle(p.alive ? plate : 0x000000);
        s.plate.setStrokeStyle(tk, WHITE, 0.95);
        s.pips.forEach((pp, k) => {                           // row centered on the seat, 16px pitch
          pp.setVisible(p.alive && k < p.lives);
          pp.x = s.x + (k - (p.lives - 1) / 2) * 16;
        });
        const chips = [];                                     // short, stacked — never wider than the tile
        if (p.alive) {                                        // a dead agent's chips are noise
          (p.immune_from || []).forEach((c) => chips.push("DIRT·" + THEME.seatName(c, roster).slice(0, 6)));
          if (p.handcuffed) chips.push("SEDATED");
        }
        s.chipT.setText(chips.join("\n"));
        const active = p.alive && p.id === view.current && view.winner == null;
        s.tile.setStrokeStyle(tk, WHITE, active ? 1 : 0.55);
        s.face.setScale(2);                                   // uniform — turn is shown by the ARROW only
        if (active) this._arrowTo(p.id);
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
    setBand(o) {                                              // burning bar: one 90s burn, white 60s -> red 30s
      const TALK = 60, DEC = 30, TOTAL = TALK + DEC;
      let left = null;
      if (o.phase === "talk" && o.secs != null) left = DEC + Math.min(o.secs, TALK);
      else if (o.phase === "decision" && o.secs != null) left = Math.min(o.secs, DEC);
      if (left != null) {
        const red = left <= DEC, col = red ? RED : WHITE;     // last 30s = red
        this.barFrame.setVisible(true);
        this.barFill.setVisible(true);
        const fw = this._bar.w * (left / TOTAL);
        this.barFill.width = fw;
        this.barFill.setFillStyle(col);
        this.barFrame.setStrokeStyle(2, col, 0.95);
        this._mFillG.clear().fillStyle(0xffffff).fillRect(this._bar.x, this._bar.y - 20, fw, 40);
        this._mEmptyG.clear().fillStyle(0xffffff).fillRect(this._bar.x + fw, this._bar.y - 20, this._bar.w - fw, 40);
        this.barSecs.setVisible(true).setText(fmt(left)).setX(W / 2);    // digits FIXED center —
        this.barSecsD.setVisible(true).setText(fmt(left)).setX(W / 2)    // the burn inverts them in place
          .setColor(red ? "#ffffff" : "#000000");
        this.bandCode.setVisible(false);                      // code only rides an idle band
      } else {
        this.barFill.setVisible(false);
        this.barSecs.setVisible(false);
        this.barSecsD.setVisible(false);
        this.barFrame.setVisible(false);
        this.bandCode.setVisible(true);
      }
      this.bandLine2.setText(o.name || "");
      this.bandNote.setText(o.note || "");
    }
    setCode(code) { this._code = code; this.bandCode.setText(code || ""); }
    setTicker(s) { this.ticker.setText(s.length > 38 ? s.slice(0, 37) + "…" : s); }

    /* ================= primitives (all waits via this.w — skippable) ================= */
    /* decode engine: GRAY binary noise; characters resolve in RANDOM order (in) and
       dissolve back to noise, then nothing (out). Per-char slots use the FINAL
       string's measured advances so the serif stays aligned. */
    _slots(txtObj, str) {
      const st = txtObj.style;
      const scratch = this.add.text(0, -999, "", { fontFamily: st.fontFamily,
        fontSize: st.fontSize, fontStyle: st.fontStyle }).setResolution(2).setVisible(false);
      const maxW = st.wordWrapWidth || 0;
      const lines = [];
      if (maxW) {                                             // word-wrap exactly like the target
        let line = "";
        for (const w of str.split(" ")) {
          const t = line ? line + " " + w : w;
          scratch.setText(t);
          if (scratch.width > maxW && line) { lines.push(line); line = w; } else line = t;
        }
        if (line) lines.push(line);
      } else lines.push(str);
      const size = parseInt(st.fontSize) || 20, lh = Math.round(size * 1.3);
      const slots = [];
      lines.forEach((ln, li) => {
        scratch.setText(ln);
        const lw = scratch.width;
        const y = txtObj.y + (li - (lines.length - 1) / 2) * lh;
        let prev = 0;
        for (let i = 0; i < ln.length; i++) {
          scratch.setText(ln.slice(0, i + 1));
          const adv = scratch.width - prev, cx = txtObj.x - lw / 2 + prev + adv / 2;
          prev = scratch.width;
          if (ln[i] === " ") continue;
          const t = this.add.text(cx, y, "", { fontFamily: st.fontFamily, fontSize: st.fontSize,
            fontStyle: st.fontStyle, color: "#ffffff", stroke: "#000000", strokeThickness: 6 })
            .setOrigin(0.5).setResolution(2).setDepth(txtObj.depth).setName("fx");
          slots.push({ t, ch: ln[i] });
        }
      });
      scratch.destroy();
      return slots;
    }
    _shuffled(n) {
      const a = [...Array(n).keys()];
      for (let i = n - 1; i > 0; i--) { const j = (Math.random() * (i + 1)) | 0; [a[i], a[j]] = [a[j], a[i]]; }
      return a;
    }
    decode(txtObj, str, dur) {                                // decode-IN
      return new Promise((resolve) => {
        txtObj.setText("");
        const slots = this._slots(txtObj, str), n = slots.length || 1, D = dur || 750;
        this._shuffled(n).forEach((r, i) => { slots[i].at = (r / n) * D; });
        const t0 = this.time.now;
        const ev = this.time.addEvent({ delay: 33, loop: true, callback: () => {
          const el = this.time.now - t0;
          let done = true;
          for (const s of slots) {
            if (el >= s.at) { if (s.t.text !== s.ch) s.t.setText(s.ch).setColor("#ffffff"); }
            else { done = false; s.t.setText(Math.random() < 0.5 ? "0" : "1").setColor("#8a8a8a"); }
          }
          if (done && el > D) {
            ev.remove();
            slots.forEach((s) => s.t.destroy());
            txtObj.setText(str);                              // steady state: one real Text again
            resolve();
          }
        } });
      });
    }
    decodeOut(txtObj, dur) {                                  // decode-OUT: white → gray noise → gone
      const str = txtObj.text;
      if (!str) return Promise.resolve();
      return new Promise((resolve) => {
        txtObj.setText("");
        const slots = this._slots(txtObj, str), n = slots.length || 1, D = dur || 600;
        this._shuffled(n).forEach((r, i) => { slots[i].at = (r / n) * D * 0.55; });
        slots.forEach((s) => s.t.setText(s.ch));
        const t0 = this.time.now;
        const ev = this.time.addEvent({ delay: 33, loop: true, callback: () => {
          const el = this.time.now - t0;
          let live = false;
          for (const s of slots) {
            if (el < s.at) live = true;
            else if (el < s.at + D * 0.4) { live = true; s.t.setText(Math.random() < 0.5 ? "0" : "1").setColor("#8a8a8a"); }
            else if (s.t.text) s.t.setText("");
          }
          if (!live) { ev.remove(); slots.forEach((s) => s.t.destroy()); resolve(); }
        } });
      });
    }
    async toast(str, hold) {
      if (!this._toast) this._toast = this.add.text(W / 2, 150, "", style(17, "#ffffff",
        { align: "center", wordWrap: { width: W - 40 } })).setOrigin(0.5)
        .setResolution(2).setDepth(18);
      await this.decode(this._toast, str, 440);
      await this.w(hold || 1400);
      await this.decodeOut(this._toast, 480);
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
      this.floatAt({ x: s.x, y: s.y - 30 }, str, red);
    }
    floatAt(pt, str, red) {
      const t = this.add.text(pt.x, pt.y, str, style(20, red ? "#c8102e" : "#ffffff")).setOrigin(0.5)
        .setResolution(2).setDepth(15).setName("fx");
      this.tweens.add({ targets: t, y: pt.y - 50, alpha: 0, duration: 950, onComplete: () => t.destroy() });
    }
    async stampSeat(id, str, red) {
      const s = this.seats.get(id); if (!s) return;
      s.stamp.setText(str).setColor(red ? "#c8102e" : "#ffffff").setVisible(true).setScale(1.6).setAlpha(0);
      const hw = s.stamp.width * 0.9 + 6;                     // clamp at peak entrance scale (1.6 + overshoot)
      s.stamp.x = Math.min(Math.max(s.x, hw), W - hw);
      this.tweens.add({ targets: s.stamp, scale: 1, alpha: 1, duration: 190, ease: "Back.easeOut" });
      await this.w(900);
      if (str !== "BURNED") { this.tweens.add({ targets: s.stamp, alpha: 0, duration: 400 }); await this.w(400);
        s.stamp.setVisible(false).setAlpha(1); }
    }
    _pt(p) { return typeof p === "object" ? p : this.seatXY(p); }
    _short(a, b0) {                                           // stop 70px before the seat — clear of the tile
      const len = Math.hypot(b0.x - a.x, b0.y - a.y) || 1;
      const t = Math.max(0.3, 1 - 70 / len);
      return { x: a.x + (b0.x - a.x) * t, y: a.y + (b0.y - a.y) * t };
    }
    async cardBack(from, to) {                                // ONE generic card-back (D16/M9/M26)
      const a = this._pt(from), b0 = this._pt(to);
      const b = this._short(a, b0);                           // stop SHORT of the
      const c = this.add.rectangle(a.x, a.y, 22, 30, 0x000000).setStrokeStyle(2, WHITE, 0.95).setDepth(15);
      const dot = this.add.rectangle(a.x, a.y, 6, 6, 0xffffff).setDepth(16);     // seat — never covers a face
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
      const a = this._pt(from); let b = this._pt(to);
      if (typeof to === "number") b = this._short(a, b);      // seat target: stop SHORT — never cover a face
      // route: kit legs go down the CENTER AISLE (x=CX), never across a seat cluster
      const AISLE = { x: CX, y: 716 }, near = (p, q) => Math.abs(p.x - q.x) + Math.abs(p.y - q.y) < 130;
      const kit = this._kitXY;
      let path = [b];
      if (near(b, kit)) {
        b = { x: kit.x, y: kit.y - 52 };                      // drop-point ABOVE the case, not on it
        path = (near(a, { x: CX, y: CY }) ? [AISLE, b] : [{ x: CX, y: CY }, AISLE, b]);
      }
      else if (near(a, kit)) path = (near(b, { x: CX, y: CY }) ? [AISLE, b] : [AISLE, { x: CX, y: CY }, b]);
      const ic = this.add.image(a.x, a.y, "icons", idx).setScale(2.4).setDepth(15).setName("fx");
      const t = label ? this.add.text(a.x, a.y + 28, label, style(13)).setOrigin(0.5).setResolution(2)
        .setDepth(15).setName("fx") : null;
      if (t) this.tweens.add({ targets: t, alpha: 0, delay: 320, duration: 200 });  // gone before landing
      let px = a.x, py = a.y;
      const total = path.reduce((s, p) => { const d = Math.hypot(p.x - px, p.y - py); px = p.x; py = p.y; return s + d; }, 0);
      px = a.x; py = a.y;
      for (const p of path) {
        const dur = Math.max(120, 550 * Math.hypot(p.x - px, p.y - py) / (total || 1));
        const seg = [this.tweens.add({ targets: ic, x: p.x, y: p.y, duration: dur, ease: "Linear" })];
        if (t) this.tweens.add({ targets: t, x: p.x, y: p.y + 28, duration: dur, ease: "Linear" });
        await new Promise((r) => seg[0].once("complete", r));
        px = p.x; py = p.y;
      }
      this.tweens.add({ targets: t ? [ic, t] : ic, alpha: 0, duration: 260,
        onComplete: () => { ic.destroy(); if (t) t.destroy(); } });
    }
    _arrowTo(id) {                                            // simple arrow above the current seat
      const s = this.seats.get(id); if (!s) return;
      if (!this._arrow) {
        this._arrow = this.add.triangle(0, 0, 0, 0, 18, 0, 9, 14, WHITE).setDepth(9);
        this._arrowTween = this.tweens.add({ targets: this._arrow, y: "+=6", yoyo: true,
          repeat: -1, duration: 420, ease: "Sine.easeInOut" });
      }
      this._arrow.setVisible(true);
      this._arrowTween.stop();
      this._arrow.setPosition(s.x, s.y - 86);                 // above the chip stack, never on it
      this._arrowTween = this.tweens.add({ targets: this._arrow, y: "+=6", yoyo: true,
        repeat: -1, duration: 420, ease: "Sine.easeInOut" });
    }
    dialTo(id) {                                              // turn indicator = the arrow moves
      const s = this.seats.get(id); if (!s) return Promise.resolve();
      this.seats.forEach((q) => q.tile.setStrokeStyle(q.tk, WHITE, q.id === id ? 1 : 0.55));
      this._arrowTo(id);
      return this.w(280);
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
      this.seats.forEach((s) => { s.plate.setFillStyle(0x000000);
        s.nameT.setColor("#ffffff").setStroke("#000000", 6);
        s.plate.setStrokeStyle(3, WHITE, 0.95); s.tile.setStrokeStyle(3, WHITE, 0.55); s.tk = 3; });
    }

    /* ---- dice ceremony (M2 full / M16 fast) — counters + transient loading cylinder ---- */
    async diceCeremony(total, live, opts) {
      opts = opts || {};
      const sp = opts.fast ? 0.5 : 1;
      this.dim(true);                                          // dark overlay — animation plays over the board
      if (opts.honor) { await this.toast("IN THEIR HONOR", 900 * sp); await this.w(520); }  // let it fade fully
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
        await this.w(200 * sp);
        cnt.t += h; cnt.l += l;                                // hi flies to TOTAL, lo to LIVE
        const fh = this.add.text(d1.x, d1.y, String(h), style(18)).setOrigin(0.5).setResolution(2).setName("fx"); layer.add(fh);
        const fl = this.add.text(d2.x, d2.y, String(l), style(18)).setOrigin(0.5).setResolution(2).setName("fx"); layer.add(fl);
        this.tweens.add({ targets: fh, x: 100, y: 150, alpha: 0, duration: 380 * sp,
          onComplete: () => { fh.destroy(); tT.setText("TOTAL " + cnt.t); } });
        this.tweens.add({ targets: fl, x: 290, y: 150, alpha: 0, duration: 380 * sp,
          onComplete: () => { fl.destroy(); lT.setText("LIVE " + cnt.l); } });
        await this.w(300 * sp);
      }
      tT.setText("TOTAL " + total); lT.setText("LIVE " + live);
      await this.w(450 * sp);
      // dice exit before the cylinder enters — one actor on stage at a time
      await new Promise((r) => this.tweens.add({ targets: [d1.g, d2.g], alpha: 0, duration: 220 * sp, onComplete: r }));
      // transient loading-cylinder: bores fill one-by-one, spin-shuffle decelerates, fade (a11-safe)
      const lc = this.add.container(CX, CY - 60).setDepth(18); layer.add(lc);   // center-stage, big
      const lg = this.add.graphics(); lc.add(lg);
      lg.lineStyle(3, WHITE, 0.95).strokeCircle(0, 0, 72);
      const bores = Math.min(total, 16), per = Math.max(25, 700 / bores) * sp;
      for (let i = 0; i < bores; i++) {
        const a = -Math.PI / 2 + i * (Math.PI * 2 / bores);
        lg.fillStyle(0xffffff, 0.9).fillCircle(54 * Math.cos(a), 54 * Math.sin(a), 6);
        await this.w(per);
      }
      await new Promise((r) => this.tweens.add({ targets: lc, angle: 900, duration: 900 * sp,
        ease: "Cubic.easeOut", onComplete: r }));
      await new Promise((r) => this.tweens.add({ targets: layer, alpha: 0, duration: 350,
        onComplete: () => { layer.destroy(); r(); } }));
      if (!opts.keepDim) this.dim(false);
    }
    async announceHold(total, live) {                          // M3 — once, ~5s total, then never again (#3b=A)
      this.dim(true);
      const msg = total + " SHELLS · " + live + " LIVE";
      const t = this.add.text(W / 2, 200, "", style(24)).setOrigin(0.5)
        .setResolution(2).setDepth(19);
      await this.decode(t, msg, 700);
      await this.w(900);
      await this.decodeOut(t, 480);
      this.dim(false);                                         // board returns; the line moves to the band
      t.destroy();
      this.bandNote.setText(msg);
      await this.w(3400);
      if (this.bandNote.text === msg) this.bandNote.setText("");
    }

    /* ---- RADIAL (the dial): GTA-style ring menu; auto half/quarter arc near edges.
       items = [{icon, label, badge, bright, dim, onPick}] — icon = frame idx or null (label-only slot).
       opts = {title, sub, hubBright, onHub, onClose, sticky} — hub tap fires onHub. ---- */
    openRadial(cx, cy, items, opts) {
      this.closeRadial();
      opts = opts || {};
      const scrim = this.add.rectangle(W / 2, H / 2, W, H, 0x000000, 1).setDepth(21)
        .setInteractive().on("pointerdown", () => {
          if (!opts.sticky) { this.closeRadial(); if (opts.onClose) opts.onClose(); }
        });
      const cont = this.add.container(0, 0).setDepth(22);
      const dx = cx < 150 ? 1 : (cx > W - 150 ? -1 : 0);      // arc opens INTO the screen
      const dy = cy < 190 ? 1 : (cy > H - 190 ? -1 : 0);
      const N = items.length;
      let R, angles = [];
      if (!dx && !dy) {                                       // full circle, first slot at 12 o'clock
        R = Math.max(96, N * 62 / (Math.PI * 2));
        for (let i = 0; i < N; i++) angles.push(-Math.PI / 2 + i * Math.PI * 2 / N);
      } else {
        const c = Math.atan2(dy, dx);
        const span = (dx && dy) ? 1.85 : 3.3;                 // quarter-ish / half-ish
        R = Math.max(100, N * 66 / span);
        for (let i = 0; i < N; i++) angles.push(c - span / 2 + span * (i + 0.5) / N);
      }
      items.forEach((it, i) => {
        const x = cx + R * Math.cos(angles[i]), y = cy + R * Math.sin(angles[i]);
        const g = this.add.container(x, y);
        const c = this.add.circle(0, 0, 26, 0x000000)
          .setStrokeStyle(it.bright ? 3 : 2, WHITE, it.dim ? 0.3 : (it.bright ? 1 : 0.8))
          .setName("rslot");
        if (it.onPick && !it.dim) c.setInteractive().on("pointerdown", () => it.onPick(it, i));
        g.add(c);
        if (it.icon != null) {
          g.add(this.add.image(0, 0, "icons", it.icon).setScale(1.8).setAlpha(it.dim ? 0.35 : 1));
          if (it.label) g.add(this.add.text(0, 38, it.label, style(9, it.dim ? "#666666" : "#cccccc"))
            .setOrigin(0.5).setResolution(2));
        } else if (it.label) {
          g.add(this.add.text(0, 0, it.label, style(it.label.length > 5 ? 8 : 11,
            it.dim ? "#666666" : "#ffffff")).setOrigin(0.5).setResolution(2));
        }
        if (it.badge) g.add(this.add.text(24, -20, it.badge, style(10)).setOrigin(0.5)
          .setResolution(2).setBackgroundColor("#000000"));
        g.setScale(0);
        this.tweens.add({ targets: g, scale: 1, duration: 150, delay: i * 28, ease: "Back.easeOut" });
        cont.add(g);
      });
      const hubC = this.add.circle(cx, cy, 36, 0x000000)
        .setStrokeStyle(2, WHITE, opts.hubBright ? 1 : 0.85).setName("rhub");
      if (opts.onHub) hubC.setInteractive().on("pointerdown", () => opts.onHub());
      cont.add(hubC);
      if (opts.title) cont.add(this.add.text(cx, cy, opts.title,                 // wraps INSIDE the hub
        style(10, "#ffffff", { align: "center", wordWrap: { width: 60 } }))
        .setOrigin(0.5).setResolution(2));
      if (opts.sub) cont.add(this.add.text(cx, Math.min(cy + R + 58, H - 26), opts.sub,
        style(10, "#aaaaaa", { align: "center" })).setOrigin(0.5).setResolution(2)); // caption BELOW the ring
      this._radial = { scrim, cont };
      return this._radial;
    }
    closeRadial() {
      if (!this._radial) return;
      this._radial.scrim.destroy(); this._radial.cont.destroy();
      this._radial = null;
    }

    /* ---- CLICK-THREAD MENU (prototype under review — Skyrim/CoD list threads to replace dial chains).
     * mode: "stack" locked picks collapse to breadcrumb lines · "fade" lists stay, siblings fade
     *       · "cols" each step is a column. anim: "stagger" | "decode". All objects live at scene
     * root depth 22 (decode slots inherit txtObj.depth — containers would strand them behind the scrim). */
    openThread(opts) {
      this.closeRadial(); this.closeThread();
      opts = opts || {};
      const mode = opts.mode || "stack", anim = opts.anim || "stagger";
      const own = [];                                          // everything the thread ever draws
      const mk = (o) => { own.push(o); return o; };
      const scrim = mk(this.add.rectangle(W / 2, H / 2, W, H, 0x000000, 0.88).setDepth(21).setInteractive());
      const title = mk(this.add.text(W / 2, mode === "fade" ? 58 : 86, "", style(15))
        .setOrigin(0.5).setResolution(2).setDepth(22).setLetterSpacing(3));
      this.decode(title, opts.title || "", 340);
      mk(this.add.rectangle(W / 2, (700 + H) / 2, W, H - 700, 0x000000, 1).setDepth(21));  // dock blackout
      const abort = mk(this.add.text(W / 2, 776, "✕ ABORT", style(12, "#aaaaaa")).setOrigin(0.5)
        .setResolution(2).setDepth(22).setInteractive()
        .on("pointerdown", () => { this.closeThread(); if (opts.onAbort) opts.onAbort(); }));
      const arrowWas = this._arrow && this._arrow.visible;     // board bleed-through garbles thread copy
      if (arrowWas) this._arrow.setVisible(false);
      const th = { steps: 0, cursorY: 96, active: null, own, scrim, abort, arrowWas };
      const colX = (k) => 52 + k * 96;

      th.list = (key, header, items) => {                      // render the ACTIVE list
        const st = { key, header, items, rows: [], hits: [] };
        let hx = W / 2, hy, rowH, fs;
        if (mode === "stack") { hy = 150 + th.steps * 30 + 14; rowH = 48; fs = 15; }
        else if (mode === "fade") { hy = th.cursorY; rowH = 44; fs = 14; }
        else { hx = colX(th.steps); hy = 128; rowH = 30; fs = 9; header = key; }
        st.headT = mk(this.add.text(hx, hy, header, style(mode === "cols" ? 9 : 10, "#aaaaaa"))
          .setOrigin(0.5).setResolution(2).setDepth(22).setLetterSpacing(2).setAlpha(0));
        this.tweens.add({ targets: st.headT, alpha: 1, duration: 140 });
        const proms = [];
        items.forEach((it, i) => {
          const y = hy + 34 + i * rowH;
          const txt = it.badge ? it.label + "  " + it.badge : it.label;
          const col = it.dim ? "#ffffff" : (it.bright ? "#ffffff" : "#cccccc");
          const t = mk(this.add.text(hx, y, "", style(fs, col)).setOrigin(0.5).setResolution(2).setDepth(22));
          if (it.dim) t.setAlpha(0.3);
          if (anim === "decode" && !it.dim) {
            proms.push(new Promise((r) => this.time.delayedCall(i * 60, () =>
              this.decode(t, txt, 260).then(r))));
          } else {
            t.setText(txt);
            const tx = mode === "cols"                         // keep column text on-screen
              ? Math.min(Math.max(hx, t.width / 2 + 4), W - t.width / 2 - 4) : hx;
            t.setX(tx - 26).setAlpha(0);
            proms.push(new Promise((r) => this.tweens.add({ targets: t, x: tx, alpha: it.dim ? 0.3 : 1,
              duration: 150, delay: i * 25, ease: "Cubic.easeOut", onComplete: r })));
          }
          const hit = mk(this.add.rectangle(hx, y, mode === "cols" ? 92 : W - 60, rowH - 4, 0xffffff, 0.001)
            .setDepth(22));
          if (!it.dim) hit.setInteractive().on("pointerdown", () => th.onRow && th.onRow(i));
          st.rows.push({ t, it }); st.hits.push(hit);
        });
        th.active = st;
        return Promise.all(proms);
      };

      th.lock = async (i) => {                                 // pick row i → lock it, retire the list
        const st = th.active; if (!st) return;
        const pick = st.rows[i];
        st.hits.forEach((h) => h.disableInteractive());
        const flash = mk(this.add.rectangle(pick.t.x, pick.t.y, pick.t.width + 22, pick.t.height + 4, 0xffffff)
          .setDepth(22));
        this.children.bringToTop(pick.t);
        pick.t.setColor("#000000").setStroke("#ffffff", 6);    // invert while the flash bar is under it
        await this.w(150);
        this.tweens.add({ targets: flash, alpha: 0, duration: 130, onComplete: () => flash.destroy() });
        pick.t.setColor("#ffffff").setStroke("#000000", 6);
        const others = st.rows.filter((_, k) => k !== i).map((r) => r.t);
        if (mode === "stack") {                                // picked row rises into the breadcrumb line
          const cy = 138 + th.steps * 30;
          this.tweens.add({ targets: others.concat([st.headT]), alpha: 0, duration: 150 });
          await new Promise((r) => this.tweens.add({ targets: pick.t, x: W / 2, y: cy, scale: 12 / 15,
            duration: 240, ease: "Cubic.easeInOut", onComplete: r }));
          pick.t.destroy();
          mk(this.add.text(W / 2, cy, st.key + " ▸ " + pick.it.label, style(12))
            .setOrigin(0.5).setResolution(2).setDepth(22));
          others.concat([st.headT]).forEach((o) => o.destroy());
        } else if (mode === "fade") {                          // list compresses in place, siblings ghost
          const base = st.headT.y + 22;
          st.headT.setAlpha(0.55).setScale(0.85);
          st.rows.forEach((r, k) => {
            r.t.setText((k === i ? "▸ " : "") + r.t.text);
            this.tweens.add({ targets: r.t, y: base + k * 24, scale: 0.72,
              alpha: k === i ? 1 : (r.it.dim ? 0.15 : 0.25), duration: 220, ease: "Cubic.easeInOut" });
          });
          th.cursorY = base + st.rows.length * 24 + 20;
          await this.w(240);
        } else {                                               // cols: the column dims, pick stays lit
          st.headT.setAlpha(0.4);
          st.rows.forEach((r, k) => {
            if (k === i) { r.t.setText("▸ " + r.t.text);
              r.t.setX(Math.min(Math.max(r.t.x, r.t.width / 2 + 4), W - r.t.width / 2 - 4)); }
            this.tweens.add({ targets: r.t, alpha: k === i ? 1 : (r.it.dim ? 0.12 : 0.3), duration: 200 });
          });
          await this.w(220);
        }
        st.hits.forEach((h) => h.destroy());
        th.steps++; th.active = null;
      };

      th.close = () => this.closeThread();
      this._thread = th;
      return th;
    }
    closeThread() {
      if (!this._thread) return;
      const t = this._thread;
      this._thread = null;
      t.own.forEach((o) => { if (o && o.destroy) o.destroy(); });
      if (t.arrowWas && this._arrow) this._arrow.setVisible(true);
    }
    setAction(label, on) {                                    // the center hub's face
      this.actionT.setText(label || "· · ·").setColor(on ? "#ffffff" : "#888888");
      this.actionHub.setStrokeStyle(on ? 3 : 2, WHITE, on ? 1 : 0.9);
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
    seatGlow(ids, on, onTap) {                                 // M26 — MARCHING ANTS dotted frame.
      this._glows.forEach((o) => { o.ev.remove(); o.g.destroy(); if (o.hit) o.hit.destroy(); });
      this._glows = [];                                        // WHITE + tap — never red (trade ≠ danger)
      if (!on) return;
      ids.forEach((id) => {
        const s = this.seats.get(id); if (!s) return;
        const g = this.add.graphics().setDepth(11);
        const HALF = 47, DASH = 9, GAP = 7, PERIM = 8 * HALF;
        let phase = 0;
        const pt = (d) => {                                    // walk the square perimeter
          d = ((d % PERIM) + PERIM) % PERIM;
          if (d < 2 * HALF) return [s.x - HALF + d, s.y - HALF];
          if (d < 4 * HALF) return [s.x + HALF, s.y - HALF + (d - 2 * HALF)];
          if (d < 6 * HALF) return [s.x + HALF - (d - 4 * HALF), s.y + HALF];
          return [s.x - HALF, s.y + HALF - (d - 6 * HALF)];
        };
        const draw = () => {
          g.clear().lineStyle(3, WHITE, 0.95);
          for (let d = phase; d < phase + PERIM; d += DASH + GAP) {
            g.beginPath();
            const [x0, y0] = pt(d); g.moveTo(x0, y0);
            for (let k = 2; k <= DASH; k += 2) { const [x, y] = pt(d + k); g.lineTo(x, y); }
            g.strokePath();
          }
          phase = (phase + 2) % (DASH + GAP);
        };
        draw();
        const ev = this.time.addEvent({ delay: 70, loop: true, callback: draw });
        let hit = null;
        if (onTap) hit = this.add.rectangle(s.x, s.y, 94, 94, 0xffffff, 0.001).setDepth(11)
          .setInteractive().on("pointerdown", () => onTap(id));
        this._glows.push({ g, ev, hit });
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
      this.add.rectangle(W / 2, H / 2, W, H, 0x000000, 1).setDepth(24);
      this.add.image(W / 2, 330, "faces", id % 12).setScale(6).setDepth(25);
      this.add.text(W / 2, 470, "LAST AGENT STANDING", style(16)).setOrigin(0.5).setResolution(2)
        .setDepth(25).setLetterSpacing(2);
      const t2 = this.add.text(W / 2, 505, "", style(26)).setOrigin(0.5)
        .setResolution(2).setDepth(25);
      this.add.text(W / 2, 810, THEME.CREDITS, style(13, "#888888")).setOrigin(0.5).setResolution(2).setDepth(25);
      await this.decode(t2, THEME.seatName(id, roster), 700);
    }

    /* ---- ACTION STRIP: verb buttons drawn on demand (used from Task 7) ---- */
    setStrip(defs) {                                           // defs = [{label, onTap, wide}]
      this.strip.removeAll(true);
      if (!defs || !defs.length) return;
      const L = 80, R = 310;                                   // free zone between LEDGER and KIT boxes
      let size = 13, texts, ws, total;
      do {                                                     // measure real glyphs; shrink till the row fits
        if (texts) texts.forEach((t) => t.destroy());
        texts = defs.map((d) => this.add.text(0, 760, d.label, style(size)).setOrigin(0.5).setResolution(2));
        ws = texts.map((t) => Math.max(36, Math.ceil(t.width) + 16));
        total = ws.reduce((a, b) => a + b, 0) + 8 * (defs.length - 1);
        size--;
      } while (total > R - L && size >= 10);
      let x = L + Math.max(0, (R - L - total) / 2);            // centered in the zone, never over a box
      defs.forEach((d, i) => {
        const w = ws[i];
        const r = this.add.rectangle(x + w / 2, 760, w, 44, 0x000000).setStrokeStyle(2, WHITE, 0.95)
          .setInteractive().on("pointerdown", () => d.onTap && d.onTap());
        texts[i].setPosition(x + w / 2, 760);
        this.strip.add([r, texts[i]]);
        x += w + 8;
      });
    }
  }

  function fmt(secs) {
    if (secs == null) return "";
    const s = Math.max(0, Math.ceil(secs));
    return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
  }

  SCENE.TableScene = TableScene; SCENE.W = W; SCENE.H = H; SCENE.RED = RED; SCENE.WHITE = WHITE;
  SCENE.CX = CX; SCENE.CY = CY;
  global.SCENE = SCENE;
})(typeof window !== "undefined" ? window : globalThis);

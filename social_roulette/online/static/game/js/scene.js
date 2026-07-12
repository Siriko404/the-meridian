/* TableScene — the dining car (spec §6.2). Layout is PARAMETRIC in seat count (D15).
 * Team = polarity (locked 2026-07-10): plates carry the team; frames are HAIRLINE 1px,
 * bloc A full alpha / bloc B half alpha. COVER = tally sticks above the avatar: 1-4 fat
 * slashes, the 5th CROSSES them (closed gate = the win-watch state); <=2 burns red.
 * Stick motion = PEN (ratified): draw-stroke in · snap out · slash close + pulse.
 * Turn = stroke brightness, never weight. Red 0xc8102e = DANGER ONLY (spec §8 list).
 * The center dial is a SEAT dial — one bore per seat, never tracks bullets (a11). */
(function (global) {
  "use strict";
  const W = 390, H = 844, RED = 0xc8102e, WHITE = 0xffffff;
  const READ = 1.6;   // beat-text pacing: decode slower + linger longer so EVERY player
                      // can read (user 2026-07-10). Menus keep their own fast timings.
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

      // ---- BURNING TIMER BAR (RATIFIED slash clock): ///// field drains L→R between two
      //      single ticket rules; digits FIXED center, black-outlined, riding the field;
      //      everything red in the last 30s; a 3-slash shimmer sweeps every 5s. ----
      const BARX = 18, BARW = W - 36, BARY = 34;
      this._bar = { x: BARX, y: BARY, w: BARW };
      this.barHatch = this.add.graphics().setDepth(5).setVisible(false);
      this.barPulse = this.add.graphics().setDepth(5);         // the loading-shimmer that rides the field
      this._hatchInfo = null;
      this.time.addEvent({ delay: 33, loop: true, callback: () => this._drawPulse() });
      this.barSecs = this.add.text(W / 2, BARY, "", style(20, "#ffffff", { strokeThickness: 8 }))
        .setOrigin(0.5).setResolution(2).setDepth(7).setLetterSpacing(1).setVisible(false);
      this.bandLine2 = this.add.text(W / 2, BARY + 34, "", style(13, "#aaaaaa")).setOrigin(0.5).setResolution(2).setDepth(6).setLetterSpacing(2);
      this.bandCode = this.add.text(W - 6, 2, "", style(11, "#777777")).setOrigin(1, 0).setResolution(2).setDepth(7);
      this.bandNote = this.add.text(W / 2, BARY + 54, "", style(12, "#cccccc", { align: "center",
        wordWrap: { width: W - 24 } })).setOrigin(0.5, 0).setResolution(2).setDepth(6).setLetterSpacing(1);

      // ---- DOCK: three circular hubs (the dial idiom) + a chat ticker row ----
      this.add.line(0, 0, 12, 700, W - 12, 700, WHITE, 0.5).setOrigin(0).setDepth(6);
      this.scanChip = this.add.container(W / 2, 716).setDepth(6).setVisible(false);
      this.scanBg = this.add.rectangle(0, 0, 128, 24, 0x000000).setStrokeStyle(2, WHITE, 0.9);
      this.scanT = this.add.text(0, 0, "", style(12)).setOrigin(0.5).setResolution(2);
      this.scanChip.add([this.scanBg, this.scanT]);
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
    setPortraits(map) {                                     // seat -> face frame (papers, spec §2);
      if (!map) return;                                     // JSON stringifies the keys
      this._portraits = {};
      Object.keys(map).forEach((k) => { this._portraits[+k] = map[k]; });
    }
    _pmap(id) {
      return this._portraits && this._portraits[id] != null ? this._portraits[id] : id % 12;
    }
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
        const face = this.add.image(x, y, "faces", this._pmap(id)).setScale(2); // faces SACRED — no tint ever
        // PLATE (ratified M2): A = black serif in a slim white box · B = white serif
        // between two thin rules · dead = bare gray + strike. Art lives in plateG.
        const plateG = this.add.graphics().setDepth(2);
        const nameT = this.add.text(x, y + 61, "", style(12, "#ffffff")).setOrigin(0.5)
          .setResolution(2).setLetterSpacing(2).setDepth(3);
        // COVER dots (#5, punch card): 5 dots right of the frame, painted per-frame
        // by update(); a hit punches a dot into a lasting ring; full 5 pulses (win-watch).
        const dots = [...Array(5)].map(() => ({ on: false, t: 0, alpha: 1 }));
        const chipG = this.add.graphics().setDepth(7);        // ⊘ / ! boxes, LEFT of the frame
        const stamp = this.add.text(x, y, "", style(16, "#ffffff")).setOrigin(0.5).setResolution(2)
          .setAngle(-12).setDepth(8).setVisible(false).setBackgroundColor("#000000").setName("stamp");
        this.seats.set(id, { id, x, y, i, tile, broken, face, plateG, nameT, chipG, chipObjs: [], stamp,
          tk: 1, fa: 1, dots, shown: 0, cover: 0, dead: false, q: Promise.resolve() });
      });
      if (!this.dotG) this.dotG = this.add.graphics().setDepth(7);
      this.buildDial(n);
      this.built = true;
    }

    buildDial() {                                             // cylinder dial REMOVED (review); turn = active-seat frame.
      this.center = this.add.container(CX, CY).setDepth(4);   // empty anchor kept for POISON/MAGNET effects
      // POISON ARMED chip, table center while a poison round is chambered (M20 — red: danger)
      this.poisonChip = this.add.text(CX, CY, "POISON ARMED", style(13, "#c8102e")).setOrigin(0.5)
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
      view.players.forEach((p) => this.paintSeat(p, view, roster));
      if (view.winner == null) this.dialTo(view.current, false);
      this.setScan(view.scan);
      this.setPoisonChip(!!view.poison_armed);
      this.bandCode.setText(this._code || "");
    }

    paintSeat(p, view, roster, live) {                        // ONE seat's full state — choreo repaints
      const s = this.seats.get(p.id); if (!s) return;         // per BEAT (live=true: never move the arrow)
      const eq = !view.teams_active;                          // M27: agencies dissolved — equalize
      const tm = THEME.TEAMS[p.team] || THEME.TEAMS.RED;
      s.tk = 1; s.fa = eq ? 1 : (tm.fa != null ? tm.fa : 1);  // hairline; B-team = half alpha
      this.repaintPlate(s, THEME.seatName(p.id, roster),
        !p.alive ? "dead" : (eq ? "bare" : (tm.plate === 0xffffff ? "box" : "rules")));
      s.dead = !p.alive;
      this.syncCover(s, p.alive ? p.cover : 0, !!live);       // dots animate on live beats only
      this.setChips(s, p, roster);
      const active = p.alive && p.id === view.current && view.winner == null;
      s.tile.setStrokeStyle(1, WHITE, (active ? 1 : 0.55) * s.fa);
      s.face.setFrame(this._pmap(p.id));                      // papers may arrive after layout
      s.face.setScale(2);                                     // uniform — turn is shown by the ARROW only
      if (active && !live) this._arrowTo(p.id);
      if (!p.alive) {                                         // M14 end-state (the beat itself is choreo)
        s.tile.setVisible(false); s.broken.setVisible(true);
        s.face.setAlpha(0.35);                                // whole-object fade — pixels untouched
        s.stamp.setText("BURNED").setColor("#c8102e").setVisible(true);
      } else {
        s.tile.setVisible(true); s.broken.setVisible(false);
        s.face.setAlpha(1);
        if (s.stamp.text === "BURNED") s.stamp.setVisible(false);
      }
    }

    /* PLATE art (ratified M2: gap 22, pad 5): box (team A) · rules (team B) ·
     * bare (FFA — team semantics ended) · dead (gray + strike). */
    repaintPlate(s, nm, mode) {
      const g = s.plateG, ny = s.y + 61;
      g.clear();
      s.nameT.setText(nm).setY(ny);
      if (mode === "dead") {
        s.nameT.setColor("#666666").setStroke("#000000", 5);
        g.lineStyle(1, WHITE, 0.7);
        g.lineBetween(s.x - s.nameT.width / 2, ny, s.x + s.nameT.width / 2, ny);
        return;
      }
      const w2 = 39, h2 = 13;                                 // plate spans the avatar frame width
      if (mode === "box") {                                   // A: black serif in a slim white box
        s.nameT.setColor("#000000").setStroke("#ffffff", 0);
        g.fillStyle(0xffffff, 1).fillRect(s.x - w2, ny - h2, w2 * 2, h2 * 2);
      } else {
        s.nameT.setColor("#ffffff").setStroke("#000000", 5);
        if (mode === "rules") {                               // B: white serif between two thin rules
          g.lineStyle(1, WHITE, 0.9);
          g.lineBetween(s.x - w2, ny - h2, s.x + w2, ny - h2);
          g.lineBetween(s.x - w2, ny + h2, s.x + w2, ny + h2);
        }                                                     // bare: nothing — name alone
      }
    }

    /* CHIPS (ratified): boxed glyphs LEFT of the frame — ⊘ (sedated) above ! (dirt);
     * every dirt-placer's monogram stacks under the !. 16px boxes: the leftmost ring
     * seat sits at x≈53, so the column must stay inside the screen. */
    setChips(s, p, roster) {
      const g = s.chipG;
      g.clear();
      s.chipObjs.forEach((o) => o.destroy());
      s.chipObjs = [];
      if (!p.alive) return;
      const dirt = (p.immune_from || []).map((c) => THEME.seatName(c, roster));
      const bx = s.x - 39 - 5 - 8;                            // 5px gap — the leftmost ring seat
                                                              // (x≈60) stays on-screen
      let cy = s.y - 22;
      if (p.shaken) {                                     // bare glyphs, no boxes (ratified)
        g.lineStyle(2, WHITE, 1).strokeCircle(bx, cy, 7);
        g.lineBetween(bx - 5, cy + 5, bx + 5, cy - 5);
        cy += 25;                                             // air between the chips
      }
      if (dirt.length) {
        s.chipObjs.push(this.add.text(bx, cy - 1, "!", style(15, "#ffffff"))
          .setOrigin(0.5).setResolution(2).setDepth(8));
        cy += 17;
        dirt.forEach((n) => {
          const t = this.add.text(bx, cy, n, style(9.6, "#ffffff"))   // 80% of the plate name
            .setOrigin(0.5, 0).setResolution(2).setDepth(8);
          s.chipObjs.push(t);
          cy += t.height + 3;
        });
      }
    }

    /* ============ cover dots (#5 — punch card, lab-ratified) ============
     * +1 stamps a dot in · a hit punches it into a lasting faint ring ·
     * <=2 red · full 5 = pulse A: dots dip to a lighter shade one by one,
     * bottom→top, continuous (the win-watch tell). */
    _tw(obj, props, dur, ease) {
      return new Promise((r) => this.tweens.add({ targets: obj, ...props, duration: dur,
        ease: ease || "Linear", onComplete: r }));
    }
    syncCover(s, n, animate) {
      if (!animate || !this.sys.isActive()) {                 // settle/reconnect: no theater
        s.cover = n; s.shown = n;
        s.dots.forEach((q, k) => Object.assign(q, { on: k < n, t: k < n ? 1 : 0, alpha: 1 }));
        return;
      }
      if (n === s.cover) return;
      s.cover = n;
      s.q = s.q.then(() => this._walkCover(s)).catch(() => {});
    }
    async _walkCover(s) {                                     // one dot at a time toward target
      while (s.shown !== s.cover) {
        if (s.shown < s.cover) {
          s.shown++;
          const q = s.dots[s.shown - 1];
          Object.assign(q, { on: true, t: 0, alpha: 1 });
          await this._tw(q, { t: 1 }, 170, "Back.easeOut");   // the stamp
        } else {
          const q = s.dots[s.shown - 1];
          await this._tw(q, { alpha: 0.25 }, 60);             // the punch…
          Object.assign(q, { on: false, t: 0, alpha: 1 });    // …the hole remains
          s.shown--;
        }
      }
    }
    clearSticks(id) {                                         // death: the card is void (M14)
      const s = this.seats.get(id); if (!s) return;
      s.dead = true;
      this.syncCover(s, 0, false);
    }
    _paintDots(g, s, pulseT) {
      const px = s.x + 39 + 6 + 3;                            // 6px gap + dot radius
      const yBot = s.y + 24;
      const col = s.shown <= 2 ? RED : WHITE;
      for (let k = 0; k < 5; k++) {
        const q = s.dots[k], cy = yBot - k * 12;
        if (q.on) {
          const grow = Math.min(1, q.t * 1.6);
          const sc = q.t < 1 ? (1.5 - 0.5 * q.t) : 1;
          let a = q.alpha;
          if (s.shown === 5) {                                // pulse A: the climbing dip
            const t = pulseT % 1;
            const d = Math.abs(t * 6 - 0.5 - k);
            a *= 1 - Math.max(0, 1 - d * 1.4) * 0.75;
          }
          g.fillStyle(col, a).fillCircle(px, cy, 3 * sc * grow);
        } else {
          g.lineStyle(1, WHITE, 0.30);                        // the punched hole
          g.strokeCircle(px, cy, 3);
        }
      }
    }
    update(_, dt) {                                           // dot layer repaint (cheap: <=25 marks)
      const g = this.dotG; if (!g) return;
      this._pulseT = (this._pulseT || 0) + (dt || 16) / 1800;
      g.clear();
      this.seats.forEach((s) => { if (!s.dead) this._paintDots(g, s, this._pulseT); });
    }

    /* ================= band ================= */
    setBand(o) {                                              // burning bar: one 90s burn, white 60s -> red 30s
      this._bandO = o;                                        // remembered — a menu opening mid-tick
      const TALK = 60, DEC = 30, TOTAL = TALK + DEC;          // paints its burn-circle immediately
      let left = null;
      // HONEST digits (timer-freeze class, 2026-07-11): the server pads phase_ends_at
      // with a beat grace — clamping here pinned the display at 0:30/1:30, frozen, for
      // the whole grace. Digits now count the real remaining; only the bar GEOMETRY caps.
      if (o.phase === "talk" && o.secs != null) left = DEC + o.secs;
      else if ((o.phase === "decision" || o.phase === "tax" || o.phase === "aiming") && o.secs != null) left = o.secs;
      if (left != null) {
        const red = o.invert || left <= DEC, col = red ? RED : WHITE;  // decision family is ALWAYS red
        const fw = this._bar.w * (Math.min(left, TOTAL) / TOTAL);
        const bx = this._bar.x, by = this._bar.y;
        const g = this.barHatch.setVisible(true);
        g.clear();
        const hh = 14, pitch = 7, lean = 8, edge = bx + fw;
        for (let x = bx + 4; x + lean <= edge; x += pitch) {   // the field runs BEHIND the digits —
          g.lineStyle(2, col, 0.45);                           // their black outline cuts them free,
          g.lineBetween(x, by + hh, x + lean, by - hh);        // and the burn edge crosses in view
        }
        g.lineStyle(2, col, 0.95);                             // ticket rules, SINGLE, no box
        [-20, 20].forEach((dy) => g.lineBetween(bx, by + dy, bx + this._bar.w, by + dy));
        this._hatchInfo = { fw, col };                         // the shimmer sweep reads this
        this.barSecs.setVisible(true).setText(fmt(left)).setX(W / 2)   // fixed digits OVER the field
          .setColor(red ? "#c8102e" : "#ffffff").setStroke("#000000", 8);
        this.bandCode.setVisible(false);                      // code only rides an idle band
      } else {
        this.barHatch.setVisible(false);
        this._hatchInfo = null; this.barPulse.clear();
        this.barSecs.setVisible(false);
        this.bandCode.setVisible(true);
      }
      this.bandLine2.setText(o.name || "");
      this.bandNote.setText(o.note || "");
      const th = this._thread;                                 // the menu's own burning circle —
      if (th && th._clock) {                                   // the player ALWAYS sees the timer
        if (left == null || th._picking) th._clock.cont.setVisible(false);  // (during a seat-pick
        else {                                                 // the duck reveals the big bar instead)
          const red = o.invert || left <= DEC, col = red ? RED : WHITE;
          th._clock.cont.setVisible(true);
          const g = th._clock.g, SEG = 24, R = 20;
          const lit = Math.ceil((Math.min(left, TOTAL) / TOTAL) * SEG);
          g.clear();
          for (let k = 0; k < SEG; k++) {                      // pixel-faceted ring of chords;
            const a0 = -Math.PI / 2 + (k * 2 * Math.PI) / SEG + 0.06;   // burned segments go dark
            const a1 = -Math.PI / 2 + ((k + 1) * 2 * Math.PI) / SEG - 0.06;
            g.lineStyle(4, col, k < lit ? 1 : 0.15);
            g.lineBetween(Math.cos(a0) * R, Math.sin(a0) * R, Math.cos(a1) * R, Math.sin(a1) * R);
          }
          th._clock.t.setText(fmt(left))                       // SAME digits as the big bar — in sync
            .setColor(red ? "#c8102e" : "#ffffff");
        }
      }
    }
    _drawPulse() {                                            // 3-slash shimmer, left → right every 5s —
      const g = this.barPulse;                                 // vintage loading-bar, mechanical linear ride
      if (!g) return;
      g.clear();
      const info = this._hatchInfo;
      if (!info || !info.fw) return;
      const PER = 5000, SWEEP = 1100;
      const el = this.time.now % PER;
      if (el > SWEEP) return;
      const bx = this._bar.x, by = this._bar.y;
      const hh = 14, pitch = 7, lean = 8;
      const edge = bx + info.fw;
      const head = bx + (info.fw + 3 * pitch) * (el / SWEEP) - 2 * pitch;
      for (let x = bx + 4; x + lean <= edge; x += pitch) {
        const d = Math.abs(x - head);
        if (d > pitch * 1.6) continue;                        // 3 slashes wide, comet-faded
        g.lineStyle(2, info.col, 1 - (d / (pitch * 1.6)) * 0.55);
        g.lineBetween(x, by + hh, x + lean, by - hh);
      }
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
        fontSize: st.fontSize, fontStyle: st.fontStyle }).setResolution(2).setVisible(false)
        .setLetterSpacing(txtObj.letterSpacing || 0);          // spaced text decodes true-to-width
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
            fontStyle: st.fontStyle, color: "#ffffff", stroke: st.stroke || "#000000", strokeThickness: 6 })
            .setOrigin(0.5).setResolution(2).setDepth(txtObj.depth).setName("fx")
            .setAlpha(txtObj.alpha);                           // dim texts decode dim
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
        const C = (txtObj.style && txtObj.style.color) || "#ffffff";   // resolve to the OWN color
        const slots = this._slots(txtObj, str), n = slots.length || 1, D = dur || 750;
        this._shuffled(n).forEach((r, i) => { slots[i].at = (r / n) * D; });
        const t0 = this.time.now;
        const ev = this.time.addEvent({ delay: 33, loop: true, callback: () => {
          if (!txtObj.scene) {                                 // target died mid-decode (menu closed)
            ev.remove(); slots.forEach((s) => s.t.destroy()); resolve(); return;
          }
          const el = this.time.now - t0;
          let done = true;
          for (const s of slots) {
            if (el >= s.at) { if (s.t.text !== s.ch) s.t.setText(s.ch).setColor(C); }
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
          if (!txtObj.scene) {                                 // target died mid-dissolve
            ev.remove(); slots.forEach((s) => s.t.destroy()); resolve(); return;
          }
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
      await this.decode(this._toast, str, 440 * READ);
      await this.w((hold || 1400) * READ);
      await this.decodeOut(this._toast, 480 * READ);
    }
    flashWhite() {
      const f = this.add.rectangle(W / 2, H / 2, W, H, 0xffffff).setDepth(20);
      this.time.delayedCall(60, () => f.destroy());
    }
    shake() { this.cameras.main.shake(140, 0.012); }
    seatRecoil(id) {
      const s = this.seats.get(id); if (!s) return;
      const parts = [s.tile, s.face, s.nameT];
      this.tweens.add({ targets: parts, x: "+=7", yoyo: true, repeat: 2, duration: 45 });
    }
    pipShatter(id, nDamage) {                                 // M12 — red particles (danger)
      const s = this.seats.get(id); if (!s) return;           // burst at the STICK row (#5)
      for (let k = 0; k < 10 * (nDamage || 1); k++) {
        const px = s.x - 18 + Math.random() * 36, py = s.y - 47;
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
      this.tweens.add({ targets: t, y: pt.y - 50, alpha: 0, duration: 950 * READ, onComplete: () => t.destroy() });
    }
    async stampSeat(id, str, red) {
      const s = this.seats.get(id); if (!s) return;
      const chips = [s.chipG, ...s.chipObjs];                 // the stamp owns the seat for its beat —
      chips.forEach((o) => o.setVisible(false));              // chips duck out (they return after)
      s.stamp.setY(s.y);
      s.stamp.setText(str).setColor(red ? "#c8102e" : "#ffffff").setVisible(true).setScale(1.6).setAlpha(0);
      const hw = s.stamp.width * 0.9 + 6;                     // clamp at peak entrance scale (1.6 + overshoot)
      s.stamp.x = Math.min(Math.max(s.x, hw), W - hw);
      this.tweens.add({ targets: s.stamp, scale: 1, alpha: 1, duration: 190, ease: "Back.easeOut" });
      await this.w(900 * READ);
      if (str !== "BURNED") { this.tweens.add({ targets: s.stamp, alpha: 0, duration: 400 }); await this.w(400);
        s.stamp.setVisible(false).setAlpha(1); }
      if (!s.dead) chips.forEach((o) => o.setVisible(true));  // dead seats keep no chips
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
      this._arrow.setVisible(!this._thread);                  // never over an open menu
      this._arrowTween.stop();
      this._arrow.setPosition(s.x, s.y - 86);                 // above the chip stack, never on it
      this._arrowTween = this.tweens.add({ targets: this._arrow, y: "+=6", yoyo: true,
        repeat: -1, duration: 420, ease: "Sine.easeInOut" });
    }
    dialTo(id) {                                              // turn indicator = the arrow moves
      const s = this.seats.get(id); if (!s) return Promise.resolve();
      this.seats.forEach((q) => q.tile.setStrokeStyle(q.tk, WHITE, (q.id === id ? 1 : 0.55) * (q.fa || 1)));
      this._arrowTo(id);
      return this.w(280);
    }
    async bulletEject() {                                      // M22: from the dial's CENTER AXIS (a11)
      const sh = this.add.rectangle(CX, CY, 8, 18, 0xffffff).setDepth(15);
      await new Promise((r) => this.tweens.add({ targets: sh, x: W + 40, y: CY - 160, angle: 260,
        duration: 600, ease: "Quad.easeOut", onComplete: r }));
      sh.destroy();
    }
    setScan(s) {                                              // M19 — own GEIGER census; red only on CERTAIN live
      const known = s && s.of > 0;
      this.scanChip.setVisible(!!known);
      if (known) {
        const certain = s.live === s.of && s.live > 0;        // all-live window → current IS live
        this.scanT.setText("NEXT " + s.of + " · " + s.live + " LIVE")
          .setColor(certain ? "#c8102e" : "#ffffff");
        this.scanBg.setStrokeStyle(2, certain ? RED : WHITE, 0.95);
      }
    }
    setPoisonChip(on) { if (this.poisonChip) this.poisonChip.setVisible(!!on); }
    setSeize(on, cb) {                                        // C2 - the HANDLER button
      if (!this.seizeBtn) {
        const c = this.add.container(66, 668).setDepth(9).setVisible(false);    // above the dock rail, clear of every hub
        c.add(this.add.circle(0, 0, 24, 0x000000).setStrokeStyle(2, WHITE, 0.95)
          .setInteractive().on("pointerdown", () => this._onSeize && this._onSeize()));
        c.add(this.add.text(0, 0, "SEIZE", style(9)).setOrigin(0.5).setResolution(2));
        this.seizeBtn = c;
      }
      this._onSeize = cb;
      this.seizeBtn.setVisible(!!on);
    }
    equalizePlates() {                                        // M27 — team semantics visibly end
      this.seats.forEach((s) => {
        if (!s.dead) this.repaintPlate(s, s.nameT.text, "bare");   // carriers vanish with the teams
        s.tile.setStrokeStyle(1, WHITE, 0.55);
        s.tk = 1; s.fa = 1; });
    }

    /* ---- HOLD AT SIGNAL (spec 2026-07-11 §4): a dropped agent freezes the car.
     * Full scrim (depth 19 — over the board, UNDER the thread menus so the
     * conductor's choice sheet still opens), serif in-world lines, wall-clock
     * digits fed by holdTick. White throughout — red stays danger-only. ---- */
    setHold(h, roster, onReady) {
      if (!h) {
        if (this._hold) { this._hold.own.forEach((o) => o.destroy()); this._hold = null; }
        return;
      }
      if (!this._hold) {
        const scrim = this.add.rectangle(W / 2, H / 2, W, H, 0x000000, 0.94)
          .setDepth(19).setInteractive();                    // absorbs board taps
        const l1 = this.add.text(W / 2, 330, "", style(16, "#ffffff",
          { align: "center", wordWrap: { width: W - 60 } })).setOrigin(0.5)
          .setResolution(2).setDepth(19).setLetterSpacing(1);
        const l2 = this.add.text(W / 2, 402, "", style(24)).setOrigin(0.5)
          .setResolution(2).setDepth(19);
        const l3 = this.add.text(W / 2, 452, "", style(11, "#aaaaaa")).setOrigin(0.5)
          .setResolution(2).setDepth(19).setLetterSpacing(2);
        this._hold = { own: [scrim, l1, l2, l3], l1, l2, l3, key: "" };
      }
      if (h.cold && !this._hold.rb && onReady) {             // the cold-car READY VOTE
        const rb = this.add.text(W / 2, 520, "✓ READY", style(15)).setOrigin(0.5)
          .setResolution(2).setDepth(19).setLetterSpacing(3)
          .setInteractive().on("pointerdown", () => onReady());
        this._hold.rb = rb;
        this._hold.own.push(rb);
      }
      const names = (h.missing || []).map((id) => THEME.seatName(id, roster));
      const ready = h.ready || {};
      const tally = Object.values(ready).filter(Boolean).length
        + "/" + Object.keys(ready).length;
      const key = names.join("·") + (h.expired ? "!" : "") + (h.cold ? tally : "");
      if (key !== this._hold.key) {
        this._hold.key = key;
        if (h.cold) {
          this.decode(this._hold.l1, "THE CAR WAS HELD AT SIGNAL OVERNIGHT", 420);
          this._hold.l3.setText("ALL ABOARD — VOTE READY · " + tally);
        } else {
          const who = (names.length > 1 ? "AGENTS " : "AGENT ") + names.join(" · ");
          this.decode(this._hold.l1, who + " LEFT THE CAR", 420);
          this._hold.l3.setText(h.expired ? "THE CONDUCTOR DECIDES" : "HOLDING AT SIGNAL");
        }
      }
    }
    holdTick(secs) {
      if (this._hold) this._hold.l2.setText(secs == null ? "" : fmt(secs));
    }
    async resumeBeat() {                 // 3·2·1 — release ships +3s for exactly this beat
      for (const d of ["3", "2", "1"]) {
        const t = this.add.text(W / 2, 390, "", style(30)).setOrigin(0.5)
          .setResolution(2).setDepth(19).setName("fx");
        await this.decode(t, d, 220);
        await this.w(420);
        t.destroy();
      }
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
      const msg = total + " BULLETS · " + live + " LIVE";
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

    /* ---- CLICK-THREAD MENU (RATIFIED — replaced the radial dial system entirely).
     * mode: "stack" locked picks collapse to breadcrumb lines · "fade" retired lists collapse to ONE crumb
     *       · "cols" each step is a column. anim: "stagger" | "decode". All objects live at scene
     * root depth 22 (decode slots inherit txtObj.depth — containers would strand them behind the scrim). */
    openThread(opts) {
      this.closeThread();
      opts = opts || {};
      const mode = opts.mode || "stack", anim = opts.anim || "stagger";
      const own = [];                                          // everything the thread ever draws
      const mk = (o) => { own.push(o); return o; };
      const scrim = mk(this.add.rectangle(W / 2, H / 2, W, H, 0x000000, 0.88).setDepth(21).setInteractive());
      const title = mk(this.add.text(W / 2, mode === "fade" ? 58 : 86, "", style(15))
        .setOrigin(0.5).setResolution(2).setDepth(22).setLetterSpacing(3));
      this.decode(title, opts.title || "", 340);
      const dockCover = mk(this.add.rectangle(W / 2, (700 + H) / 2, W, H - 700, 0x000000, 1).setDepth(21));
      const topCover = mk(this.add.rectangle(W / 2, 62, W, 124, 0x000000, 1).setDepth(21));  // the bar
      // sleeps behind this while the menu's own burn-circle carries the time (ducks reveal it again)
      const abort = mk(this.add.text(W / 2 + 80, 776, "", style(12, "#aaaaaa")).setOrigin(0.5)
        .setResolution(2).setDepth(22).setName("tabort"));
      this.decode(abort, opts.abortLabel || "✕ ABORT", 240).then(() => { if (abort.scene)
        abort.setInteractive()
          .on("pointerdown", () => { this.closeThread(); if (opts.onAbort) opts.onAbort(); }); });
      const backB = mk(this.add.text(W / 2 - 80, 776, "", style(12, "#aaaaaa")).setOrigin(0.5)
        .setResolution(2).setDepth(22).setAlpha(0.3).setName("tback"));
      this.decode(backB, "◂ BACK", 240).then(() => { if (backB.scene)
        backB.setInteractive()
          .on("pointerdown", () => { if (!th._act && th.steps && th.onBack) th.onBack(); }); });
      const arrowWas = this._arrow && this._arrow.visible;     // board bleed-through garbles thread copy
      if (arrowWas) this._arrow.setVisible(false);
      const clockC = mk(this.add.container(W / 2, 100).setDepth(22).setVisible(false));
      const clockG = this.add.graphics();                      // the menu burn-circle (fed by setBand)
      const clockT = this.add.text(0, 0, "", style(9, "#ffffff", { strokeThickness: 3 }))
        .setOrigin(0.5).setResolution(2);
      clockC.add([clockG, clockT]);
      const th = { steps: 0, cursorY: 96, active: null, own, scrim, abort, arrowWas, _sections: [],
        _clock: { cont: clockC, g: clockG, t: clockT } };
      const colX = (k) => 52 + k * 96;

      th.list = (key, header, items, fast) => {                // render the ACTIVE list
        const st = { key, header, items, rows: [], hits: [] };
        let hx = W / 2, hy, rowH, fs;
        if (mode === "stack") { hy = 150 + th.steps * 30 + 14; rowH = 48; fs = 15; }
        else if (mode === "fade") { hy = th.cursorY; rowH = items.length >= 6 ? 36 : 44; fs = 14; }
        else { hx = colX(th.steps); hy = 128; rowH = 30; fs = 9; header = key; }
        backB.setAlpha(th.steps ? 1 : 0.3);
        const off = header ? 34 : 14;
        const pitch = items.map((it) =>                        // per-row heights
          it.dot ? 38 : ((mode === "fade" && it.sub) ? 58 : rowH));
        const Hs = off + pitch.reduce((a, b) => a + b, 0);
        if (mode === "fade") {                                 // ACTIVE list rides screen center;
          const floor = 138 + th.steps * 22;                   // …but never under the burn-circle
          const targetHy = Math.max(floor, 384 - Hs / 2);      // or the crumb rail (2026-07-11 fix)
          if (!th._sections.length && !th.active) th.cursorY = targetHy;
          else if (Math.abs(targetHy - th.cursorY) > 4) th._slide(targetHy - th.cursorY);
          hy = th.cursorY;
        }
        st.baseY = th.cursorY; st.hy = hy;                     // AFTER centering — back() restores true
        if (header) {                                          // roots go headerless — the list IS the move
          st.headT = mk(this.add.text(hx, hy, "", style(mode === "cols" ? 9 : 10, "#aaaaaa"))
            .setOrigin(0.5).setResolution(2).setDepth(22).setLetterSpacing(2));
          this.decode(st.headT, header, fast ? 130 : 200);
        }
        if (opts.rules && mode === "fade") {                   // ticket double-rules framing the list
          const yTop = header ? hy + 18 : hy - (pitch[0] === 58 ? 16 : 8);
          const yBot = hy + Hs - pitch[pitch.length - 1] / 2 + 10;
          const rule = (yy) => { const g = this.add.graphics().setDepth(22).setAlpha(0);
            g.lineStyle(2, WHITE, 0.8);
            g.lineBetween(W / 2 - 120, yy, W / 2 + 120, yy);
            g.lineBetween(W / 2 - 120, yy + 4, W / 2 + 120, yy + 4);
            this.tweens.add({ targets: g, alpha: 1, duration: 300 });
            return mk(g); };
          st.rules = [rule(yTop), rule(yBot)];
        }
        const proms = [];
        let acc = 0;
        items.forEach((it, i) => {
          const y = hy + off + acc - (it.tight ? 8 : 0);
          const rh = pitch[i];
          acc += rh;
          if (it.dot) {                                        // divider dot — options above, buttons below
            const d = mk(this.add.text(hx, y + 4, "·", style(13, "#aaaaaa")).setOrigin(0.5)
              .setResolution(2).setDepth(22).setAlpha(0));
            this.tweens.add({ targets: d, alpha: 0.9, duration: 220 });
            const hit0 = mk(this.add.rectangle(hx, y, 10, 10, 0xffffff, 0.001).setDepth(22));
            st.rows.push({ t: d, it }); st.hits.push(hit0);
            return;
          }
          if (it.split) {                                      // two stat columns around a center dot
            const stat = (x) => mk(this.add.text(x, y, "", style(fs - 3, "#cccccc"))
              .setOrigin(0.5).setResolution(2).setDepth(22));
            const l = stat(hx - 85), d = stat(hx).setText("·").setAlpha(0), rr = stat(hx + 85);
            this.tweens.add({ targets: d, alpha: 1, duration: 140 });
            proms.push(this.decode(l, it.split[0], fast ? 130 : 220));
            proms.push(this.decode(rr, it.split[1], fast ? 130 : 220));
            const hit0 = mk(this.add.rectangle(hx, y, W - 60, rh - 4, 0xffffff, 0.001)
              .setDepth(22).setName("trow"));
            st.rows.push({ t: l, it, extra: [d, rr] }); st.hits.push(hit0);
            return;
          }
          const txt = it.badge ? it.label + "  " + it.badge : it.label;
          const col = it.info ? "#aaaaaa" : (it.dim ? "#ffffff" : (it.bright ? "#ffffff" : "#cccccc"));
          const t = mk(this.add.text(hx, y, "", style(it.info ? fs - 4 : fs, col))
            .setOrigin(0.5).setResolution(2).setDepth(22));
          if (it.dim) t.setAlpha(0.3);
          let subT = null;
          if (it.sub) {                                        // whisper caption under the verb
            subT = mk(this.add.text(hx, y + 20, "", style(8, "#aaaaaa", { strokeThickness: 4 }))
              .setOrigin(0.5).setResolution(2).setDepth(22).setLetterSpacing(1));
            if (it.dim) subT.setAlpha(0.3);
            proms.push(new Promise((r) => this.time.delayedCall(fast ? 0 : i * 60 + 90, () =>
              this.decode(subT, it.sub, fast ? 130 : 220).then(r))));
          }
          if (subT) t.setY(y - 6);                             // pair: verb up, whisper below
          if (anim === "decode" || fast) {                     // EVERY text decodes; swaps just decode FAST
            proms.push(new Promise((r) => this.time.delayedCall(fast ? 0 : i * 60, () =>
              this.decode(t, txt, fast ? 130 : 260).then(r))));
          } else {
            t.setText(txt);
            const tx = mode === "cols"                         // keep column text on-screen
              ? Math.min(Math.max(hx, t.width / 2 + 4), W - t.width / 2 - 4) : hx;
            t.setX(tx - 26).setAlpha(0);
            proms.push(new Promise((r) => this.tweens.add({ targets: t, x: tx, alpha: it.dim ? 0.3 : 1,
              duration: 150, delay: i * 25, ease: "Cubic.easeOut", onComplete: r })));
          }
          const hit = mk(this.add.rectangle(hx, y, mode === "cols" ? 92 : W - 60, rh - 4, 0xffffff, 0.001)
            .setDepth(22).setName("trow"));
          st.rows.push({ t, it, extra: subT ? [subT] : undefined }); st.hits.push(hit);
        });
        th.active = st;
        return Promise.all(proms).then(() => {                 // rows arm only once fully landed
          if (th.active !== st) return;
          st.rows.forEach((r, i) => {
            if (r.it.frame && r.t.scene) {                     // corner ticks around the default verb
              const g = this.add.graphics().setDepth(22);
              const hw = r.t.width / 2 + 18, hh = 19, x = r.t.x, y = r.t.y;
              [[-hw, -hh, 1, 1], [hw, -hh, -1, 1], [-hw, hh, 1, -1], [hw, hh, -1, -1]]
                .forEach(([dx, dy, sx, sy]) => {
                  g.lineStyle(2, WHITE, 0.95);
                  g.lineBetween(x + dx, y + dy, x + dx + sx * 10, y + dy);
                  g.lineBetween(x + dx, y + dy, x + dx, y + dy + sy * 8);
                });
              g.setAlpha(0); this.tweens.add({ targets: g, alpha: 1, duration: 200 });
              mk(g); (r.extra = r.extra || []).push(g);
            }
            if (r.it.dim || r.it.info || r.it.split || r.it.still || r.it.dot || !st.hits[i].scene) return;
            st.hits[i].setInteractive().on("pointerdown", () => {
              if (th._act || !th.onRow) return;                // double-tap guard: one action in flight
              th._act = true;
              Promise.resolve(th.onRow(i)).catch(() => {}).then(() => { th._act = false; });
            });
          });
        });
      };

      th.lock = async (i) => {                                 // pick row i → lock it, retire the list
        const st = th.active; if (!st) return;
        const pick = st.rows[i];
        st.hits.forEach((h) => h.disableInteractive());
        const deco = (st.rules || []).concat(...st.rows.map((r) => r.extra || []));
        st.rules = null; st.rows.forEach((r) => { r.extra = null; });   // dressings don't ghost
        deco.forEach((o) => this.tweens.add({ targets: o, alpha: 0, duration: 150,
          onComplete: () => o.destroy() }));
        const flash = mk(this.add.rectangle(pick.t.x, pick.t.y, pick.t.width + 22, pick.t.height + 4, 0xffffff)
          .setDepth(22));
        this.children.bringToTop(pick.t);
        pick.t.setColor("#000000").setStroke("#ffffff", 6);    // invert while the flash bar is under it
        await this.w(150);
        this.tweens.add({ targets: flash, alpha: 0, duration: 130, onComplete: () => flash.destroy() });
        pick.t.setColor("#ffffff").setStroke("#000000", 6);
        const others = st.rows.filter((_, k) => k !== i).map((r) => r.t)
          .concat(st.headT ? [st.headT] : []);
        if (mode === "stack") {                                // picked row rises into the breadcrumb line
          const cy = 138 + th.steps * 30;
          this.tweens.add({ targets: others, alpha: 0, duration: 150 });
          await new Promise((r) => this.tweens.add({ targets: pick.t, x: W / 2, y: cy, scale: 12 / 15,
            duration: 240, ease: "Cubic.easeInOut", onComplete: r }));
          pick.t.destroy();
          st.crumb = mk(this.add.text(W / 2, cy, st.key + " ▸ " + pick.it.label, style(12))
            .setOrigin(0.5).setResolution(2).setDepth(22));
          others.forEach((o) => o.destroy());
        } else if (mode === "fade") {                          // retire to ONE crumb line — ghosting
          const cy = 134 + th.steps * 22;                      // whole lists buried the next sheet
          if (st.headT) {                                      // (playtest photos, 2026-07-11)
            const h = st.headT; st.headT = null;
            this.tweens.add({ targets: h, alpha: 0, duration: 150, onComplete: () => h.destroy() });
          }
          st.rows.forEach((r, k) => {
            if (k === i) {
              r.t.setText((r.t.text.indexOf("▸") < 0 ? "▸ " : "") + r.t.text);
              r.t._pick = th.steps;                            // pinned on the crumb rail
              this.tweens.add({ targets: r.t, x: W / 2, y: cy, scale: 0.72, alpha: 1,
                duration: 220, ease: "Cubic.easeInOut" });
            } else {
              const o = r.t; r.t = null;
              this.tweens.add({ targets: o, alpha: 0, duration: 150, onComplete: () => o.destroy() });
            }
          });
          th.cursorY = cy + 22;
          await this.w(240);
        } else {                                               // cols: the column dims, pick stays lit
          if (st.headT) st.headT.setAlpha(0.4);
          st.rows.forEach((r, k) => {
            if (k === i) { r.t.setText("▸ " + r.t.text);
              r.t.setX(Math.min(Math.max(r.t.x, r.t.width / 2 + 4), W - r.t.width / 2 - 4)); }
            this.tweens.add({ targets: r.t, alpha: k === i ? 1 : (r.it.dim ? 0.12 : 0.3), duration: 200 });
          });
          await this.w(220);
        }
        st.hits.forEach((h) => h.destroy());
        th.steps++; th.active = null;
        th._sections.push(st);
        backB.setAlpha(1);
      };

      const FIXED = new Set([scrim, dockCover, topCover, abort, backB, clockC, title]);  // chrome never slides
      th._slide = (dy) => {                                    // move the whole trail (crumbs stay pinned)
        own.forEach((o) => {
          if (FIXED.has(o) || !o.scene || o.y == null) return;
          if (o._ba == null) o._ba = o.alpha;                  // remember the resting alpha
          if (o._oy == null) o._oy = o.y;                      // and the home position
          o._ty = (o._ty == null ? o.y : o._ty) + dy;          // settled target — overlapping slides
          const ty = o._pick != null                           // a "▸ pick" IS the crumb rail — it
            ? 134 + o._pick * 22 : o._ty;                      // never drifts, up OR down
          this.tweens.add({ targets: o, y: ty, alpha: ty < 134 ? 0 : o._ba,  // ghosts fade BEFORE
            duration: 240, ease: "Cubic.easeInOut" });         // the burn-circle zone
        });
        th._sections.forEach((s) => { s.baseY += dy; s.hy += dy; });
        th.cursorY += dy;
      };
      th._kill = (st) => { if (!st) return;                    // shared by back/swap
        st.rows.forEach((r) => { if (r.t) r.t.destroy();
          if (r.extra) r.extra.forEach((o) => o.destroy()); });
        st.hits.forEach((h) => h.destroy());
        if (st.headT) st.headT.destroy();
        if (st.crumb) st.crumb.destroy();
        if (st.rules) st.rules.forEach((o) => o.destroy());
      };
      th.back = () => {                                        // rewind ONE step; caller re-lists it
        th._kill(th.active); th.active = null;
        const prev = th._sections.pop();
        if (!prev) return null;
        th._kill(prev);
        th.steps--; th.cursorY = prev.baseY;
        backB.setAlpha(th.steps ? 1 : 0.3);
        return prev;
      };
      th.home = () => {                                        // STAND DOWN: collapse to the root step
        th._kill(th.active); th.active = null;
        while (th._sections.length) {
          const s = th._sections.pop();
          th._kill(s); th.steps--; th.cursorY = s.baseY;
        }
        own.forEach((o) => {                                   // survivors (title) return home
          if (FIXED.has(o) || !o.scene || o._oy == null) return;
          o._ty = o._oy;
          this.tweens.add({ targets: o, y: o._oy, alpha: o._ba == null ? 1 : o._ba,
            duration: 240, ease: "Cubic.easeInOut" });
        });
        backB.setAlpha(0.3);
      };
      th.swap = (key, header, items) => {                      // re-list IN PLACE (count/pay loops)
        const had = !!th.active;                               // step entry keeps the decode ceremony;
        th._kill(th.active); th.active = null;                 // in-loop swaps are INSTANT
        return th.list(key, header, items, had);
      };

      th.pickSeat = (kind, ids, note) => new Promise((resolve) => {
        th._picking = true;                                    // the burn-circle sleeps — the big bar is back
        own.forEach((o) => { if (o !== dockCover && o.setVisible) o.setVisible(false); });  // duck — board is the menu
        const ribbon = mk(this.add.text(W / 2, 178, "", style(13, "#ffffff", { align: "center" }))
          .setOrigin(0.5).setResolution(2).setDepth(22));      // below the band AND a 3-line note (M11),
                                                               // above the top seat frames (~y205)
        this.decode(ribbon, note, 260);
        const cancel = mk(this.add.text(W / 2, 776, "", style(12, "#aaaaaa")).setOrigin(0.5)
          .setResolution(2).setDepth(22).setName("tcxl"));
        const arm = this.decode(cancel, "✕ CANCEL", 240);
        const done = (id) => {
          if (kind === "trade" || kind === "seize") this.seatGlow([], false); else this.clearTargets();
          ribbon.destroy(); cancel.destroy();
          th._picking = false;
          if (this._thread === th) {
            own.forEach((o) => o.setVisible && o.setVisible(true));
            if (this._bandO) this.setBand(this._bandO);        // circle returns with FRESH digits
          }
          th._pickDone = null;
          resolve(id);
        };
        th._pickDone = done;                                   // rig hook (films drive picks directly)
        arm.then(() => { if (cancel.scene) cancel.setInteractive()   // back to the menu — NOT a full abort
          .on("pointerdown", () => done(null)); });
        if (kind === "shoot" || kind === "flip") this.setTargets(ids, done);  // red frame: danger
        else if (kind === "trade") this.seatGlow(ids, true, done);   // white ants
        else if (kind === "seize") this.seatGlow(ids, true, done, RED);  // RED ants — a re-aimed shot
        else this.setItemTargets(ids, done);                   // white pulse: item
      });
      th.close = () => this.closeThread();
      this._thread = th;
      if (this._bandO) this.setBand(this._bandO);              // burn-circle lights NOW, not next tick
      return th;
    }
    closeThread() {
      if (!this._thread) return;
      const t = this._thread;
      this._thread = null;
      if (t._pickDone) t._pickDone(null);                      // mid-pick close: clear brackets/ants,
      t.own.forEach((o) => { if (o && o.destroy) o.destroy(); });  // resolve the pick as cancelled
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
        const hit = this.add.rectangle(s.x, s.y, 88, 88, 0xffffff, 0.001).setDepth(12).setName("tgt")
          .setInteractive().on("pointerdown", () => onTap && onTap(id));
        this._brackets.push(g, hit);
      });
    }
    clearTargets() { this._brackets.forEach((o) => o.destroy()); this._brackets = []; }
    setItemTargets(ids, onTap) {                               // item targeting — WHITE pulsing brackets
      this.clearTargets();                                     // (red = danger only; ants = trade)
      ids.forEach((id) => {
        const s = this.seats.get(id); if (!s) return;
        const g = this.add.graphics().setDepth(12);
        [[-44, -44, 1, 1], [44, -44, -1, 1], [-44, 44, 1, -1], [44, 44, -1, -1]].forEach(([dx, dy, sx, sy]) => {
          g.lineStyle(3, WHITE, 1);
          g.lineBetween(s.x + dx, s.y + dy, s.x + dx + sx * 14, s.y + dy);
          g.lineBetween(s.x + dx, s.y + dy, s.x + dx, s.y + dy + sy * 14);
        });
        const tw = this.tweens.add({ targets: g, alpha: 0.25, duration: 480, yoyo: true, repeat: -1 });
        const hit = this.add.rectangle(s.x, s.y, 88, 88, 0xffffff, 0.001).setDepth(12).setName("tgt")
          .setInteractive().on("pointerdown", () => onTap && onTap(id));
        this._brackets.push({ destroy: () => { tw.remove(); g.destroy(); } }, hit);
      });
    }
    seatGlow(ids, on, onTap, color) {                          // M26 — MARCHING ANTS dotted frame.
      this._glows.forEach((o) => { o.ev.remove(); o.g.destroy(); if (o.hit) o.hit.destroy(); });
      this._glows = [];                                        // WHITE = trade; RED = seize (someone
      if (!on) return;                                         // else's shot re-aimed = danger)
      const tint = color == null ? WHITE : color;
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
          g.clear().lineStyle(3, tint, 0.95);
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
          .setName("tgt").setInteractive().on("pointerdown", () => onTap(id));
        this._glows.push({ g, ev, hit });
      });
    }
    async skipBeat(id, roster) {                               // M23 — the invisible skip becomes a beat
      await this.dialTo(id, false);
      await this.stampSeat(id, "SKIPPED", false);
      // the ⊘ chip clears via choreo's work-copy repaint right after this beat
    }
    async winnerScene(id, roster) {                            // M28
      this.add.rectangle(W / 2, H / 2, W, H, 0x000000, 1).setDepth(24);
      this.add.image(W / 2, 330, "faces", this._pmap(id)).setScale(6).setDepth(25);
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
  SCENE.CX = CX; SCENE.CY = CY; SCENE.READ = READ;
  global.SCENE = SCENE;
})(typeof window !== "undefined" ? window : globalThis);

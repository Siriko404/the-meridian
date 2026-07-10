/* TALLY-STICK ANIMATION SAMPLES — three complete motion characters, auto-looping:
 * add sticks 1..4 → 5th CLOSES the gate → hold → remove back down to 1 → repeat.
 * Each row: the real-size seat + a 2.2x magnified stack. <=2 cover burns red.
 * Motion language: decode/stamp/click-step/shatter — the game's own, no cartoon. */
"use strict";
const W = 390, H = 844, WHITE = 0xffffff, RED = 0xc8102e;
const PITCH = 9, SW = 6, HHT = 6;

function mkSticks() {                         // 0..3 = slashes, 4 = the gate cross
  return [...Array(5)].map(() => ({ on: false, prog: 0, off: 0, dx: 0, alpha: 1, sc: 1, snap: 0, burn: 0 }));
}

class Lab extends Phaser.Scene {
  preload() {
    this.load.spritesheet("faces", "/static/game/assets/portraits/Noir-portraits/36x36-bw-portraits-no-background.png",
      { frameWidth: 36, frameHeight: 36 });
  }

  seatChrome(x, y, faceIdx, name) {
    const g = this.add.graphics();
    g.fillStyle(0x000000).fillRect(x - 32, y - 32, 64, 64);
    g.lineStyle(1, WHITE, 1).strokeRect(x - 32, y - 32, 64, 64);   // hairline frame (ratified thinner)
    this.add.image(x, y + 2, "faces", faceIdx).setScale(1.7);
    g.fillStyle(0x000000).fillRect(x - 26, y + 36, 52, 18);
    g.lineStyle(1, WHITE, 0.95).strokeRect(x - 26, y + 36, 52, 18);
    this.add.text(x, y + 45, name, { fontFamily: "Consolas,monospace", fontSize: "12px",
      color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
  }

  paintStack(g, st, cx, by, s, flash) {
    const cover = st.filter(q => q.on).length;
    const col = cover <= 2 ? RED : WHITE;
    const gw = 3 * PITCH + SW, x0 = cx - (gw * s) / 2;
    const dim = 1 - (flash || 0) * 0.45;
    for (let k = 0; k < 4; k++) {
      const q = st[k];
      if (!q.on && q.snap === 0) continue;
      const sx = x0 + (k * PITCH + q.dx) * s, sy = by + q.off * s;
      const a = Math.max(0, Math.min(1, q.alpha)) * dim;
      if (a <= 0.01) continue;
      if (q.snap > 0) {                        // SNAP: two halves part + drop
        const mx = sx + (SW / 2) * s, myTop = sy - HHT * s, myBot = sy + HHT * s, my = sy;
        g.lineStyle(3 * s, col, a);
        g.lineBetween(sx, myBot + q.snap * 8 * s, mx - q.snap * 3 * s, my + q.snap * 10 * s);
        g.lineBetween(mx + q.snap * 3 * s, my + q.snap * 10 * s, sx + SW * s, myTop + q.snap * 14 * s);
        continue;
      }
      const p = q.prog;                        // DRAW: partial stroke, tip to tail
      g.lineStyle(3 * s * q.sc, col, a);
      g.lineBetween(sx, sy + HHT * s, sx + SW * s * p, sy + HHT * s - 2 * HHT * s * p);
    }
    const c = st[4];                           // the gate cross
    if (c.on || c.prog > 0) {
      const a = Math.max(0, Math.min(1, c.alpha)) * dim;
      if (a > 0.01) {
        const len = gw + 5, lx = x0 - 3 * s;
        const cxm = lx + (len * s) / 2, cym = by;
        const half = (len * s * c.prog * c.sc) / 2;
        g.lineStyle(3 * s * c.sc, col, a);
        g.lineBetween(cxm - half, cym - (HHT * s * c.prog * c.sc), cxm + half, cym + (HHT * s * c.prog * c.sc));
      }
    }
  }

  tw(obj, props, dur, ease) {
    return new Promise((r) => this.tweens.add({ targets: obj, ...props, duration: dur,
      ease: ease || "Linear", onComplete: r }));
  }

  shatter(cx, by, s) {                         // red fragments fall — the damage language
    for (let i = 0; i < 4; i++) {
      const d = this.add.rectangle(cx + (Math.random() - 0.5) * 14 * s, by, 2 * s, 2 * s, RED).setDepth(9);
      this.tweens.add({ targets: d, y: by + (16 + Math.random() * 14) * s,
        x: d.x + (Math.random() - 0.5) * 16 * s, alpha: 0, duration: 380,
        onComplete: () => d.destroy() });
    }
  }

  async animAdd(r, k) {
    const q = r.st[k]; q.on = true;
    if (r.kind === "pen") { q.prog = 0; q.alpha = 1; await this.tw(q, { prog: 1 }, 150); }
    else if (r.kind === "stamp") { q.prog = 1; q.alpha = 0; q.sc = 1.7;
      await this.tw(q, { alpha: 1, sc: 1 }, 190, "Back.easeOut"); }
    else { q.prog = 1; q.alpha = 0; q.off = -10;
      await this.tw(q, { alpha: 1, off: 1 }, 130, "Quad.easeIn"); await this.tw(q, { off: 0 }, 50); }
  }

  async animRemove(r, k) {
    const q = r.st[k];
    if (r.kind === "pen") { await this.tw(q, { snap: 1, alpha: 0 }, 210, "Quad.easeIn");
      q.on = false; q.snap = 0; }
    else if (r.kind === "stamp") {
      [r.zoom, r.real].forEach((c) => this.shatter(c.cx + (k * PITCH - (3 * PITCH + SW) / 2 + SW / 2) * c.s, c.by, c.s));
      q.alpha = 0.9; await this.tw(q, { alpha: 0 }, 120); q.on = false; }
    else { const fl = { t: 0 };
      await new Promise((res) => this.tweens.add({ targets: fl, t: 1, duration: 260,
        onUpdate: () => { q.alpha = Math.sin(fl.t * 22) > 0 ? 1 - fl.t : 0.15; },
        onComplete: res }));
      q.alpha = 0; q.on = false; }
    q.alpha = 1; q.prog = r.kind === "pen" ? 0 : q.prog;
    if (!q.on) { q.prog = 0; q.sc = 1; }
  }

  async animClose(r) {
    const c = r.st[4]; c.on = true;
    if (r.kind === "pen") { c.prog = 0; c.alpha = 1; c.sc = 1;
      await this.tw(c, { prog: 1 }, 180, "Quad.easeOut");
      await this.tw(r, { flash: 0.9 }, 90); await this.tw(r, { flash: 0 }, 140); }
    else if (r.kind === "stamp") { c.prog = 1; c.alpha = 0; c.sc = 2;
      const jolt = this.tw(c, { alpha: 1, sc: 1 }, 220, "Back.easeOut");
      r.st.slice(0, 4).forEach((q) => { this.tweens.add({ targets: q, off: 1, duration: 70, yoyo: true }); });
      await jolt; }
    else { for (const q of r.st.slice(0, 4))
        this.tweens.add({ targets: q, dx: 0.9, duration: 110, yoyo: true, ease: "Quad.easeInOut" });
      await this.tw({ t: 0 }, { t: 1 }, 130);
      c.prog = 0; c.alpha = 1; c.sc = 1;
      await this.tw(c, { prog: 1 }, 200);
      await this.tw(r, { flash: 0.7 }, 110); await this.tw(r, { flash: 0 }, 160); }
  }

  async seq(r) {
    const w = (ms) => new Promise((res) => this.time.delayedCall(ms, res));
    for (;;) {
      r.st.forEach((q) => Object.assign(q, { on: false, prog: 0, off: 0, dx: 0, alpha: 1, sc: 1, snap: 0 }));
      await w(500);
      for (let k = 0; k < 4; k++) { r.label.setText("+1 COVER"); await this.animAdd(r, k); await w(420); }
      r.label.setText("GATE CLOSES — FULL COVER");
      await this.animClose(r); await w(1500);
      r.label.setText("−1 COVER");
      await this.animRemove(r, 4); await w(380);        // the cross opens first
      for (let k = 3; k >= 1; k--) { await this.animRemove(r, k); await w(380); }
      r.label.setText("1 COVER — MORTAL"); await w(1000);
    }
  }

  create() {
    this.add.text(W / 2, 20, "STICK MOTION — PICK A ROW", { fontFamily: "Consolas,monospace",
      fontSize: "15px", color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
    this.add.text(W / 2, 40, "loops: +1 ×4 · gate · −1 back to 1 · left real · right 2.2×", { fontFamily: "Consolas,monospace",
      fontSize: "10px", color: "#9a9a9a" }).setOrigin(0.5).setResolution(2);
    const defs = [
      { y: 165, kind: "pen",   name: "1 · PEN — draw in · snap out · slash close" },
      { y: 420, kind: "stamp", name: "2 · STAMP — stamp in · shatter out · slam close" },
      { y: 675, kind: "mech",  name: "3 · MECHANISM — drop-click in · burn out · lock close" },
    ];
    this.rows = defs.map((d) => {
      this.add.text(16, d.y - 105, d.name, { fontFamily: "Consolas,monospace", fontSize: "12px",
        color: "#ffffff", fontStyle: "bold" }).setResolution(2);
      this.seatChrome(80, d.y, 2, "K.V.");
      const label = this.add.text(W / 2, d.y + 78, "", { fontFamily: "Consolas,monospace",
        fontSize: "11px", color: "#9a9a9a" }).setOrigin(0.5).setResolution(2);
      const r = { kind: d.kind, st: mkSticks(), flash: 0, label,
        real: { cx: 80, by: d.y - 44, s: 1 },
        zoom: { cx: 265, by: d.y - 10, s: 2.2 },
        g: this.add.graphics().setDepth(8) };
      this.seq(r);
      return r;
    });
  }

  update() {
    for (const r of this.rows) {
      r.g.clear();
      this.paintStack(r.g, r.st, r.real.cx, r.real.by, r.real.s, r.flash);
      this.paintStack(r.g, r.st, r.zoom.cx, r.zoom.by, r.zoom.s, r.flash);
    }
  }
}

new Phaser.Game({
  type: Phaser.CANVAS, parent: "stage", width: W, height: H, backgroundColor: "#000000",
  pixelArt: true, scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene: Lab,
});

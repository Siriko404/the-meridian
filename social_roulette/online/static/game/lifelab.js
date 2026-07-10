/* LIFE = VERTICAL BAR of FAT LEANED SQUARES, right side of the avatar frame.
 * Rows 1-3: bar variants, LOOPING +1/-1 cycle (real size + 2.2x zoom).
 * Row 4: chip (SEDATED / DIRT) relocation candidates — pick one of each.
 * <=2 cover red · full 5 pulses once (win-watch tell) · hairline frames. */
"use strict";
const W = 390, H = 844, WHITE = 0xffffff, RED = 0xc8102e;
const SEGH = 12, SEGW = 9, GAP = 2, LEAN = 3;     // fat leaned square geometry

function mkSegs() { return [...Array(5)].map(() => ({ on: false, fill: 0, dx: 0, dy: 0, alpha: 1 })); }

class Lab extends Phaser.Scene {
  preload() {
    this.load.spritesheet("faces", "/static/game/assets/portraits/Noir-portraits/36x36-bw-portraits-no-background.png",
      { frameWidth: 36, frameHeight: 36 });
    this.load.spritesheet("icons", "/static/game/assets/Mystery_Icons.png", { frameWidth: 16, frameHeight: 16 });
  }

  chrome(x, y, faceIdx, name) {
    const g = this.add.graphics();
    g.fillStyle(0x000000).fillRect(x - 32, y - 32, 64, 64);
    g.lineStyle(1, WHITE, 1).strokeRect(x - 32, y - 32, 64, 64);
    this.add.image(x, y + 2, "faces", faceIdx).setScale(1.7);
    g.fillStyle(0x000000).fillRect(x - 26, y + 36, 52, 18);
    g.lineStyle(1, WHITE, 0.95).strokeRect(x - 26, y + 36, 52, 18);
    this.add.text(x, y + 45, name, { fontFamily: "Consolas,monospace", fontSize: "12px",
      color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
    return g;
  }

  /* one leaned square: bottom-anchored parallelogram (game's / lean) */
  seg(g, bx, by, q, col, s, capped) {
    const a = Math.max(0, Math.min(1, q.alpha));
    if (a <= 0.01 || q.fill <= 0) return;
    const h = SEGH * q.fill * s;                   // fill wipes bottom -> top
    const x = bx + q.dx * s, yb = by + q.dy * s;
    g.fillStyle(col, a);
    g.fillPoints([
      { x: x,               y: yb },
      { x: x + SEGW * s,    y: yb },
      { x: x + (SEGW + LEAN) * s, y: yb - h },
      { x: x + LEAN * s,          y: yb - h },
    ], true);
    if (capped) g.lineStyle(1, col, a).strokePoints([
      { x: x, y: yb }, { x: x + SEGW * s, y: yb },
      { x: x + (SEGW + LEAN) * s, y: yb - h }, { x: x + LEAN * s, y: yb - h }], true, true);
  }

  paintBar(g, st, bx, byBase, s, variant, flash) {
    const cover = st.filter(q => q.on).length;
    const col = cover <= 2 ? RED : WHITE;
    const dim = 1 - (flash || 0) * 0.45;
    for (let k = 0; k < 5; k++) {
      const q = st[k];
      if (!q.on && q.fill <= 0) continue;
      const isCap = variant === "cap" && k === 4;
      const by = byBase - k * (SEGH + GAP) * s;
      const qq = { ...q, alpha: q.alpha * dim };
      if (isCap) {                                 // 5th = flat CAP slab across the bar top
        const a = Math.max(0, Math.min(1, qq.alpha));
        if (a > 0.01 && q.fill > 0) {
          const x = bx - 3 * s + q.dx * s, yb = byBase - 4 * (SEGH + GAP) * s + q.dy * s;
          g.fillStyle(col, a);
          g.fillRect(x, yb - 5 * s, (SEGW + LEAN + 6) * s * q.fill, 5 * s);
        }
        continue;
      }
      this.seg(g, bx, by, qq, col, s, variant === "outline");
    }
  }

  async tw(obj, props, dur, ease) {
    return new Promise((r) => this.tweens.add({ targets: obj, ...props, duration: dur,
      ease: ease || "Linear", onComplete: r }));
  }

  async add1(r, k) {
    const q = r.st[k];
    Object.assign(q, { on: true, fill: 0, dx: 0, dy: 0, alpha: 1 });
    await this.tw(q, { fill: 1 }, 140, "Quad.easeOut");        // wipe up
    if (k === 4) { await this.tw(r, { flash: 0.9 }, 90); await this.tw(r, { flash: 0 }, 150); }
  }
  async rem1(r, k) {
    const q = r.st[k];                                          // shear off: right + down + fade
    await this.tw(q, { dx: 14, dy: 10, alpha: 0 }, 210, "Quad.easeIn");
    Object.assign(q, { on: false, fill: 0, dx: 0, dy: 0, alpha: 1 });
  }

  async seq(r) {
    const w = (ms) => new Promise((res) => this.time.delayedCall(ms, res));
    for (;;) {
      r.st.forEach((q) => Object.assign(q, { on: false, fill: 0, dx: 0, dy: 0, alpha: 1 }));
      await w(500);
      for (let k = 0; k < 5; k++) { r.label.setText(k === 4 ? "FULL — WIN WATCH" : "+1"); await this.add1(r, k); await w(380); }
      await w(1200);
      r.label.setText("−1");
      for (let k = 4; k >= 1; k--) { await this.rem1(r, k); await w(360); }
      r.label.setText("1 — MORTAL"); await w(900);
    }
  }

  chipSeat(x, y, faceIdx, mode) {                               // row 4: chip relocation
    this.chrome(x, y, faceIdx, "N.D.");
    if (mode === "icons") {                                     // LEFT edge icon stack (mirrors bar)
      this.add.image(x - 40, y - 18, "icons", 14).setScale(1.4);          // DIRT (envelope)
      this.add.text(x - 40, y - 5, "N.D", { fontFamily: "Consolas,monospace", fontSize: "8px",
        color: "#ffffff" }).setOrigin(0.5).setResolution(2);
      this.add.image(x - 40, y + 12, "icons", 2).setScale(1.4);           // SEDATED
    } else if (mode === "corner") {                             // inside-tile top-left tags
      this.add.text(x - 30, y - 30, "DIRT·N.D.\nSEDATED", { fontFamily: "Consolas,monospace",
        fontSize: "8px", color: "#ffffff", backgroundColor: "#000000" }).setResolution(2);
    } else {                                                    // tight under the plate
      this.add.text(x, y + 58, "DIRT·N.D. · SEDATED", { fontFamily: "Consolas,monospace",
        fontSize: "8px", color: "#ffffff", backgroundColor: "#000000" }).setOrigin(0.5, 0).setResolution(2);
    }
  }

  create() {
    this.add.text(W / 2, 18, "V-BAR SEGMENTS + CHIP SPOT — PICK 1 OF EACH", { fontFamily: "Consolas,monospace",
      fontSize: "13px", color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
    this.add.text(W / 2, 36, "bar right of frame, bottom-up · <=2 red · full pulses", { fontFamily: "Consolas,monospace",
      fontSize: "10px", color: "#9a9a9a" }).setOrigin(0.5).setResolution(2);

    const defs = [
      { y: 140, variant: "plain",   name: "1 · LEANED SQUARES — 5 equal, gaps" },
      { y: 330, variant: "outline", name: "2 · same + hairline outline each" },
      { y: 520, variant: "cap",     name: "3 · 4 SQUARES + flat CAP slab as the 5th" },
    ];
    this.rows = defs.map((d) => {
      this.add.text(16, d.y - 88, d.name, { fontFamily: "Consolas,monospace", fontSize: "12px",
        color: "#ffffff", fontStyle: "bold" }).setResolution(2);
      this.chrome(80, d.y, 2, "K.V.");
      const label = this.add.text(120, d.y + 78, "", { fontFamily: "Consolas,monospace",
        fontSize: "10px", color: "#9a9a9a" }).setOrigin(0.5).setResolution(2);
      const r = { st: mkSegs(), flash: 0, variant: d.variant, label,
        real: { bx: 80 + 32 + 4, by: d.y + 30, s: 1 },
        zoom: { bx: 220, by: d.y + 60, s: 1.8 },
        g: this.add.graphics().setDepth(8) };
      this.seq(r);
      return r;
    });

    this.add.text(16, 620, "4 · CHIP SPOT — A icons-left · B corner-tag · C tight-under", {
      fontFamily: "Consolas,monospace", fontSize: "12px", color: "#ffffff", fontStyle: "bold" }).setResolution(2);
    this.chipSeat(75, 720, 7, "icons");
    this.chipSeat(195, 720, 7, "corner");
    this.chipSeat(315, 720, 7, "under");
    ["A", "B", "C"].forEach((t, i) => this.add.text(75 + i * 120, 795, t, {
      fontFamily: "Consolas,monospace", fontSize: "12px", color: "#9a9a9a" }).setOrigin(0.5).setResolution(2));
    console.log("LIFELAB vbar samples OK");
  }

  update() {
    for (const r of this.rows) {
      r.g.clear();
      this.paintBar(r.g, r.st, r.real.bx, r.real.by, r.real.s, r.variant, r.flash);
      this.paintBar(r.g, r.st, r.zoom.bx, r.zoom.by, r.zoom.s, r.variant, r.flash);
    }
  }
}

window.__lab = new Phaser.Game({
  type: Phaser.CANVAS, parent: "stage", width: W, height: H, backgroundColor: "#000000",
  pixelArt: true, scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene: Lab,
});

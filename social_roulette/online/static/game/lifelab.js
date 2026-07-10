/* COVER METER v6 — thin strokes in rhythm (the game's own material: timer slashes,
 * ticket hairlines, engraved marks). NO solid blocks. Right edge of the frame.
 * Motion: +1 draws in (pen) · -1 is STRUCK THROUGH red then fades (ledger correction)
 * · full 5 shimmers once (win-watch). <=2 red. Row 4: chip redesign, legible sizes. */
"use strict";
const W = 390, H = 844, WHITE = 0xffffff, RED = 0xc8102e;
const PITCH = 12, SLEN = 8, SLEAN = 5;            // stroke geometry: thin, tight rhythm

function mkStrokes() { return [...Array(5)].map(() => ({ on: false, prog: 0, alpha: 1, strike: 0 })); }

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

  /* stroke k position: stacked bottom-up beside/on the frame right edge */
  paintMeter(g, st, x, y, s, variant, shimmer) {
    const cover = st.filter(q => q.on).length;
    const base = cover <= 2 ? RED : WHITE;
    const yBot = y + 2 * variant.pitch * s;
    const P = variant.pitch, L = variant.len, TH = variant.th, OX = variant.ox;
    for (let k = 0; k < 5; k++) {
      const q = st[k];
      if (!q.on && q.strike === 0) continue;
      const a0 = Math.max(0, Math.min(1, q.alpha));
      if (a0 <= 0.01) continue;
      const sy = yBot - k * P * s;
      const sx = x + (32 + OX) * s;
      // shimmer: a brightness wave rides bottom->top once (timer idiom)
      const wave = shimmer > 0 ? Math.max(0, 1 - Math.abs(shimmer * 6 - 1 - k) * 0.9) : 0;
      const a = Math.min(1, a0 + wave * 0.6);
      const col = q.strike > 0 ? RED : base;
      g.lineStyle(TH, col, a);                                   // thin / stroke, timer material
      g.lineBetween(sx, sy + L * 0.5 * s * q.prog, sx + L * 0.55 * s * q.prog, sy - L * 0.5 * s * q.prog);
      if (q.strike > 0) {                                        // the ledger strike-through
        g.lineStyle(2, RED, Math.min(1, q.strike * 1.4));
        const sw = (L * 0.8) * s * Math.min(1, q.strike * 1.6);
        g.lineBetween(sx - sw / 2 + 2 * s, sy, sx + sw + 2 * s, sy);
      }
    }
  }

  tw(obj, props, dur, ease) {
    return new Promise((r) => this.tweens.add({ targets: obj, ...props, duration: dur,
      ease: ease || "Linear", onComplete: r }));
  }

  async add1(r, k) {
    const q = r.st[k];
    Object.assign(q, { on: true, prog: 0, alpha: 1, strike: 0 });
    await this.tw(q, { prog: 1 }, 140, "Quad.easeOut");          // pen draw
    if (k === 4) { r.shimmer = 0; await this.tw(r, { shimmer: 1 }, 340, "Quad.easeOut"); r.shimmer = 0; }
  }
  async rem1(r, k) {
    const q = r.st[k];
    await this.tw(q, { strike: 1 }, 90, "Quad.easeOut");         // struck through (red)
    await this.tw(q, { alpha: 0, strike: 1 }, 160);              // both fade
    Object.assign(q, { on: false, prog: 0, alpha: 1, strike: 0 });
  }

  async seq(r) {
    const w = (ms) => new Promise((res) => this.time.delayedCall(ms, res));
    for (;;) {
      r.st.forEach((q) => Object.assign(q, { on: false, prog: 0, alpha: 1, strike: 0 }));
      await w(500);
      for (let k = 0; k < 5; k++) { r.label.setText(k === 4 ? "FULL" : "+1"); await this.add1(r, k); await w(360); }
      await w(1200);
      r.label.setText("−1");
      for (let k = 4; k >= 1; k--) { await this.rem1(r, k); await w(340); }
      r.label.setText("1 — MORTAL"); await w(900);
    }
  }

  chipSeat(x, y, faceIdx, mode) {                                // row 4 — LEGIBLE chips
    this.chrome(x, y, faceIdx, "N.D.");
    if (mode === "icons") {                                      // icon row under the plate, clear pitch
      this.add.image(x - 24, y + 66, "icons", 14).setScale(1.6); // DIRT envelope
      this.add.text(x - 8, y + 66, "N.D.", { fontFamily: "'Times New Roman',serif", fontSize: "11px",
        color: "#ffffff", fontStyle: "bold", stroke: "#000000", strokeThickness: 4 })
        .setOrigin(0, 0.5).setResolution(2);
      this.add.image(x + 26, y + 66, "icons", 2).setScale(1.6);  // SEDATED
    } else {                                                     // one letterspaced line
      this.add.text(x, y + 60, "DIRT N.D. · SEDATED", { fontFamily: "'Times New Roman',serif",
        fontSize: "11px", color: "#ffffff", fontStyle: "bold", stroke: "#000000", strokeThickness: 4 })
        .setOrigin(0.5, 0).setResolution(2).setLetterSpacing(1);
    }
  }

  create() {
    this.add.text(W / 2, 18, "COVER METER v6 — THIN STROKES — PICK", { fontFamily: "Consolas,monospace",
      fontSize: "13px", color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
    this.add.text(W / 2, 36, "+1 draws · −1 struck through red · full shimmers · <=2 red", { fontFamily: "Consolas,monospace",
      fontSize: "10px", color: "#9a9a9a" }).setOrigin(0.5).setResolution(2);

    const defs = [
      { y: 140, variant: { pitch: 12, len: 8,  th: 2, ox: 5 }, name: "1 · TIGHT — 2px strokes, hugging the frame" },
      { y: 330, variant: { pitch: 14, len: 10, th: 2, ox: 7 }, name: "2 · AIRY — longer strokes, breathing room" },
      { y: 520, variant: { pitch: 13, len: 9,  th: 3, ox: 6 }, name: "3 · FIRM — 3px strokes (a touch of fat)" },
    ];
    this.rows = defs.map((d) => {
      this.add.text(16, d.y - 88, d.name, { fontFamily: "Consolas,monospace", fontSize: "12px",
        color: "#ffffff", fontStyle: "bold" }).setResolution(2);
      this.chrome(80, d.y, 2, "K.V.");
      const label = this.add.text(120, d.y + 78, "", { fontFamily: "Consolas,monospace",
        fontSize: "10px", color: "#9a9a9a" }).setOrigin(0.5).setResolution(2);
      const r = { st: mkStrokes(), shimmer: 0, variant: d.variant, label,
        real: { x: 80, y: d.y, s: 1 },
        zoom: { x: 230, y: d.y, s: 2.4 },
        g: this.add.graphics().setDepth(8) };
      this.seq(r);
      return r;
    });

    this.add.text(16, 622, "4 · CHIPS — A icon row + monogram · B one serif line", {
      fontFamily: "Consolas,monospace", fontSize: "12px", color: "#ffffff", fontStyle: "bold" }).setResolution(2);
    this.chipSeat(100, 715, 7, "icons");
    this.chipSeat(280, 715, 7, "line");
    ["A", "B"].forEach((t, i) => this.add.text(100 + i * 180, 800, t, {
      fontFamily: "Consolas,monospace", fontSize: "12px", color: "#9a9a9a" }).setOrigin(0.5).setResolution(2));
    console.log("LIFELAB v6 OK");
  }

  update() {
    for (const r of this.rows) {
      r.g.clear();
      this.paintMeter(r.g, r.st, r.real.x, r.real.y, r.real.s, r.variant, r.shimmer);
      this.paintMeter(r.g, r.st, r.zoom.x, r.zoom.y, r.zoom.s, r.variant, r.shimmer);
    }
  }
}

window.__lab = new Phaser.Game({
  type: Phaser.CANVAS, parent: "stage", width: W, height: H, backgroundColor: "#000000",
  pixelArt: true, scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene: Lab,
});

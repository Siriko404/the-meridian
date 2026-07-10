/* LIFE-FRAME treatments (#5): team polarity moves INTO the life display; hearts retire.
 * Each row: bloc-A agent at 5 and 1 cover, bloc-B agent at 3. Faces never altered.
 * RED appears ONLY at 1 cover (mortal danger) — flag if that reads wrong. Pick a row. */
"use strict";
const W = 390, H = 844, WHITE = 0xffffff, RED = 0xc8102e;
const MAXC = 5;

class Samples extends Phaser.Scene {
  preload() {
    this.load.spritesheet("faces", "/static/game/assets/portraits/Noir-portraits/36x36-bw-portraits-no-background.png",
      { frameWidth: 36, frameHeight: 36 });
  }

  base(x, y, faceIdx, name) {                     // tile + neutral plate (team reads from the LIFE element)
    const g = this.add.graphics();
    g.fillStyle(0x000000).fillRect(x - 32, y - 32, 64, 64);
    this.add.image(x, y + 2, "faces", faceIdx).setScale(1.7);
    g.fillStyle(0x000000).fillRect(x - 26, y + 36, 52, 18);
    g.lineStyle(2, WHITE, 0.95).strokeRect(x - 26, y + 36, 52, 18);
    this.add.text(x, y + 45, name, { fontFamily: "Consolas,monospace", fontSize: "13px",
      color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
    return g;
  }

  /* 1 · SEGMENTED FRAME — the avatar frame IS the cover meter: 5 edge segments.
   *     Team A = solid strokes, team B = hollow (double-line) strokes. */
  segFrame(x, y, faceIdx, name, cover, blocA) {
    const g = this.base(x, y, faceIdx, name);
    const P = [ [-32,-32, 32,-32], [32,-32, 32,32], [32,32, -32,32],
                [-32,32, -32,-4], [-32,-4, -32,-32] ];             // 4 sides + doubled left = 5 slots
    const segs = [ [[-32,-32],[32,-32]], [[32,-32],[32,32]], [[-32,32],[32,32]],
                   [[-32,-32],[-32,0]], [[-32,0],[-32,32]] ];
    segs.forEach((s, k) => {
      if (k >= cover) return;
      const col = (cover === 1) ? RED : WHITE;
      g.lineStyle(blocA ? 4 : 1, col, 1);                       // team = ratified thick/thin
      g.lineBetween(x + s[0][0], y + s[0][1], x + s[1][0], y + s[1][1]);
    });
  }

  /* 2 · LEDGER TALLY — a slim bar under the face: 5 tally ticks.
   *     Team A = white ticks on black; team B = black ticks on white (polarity). */
  tally(x, y, faceIdx, name, cover, blocA) {
    const g = this.base(x, y, faceIdx, name);
    g.lineStyle(2, WHITE, 0.95).strokeRect(x - 32, y - 32, 64, 64);   // plain frame
    const by = y + 62;
    g.fillStyle(blocA ? 0x000000 : 0xffffff).fillRect(x - 26, by, 52, 12);
    g.lineStyle(1, WHITE, 0.9).strokeRect(x - 26, by, 52, 12);
    for (let k = 0; k < cover; k++) {
      const col = (cover === 1) ? RED : (blocA ? WHITE : 0x000000);
      g.fillStyle(col, 1).fillRect(x - 21 + k * 10, by + 2, 4, 8);
    }
  }

  /* 3 · WAX SEAL — a 5-segment seal ring on the tile corner (menu burn-circle idiom).
   *     Team A = filled seal core; team B = hollow core. */
  seal(x, y, faceIdx, name, cover, blocA) {
    const g = this.base(x, y, faceIdx, name);
    g.lineStyle(2, WHITE, 0.95).strokeRect(x - 32, y - 32, 64, 64);
    const cx = x + 20, cy = y - 20, R = 10, SEG = MAXC;   // inside the tile corner — no overlap
    if (blocA) g.fillStyle(0xffffff, 1).fillCircle(cx, cy, 5);
    else g.lineStyle(2, WHITE, 1).strokeCircle(cx, cy, 5);
    for (let k = 0; k < SEG; k++) {
      const a0 = -Math.PI / 2 + (k * 2 * Math.PI) / SEG + 0.14;
      const a1 = -Math.PI / 2 + ((k + 1) * 2 * Math.PI) / SEG - 0.14;
      const col = (cover === 1) ? RED : WHITE;
      g.lineStyle(3, col, k < cover ? 1 : 0.15);
      g.lineBetween(cx + Math.cos(a0) * R, cy + Math.sin(a0) * R,
                    cx + Math.cos(a1) * R, cy + Math.sin(a1) * R);
    }
  }

  /* 4 · DOUBLE BORDER — outer frame = team (thick vs thin-double, existing idiom);
   *     inner frame thins as cover drops; last cover = red dashes. */
  dblBorder(x, y, faceIdx, name, cover, blocA) {
    const g = this.base(x, y, faceIdx, name);
    if (blocA) g.lineStyle(4, WHITE, 1).strokeRect(x - 34, y - 34, 68, 68);
    else {
      g.lineStyle(1, WHITE, 1).strokeRect(x - 35, y - 35, 70, 70);
      g.lineStyle(1, WHITE, 1).strokeRect(x - 32, y - 32, 64, 64);
    }
    if (cover > 1) g.lineStyle(cover, WHITE, 0.95).strokeRect(x - 27, y - 27, 54, 54);
    else {                                                          // 1 cover: red dashed inner
      g.lineStyle(2, RED, 1);
      for (let s = -27; s < 27; s += 9) {
        g.lineBetween(x + s, y - 27, x + s + 5, y - 27); g.lineBetween(x + s, y + 27, x + s + 5, y + 27);
        g.lineBetween(x - 27, y + s, x - 27, y + s + 5); g.lineBetween(x + 27, y + s, x + 27, y + s + 5);
      }
    }
  }

  /* 0 · CURRENT (reference) — ratified frames + heart pips, unchanged */
  current(x, y, faceIdx, name, cover, blocA) {
    const g = this.base(x, y, faceIdx, name);
    if (blocA) g.lineStyle(4, WHITE, 1).strokeRect(x - 32, y - 32, 64, 64);
    else g.lineStyle(1, WHITE, 1).strokeRect(x - 32, y - 32, 64, 64);
    for (let k = 0; k < cover; k++)
      this.add.text(x + (k - (cover - 1) / 2) * 13, y + 64, "♥", { fontFamily: "Consolas,monospace",
        fontSize: "11px", color: "#ffffff" }).setOrigin(0.5).setResolution(2);
  }

  create() {
    this.add.text(W / 2, 22, "LIFE FRAME — PICK A ROW", { fontFamily: "Consolas,monospace",
      fontSize: "16px", color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
    this.add.text(W / 2, 42, "A@5 · A@1 (red = mortal danger) · B@3 — plates neutral", { fontFamily: "Consolas,monospace",
      fontSize: "10px", color: "#9a9a9a" }).setOrigin(0.5).setResolution(2);

    const rows = [
      { fn: this.current,   y: 130, label: "0 · CURRENT — frames + hearts (reference)" },
      { fn: this.segFrame,  y: 280, label: "1 · SEGMENTED FRAME — frame IS the cover" },
      { fn: this.tally,     y: 425, label: "2 · LEDGER TALLY — polarity bar, 5 ticks" },
      { fn: this.seal,      y: 575, label: "3 · WAX SEAL — corner seal ring burns down" },
      { fn: this.dblBorder, y: 720, label: "4 · DOUBLE BORDER — inner border thins" },
    ];
    for (const r of rows) {
      this.add.text(16, r.y - 78, r.label, { fontFamily: "Consolas,monospace", fontSize: "12px",
        color: "#ffffff", fontStyle: "bold" }).setResolution(2);
      r.fn.call(this, 75, r.y, 2, "A·5", 5, true);
      r.fn.call(this, 195, r.y, 2, "A·1", 1, true);
      r.fn.call(this, 315, r.y, 7, "B·3", 3, false);
    }
    console.log("LIFELAB samples OK");
  }
}

new Phaser.Game({
  type: Phaser.CANVAS, parent: "stage", width: W, height: H, backgroundColor: "#000000",
  pixelArt: true, scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene: Samples,
});

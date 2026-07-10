/* LIFE = borderless CHARGE BAR above the avatar frame (user spec 2026-07-10).
 * Frames stay simple: thick = team A, thin = team B (ratified idiom, unchanged).
 * Three tick styles of the SAME spec — pick one. Red only at 1 cover. */
"use strict";
const W = 390, H = 844, WHITE = 0xffffff, RED = 0xc8102e;
const MAXC = 5;

class Samples extends Phaser.Scene {
  preload() {
    this.load.spritesheet("faces", "/static/game/assets/portraits/Noir-portraits/36x36-bw-portraits-no-background.png",
      { frameWidth: 36, frameHeight: 36 });
  }

  base(x, y, faceIdx, name, blocA) {              // simple tile: thick/thin frame = team (unchanged)
    const g = this.add.graphics();
    g.fillStyle(0x000000).fillRect(x - 32, y - 32, 64, 64);
    g.lineStyle(blocA ? 4 : 1, WHITE, 1).strokeRect(x - 32, y - 32, 64, 64);
    this.add.image(x, y + 2, "faces", faceIdx).setScale(1.7);
    g.fillStyle(0x000000).fillRect(x - 26, y + 36, 52, 18);
    g.lineStyle(2, WHITE, 0.95).strokeRect(x - 26, y + 36, 52, 18);
    this.add.text(x, y + 45, name, { fontFamily: "Consolas,monospace", fontSize: "13px",
      color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
    return g;
  }

  /* 1 · SQUARE TICKS — 5 crisp blocks, gap-separated */
  squares(x, y, faceIdx, name, cover, blocA) {
    const g = this.base(x, y, faceIdx, name, blocA);
    const by = y - 44;
    for (let k = 0; k < cover; k++)
      g.fillStyle(cover === 1 ? RED : WHITE, 1).fillRect(x - 24 + k * 11, by - 3, 7, 6);
  }

  /* 2 · SLASHES — the big timer bar's ///// idiom, seat-sized */
  slashes(x, y, faceIdx, name, cover, blocA) {
    const g = this.base(x, y, faceIdx, name, blocA);
    const by = y - 44;
    g.lineStyle(2, cover === 1 ? RED : WHITE, 0.95);
    for (let k = 0; k < cover; k++)
      g.lineBetween(x - 24 + k * 11, by + 4, x - 24 + k * 11 + 6, by - 4);
  }

  /* 3 · SOLID BAR — one continuous charge, drains right-to-left */
  solid(x, y, faceIdx, name, cover, blocA) {
    const g = this.base(x, y, faceIdx, name, blocA);
    const by = y - 44, full = 52;
    g.fillStyle(cover === 1 ? RED : WHITE, 1)
      .fillRect(x - 26, by - 2, Math.round(full * (cover / MAXC)), 5);
  }

  /* 0 · CURRENT (reference) — hearts below */
  current(x, y, faceIdx, name, cover, blocA) {
    this.base(x, y, faceIdx, name, blocA);
    for (let k = 0; k < cover; k++)
      this.add.text(x + (k - (cover - 1) / 2) * 13, y + 64, "♥", { fontFamily: "Consolas,monospace",
        fontSize: "11px", color: "#ffffff" }).setOrigin(0.5).setResolution(2);
  }

  create() {
    this.add.text(W / 2, 22, "CHARGE BAR ABOVE AVATAR — PICK A ROW", { fontFamily: "Consolas,monospace",
      fontSize: "15px", color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
    this.add.text(W / 2, 42, "no border box · frames simple (thick=A thin=B) · red = 1 cover", { fontFamily: "Consolas,monospace",
      fontSize: "10px", color: "#9a9a9a" }).setOrigin(0.5).setResolution(2);

    const rows = [
      { fn: this.current, y: 140, label: "0 · CURRENT — hearts (reference)" },
      { fn: this.squares, y: 320, label: "1 · SQUARE TICKS" },
      { fn: this.slashes, y: 500, label: "2 · SLASHES — same idiom as the big timer" },
      { fn: this.solid,   y: 680, label: "3 · SOLID BAR — continuous charge" },
    ];
    for (const r of rows) {
      this.add.text(16, r.y - 90, r.label, { fontFamily: "Consolas,monospace", fontSize: "12px",
        color: "#ffffff", fontStyle: "bold" }).setResolution(2);
      r.fn.call(this, 75, r.y, 2, "A·5", 5, true);
      r.fn.call(this, 195, r.y, 2, "A·1", 1, true);
      r.fn.call(this, 315, r.y, 7, "B·3", 3, false);
    }
    console.log("LIFELAB charge-bar samples OK");
  }
}

new Phaser.Game({
  type: Phaser.CANVAS, parent: "stage", width: W, height: H, backgroundColor: "#000000",
  pixelArt: true, scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene: Samples,
});

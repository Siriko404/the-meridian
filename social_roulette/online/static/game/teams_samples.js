/* Team-marker treatments, rendered for real — same two agents in each row.
 * Faces are never altered. Pick a row. */
"use strict";
const W = 390, H = 844, WHITE = 0xffffff;

class Samples extends Phaser.Scene {
  preload() {
    this.load.spritesheet("faces", "/game/assets/portraits/Noir-portraits/36x36-bw-portraits-no-background.png",
      { frameWidth: 36, frameHeight: 36 });
  }

  seat(x, y, faceIdx, blocA, treatment) {
    const g = this.add.graphics();
    // base tile — identical everywhere
    g.fillStyle(0x000000).fillRect(x - 39, y - 39, 78, 78);
    g.lineStyle(2, WHITE, 0.95).strokeRect(x - 39, y - 39, 78, 78);
    this.add.image(x, y + 4, "faces", faceIdx).setScale(2);

    if (treatment === 1) {                       // 1 · HERALDIC BAND across the tile top
      if (blocA) g.fillStyle(WHITE, 1).fillRect(x - 39, y - 39, 78, 12);
      else {
        g.fillStyle(0x000000).fillRect(x - 39, y - 39, 78, 12);
        g.lineStyle(2, WHITE, 1);
        for (let s = -39; s < 39; s += 8) g.lineBetween(x + s, y - 27, x + s + 8, y - 39);
        g.lineStyle(1, WHITE, 0.9).strokeRect(x - 39, y - 39, 78, 12);
      }
    }
    // nameplate
    const plateA = treatment === 2 && blocA;
    g.fillStyle(plateA ? 0xffffff : 0x000000).fillRect(x - 29, y + 42, 58, 22);
    g.lineStyle(2, WHITE, 0.95).strokeRect(x - 29, y + 42, 58, 22);
    this.add.text(x, y + 53, blocA ? "P2" : "P3", { fontFamily: "Consolas,monospace", fontSize: "17px",
      color: plateA ? "#000000" : "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);

    if (treatment === 3 && blocA) {              // 3 · SIDE RAILS flanking the tile
      g.fillStyle(WHITE, 1).fillRect(x - 51, y - 39, 7, 103);
      g.fillStyle(WHITE, 1).fillRect(x + 44, y - 39, 7, 103);
    }
  }

  create() {
    this.add.text(W / 2, 26, "TEAM MARKERS — PICK A ROW", { fontFamily: "Consolas,monospace",
      fontSize: "17px", color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
    this.add.text(W / 2, 48, "same agents each row · faces untouched", { fontFamily: "Consolas,monospace",
      fontSize: "12px", color: "#9a9a9a" }).setOrigin(0.5).setResolution(2);

    const rows = [
      { t: 1, y: 150, label: "1 · BAND — solid vs striped" },
      { t: 2, y: 400, label: "2 · NAMEPLATE — inverted vs plain" },
      { t: 3, y: 650, label: "3 · RAILS — flanked vs clean" },
    ];
    for (const r of rows) {
      this.add.text(28, r.y - 90, r.label, { fontFamily: "Consolas,monospace", fontSize: "14px",
        color: "#ffffff", fontStyle: "bold" }).setResolution(2);
      this.seat(120, r.y, 2, true,  r.t);   // bloc A agent
      this.seat(270, r.y, 7, false, r.t);   // bloc B agent
      this.add.text(120, r.y - 62, "BLOC A", { fontFamily: "Consolas,monospace", fontSize: "11px", color: "#888888" }).setOrigin(0.5).setResolution(2);
      this.add.text(270, r.y - 62, "BLOC B", { fontFamily: "Consolas,monospace", fontSize: "11px", color: "#888888" }).setOrigin(0.5).setResolution(2);
    }
    console.log("TEAMS samples OK");
  }
}

new Phaser.Game({
  type: Phaser.AUTO, parent: "stage", width: W, height: H, backgroundColor: "#000000",
  pixelArt: true, scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene: Samples,
});

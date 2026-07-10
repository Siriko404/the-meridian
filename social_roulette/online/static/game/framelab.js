/* FRAME WEIGHT samples (#5) — game-TRUE 78px tiles, plate polarity carrying team
 * exactly as live (A = white plate/black text, B = inverse). Each row shows the
 * pair in BOTH states the table renders: ACTIVE (full alpha) and idle (0.55).
 * "0.5px" = 1px at half alpha (canvas has no true sub-pixel). Sticks for context. */
"use strict";
const W = 390, H = 844, WHITE = 0xffffff;

class Lab extends Phaser.Scene {
  preload() {
    this.load.spritesheet("faces", "/static/game/assets/portraits/Noir-portraits/36x36-bw-portraits-no-background.png",
      { frameWidth: 36, frameHeight: 36 });
  }

  seat(x, y, faceIdx, blocA, w, frameAlpha, active) {
    const g = this.add.graphics();
    g.fillStyle(0x000000).fillRect(x - 39, y - 39, 78, 78);
    g.lineStyle(w, WHITE, (active ? 1 : 0.55) * frameAlpha).strokeRect(x - 39, y - 39, 78, 78);
    this.add.image(x, y, "faces", faceIdx).setScale(2);
    // plate polarity = team (live behavior)
    g.fillStyle(blocA ? 0xffffff : 0x000000).fillRect(x - 41, y + 42, 82, 24);
    g.lineStyle(1, WHITE, 0.95).strokeRect(x - 41, y + 42, 82, 24);
    this.add.text(x, y + 54, blocA ? "A.N." : "B.S.", { fontFamily: "Consolas,monospace",
      fontSize: "15px", color: blocA ? "#000000" : "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
    g.lineStyle(3, WHITE, 1);                                  // 3 sticks, context
    for (let k = 0; k < 3; k++)
      g.lineBetween(x - 14 + k * 9, y - 46, x - 8 + k * 9, y - 58);
    this.add.text(x, y + 76, active ? "ACTIVE" : "idle", { fontFamily: "Consolas,monospace",
      fontSize: "9px", color: "#777777" }).setOrigin(0.5).setResolution(2);
  }

  row(y, label, wA, aA, wB, aB) {
    this.add.text(16, y - 92, label, { fontFamily: "Consolas,monospace", fontSize: "12px",
      color: "#ffffff", fontStyle: "bold" }).setResolution(2);
    this.seat(52,  y, 2, true,  wA, aA, true);
    this.seat(144, y, 2, true,  wA, aA, false);
    this.seat(236, y, 7, false, wB, aB, true);
    this.seat(328, y, 7, false, wB, aB, false);
  }

  create() {
    this.add.text(W / 2, 20, "FRAME WEIGHT — PICK A ROW", { fontFamily: "Consolas,monospace",
      fontSize: "15px", color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
    this.add.text(W / 2, 40, "team stays on plate polarity · both table states shown", { fontFamily: "Consolas,monospace",
      fontSize: "10px", color: "#9a9a9a" }).setOrigin(0.5).setResolution(2);

    this.row(190, "1 · BOTH 1px — team from plates only", 1, 1, 1, 1);
    this.row(420, "2 · A 1px / B 0.5px (half-alpha hairline)", 1, 1, 1, 0.5);
    this.row(650, "3 · A 2px / B 1px — minimal weight cue kept", 2, 1, 1, 1);
    console.log("FRAMELAB samples OK");
  }
}

new Phaser.Game({
  type: Phaser.CANVAS, parent: "stage", width: W, height: H, backgroundColor: "#000000",
  pixelArt: true, scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene: Lab,
});

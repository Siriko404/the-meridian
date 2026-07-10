/* LIFE = FAT SLASHES above the avatar, borderless; the LAST 2 covers burn RED.
 * Frames redesigned THINNER — two weight pairs to pick from (team = thick vs thin).
 * Seats per row: A@5 · A@2 (red pair) · A@1 · B@3. */
"use strict";
const W = 390, H = 844, WHITE = 0xffffff, RED = 0xc8102e;

class Samples extends Phaser.Scene {
  preload() {
    this.load.spritesheet("faces", "/static/game/assets/portraits/Noir-portraits/36x36-bw-portraits-no-background.png",
      { frameWidth: 36, frameHeight: 36 });
  }

  seat(x, y, faceIdx, name, cover, blocA, wA, wB) {
    const g = this.add.graphics();
    g.fillStyle(0x000000).fillRect(x - 32, y - 32, 64, 64);
    g.lineStyle(blocA ? wA : wB, WHITE, 1).strokeRect(x - 32, y - 32, 64, 64);
    this.add.image(x, y + 2, "faces", faceIdx).setScale(1.7);
    g.fillStyle(0x000000).fillRect(x - 26, y + 36, 52, 18);
    g.lineStyle(2, WHITE, 0.95).strokeRect(x - 26, y + 36, 52, 18);
    this.add.text(x, y + 45, name, { fontFamily: "Consolas,monospace", fontSize: "12px",
      color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
    // FAT slashes, no border box; remaining covers <= 2 burn red
    const by = y - 43, col = cover <= 2 ? RED : WHITE;
    g.lineStyle(4, col, 1);
    for (let k = 0; k < cover; k++)
      g.lineBetween(x - 25 + k * 11, by + 5, x - 25 + k * 11 + 7, by - 5);
  }

  row(y, label, wA, wB) {
    this.add.text(16, y - 92, label, { fontFamily: "Consolas,monospace", fontSize: "12px",
      color: "#ffffff", fontStyle: "bold" }).setResolution(2);
    this.seat(60,  y, 2, "A·5", 5, true,  wA, wB);
    this.seat(150, y, 2, "A·2", 2, true,  wA, wB);
    this.seat(240, y, 2, "A·1", 1, true,  wA, wB);
    this.seat(330, y, 7, "B·3", 3, false, wA, wB);
  }

  create() {
    this.add.text(W / 2, 22, "FAT SLASHES · LAST 2 RED — PICK FRAMES", { fontFamily: "Consolas,monospace",
      fontSize: "15px", color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
    this.add.text(W / 2, 42, "bar borderless above avatar · team = frame weight", { fontFamily: "Consolas,monospace",
      fontSize: "10px", color: "#9a9a9a" }).setOrigin(0.5).setResolution(2);

    this.row(190, "1 · FRAMES 3px / 1px", 3, 1);
    this.row(420, "2 · FRAMES 2px / 1px", 2, 1);
    this.row(650, "3 · OLD 4px / 1px (reference)", 4, 1);
    console.log("LIFELAB fat-slash samples OK");
  }
}

new Phaser.Game({
  type: Phaser.CANVAS, parent: "stage", width: W, height: H, backgroundColor: "#000000",
  pixelArt: true, scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene: Samples,
});

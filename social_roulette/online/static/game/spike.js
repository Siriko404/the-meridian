/* Phaser 4 spike — the dining car with REAL community assets.
 * Proves: v4 boots · pixel-art crisp · spritesheets · tweens (turn-light) · phone frame.
 * Assets: JJ99 "Noir 1-bit Portraits" (commercial OK) · Darkmoonfire "1-Bit Mystery Icons" (CC-BY-SA). */
"use strict";

const W = 390, H = 844;
const RED = 0xc8102e, WHITE = 0xffffff;

class DiningCar extends Phaser.Scene {
  preload() {
    this.load.spritesheet("faces", "/game/assets/portraits/Noir-portraits/36x36-bw-portraits-no-background.png",
      { frameWidth: 36, frameHeight: 36 });
    this.load.spritesheet("icons", "/game/assets/Mystery_Icons.png", { frameWidth: 16, frameHeight: 16 });
  }

  create() {
    const g = this.add.graphics();

    // ---- destination board ----
    this.add.text(W / 2, 30, "THE MERIDIAN", { fontFamily: "Consolas,monospace", fontSize: "20px", color: "#ffffff" })
      .setOrigin(0.5).setLetterSpacing(6);
    this.add.text(W / 2, 52, "LAST SERVICE · CAR 4", { fontFamily: "Consolas,monospace", fontSize: "10px", color: "#8a8a8a" })
      .setOrigin(0.5).setLetterSpacing(4);
    g.lineStyle(1, WHITE, 0.5).lineBetween(24, 66, W - 24, 66);

    // ---- window band: three frames, the war passing outside ----
    const wy = 92, wh = 96;
    g.lineStyle(2, WHITE, 0.9);
    [24, 148, 272].forEach(x => g.strokeRect(x, wy, 94, wh));
    g.lineStyle(1, WHITE, 0.35);
    [24, 148, 272].forEach(x => g.lineBetween(x + 47, wy, x + 47, wy + wh));
    // streaks of passing light
    for (const [x1, y] of [[30, 120], [160, 150], [286, 132], [70, 168]]) {
      const s = this.add.rectangle(x1, y, 26, 2, WHITE, 0.28);
      this.tweens.add({ targets: s, x: x1 - 40, alpha: 0, duration: 900, repeat: -1, delay: Math.random() * 800 });
    }
    // the red signal lamp sliding past (the ONLY red on screen while nothing is lethal)
    const sig = this.add.circle(300, 126, 3, RED);
    this.tweens.add({ targets: sig, x: 40, duration: 5200, repeat: -1, ease: "Linear" });

    // ---- seats: 5 agents on an arc, portraits from the pack ----
    const seats = [];
    const cx = W / 2, cy = 452, rx = 142, ry = 150;
    for (let i = 0; i < 5; i++) {
      const a = -Math.PI / 2 + i * (Math.PI * 2 / 5);
      const x = cx + rx * Math.cos(a), y = cy + ry * Math.sin(a);
      const frame = this.add.rectangle(x, y, 78, 78).setStrokeStyle(2, WHITE, 0.9);
      const face = this.add.image(x, y, "faces", i).setScale(2);
      const name = this.add.text(x, y + 52, "P" + i, { fontFamily: "Consolas,monospace", fontSize: "13px", color: "#ffffff" }).setOrigin(0.5);
      // cover-identity pips (lives): 3 tiny hearts
      const pips = [0, 1, 2].map(k => this.add.image(x - 14 + k * 14, y + 70, "icons", 20).setScale(1));
      // team badge: filled vs hollow square (form, not color)
      const badge = i % 2 === 0
        ? this.add.rectangle(x - 30, y - 30, 10, 10, WHITE)
        : this.add.rectangle(x - 30, y - 30, 10, 10).setStrokeStyle(2, WHITE);
      seats.push({ x, y, frame, face });
    }

    // ---- center: the revolver under the lamp ----
    const lamp = this.add.graphics();
    const revolver = this.add.image(cx, cy, "icons", 0).setScale(5); // index fixed after debug pass
    // turn-light: the cone swings seat to seat (the lamp chooses whose turn it is)
    let turn = 0;
    const retarget = () => {
      const s = seats[turn];
      lamp.clear().fillStyle(WHITE, 0.10)
        .fillTriangle(cx, cy - 120, s.x - 42, s.y + 30, s.x + 42, s.y + 30);
      seats.forEach((q, k) => {
        q.frame.setStrokeStyle(2, WHITE, k === turn ? 1 : 0.45);
        this.tweens.add({ targets: q.face, scale: k === turn ? 2.3 : 2, duration: 260 });
      });
      turn = (turn + 1) % 5;
    };
    retarget();
    this.time.addEvent({ delay: 2200, loop: true, callback: retarget });

    // ---- item tray: six instruments from the icon sheet ----
    const items = [
      { f: 37, n: "PAPERS" }, { f: 40, n: "COVER" }, { f: 14, n: "MANIFEST" },
      { f: 11, n: "POISON" }, { f: 38, n: "INTERCEPT" }, { f: 25, n: "BURN" },
    ];
    const ty = 736, tw = 56;
    items.forEach((it, k) => {
      const x = 34 + k * (tw + 6) + tw / 2;
      this.add.rectangle(x, ty, tw, 66).setStrokeStyle(1, WHITE, 0.6);
      this.add.image(x, ty - 12, "icons", it.f).setScale(2.2);
      this.add.text(x, ty + 20, it.n, { fontFamily: "Consolas,monospace", fontSize: "7px", color: "#bbbbbb" }).setOrigin(0.5);
    });


    // filters probe (Phaser 4 unified filter system) — report, never crash
    try {
      const cam = this.cameras.main;
      if (cam.filters && cam.filters.internal && cam.filters.internal.addVignette) {
        cam.filters.internal.addVignette(0.5, 0.5, 0.9, 0.45);
        console.log("SPIKE filters: vignette OK");
      } else console.log("SPIKE filters: API not found on camera", Object.keys(cam.filters || {}));
    } catch (e) { console.log("SPIKE filters error: " + e.message); }

    console.log("SPIKE create OK, Phaser " + Phaser.VERSION);
  }
}

new Phaser.Game({
  type: Phaser.AUTO,
  parent: "stage",
  width: W, height: H,
  backgroundColor: "#000000",
  pixelArt: true,
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene: DiningCar,
});

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
    this.add.text(W / 2, 28, "THE MERIDIAN", { fontFamily: "Consolas,monospace", fontSize: "26px", color: "#ffffff" })
      .setOrigin(0.5).setLetterSpacing(6).setResolution(2);
    this.add.text(W / 2, 53, "LAST SERVICE · CAR 4", { fontFamily: "Consolas,monospace", fontSize: "14px", color: "#aaaaaa" })
      .setOrigin(0.5).setLetterSpacing(4).setResolution(2);
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

    // ---- seats: 5 agents on an arc; the FRAME + NAMEPLATE is the team ----
    // bloc A (even seats): heavy 4px frame + INVERTED white nameplate (black text)
    // bloc B (odd seats):  thin  2px frame + black nameplate (white text)
    const seats = [];
    const cx = W / 2, cy = 452, rx = 142, ry = 150;
    for (let i = 0; i < 5; i++) {
      const a = -Math.PI / 2 + i * (Math.PI * 2 / 5);
      const x = cx + rx * Math.cos(a), y = cy + ry * Math.sin(a);
      const blocA = i % 2 === 0;
      const frame = this.add.rectangle(x, y, 78, 78).setStrokeStyle(blocA ? 4 : 2, WHITE, 0.95);
      if (blocA) this.add.rectangle(x, y, 88, 88).setStrokeStyle(1, WHITE, 0.5);   // double rim
      const face = this.add.image(x, y, "faces", i).setScale(2);
      const plate = this.add.rectangle(x, y + 53, 58, 22, blocA ? 0xffffff : 0x000000)
        .setStrokeStyle(2, WHITE, 0.95);
      const name = this.add.text(x, y + 53, "P" + i, { fontFamily: "Consolas,monospace", fontSize: "17px",
        color: blocA ? "#000000" : "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
      const pips = [0, 1, 2].map(k => this.add.image(x - 21 + k * 21, y + 78, "icons", 20).setScale(1.5));
      seats.push({ x, y, frame, face, angleDeg: -90 + i * 72 });
    }

    // ---- center: the CYLINDER as the turn dial (the archived dial+dot, made diegetic) ----
    // top-down revolver cylinder; it ROTATES with a mechanical click so the chambered
    // round points at whoever's turn it is.
    const cyl = this.add.container(cx, cy);
    const cg = this.add.graphics();
    // FLUTED silhouette: convex arc bulging around each bore, concave scallop between bores.
    const BORE_D = 30, BORE_R = 10, BULGE_R = 17, FLUTE_R = 5, FLUTE_D = 44;   // shallow flutes (1/3 depth)
    const pts = [];
    const P = (r, cxx, cyy, a) => pts.push({ x: cxx + r * Math.cos(a), y: cyy + r * Math.sin(a) });
    for (let i = 0; i < 5; i++) {
      const a0 = (-90 + i * 72) * Math.PI / 180;             // this chamber's outward direction
      const bx = BORE_D * Math.cos(a0), by = BORE_D * Math.sin(a0);
      for (let k = -6; k <= 6; k++) P(BULGE_R, bx, by, a0 + k * (0.16));          // convex bulge
      const am = a0 + (36 * Math.PI / 180);                  // midpoint toward next chamber
      const fx = FLUTE_D * Math.cos(am), fy = FLUTE_D * Math.sin(am);
      for (let k = 5; k >= -5; k--) P(FLUTE_R, fx, fy, am + k * (0.14) + Math.PI); // concave flute (inward arc)
    }
    cg.fillStyle(0x000000, 1).lineStyle(3, WHITE, 0.95);
    cg.beginPath(); cg.moveTo(pts[0].x, pts[0].y);
    pts.forEach(p => cg.lineTo(p.x, p.y));
    cg.closePath(); cg.fillPath(); cg.strokePath();
    // bores: dark holes; the CHAMBERED one (local -90) is filled — it points where the cylinder points
    for (let i = 0; i < 5; i++) {
      const a = (-90 + i * 72) * Math.PI / 180;
      cg.lineStyle(2, WHITE, 0.9).strokeCircle(BORE_D * Math.cos(a), BORE_D * Math.sin(a), BORE_R);
    }
    cg.fillStyle(0xffffff, 0.25).fillCircle(0, 0, 7);        // axis pin
    cg.lineStyle(2, WHITE, 0.7).strokeCircle(0, 0, 7);
    const chambered = this.add.circle(0, -BORE_D, BORE_R - 3, WHITE);
    cyl.add([cg, chambered]);

    let turn = 0;
    const retarget = () => {
      const s = seats[turn];
      this.tweens.add({ targets: cyl, angle: s.angleDeg + 90, duration: 420, ease: "Back.easeOut" }); // click-step
      seats.forEach((q, k) => {
        q.frame.setStrokeStyle(k % 2 === 0 ? 4 : 2, WHITE, k === turn ? 1 : 0.55);
        this.tweens.add({ targets: q.face, scale: k === turn ? 2.3 : 2, duration: 260 });
      });
      turn = (turn + 1) % 5;
    };
    retarget();
    this.time.addEvent({ delay: 2200, loop: true, callback: retarget });

    // ---- DESIGN PRINCIPLE: screen-occupying menus live BEHIND ICONS (tap to open) ----
    // inventory = the agent's KIT: a briefcase icon bottom-right; tap toggles the tray.
    const items = [
      { f: 37, n: "PAPERS" }, { f: 40, n: "COVER" }, { f: 14, n: "MANIFEST" },
      { f: 11, n: "POISON" }, { f: 38, n: "INTERCEPT" }, { f: 25, n: "BURN" },
    ];
    const tray = this.add.container(0, 0).setVisible(false);
    tray.add(this.add.rectangle(W / 2, 738, W - 16, 96, 0x000000, 0.96).setStrokeStyle(2, WHITE, 0.9));
    const ty = 740, tw = 56;
    items.forEach((it, k) => {
      const x = 30 + k * (tw + 3) + tw / 2;
      tray.add(this.add.rectangle(x, ty, tw, 80).setStrokeStyle(1, WHITE, 0.6));
      tray.add(this.add.image(x, ty - 16, "icons", it.f).setScale(2.4));
      tray.add(this.add.text(x, ty + 24, it.n, { fontFamily: "Consolas,monospace", fontSize: "12px",
        color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2));
    });
    const kitBtn = this.add.rectangle(W - 46, 792, 64, 64).setStrokeStyle(2, WHITE, 0.9).setInteractive();
    this.add.image(W - 46, 786, "icons", 40).setScale(2.6);
    this.add.text(W - 46, 812, "KIT", { fontFamily: "Consolas,monospace", fontSize: "12px",
      color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
    kitBtn.on("pointerdown", () => {
      const open = !tray.__open;
      tray.__open = open;
      if (open) {
        tray.setVisible(true); tray.y = 30; tray.alpha = 0;
        this.tweens.add({ targets: tray, y: -66, alpha: 1, duration: 200, ease: "Quad.easeOut" });
      } else {
        this.tweens.add({ targets: tray, y: 30, alpha: 0, duration: 160, ease: "Quad.easeIn",
          onComplete: () => tray.setVisible(false) });
      }
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

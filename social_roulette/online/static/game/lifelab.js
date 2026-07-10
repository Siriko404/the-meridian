/* PUNCH CARD v10 — final spec.
 * Full-5 tell: a FAINT PULSE DOT glides bottom->top along the column (timer idiom),
 * lighter than the life dots (alpha 0.35), looping while at 5.
 * Chips: ONE struck-O (top) + ONE "!" below it; every dirt-placer's monogram
 * stacks under the "!". View: http://127.0.0.1:8000/static/game/lifelab.html */
"use strict";
const W = 390, H = 844, WHITE = 0xffffff, RED = 0xc8102e;
const DR = 3, DPITCH = 12, DGAP = 6;

function mkP() { return [...Array(5)].map(() => ({ on: false, t: 0, alpha: 1 })); }

class Lab extends Phaser.Scene {
  preload() {
    this.load.spritesheet("faces", "/static/game/assets/portraits/Noir-portraits/36x36-bw-portraits-no-background.png",
      { frameWidth: 36, frameHeight: 36 });
  }

  chrome(x, y, faceIdx, name, blocA) {
    const g = this.add.graphics();
    g.fillStyle(0x000000).fillRect(x - 32, y - 32, 64, 64);
    g.lineStyle(1, WHITE, 1).strokeRect(x - 32, y - 32, 64, 64);
    this.add.image(x, y + 2, "faces", faceIdx).setScale(1.7);
    const pw = blocA ? 0xffffff : 0x000000, pt = blocA ? "#000000" : "#ffffff";
    g.fillStyle(pw).fillRect(x - 26, y + 36, 52, 18);
    g.lineStyle(1, WHITE, 0.95).strokeRect(x - 26, y + 36, 52, 18);
    this.add.text(x, y + 45, name, { fontFamily: "'Times New Roman',serif", fontSize: "13px",
      color: pt, fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
    return g;
  }

  paintPunch(g, st, c, pulseT, mode) {
    const cover = st.filter(q => q.on).length;
    const col = cover <= 2 ? RED : WHITE;
    const px = c.x + (32 + DGAP + DR) * c.s;
    const yBot = c.y + 2 * DPITCH * c.s;
    for (let k = 0; k < 5; k++) {
      const q = st[k], cy = yBot - k * DPITCH * c.s;
      if (q.on) {
        const grow = Math.min(1, q.t * 1.6);
        const sc = q.t < 1 ? (1.5 - 0.5 * q.t) : 1;
        let a = q.alpha;
        if (cover === 5 && pulseT != null) {          // the PULSE: dots shade one by one, bottom->top
          const t = pulseT % 1;                       // wave position 0..1 across the column
          const d = Math.abs(t * 6 - 0.5 - k);        // distance of the wave from dot k
          const wave = Math.max(0, 1 - d * 1.4);      // ~one dot wide
          if (mode === "dip") a *= 1 - wave * 0.75;   // dot goes LIGHTER (deep gray) as the wave passes
          else a *= 0.45 + wave * 0.55;               // dots rest dim; the wave lifts each to full
        }
        g.fillStyle(col, a).fillCircle(px, cy, DR * c.s * sc * grow);
      } else {
        g.lineStyle(1, WHITE, 0.30);
        g.strokeCircle(px, cy, DR * c.s);
      }
    }
  }

  tw(obj, props, dur, ease) {
    return new Promise((r) => this.tweens.add({ targets: obj, ...props, duration: dur,
      ease: ease || "Linear", onComplete: r }));
  }

  async seq(r) {
    const w = (ms) => new Promise((res) => this.time.delayedCall(ms, res));
    for (;;) {
      r.st.forEach((q) => Object.assign(q, { on: false, t: 0, alpha: 1 }));
      await w(600);
      for (let k = 0; k < 5; k++) {
        r.label.setText(k === 4 ? "FULL — WIN WATCH" : "+1");
        const q = r.st[k];
        Object.assign(q, { on: true, t: 0, alpha: 1 });
        await this.tw(q, { t: 1 }, 170, "Back.easeOut");
        await w(360);
      }
      await w(5200);                                  // linger: watch the pulse ride
      r.label.setText("−1 (PUNCHED)");
      for (let k = 4; k >= 1; k--) {
        const q = r.st[k];
        await this.tw(q, { alpha: 0.25 }, 60);
        Object.assign(q, { on: false, t: 0, alpha: 1 });
        await w(400);
      }
      r.label.setText("1 — MORTAL"); await w(1000);
    }
  }

  chipStack(x, y, sedated, dirtNames) {               // ONE struck-O above ONE "!", names below
    const bx = x - 32 - DGAP - 9;
    let cy = y - 20;
    const box = () => {
      const g = this.add.graphics();
      g.fillStyle(0x000000).fillRect(bx - 9, cy - 9, 18, 18);
      g.lineStyle(1, WHITE, 0.9).strokeRect(bx - 9, cy - 9, 18, 18);
      return g;
    };
    if (sedated) {
      const g = box();
      g.lineStyle(1.5, WHITE, 1).strokeCircle(bx, cy, 5.2);
      g.lineBetween(bx - 4, cy + 4, bx + 4, cy - 4);
      cy += 22;
    }
    if (dirtNames.length) {
      box();
      this.add.text(bx, cy - 1, "!", { fontFamily: "'Times New Roman',serif", fontSize: "16px",
        color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
      cy += 15;
      dirtNames.forEach((n) => {
        this.add.text(bx, cy, n, { fontFamily: "'Times New Roman',serif", fontSize: "9px",
          color: "#ffffff", fontStyle: "bold", backgroundColor: "#000000" })
          .setOrigin(0.5, 0).setResolution(2);
        cy += 11;
      });
    }
  }

  chipSeat(x, y, faceIdx, sedated, dirtNames, cap) {
    this.chrome(x, y, faceIdx, "N.D.", true);
    this.chipStack(x, y, sedated, dirtNames);
    this.add.text(x, y + 78, cap, { fontFamily: "Consolas,monospace", fontSize: "9px",
      color: "#9a9a9a" }).setOrigin(0.5).setResolution(2);
  }

  create() {
    this.add.text(W / 2, 18, "PULSE TELL + CHIP STACK — approve", { fontFamily: "Consolas,monospace",
      fontSize: "12px", color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);

    const mkRow = (y, mode, title) => {
      this.add.text(16, y - 105, title, { fontFamily: "Consolas,monospace", fontSize: "11px",
        color: "#ffffff", fontStyle: "bold" }).setResolution(2);
      this.chrome(80, y, 2, "K.V.", true);
      const label = this.add.text(130, y + 80, "", { fontFamily: "Consolas,monospace",
        fontSize: "10px", color: "#9a9a9a" }).setOrigin(0.5).setResolution(2);
      const r = { st: mkP(), label, pulseT: 0, mode,
        real: { x: 80, y, s: 1 }, zoom: { x: 240, y, s: 2.2 },
        g: this.add.graphics().setDepth(8) };
      this.seq(r);
      return r;
    };
    this.rows = [
      mkRow(165, "dip",  "A · DIP — each dot fades to a LIGHTER gray as the wave climbs"),
      mkRow(380, "lift", "B · LIFT — dots rest dimmer; the wave lights each to full"),
    ];
    this.time.addEvent({ delay: 33, loop: true, callback: () => {
      this.rows.forEach((r) => { r.pulseT += 0.033 / 1.8; }); } });

    this.add.text(16, 560, "CHIPS (approved layout, for reference)", {
      fontFamily: "Consolas,monospace", fontSize: "11px", color: "#ffffff", fontStyle: "bold" }).setResolution(2);
    this.chipSeat(110, 660, 7, true,  ["K.V."],                 "sedated + 1 dirt");
    this.chipSeat(290, 660, 7, true,  ["K.V.", "W.N.", "C.W."], "sedated + 3 dirts");
    console.log("LIFELAB v10 OK");
  }

  update() {
    for (const r of this.rows) {
      r.g.clear();
      [r.real, r.zoom].forEach((c) => this.paintPunch(r.g, r.st, c, r.pulseT));
    }
  }
}

window.__lab = new Phaser.Game({
  type: Phaser.CANVAS, parent: "stage", width: W, height: H, backgroundColor: "#000000",
  pixelArt: true, scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene: Lab,
});

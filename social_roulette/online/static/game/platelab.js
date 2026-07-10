/* NAMEPLATE v1 — minimal/elegant, box KILLED. Bare serif name under the frame;
 * team polarity carried by: 1 RULE (solid vs dotted hairline) · 2 MARKER (filled
 * vs hollow diamond) · 3 SHADE (full vs soft alpha). Both teams + dead state.
 * Chips reference: dirt names at 80% of the plate-name size.
 * View: http://127.0.0.1:8000/static/game/platelab.html */
"use strict";
const W = 390, H = 844, WHITE = 0xffffff, RED = 0xc8102e;
const DR = 3, DPITCH = 12, DGAP = 6;
const NAME_FS = 14;                                   // plate name; chips = 80% of this

class Lab extends Phaser.Scene {
  preload() {
    this.load.spritesheet("faces", "/static/game/assets/portraits/Noir-portraits/36x36-bw-portraits-no-background.png",
      { frameWidth: 36, frameHeight: 36 });
  }

  tile(x, y, faceIdx, blocA, dead) {
    const g = this.add.graphics();
    g.fillStyle(0x000000).fillRect(x - 32, y - 32, 64, 64);
    g.lineStyle(1, WHITE, (dead ? 0.4 : 1) * (blocA ? 1 : 0.5)).strokeRect(x - 32, y - 32, 64, 64);
    const f = this.add.image(x, y + 2, "faces", faceIdx).setScale(1.7);
    if (dead) f.setAlpha(0.35);
    return g;
  }

  name(x, y, txt, blocA, m, dead) {                   // m = {gap, pad} margins
    const g = this.add.graphics();
    const ny = y + 32 + m.gap;                        // name center: tile bottom + gap
    if (dead) {
      const t = this.add.text(x, ny, txt, { fontFamily: "'Times New Roman',serif",
        fontSize: NAME_FS + "px", color: "#666666", fontStyle: "bold", stroke: "#000000",
        strokeThickness: 5 }).setOrigin(0.5).setResolution(2).setLetterSpacing(2);
      g.lineStyle(1, WHITE, 0.7).lineBetween(x - t.width / 2, ny, x + t.width / 2, ny);
      return;
    }
    const w2 = 32, h2 = 7 + m.pad;                    // plate spans the frame width (lab tile = 64)
    if (blocA) {                                      // A: black text in a slim WHITE BOX
      this.add.text(x, ny, txt, { fontFamily: "'Times New Roman',serif",
        fontSize: NAME_FS + "px", color: "#000000", fontStyle: "bold" })
        .setOrigin(0.5).setResolution(2).setLetterSpacing(2).setDepth(2);
      g.fillStyle(0xffffff, 1).fillRect(x - w2, ny - h2, w2 * 2, h2 * 2);
    } else {                                          // B: white text between two thin rules
      this.add.text(x, ny, txt, { fontFamily: "'Times New Roman',serif",
        fontSize: NAME_FS + "px", color: "#ffffff", fontStyle: "bold", stroke: "#000000",
        strokeThickness: 5 }).setOrigin(0.5).setResolution(2).setLetterSpacing(2);
      g.lineStyle(1, WHITE, 0.9);
      g.lineBetween(x - w2, ny - h2, x + w2, ny - h2);
      g.lineBetween(x - w2, ny + h2, x + w2, ny + h2);
    }
  }

  dots(x, y, n) {
    const g = this.add.graphics();
    const px = x + 32 + DGAP + DR, y0 = y + 2 * DPITCH;
    for (let k = 0; k < 5; k++) {
      const cy = y0 - k * DPITCH;
      if (k < n) g.fillStyle(n <= 2 ? RED : WHITE, 1).fillCircle(px, cy, DR);
      else { g.lineStyle(1, WHITE, 0.3); g.strokeCircle(px, cy, DR); }
    }
  }

  chips(x, y, sedated, dirtNames) {
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
        this.add.text(bx, cy, n, { fontFamily: "'Times New Roman',serif",
          fontSize: Math.round(NAME_FS * 0.8) + "px", color: "#ffffff", fontStyle: "bold",
          stroke: "#000000", strokeThickness: 4 }).setOrigin(0.5, 0).setResolution(2);
        cy += Math.round(NAME_FS * 0.8) + 3;
      });
    }
  }

  seat(x, y, faceIdx, txt, blocA, mode, opts) {
    opts = opts || {};
    this.tile(x, y, faceIdx, blocA, opts.dead);
    this.name(x, y, txt, blocA, mode, opts.dead);
    if (!opts.dead) this.dots(x, y, opts.cover != null ? opts.cover : 3);
    if (opts.chips) this.chips(x, y, true, ["K.V."]);
  }

  create() {
    this.add.text(W / 2, 18, "NAMEPLATES — MINIMAL — PICK A ROW", { fontFamily: "Consolas,monospace",
      fontSize: "13px", color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
    this.add.text(W / 2, 36, "per row: team A · team B · dead — dots+chips for context", { fontFamily: "Consolas,monospace",
      fontSize: "10px", color: "#9a9a9a" }).setOrigin(0.5).setResolution(2);

    this.add.text(16, 60, "M1 — gap 16 / pad 3", {
      fontFamily: "Consolas,monospace", fontSize: "11px", color: "#ffffff", fontStyle: "bold" }).setResolution(2);
    const M1 = { gap: 16, pad: 3 };
    this.seat(75,  170, 2, "K.V.", true,  M1, { cover: 5, chips: true });
    this.seat(195, 170, 7, "W.N.", false, M1, { cover: 2 });
    this.seat(315, 170, 4, "C.W.", true,  M1, { dead: true });
    this.add.text(16, 300, "M2 — gap 22 / pad 5 (more air)", {
      fontFamily: "Consolas,monospace", fontSize: "11px", color: "#ffffff", fontStyle: "bold" }).setResolution(2);
    const M2 = { gap: 22, pad: 5 };
    this.seat(75,  410, 5, "H.Y.", false, M2, { cover: 4 });
    this.seat(195, 410, 9, "M.T.", true,  M2, { cover: 3 });
    this.seat(315, 410, 11, "P.K.", false, M2, { dead: true });
    console.log("PLATELAB v1 OK");
  }
}

window.__lab = new Phaser.Game({
  type: Phaser.CANVAS, parent: "stage", width: W, height: H, backgroundColor: "#000000",
  pixelArt: true, scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene: Lab,
});

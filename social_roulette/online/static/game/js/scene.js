/* TableScene — the dining car. Task 3 stub: boots, loads assets, proves the pipeline. */
(function (global) {
  "use strict";
  const W = 390, H = 844, RED = 0xc8102e, WHITE = 0xffffff;
  const SCENE = { ready: null };            // main.js sets SCENE.ready before boot

  class TableScene extends Phaser.Scene {
    preload() {
      this.load.spritesheet("faces", "/static/game/assets/portraits/Noir-portraits/36x36-bw-portraits-no-background.png",
        { frameWidth: 36, frameHeight: 36 });
      this.load.spritesheet("icons", "/static/game/assets/Mystery_Icons.png", { frameWidth: 16, frameHeight: 16 });
    }
    create() {
      this.add.text(W / 2, H / 2, "CAR 4", { fontFamily: "Consolas,monospace", fontSize: "20px",
        color: "#ffffff", fontStyle: "bold" }).setOrigin(0.5).setResolution(2);
      if (SCENE.ready) SCENE.ready(this);
    }
    render(view, roster) { /* Task 4 */ }
  }

  SCENE.TableScene = TableScene; SCENE.W = W; SCENE.H = H; SCENE.RED = RED; SCENE.WHITE = WHITE;
  global.SCENE = SCENE;
})(typeof window !== "undefined" ? window : globalThis);

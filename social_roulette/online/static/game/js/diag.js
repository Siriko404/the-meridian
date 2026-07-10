/* DEV-ONLY FPS diagnosis HUD — loaded ONLY with ?diag in the URL (index.html gate).
 * Measures raw rAF cadence + names the renderer; the toggle links reload with one
 * suspect disabled each, so a single phone session can bisect the FPS culprit. */
(function () {
  "use strict";
  const q = new URLSearchParams(location.search);

  /* ---- suspect toggles (each reload flips ONE knob) ---- */
  if (q.get("res1") && window.Phaser)            // all text textures at 1x instead of 2x
    Phaser.GameObjects.Text.prototype.setResolution = function () { return this; };
  if (q.get("nopulse") && window.SCENE && SCENE.TableScene)   // stop the 33ms shimmer redraw
    SCENE.TableScene.prototype._drawPulse = function () {};

  /* ---- HUD ---- */
  const hud = document.createElement("div");
  hud.style.cssText = "position:fixed;left:4px;top:4px;z-index:9999;font:11px monospace;" +
    "color:#0f0;background:rgba(0,0,0,.75);padding:4px 6px;pointer-events:none;white-space:pre";
  document.body.appendChild(hud);
  const bar = document.createElement("div");
  bar.style.cssText = "position:fixed;left:4px;top:56px;z-index:9999;font:12px monospace;" +
    "background:rgba(0,0,0,.75);padding:4px 6px";
  const mk = (label, params) => '<a style="color:#ff0;margin-right:10px" href="?' + params + '">' + label + "</a>";
  bar.innerHTML = mk("BASE", "diag=1") + mk("RES1", "diag=1&res1=1") +
    mk("NOPULSE", "diag=1&nopulse=1") + mk("CANVAS", "diag=1&canvas=1") +
    mk("ALL", "diag=1&res1=1&nopulse=1&canvas=1");
  document.body.appendChild(bar);

  /* ---- rAF meter: rolling 2s window ---- */
  let frames = [], last = performance.now();
  (function loop(t) {
    if (t != null) {
      const d = t - last; last = t;
      if (d < 1000) frames.push(d);   // >1s = tab was hidden (rAF paused), not a real frame
    }
    if (frames.length > 120) frames.shift();
    requestAnimationFrame(loop);
  })();
  setInterval(() => {
    if (!frames.length) { hud.textContent = "rAF paused — bring the tab to the foreground"; return; }
    const avg = frames.reduce((a, b) => a + b, 0) / frames.length;
    const worst = Math.max.apply(null, frames);
    const g = window.__game, sc = window.__scene;
    const r = g && g.renderer ? (g.renderer.gl ? "WEBGL" : "CANVAS") : "no game yet";
    const cv = g && g.canvas ? g.canvas.width + "x" + g.canvas.height : "";
    const objs = sc && sc.children ? sc.children.list.length : 0;
    const flags = ["res1", "nopulse", "canvas"].filter((k) => q.get(k)).join("+") || "none";
    hud.textContent =
      "FPS " + (1000 / avg).toFixed(0) + " · avg " + avg.toFixed(1) + "ms · worst " + worst.toFixed(0) + "ms\n" +
      r + " · DPR " + (window.devicePixelRatio || 1) + " · " + cv + " · objs " + objs + "\n" +
      "flags " + flags;
  }, 500);
})();

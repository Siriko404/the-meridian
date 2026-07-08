/* TRAYS — icon-gated sheets over the dock (spec §6.2). One open at a time.
 * KIT caps ALWAYS visible while open, as numbers (S7/I10/a15 — Global Constraint 16). */
(function (global) {
  "use strict";
  const MONO = "Consolas,monospace";
  const st = (size, color) => ({ fontFamily: MONO, fontSize: (size + 1) + "px",
    color: color || "#ffffff", fontStyle: "bold", align: "center",
    stroke: "#000000", strokeThickness: 4 });
  const ORDER = ["BEER", "HANDCUFFS", "MAGNIFIER", "SAW", "CIGARETTES", "IMMUNITY"];
  let open = null;

  function close() {
    if (!open) return;
    open.scene.seats.forEach((s) => s.chipT.setVisible(true));   // board chips return
    open.cont.destroy(); open = null;
  }
  function tray(scene, name, h) {
    close();
    scene.seats.forEach((s) => s.chipT.setVisible(false));       // modal focus — no half-cut chips
    const y = 844 - h / 2 - 4;
    const cont = scene.add.container(0, 0).setDepth(22);
    cont.add(scene.add.rectangle(SCENE.W / 2, y, SCENE.W - 8, h, 0x000000, 0.97)
      .setStrokeStyle(2, 0xffffff, 0.95).setInteractive()
      .on("pointerdown", close));                               // sheet tap = dismiss (child buttons run first)
    cont.y = h; scene.tweens.add({ targets: cont, y: 0, duration: 180, ease: "Quad.easeOut" });
    open = { cont, name, scene };
    return { cont, top: y - h / 2 };
  }
  const txt = (scene, cont, x, y, s, size, color) => {
    const t = scene.add.text(x, y, s, st(size, color)).setOrigin(0.5).setResolution(2);
    cont.add(t); return t;
  };
  const btn = (scene, cont, x, y, w, h, label, cb) => {
    cont.add(scene.add.rectangle(x, y, w, h, 0x000000).setStrokeStyle(2, 0xffffff, 0.95)
      .setInteractive().on("pointerdown", cb));
    txt(scene, cont, x, y, label, 14);
  };

  /* ---- KIT: your items + ALL the cap numbers (Global Constraint 16) ---- */
  function kit(scene, view, opts) {
    if (open && open.name === "kit") { close(); return; }
    const { cont, top } = tray(scene, "kit", 190);
    const total = Object.values(view.your_hand || {}).reduce((a, b) => a + b, 0);
    txt(scene, cont, SCENE.W / 2, top + 16, "KIT · " + total + "/" + THEME.MAX_TOTAL, 15);
    const me = view.players.find((p) => p.id === view.you) || {};
    ORDER.forEach((en, k) => {
      const x = 36 + k * 62, y = top + 108;
      const n = (view.your_hand || {})[en] || 0;
      const left = Math.max(0, (view.use_limit || 0) - ((view.use_counts || {})[en] || 0));
      const sealed = left <= 0;
      const fullCover = en === "CIGARETTES" && (me.lives || 0) >= THEME.MAX_LIVES;
      const usable = !!(opts && opts.usable && opts.usable.has(en)) && n > 0 && !sealed && !fullCover;
      const card = scene.add.rectangle(x, y, 58, 134, 0x000000)
        .setStrokeStyle(1, 0xffffff, usable ? 0.95 : 0.4);
      cont.add(card);
      cont.add(scene.add.image(x, y - 44, "icons", THEME.ITEMS[en].icon).setScale(2.2)
        .setAlpha(n > 0 && !sealed && !fullCover ? 1 : 0.35));
      txt(scene, cont, x, y - 18, THEME.ITEMS[en].name, 10, n > 0 ? "#ffffff" : "#666666");
      txt(scene, cont, x, y + 2, n + "/" + THEME.MAX_PER_TYPE, 13, n > 0 ? "#ffffff" : "#666666");
      txt(scene, cont, x, y + 22, left + " LEFT", 13, sealed ? "#666666" : "#aaaaaa");
      if (sealed) txt(scene, cont, x, y + 46, "SEALED\nTIL DEATH", 13, "#666666");
      else if (fullCover) txt(scene, cont, x, y + 46, "AT FULL\nCOVER", 13, "#666666");
      if (usable) card.setInteractive().on("pointerdown", () => { close(); opts.onPick(en); });
    });
  }

  /* ---- LEDGER: the public counts panel (V3/I10) ---- */
  function ledger(scene, view) {
    if (open && open.name === "ledger") { close(); return; }
    const { cont, top } = tray(scene, "ledger", 170);
    txt(scene, cont, SCENE.W / 2, top + 16, "LEDGER · IN PLAY / USES LEFT", 14);
    ORDER.forEach((en, k) => {
      const x = 36 + k * 62, y = top + 96;
      const inPlay = (view.item_counts || {})[en] || 0;
      const left = Math.max(0, (view.use_limit || 0) - ((view.use_counts || {})[en] || 0));
      cont.add(scene.add.rectangle(x, y, 58, 110, 0x000000).setStrokeStyle(1, 0xffffff, 0.5));
      cont.add(scene.add.image(x, y - 32, "icons", THEME.ITEMS[en].icon).setScale(2.2)
        .setAlpha(inPlay > 0 ? 1 : 0.35));
      txt(scene, cont, x, y - 6, THEME.ITEMS[en].name, 10);
      txt(scene, cont, x, y + 16, "×" + inPlay, 14, inPlay > 0 ? "#ffffff" : "#666666");
      txt(scene, cont, x, y + 38, left + " LEFT", 13, left > 0 ? "#aaaaaa" : "#666666");
    });
  }

  /* ---- FLIP payment: pick which items pay (E4). Ownership-only — PASSPORT at
   *      full cover stays selectable here (Global Constraint 16). ---- */
  function pay(scene, view, target, cost, roster, onConfirm, onCancel) {
    const chosen = [];
    function build() {
      const { cont, top } = tray(scene, "pay", 214);
      const total = chosen.reduce((s, en) => s + THEME.ITEMS[en].pts, 0);
      txt(scene, cont, SCENE.W / 2, top + 16,
        "FLIP " + THEME.seatName(target, roster) + " · " + total + "/" + cost + " PTS", 15);
      const avail = Object.assign({}, view.your_hand || {});
      chosen.forEach((en) => { avail[en] = (avail[en] || 0) - 1; });
      ORDER.forEach((en, k) => {
        const x = 36 + k * 62, y = top + 84;
        const can = (avail[en] || 0) > 0;
        const card = scene.add.rectangle(x, y, 58, 86, 0x000000).setStrokeStyle(1, 0xffffff, can ? 0.95 : 0.35);
        cont.add(card);
        cont.add(scene.add.image(x, y - 22, "icons", THEME.ITEMS[en].icon).setScale(2).setAlpha(can ? 1 : 0.35));
        txt(scene, cont, x, y + 4, THEME.ITEMS[en].name, 10, can ? "#ffffff" : "#666666");
        txt(scene, cont, x, y + 26, THEME.ITEMS[en].pts + " PTS", 13, can ? "#aaaaaa" : "#666666");
        if (can) card.setInteractive().on("pointerdown", () => { chosen.push(en); build(); });
      });
      const by = top + 172;
      btn(scene, cont, 70, by, 110, 38, "CANCEL", () => { close(); onCancel(); });
      if (chosen.length) btn(scene, cont, 195, by, 100, 38, "UNDO", () => { chosen.pop(); build(); });
      if (total >= cost) btn(scene, cont, 320, by, 110, 38, "CONFIRM", () => onConfirm(chosen.slice()));
    }
    build();
  }

  /* ---- TRADE offer: GIVE/WANT pickers, UNBOUND from inventory (bluffing designed-in, §4.5) ---- */
  function offer(scene, view, to, roster, onSend, onCancel) {
    const give = {}, want = {};
    function row(cont, top, label, bag, yy) {
      txt(scene, cont, 34, yy, label, 14);
      ORDER.forEach((en, k) => {
        const x = 78 + k * 52, y = yy;
        const cnt = bag[en] || 0;
        const c = scene.add.rectangle(x, y, 48, 54, 0x000000).setStrokeStyle(1, 0xffffff, cnt ? 0.95 : 0.4)
          .setInteractive().on("pointerdown", () => { bag[en] = ((bag[en] || 0) + 1) % 4; build(); });
        cont.add(c);
        cont.add(scene.add.image(x, y - 12, "icons", THEME.ITEMS[en].icon).setScale(1.7)
          .setAlpha(cnt ? 1 : 0.45));
        txt(scene, cont, x, y + 16, "×" + cnt, 13, cnt ? "#ffffff" : "#555555");
      });
    }
    function build() {
      const { cont, top } = tray(scene, "offer", 250);
      txt(scene, cont, SCENE.W / 2, top + 16, "OFFER TO " + THEME.seatName(to, roster) + " · PRIVATE", 15);
      txt(scene, cont, SCENE.W / 2, top + 36, "TAP CYCLES ×0–×3 · UNBOUND — BLUFF FREELY", 13, "#888888");
      row(cont, top, "GIVE", give, top + 84);
      row(cont, top, "WANT", want, top + 150);
      const expand = (bag) => Object.entries(bag).flatMap(([en, c]) => Array(c).fill(en));
      const by = top + 212;
      btn(scene, cont, 100, by, 140, 38, "CANCEL", () => { close(); onCancel(); });
      btn(scene, cont, 280, by, 160, 38, "SEND OFFER", () => onSend(expand(give), expand(want)));
    }
    build();
  }

  /* ---- respond: the counterparty's ACCEPT/DECLINE (rides the VIEW — reconnect-safe, a19) ---- */
  function respond(scene, view, roster, onAccept, onDecline) {
    const po = view.pending_offer; if (!po) return;
    const { cont, top } = tray(scene, "respond", 190);
    const list = (arr) => arr && arr.length
      ? arr.map((en) => THEME.itemName(en)).join(" · ") : "NOTHING";
    txt(scene, cont, SCENE.W / 2, top + 16, THEME.seatName(po.from, roster) + " OFFERS · PRIVATE", 15);
    txt(scene, cont, SCENE.W / 2, top + 54, "THEY GIVE: " + list(po.give), 13);
    txt(scene, cont, SCENE.W / 2, top + 84, "THEY WANT: " + list(po.want), 13);
    txt(scene, cont, SCENE.W / 2, top + 112, "OFFERS MAY BLUFF — SETTLEMENT VERIFIES", 13, "#888888");
    const by = top + 152;
    btn(scene, cont, 110, by, 150, 40, "DECLINE", onDecline);
    btn(scene, cont, 280, by, 150, 40, "ACCEPT", onAccept);
  }

  const TRAYS = { close, kit, ledger, pay, offer, respond };
  global.TRAYS = TRAYS;
  if (typeof module !== "undefined" && module.exports) module.exports = TRAYS;
})(typeof window !== "undefined" ? window : globalThis);

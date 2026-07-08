/* Controller. Sections: [NET-GLUE] ws+lobby · [DRAIN] queue (replaced Task 6) · [ACT] (added Task 7). */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ("&#" + c.charCodeAt(0) + ";"));
  let net = null, token = localStorage.meridian_token || null, host = false;
  let game = null, scene = null, sceneCode = "";
  let queue = [], busy = false, ended = false, endWinner = null;
  let curView = null, roster = null;
  const accept = NET.genGate();
  let bannerT = null;

  function banner(text, holdMs) {
    const b = $("banner");
    b.textContent = text; b.style.display = "block";
    clearTimeout(bannerT);
    bannerT = setTimeout(() => { b.style.display = "none"; }, holdMs || 2500);
  }
  function show(id) {
    document.querySelectorAll(".overlay").forEach((s) => s.classList.remove("on"));
    if (id) $(id).classList.add("on");
  }

  /* ---- [NET-GLUE] ---- */
  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    net = NET.connect(() => new WebSocket(proto + "://" + location.host + "/ws"), handle);
    net.ws.onopen = () => net.send({ type: "join", code: $("code").value, name: $("name").value, token });
    net.ws.onclose = () => banner("DISCONNECTED — RELOAD TO RECONNECT", 60000);
    setInterval(() => net.send({ type: "ping" }), 20000);
  }
  function handle(m) {
    if (m.type === "joined") {
      token = m.token; host = m.host; localStorage.meridian_token = token;
      show("lobby"); $("startbtn").style.display = host ? "" : "none";
    } else if (m.type === "lobby") {
      sceneCode = m.code;
      $("lcode").textContent = m.code;
      $("members").innerHTML = m.members.map((x) =>
        `<div class="member">${esc(x.name)}${x.host ? " · CONDUCTOR" : ""}</div>`).join("");
    } else if (m.type === "view") {
      roster = m.roster || roster;
      queue.push({ events: accept(m) ? (m.events || []) : [], view: m });
      bootGame(); drain();
    } else if (m.type === "chat") {
      const log = $("chatlog");
      log.innerHTML += `<div><b>${esc(m.from)}</b> ${esc(m.text)}</div>`;
      log.scrollTop = log.scrollHeight;
      if (scene) scene.setTicker(m.from + ": " + m.text);
    } else if (m.type === "error") {
      banner("⚠ " + m.msg);
      if (curView) cancelSel();               // rejected action → restore the verb strip
    } else if (m.type === "end") {
      ended = true; endWinner = m.winner; drain();
    }
  }
  function bootGame() {
    if (game) return;
    show(null);
    SCENE.ready = (s) => { scene = s; s.setCode(sceneCode); drain(); };
    game = new Phaser.Game({
      type: Phaser.AUTO, parent: "stage", width: SCENE.W, height: SCENE.H,
      backgroundColor: "#000000", pixelArt: true,
      scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
      scene: SCENE.TableScene,
    });
  }

  /* ---- [DRAIN] queue → choreography → settle (v1's proven loop, gen-gated at enqueue) ---- */
  let firstView = true, leftFn = null, noteOverride = null;

  async function drain() {
    if (busy || !scene) return;
    busy = true;
    scene.setBand({ phase: null });                            // timers stand down while beats play
    while (queue.length) {
      const it = queue.shift();
      const prev = curView;
      curView = it.view;
      leftFn = NET.countdown(curView);
      if (firstView) {
        firstView = false;
        const ann = (it.events || []).find((e) => e.type === "announce");
        await CHOREO.setup(scene, curView, roster, ann);       // M1–M5
      } else if (it.events && it.events.length) {
        await CHOREO.play(scene, it.events, prev, curView, roster);
      } else {
        scene.render(curView, roster);                         // stale/rebroadcast: settle only
      }
    }
    busy = false;                                              // BEFORE afterSettle — myTurn() checks it
    noteOverride = null;
    afterSettle();                                             // Task 7: rebuild verbs/trays
    tick();
  }
  /* ---- [ACT] interaction grammar (§6.3): verb → picker → red brackets → confirm ---- */
  function myTurn() {
    return curView && curView.winner == null && curView.current === curView.you && !busy;
  }
  function meAlive() {
    const p = curView && curView.players.find((q) => q.id === curView.you);
    return !!(p && p.alive);
  }
  function teammates() {
    if (!curView.teams_active) return [];
    const me = curView.players.find((p) => p.id === curView.you);
    return curView.players.filter((p) => p.alive && p.id !== curView.you && p.team === me.team)
      .map((p) => p.id);
  }

  function afterSettle() {
    noteOverride = null;
    scene.clearTargets(); scene.seatGlow([], false); TRAYS.close();
    const over = curView.winner != null;
    scene.onKit = over ? null : () => TRAYS.kit(scene, curView, usableOpts());   // info mode off-turn
    scene.onLedger = over ? null : () => TRAYS.ledger(scene, curView);
    scene.onPhone = () => $("chatsheet").classList.toggle("on");
    const chatOk = curView.phase === "talk" && meAlive() && curView.winner == null;
    $("chatin").disabled = !chatOk;
    $("chatin").placeholder = chatOk ? "say something…" : "SILENCE.";
    buildStrip();
    const po = curView.pending_offer;                                // incoming offer → tray now
    if (po && po.to === curView.you) {                               // (rides the view: reconnect-safe)
      TRAYS.respond(scene, curView, roster,
        () => { TRAYS.close(); net.send({ type: "trade_respond", accept: true }); },
        () => { TRAYS.close(); net.send({ type: "trade_respond", accept: false }); });
    }
  }

  function usableOpts() {
    if (!myTurn()) return {};
    const usable = new Set((curView.legal || []).filter((a) => a.kind === "item").map((a) => a.item));
    return { usable, onPick: pickItemTargets };
  }

  function buildStrip() {
    if (!myTurn()) { scene.setStrip([]); return; }
    const kinds = new Set((curView.legal || []).map((a) => a.kind));
    const po = curView.pending_offer;
    const defs = [];
    if (curView.phase === "talk") {
      if (kinds.has("item")) defs.push({ label: "ITEM", onTap: () => TRAYS.kit(scene, curView, usableOpts()) });
      if (po && po.from === curView.you)
        defs.push({ label: "WITHDRAW", onTap: () => net.send({ type: "trade_withdraw" }), wide: true });
      else if (teammates().length) defs.push({ label: "TRADE", onTap: pickTrade });
      defs.push({ label: "PROCEED", onTap: () => { wait(); net.send({ type: "proceed" }); }, wide: true });
    } else if (curView.phase === "decision") {
      if (kinds.has("shoot")) defs.push({ label: "SHOOT", onTap: () => pickTarget("shoot") });
      if (kinds.has("flip")) defs.push({ label: "FLIP", onTap: () => pickTarget("flip") });
      if (kinds.has("item")) defs.push({ label: "ITEM", onTap: () => TRAYS.kit(scene, curView, usableOpts()) });
    }
    scene.setStrip(defs);
  }

  function cancelSel() {
    noteOverride = null;
    scene.clearTargets(); scene.seatGlow([], false); TRAYS.close();
    buildStrip(); tick();
  }
  function confirmAct(label, go) {
    scene.setStrip([{ label: label, onTap: go, wide: true },   // the labeled verb IS the confirm
                    { label: "✕", onTap: cancelSel }]);
  }
  function wait() { scene.clearTargets(); scene.seatGlow([], false); scene.setStrip([]); }
  function sendAction(i) { wait(); TRAYS.close(); net.send({ type: "action", i }); }

  function pickItemTargets(en) {
    const entries = curView.legal.filter((a) => a.kind === "item" && a.item === en);
    const nt = entries.find((a) => a.target == null);
    if (nt) { confirmAct("USE " + THEME.itemName(en), () => sendAction(nt.i)); return; }
    scene.setTargets(entries.map((a) => a.target), (id) => {
      const a = entries.find((x) => x.target === id);
      scene.clearTargets();
      confirmAct(THEME.itemName(en) + " → " + THEME.seatName(id, roster), () => sendAction(a.i));
    });
  }

  function pickTarget(kind) {
    const entries = curView.legal.filter((a) => a.kind === kind);
    const ids = entries.map((a) => a.target);
    if (kind === "shoot" && ids.length === 1 && ids[0] === curView.you) {     // M11/L4
      noteOverride = "NO LEGAL TARGETS — YOU FACE THE GUN (FLIP SOMEONE TO CHANGE THAT)";
      tick();
    }
    scene.setTargets(ids, (id) => {
      const a = entries.find((x) => x.target === id);
      scene.clearTargets();
      if (kind === "flip") {
        TRAYS.pay(scene, curView, id, a.cost, roster,
          (items) => { TRAYS.close(); wait(); net.send({ type: "flip", target: id, items }); },
          cancelSel);
      } else {
        const tgt = id === curView.you ? "YOURSELF" : THEME.seatName(id, roster);
        confirmAct("SHOOT " + tgt, () => sendAction(a.i));
      }
    });
  }

  function pickTrade() {                                          // M26 — glow, NOT red brackets
    scene.seatGlow(teammates(), true, (id) => {
      scene.seatGlow([], false);
      TRAYS.offer(scene, curView, id, roster,
        (give, want) => { TRAYS.close(); net.send({ type: "trade_offer", to: id, give, want }); buildStrip(); },
        cancelSel);
    });
  }

  /* ---- band timer: wall-clock tick (rAF-throttle safe — constraint 17) ---- */
  function computeNote(v) {
    if (!v || v.winner != null) return "";
    if (noteOverride) return noteOverride;                     // M11 forced-self line (Task 7)
    const living = v.players.filter((p) => p.alive);
    if (v.teams_active && living.length >= 3 && new Set(living.map((p) => p.team)).size === 1)
      return "ONE AGENCY HOLDS THE TRAIN — TURN SOMEONE, OR FACE THE GUN";   // M27b
    return "";
  }
  function tick() {
    if (!curView || !scene || !scene.built || busy) return;    // never overwrite a playing beat
    const secs = leftFn ? leftFn() : null;
    const mine = curView.current === curView.you;
    scene.setBand({
      phase: curView.winner != null ? null : curView.phase,
      secs,
      name: curView.winner != null ? "" :
        (mine ? "YOUR TURN · " : "") + THEME.seatName(curView.current, roster),
      bonus: curView.bonus,
      invert: curView.phase === "decision" && curView.winner == null,
      note: computeNote(curView),
    });
  }
  setInterval(tick, 250);
  document.addEventListener("pointerdown", () => { if (busy) CHOREO.skip(); }, true);

  /* ---- wiring ---- */
  $("enterbtn").addEventListener("click", connect);
  $("name").addEventListener("keydown", (e) => { if (e.key === "Enter") connect(); });
  $("code").addEventListener("keydown", (e) => { if (e.key === "Enter") connect(); });
  $("startbtn").addEventListener("click", () => net.send({ type: "start" }));
  const sendChat = () => {
    const t = $("chatin").value.trim();
    if (t) { net.send({ type: "chat", text: t }); $("chatin").value = ""; }
  };
  $("chatsend").addEventListener("click", sendChat);
  $("chatin").addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });
})();

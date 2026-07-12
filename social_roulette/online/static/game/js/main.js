/* Controller. Sections: [NET-GLUE] ws+lobby · [DRAIN] queue (replaced Task 6) · [ACT] (added Task 7). */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ("&#" + c.charCodeAt(0) + ";"));
  let net = null, host = false;
  let pid = localStorage.meridian_pid || null, profile = null;
  try { profile = JSON.parse(localStorage.meridian_profile || "null"); } catch (e) { /* stale */ }
  let pendingCode = null, joining = false;      // the code we asked to board (join-phase errors only)
  let myReady = false, lobbySeats = 5, lobbyAllReady = false;   // platform state (spec §3)
  let game = null, scene = null, sceneCode = "";
  let queue = [], busy = false, ended = false, endWinner = null;
  let curView = null, roster = null, portraits = null;
  const accept = NET.genGate();
  let bannerT = null;
  let seizeInFlight = false;                  // a seize awaiting its verdict (v2-3 alarm routing)

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

  /* ---- [PAPERS] identity pages: terminus → papers/sign-in → dashboard (spec §1) ---- */
  const api = (path, opts) => fetch(path, opts).then(async (r) => {
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.msg || "the line is down");
    return j;
  });
  const faceCSS = (el, frame) => {                          // 4x3 sheet of 36px, shown 2x
    el.style.backgroundPosition = (-(frame % 4) * 72) + "px " + (-Math.floor(frame / 4) * 72) + "px";
  };
  function saveProfile(p) {
    profile = p; pid = p.pid;
    localStorage.meridian_pid = pid;
    localStorage.meridian_profile = JSON.stringify(p);
  }
  function gotoTerminus() {
    if (profile) {
      $("contbtn").style.display = "";
      $("contbtn").textContent = "CONTINUE AS " + profile.initials;
    } else $("contbtn").style.display = "none";
    show("terminus");
  }
  function gotoDashboard() {
    faceCSS($("dface"), profile.portrait);
    $("dmono").textContent = profile.initials;
    $("dpid").textContent = "DOCUMENT NO. " + profile.pid;
    show("dashboard");
    api("/journeys?pid=" + encodeURIComponent(pid)).then((j) => {
      const rows = (j.journeys || []).map((x) =>
        `<div class="jrow"><span class="member">CAR ${esc(x.code)} · ${x.seats || "?"} SEATS</span>` +
        `<button data-code="${esc(x.code)}">REJOIN</button></div>`).join("");
      $("journeys").innerHTML = rows || '<p class="hint">THE LINE IS QUIET.</p>';
      $("journeys").querySelectorAll("button").forEach((b) =>
        b.addEventListener("click", () => connect(b.dataset.code)));
    }).catch(() => {});
  }

  /* ---- [NET-GLUE] ---- */
  function connect(code) {
    pendingCode = String(code == null ? $("code").value : code).trim().toUpperCase();
    joining = true;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    net = NET.connect(() => new WebSocket(proto + "://" + location.host + "/ws"), handle);
    net.ws.onopen = () => net.send({ type: "join", code: pendingCode, pid });
    net.ws.onclose = () => banner("DISCONNECTED — RELOAD TO RECONNECT", 60000);
    setInterval(() => net.send({ type: "ping" }), 20000);
  }
  function handle(m) {
    if (m.type === "joined") {
      joining = false; host = m.host;
      if (pendingCode) localStorage.meridian_car = pendingCode;   // rejoinable from any device
      show("lobby"); $("startbtn").style.display = host ? "" : "none";
    } else if (m.type === "lobby") {
      sceneCode = m.code;
      localStorage.meridian_car = m.code;                   // a fresh car mints its code here
      host = m.host; lobbySeats = m.seats; lobbyAllReady = m.all_ready;
      $("lcode").textContent = m.code;
      $("lsub").textContent = "NIGHT SERVICE · " + m.seats + " SEATS";
      $("seatsn").textContent = m.seats + " SEATS";
      $("members").innerHTML = m.members.map((x) =>
        `<div class="mrow"><span class="mface" style="background-position:${-(x.portrait % 4) * 36}px ${-Math.floor(x.portrait / 4) * 36}px"></span>` +
        `<span class="member">${esc(x.name)}${x.host ? " · CONDUCTOR" : ""}</span>` +
        `<span class="mready${x.ready ? " on" : ""}">${x.ready ? "✓" : "·"}</span></div>`).join("");
      const me = m.members[m.you] || {};
      myReady = !!me.ready;
      $("readybtn").textContent = myReady ? "READY ✓" : "I AM READY";
      $("readybtn").classList.toggle("ghost", !myReady);
      $("dial").style.display = m.host ? "flex" : "none";
      $("startbtn").style.display = m.host ? "" : "none";
      $("startbtn").classList.toggle("locked", !m.all_ready);   // DEPART sleeps until the
    } else if (m.type === "view") {
      roster = m.roster || roster;
      portraits = m.portraits || portraits;
      seizeInFlight = false;                  // any fresh state settles the seize silently
      // anchor the countdown at ARRIVAL — anchoring at drain time (after queued beats
      // played) ran the clock seconds ahead, then re-anchors jumped it (timer-freeze class)
      queue.push({ events: accept(m) ? (m.events || []) : [], view: m, left: NET.countdown(m),
        // the hold clock is wall-anchored the same way as the band (timer law)
        holdLeft: m.hold ? NET.countdown({ phase_ends_at: m.hold.deadline,
                                           server_now: m.server_now }) : null });
      bootGame(); drain();
    } else if (m.type === "chat") {
      const log = $("chatlog");
      log.innerHTML += `<div><b>${esc(m.from)}</b> ${esc(m.text)}</div>`;
      log.scrollTop = log.scrollHeight;
      if (scene) scene.setTicker(m.from + ": " + m.text);
    } else if (m.type === "error") {
      if (joining) {                          // join refused (papers/full/departed) → back to the pages
        joining = false;
        delete localStorage.meridian_car;
        banner("⚠ " + m.msg.toUpperCase());
        if (profile) gotoDashboard(); else gotoTerminus();
      } else if (seizeInFlight && scene) {    // the v2-3 alarm is an IN-WORLD beat — serif
        seizeInFlight = false;                // toast, never the harness's white banner
        scene.toast((m.msg || "the trigger is already held").toUpperCase(), 1600);
      } else banner("⚠ " + m.msg);
      if (curView) cancelSel();               // rejected action → restore the verb strip
    } else if (m.type === "end") {
      ended = true; endWinner = m.winner;
      delete localStorage.meridian_car;       // the journey is over — don't auto-board a corpse
      if (m.winner == null) showRecord();     // END THE LINE: no verdict, straight to the ticket
      else recordArmed = true;                // verdict: winnerScene plays; next tap → ticket
      drain();
    }
  }
  function showRecord() {                     // C6 — the record ticket (spec §4)
    if (scene) scene.setHold(null);
    closeTh();
    $("rline").textContent = endWinner != null
      ? "LAST AGENT STANDING · " + THEME.seatName(endWinner, roster) : "NO VERDICT";
    $("dlbtn").href = "/session/" + encodeURIComponent(sceneCode) + "/record";
    show("record");
  }
  function bootGame() {
    if (game) return;
    show(null);
    // DPR 3 backing store, camera-zoomed: layout coordinates untouched, text crisp on
    // phones (reslab lock 2026-07-11; his one-go phone check of ?dpr=3: "its perfect" —
    // sharpness AND taps). ?dpr=1 is the no-redeploy escape hatch.
    const q = new URLSearchParams(location.search);
    const DPR = Math.max(1, parseInt(q.get("dpr") || "3", 10) || 3);
    const origRes = Phaser.GameObjects.Text.prototype.setResolution;
    Phaser.GameObjects.Text.prototype.setResolution = function (r) {
      return origRes.call(this, Math.max(r || 1, DPR));     // texts match the backing store
    };
    SCENE.ready = (s) => {
      scene = s; window.__scene = s; s.setCode(sceneCode);
      if (DPR !== 1) { s.cameras.main.setZoom(DPR); s.cameras.main.centerOn(SCENE.W / 2, SCENE.H / 2); }
      drain();
    };
    game = new Phaser.Game({
      // CANVAS by default: phone-verified smooth where the WebGL path stuttered hard
      // (2026-07-10 live ?diag bisect). ?webgl=1 restores AUTO for A/B.
      type: q.get("webgl") ? Phaser.AUTO : Phaser.CANVAS,
      parent: "stage", width: SCENE.W * DPR, height: SCENE.H * DPR,
      backgroundColor: "#000000", pixelArt: true,
      scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
      scene: SCENE.TableScene,
    });
    window.__game = game;                                      // dev handle (devbot pump)
  }

  /* ---- [DRAIN] queue → choreography → settle (v1's proven loop, gen-gated at enqueue) ---- */
  let firstView = true, leftFn = null, noteOverride = null;
  let wasHeld = false, curHoldLeft = null, coldReady = false;   // hold lifecycle (spec §4)
  let recordArmed = false;                      // post-winner: next tap opens the record ticket

  async function drain() {
    if (busy || !scene) return;
    busy = true;
    if (queue.some((it) => it.events && it.events.length)) {   // beats NEVER play under an open menu
      closeTh();                                               // (ratified law — tr_race)
      scene.setBand({ phase: null });                          // timers stand down while beats play —
    }                                                          // a beatless refresh must not blink the band
    while (queue.length) {
      const it = queue.shift();
      const prev = curView;
      curView = it.view;
      leftFn = it.left || NET.countdown(curView);
      if (scene.setPortraits) scene.setPortraits(portraits);   // faces follow the papers
      if (firstView) {
        firstView = false;
        const ann = (it.events || []).find((e) => e.type === "announce");
        await CHOREO.setup(scene, curView, roster, ann);       // M1–M5
      } else if (it.events && it.events.length) {
        await CHOREO.play(scene, it.events, prev, curView, roster);
      } else {
        scene.render(curView, roster);                         // stale/rebroadcast: settle only
      }
      if (curView.hold) {                                      // the car is HELD — scrim owns the stage
        const hv = curView.hold_vote;                          // cold cars carry the vote tally
        coldReady = !!(hv && hv.ready && hv.ready[curView.you]);
        scene.setHold(hv ? Object.assign({}, curView.hold, hv) : curView.hold, roster,
          () => net.send({ type: "ready", on: !coldReady }));
        wasHeld = true; curHoldLeft = it.holdLeft;
      } else if (wasHeld) {
        wasHeld = false; curHoldLeft = null;
        scene.setHold(null);
        await scene.resumeBeat();                              // 3·2·1 — the release carried +3s
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

  const ORDER = ["MAGNET", "SHAKEDOWN", "GEIGER", "POISON", "PASSPORT", "TERMS"];

  function afterSettle() {
    noteOverride = null;
    scene.clearTargets(); scene.seatGlow([], false); closeTh();
    const over = curView.winner != null;
    scene.onKit = over ? null : () => { if (!busy) (myTurn() ? kitUseThread() : kitInfoThread()); };
    scene.onLedger = over ? null : () => { if (!busy) ledgerThread(); };   // menus WAIT for the beats
    scene.onAction = over ? null : () => {
      if (busy) return;
      const po = curView.pending_offer;                              // an unanswered offer owns the hub
      if (po && po.to === curView.you) respondThread(po);
      else if (curView.phase === "tax" && myTurn()) taxThread();
      else moveThread();
    };
    scene.onPhone = () => $("chatsheet").classList.toggle("on");
    const h = curView.hold;                                          // held car: chat frozen,
    if (h && h.expired && h.chooser === curView.you) holdChoiceThread();   // conductor decides
    const chatOk = curView.phase === "talk" && meAlive() && curView.winner == null && !h;
    $("chatin").disabled = !chatOk;
    $("chatin").placeholder = chatOk ? "say something…" : "SILENCE.";
    buildFace();
    scene.setSeize(!!curView.handler_available && !over, () => {
      if (!busy && curView.handler_available) seizeSheet();
    });
    const po = curView.pending_offer;                                // incoming offer → the sheet ARRIVES
    if (po && po.to === curView.you) respondThread(po);              // (rides the view: reconnect-safe)
    if (curView.phase === "tax" && myTurn()) taxThread();            // B3: the shakedown sheet arrives
    if (curView.warrant_pick) warrantSheet(curView.warrant_pick);    // your open warrant (reconnect-safe)
    else if (curView.dragnet_report && !seenDragnet) dragnetSheet(curView.dragnet_report);
  }

  function buildFace() {                                             // the center hub's face
    if (curView.winner != null) { scene.setAction("", false); return; }
    scene.setAction(myTurn() ? "YOUR\nMOVE" : "· · ·", myTurn());
  }

  /* ---- the THREAD menus (ratified system — see scene.openThread) ---- */
  let th = null;                                                     // one menu at a time
  const iname = (en) => THEME.ITEMS[en].name;

  function openTh(title, abortLabel) {
    th = scene.openThread({ mode: "fade", anim: "decode", title, abortLabel,
      onAbort: () => { th = null; cancelSel(); } });
    th._hist = [];
    th.alive = () => scene._thread === th;                           // a drain may close us mid-flow
    th.show = (fn) => { th._hist.push(fn); fn(); };
    th.onBack = () => {
      if (th._pop) { const f = th._pop; th._pop = null; f(); return; }   // inside a swap sub-list
      if (th._hist.length < 2) return;
      th.back(); th._hist.pop(); th._hist[th._hist.length - 1]();
    };
    th.homeTo = () => {                                              // STAND DOWN → the thread's MAIN menu
      th._pop = null; th.home();
      th._hist.length = 1; th._hist[0]();
    };
    return th;
  }
  function closeTh() { th = null; scene.closeThread(); }

  function confirmStep(label, blurb, go) {                           // ✓ EXECUTE / ✕ STAND DOWN, dot-divided
    const t = th;
    t.show(() => {
      const rows = blurb ? [{ info: true, label: blurb }] : [];
      rows.push({ dot: true },
        { label: "✓ EXECUTE", bright: true }, { label: "✕ STAND DOWN", down: true });
      t.list("GO", "CONFIRM — " + label, rows);
      t.onRow = async (i) => {
        if (!t.alive()) return;
        if (rows[i].down) { t.homeTo(); return; }
        await t.lock(i);
        if (!t.alive()) return;
        closeTh(); go();
      };
    });
  }

  function moveThread() {                                            // the root — headerless, B whispers
    if (!myTurn()) return;
    const kinds = new Set((curView.legal || []).map((a) => a.kind));
    const po = curView.pending_offer;
    openTh("YOUR MOVE");
    const me = th;
    th.show(() => {
      let rows;
      if (curView.phase === "talk") {
        const out = po && po.from === curView.you;
        const canTrade = !out && teammates().length > 0;
        rows = [
          { label: "ITEM", kit: kinds.has("item"), dim: !kinds.has("item"), sub: "OPEN YOUR KIT" },
          out ? { label: "WITHDRAW OFFER", recall: true, sub: "PULL YOUR OFFER BACK" }
              : { label: "TRADE", trade: canTrade, dim: !canTrade, sub: "PRIVATE OFFER TO A TEAMMATE" },
          { label: "PROCEED", bright: true, go: true, sub: "GO SILENT — DECIDE" }];
      } else {
        rows = [
          { label: "SHOOT", shoot: kinds.has("shoot"), bright: kinds.has("shoot"),
            dim: !kinds.has("shoot"),
            sub: "PICK A TARGET — OR YOURSELF" },
          { label: "FLIP", flip: kinds.has("flip"), dim: !kinds.has("flip"), sub: "BUY A CHANGE OF LOYALTY" },
          { label: "ITEM", kit: kinds.has("item"), dim: !kinds.has("item"), sub: "OPEN YOUR KIT" }];
      }
      th.list("MOVE", "", rows);
      th.onRow = async (i) => {
        if (!me.alive()) return;
        const r = rows[i];
        if (r.kit) { await th.lock(i); if (me.alive()) kitStep(); }
        else if (r.recall) { await th.lock(i); closeTh(); net.send({ type: "trade_withdraw" }); }
        else if (r.go) { await th.lock(i); closeTh(); wait(); net.send({ type: "proceed" }); }
        else if (r.trade) {
          const id = await th.pickSeat("trade", teammates(), "TRADE — TAP A TEAMMATE");
          if (id == null || !me.alive()) return;
          await th.lock(i); if (me.alive()) offerStep(id);
        } else if (r.shoot) {
          const entries = curView.legal.filter((a) => a.kind === "shoot");
          const ids = entries.map((a) => a.target);
          if (ids.length === 1 && ids[0] === curView.you) {          // M11/L4 forced-self line
            noteOverride = "NO LEGAL TARGETS — YOU FACE THE GUN (FLIP SOMEONE TO CHANGE THAT)";
            tick();
          }
          const id = await th.pickSeat("shoot", ids, "SHOOT — TAP A TARGET");
          noteOverride = null;
          if (id == null || !me.alive()) return;
          const a = entries.find((x) => x.target === id);
          await th.lock(i);
          if (me.alive()) confirmStep("SHOOT " +
            (id === curView.you ? "YOURSELF" : THEME.seatName(id, roster)), null, () => sendAction(a.i));
        } else if (r.flip) {
          const entries = curView.legal.filter((a) => a.kind === "flip");
          const id = await th.pickSeat("flip", entries.map((a) => a.target), "FLIP — TAP A TARGET");
          if (id == null || !me.alive()) return;
          const a = entries.find((x) => x.target === id);
          await th.lock(i); if (me.alive()) payStep(id, a.cost);
        }
      };
    });
  }

  function kitStep() {                                               // every row wears its blurb (ratified)
    const t = th;
    t.show(() => {
      const v = curView, me = v.players.find((p) => p.id === v.you) || {};
      const usable = new Set((v.legal || []).filter((a) => a.kind === "item").map((a) => a.item));
      const total = Object.values(v.your_hand || {}).reduce((a, b) => a + b, 0);
      const rows = ORDER.map((en) => {
        const n = (v.your_hand || {})[en] || 0;
        const left = Math.max(0, (v.use_limit || 0) - ((v.use_counts || {})[en] || 0));
        const ok = usable.has(en) && n > 0 && left > 0 &&
          !(en === "PASSPORT" && (me.cover || 0) >= THEME.MAX_COVER);
        return { en, label: iname(en), badge: "×" + n,
          sub: THEME.ITEMS[en].blurb + (left > 0 ? "" : " · SEALED"),
          bright: ok, dim: !ok };
      });
      const sp = curView.your_specials || {};
      const spTotal = ["WARRANT", "DRAGNET", "HANDLER"].reduce((a, k) => a + (sp[k] || 0), 0);
      const canSp = myTurn() && (curView.phase === "talk" || curView.phase === "decision");
      rows.push({ dot: true },
        { spmenu: true, label: "SPECIALS", badge: "×" + spTotal,
          sub: "ONE-SHOT POWERS — NOT CURRENCY, NEVER FINED",
          bright: spTotal > 0 && canSp, dim: spTotal === 0 });
      t.list("KIT", "YOUR KIT · " + total + "/" + THEME.MAX_TOTAL, rows);
      t.onRow = async (i) => {
        if (!t.alive()) return;
        if (rows[i].spmenu) {
          if (rows[i].dim) return;
          await t.lock(i);
          if (t.alive()) specialsStep(canSp);
          return;
        }
        const en = rows[i].en;
        const entries = curView.legal.filter((a) => a.kind === "item" && a.item === en);
        const nt = entries.find((a) => a.target == null);
        if (nt) {
          await t.lock(i);
          if (t.alive()) confirmStep("USE " + iname(en), THEME.ITEMS[en].blurb, () => sendAction(nt.i));
          return;
        }
        const id = await t.pickSeat("item", entries.map((a) => a.target), iname(en) + " — TAP A PLAYER");
        if (id == null || !t.alive()) return;
        const a = entries.find((x) => x.target === id);
        await t.lock(i);
        if (t.alive()) confirmStep(iname(en) + " → " + THEME.seatName(id, roster), THEME.ITEMS[en].blurb,
          () => sendAction(a.i));
      };
    });
  }
  function specialsStep(canSp) {
    const t = th, sp = curView.your_specials || {};
    t.show(() => {
      const rows = ["WARRANT", "DRAGNET", "HANDLER"].map((k) => {
        const n = sp[k] || 0;
        return { sp: k, label: THEME.SPECIALS[k].name, badge: "×" + n,
          sub: THEME.SPECIALS[k].blurb,
          bright: n > 0 && canSp && k !== "HANDLER", dim: n === 0 };
      });
      t.list("SP", "CALLS TO A HIGHER POWER", rows);
      t.onRow = async (i) => {
        if (!t.alive()) return;
        const k = rows[i].sp, n = sp[k] || 0;
        if (k === "HANDLER" || n === 0 || !canSp) return;            // handler is reactive-only
        if (k === "DRAGNET") {
          await t.lock(i);
          if (t.alive()) confirmStep("CALL A DRAGNET", THEME.SPECIALS.DRAGNET.blurb,
            () => { seenDragnet = false; net.send({ type: "special", kind: "DRAGNET" }); });
          return;
        }
        const others = curView.players.filter((p) => p.alive && p.id !== curView.you).map((p) => p.id);
        const id = await t.pickSeat("item", others, "WARRANT — TAP A PLAYER");
        if (id == null || !t.alive()) return;
        await t.lock(i);
        if (t.alive()) confirmStep("SEARCH " + THEME.seatName(id, roster), THEME.SPECIALS.WARRANT.blurb,
          () => net.send({ type: "special", kind: "WARRANT", target: id }));
      };
    });
  }
  function kitUseThread() { openTh("YOUR MOVE"); kitStep(); }        // briefcase, on-turn

  /* ---- the offer builder: GIVE ⇄ COUNT → WANT → SEND (bluff freely — §4.5) ---- */
  function offerStep(to) {
    const t = th, bag = { GIVE: {}, WANT: {} };
    const phaseStep = (phase) => t.show(() => renderPhase(phase));
    function renderPhase(phase) {
      const cur = bag[phase], last = phase === "WANT";
      const rows = ORDER.map((en) => ({ en, label: iname(en),
        badge: cur[en] ? "×" + cur[en] : "",
        bright: phase === "GIVE" && ((curView.your_hand || {})[en] || 0) > 0 }));
      rows.push({ dot: true },
        { go: true, label: last ? "SEND OFFER ▸" : "CONTINUE ▸", bright: true,
          sub: last ? "OFFERS MAY BLUFF — SETTLEMENT VERIFIES" : "NEXT — WHAT YOU WANT BACK" });
      t.swap(phase, (last ? "WANT ← " : "GIVE → ") + THEME.seatName(to, roster), rows);
      t.onRow = async (i) => {
        if (!t.alive()) return;
        if (rows[i].go) {
          await t.lock(i);
          if (!last) { if (t.alive()) phaseStep("WANT"); return; }
          const expand = (b) => Object.entries(b).flatMap(([en, c]) => Array(c).fill(en));
          closeTh();
          net.send({ type: "trade_offer", to, give: expand(bag.GIVE), want: expand(bag.WANT) });
          buildFace();
          return;
        }
        const en = rows[i].en, own = (curView.your_hand || {})[en] || 0;
        t._pop = () => renderPhase(phase);                           // ◂ BACK inside the count
        const cnt = [0, 1, 2, 3].map((k) => ({ label: String(k),
          bright: phase === "GIVE" && k === own }));                 // your REAL count glows
        if (phase === "GIVE") cnt.push({ info: true, label: "YOU HOLD ×" + own });
        t.swap("N", iname(en) + " — HOW MANY?", cnt);
        t.onRow = (k) => { bag[phase][en] = k; t._pop = null; renderPhase(phase); };
      };
    }
    phaseStep("GIVE");
  }

  /* ---- FLIP payment: tap items until the cost is covered (real pts; overpay is spent) ---- */
  function payStep(target, cost) {
    const t = th, chosen = {};
    const render = () => {
      const avail = curView.your_hand || {};
      const total = ORDER.reduce((s, en) => s + (chosen[en] || 0) * THEME.ITEMS[en].pts, 0);
      const rows = ORDER.map((en) => ({ en,
        label: iname(en) + " · " + THEME.ITEMS[en].pts + " PTS",
        badge: chosen[en] ? "PAY ×" + chosen[en] : "×" + (avail[en] || 0),
        bright: !!chosen[en], dim: (avail[en] || 0) === 0 }));
      rows.push({ dot: true },
        { pay: true, label: "✓ PAY " + total + "/" + cost + " PTS",
          bright: total >= cost, dim: total < cost, sub: "OVERPAY IS SPENT — NO CHANGE" },
        { label: "✕ STAND DOWN", down: true });
      t.swap("PAY", "FLIP " + THEME.seatName(target, roster) + " — TAP ITEMS TO PAY", rows);
      t.onRow = async (i) => {
        if (!t.alive()) return;
        if (rows[i].down) { t.homeTo(); return; }
        if (rows[i].pay) {
          await t.lock(i);
          if (!t.alive()) return;
          const items = ORDER.flatMap((en) => Array(chosen[en] || 0).fill(en));
          closeTh(); wait();
          net.send({ type: "flip", target, items });
          return;
        }
        const en = rows[i].en;
        chosen[en] = ((chosen[en] || 0) + 1) % (((curView.your_hand || {})[en] || 0) + 1);
        render();
      };
    };
    t.show(render);
  }

  /* ---- info threads: ONE screen, no taps (ratified) ---- */
  function kitInfoThread() {
    const v = curView, total = Object.values(v.your_hand || {}).reduce((a, b) => a + b, 0);
    openTh("KIT " + total + "/" + THEME.MAX_TOTAL, "✕ CLOSE");
    const rows = ORDER.map((en) => {
      const n = (v.your_hand || {})[en] || 0;
      const left = Math.max(0, (v.use_limit || 0) - ((v.use_counts || {})[en] || 0));
      return { label: iname(en), badge: "×" + n, still: true,
        sub: THEME.ITEMS[en].blurb + (left > 0 ? "" : " · SEALED"),
        bright: n > 0 && left > 0, dim: n === 0 || left === 0 };
    });
    const t = th;
    t.show(() => { t.list("i", "", rows); t.onRow = null; });
  }
  function ledgerThread() {
    openTh("LEDGER", "✕ CLOSE");
    const v = curView, rows = [];
    ORDER.forEach((en) => {                                           // ONE ruled row per item —
      const live = (v.item_counts || {})[en] || 0;                    // the specials section made the
      const use = Math.max(0, (v.use_limit || 0) - ((v.use_counts || {})[en] || 0));  // 2-row layout overflow
      rows.push({ split: [iname(en) + " ×" + live, use + " TO USE"] });
    });
    rows.push({ dot: true });
    ["WARRANT", "DRAGNET", "HANDLER"].forEach((k) => {                // user 2026-07-10: live, NO cap
      const live = (v.special_counts || {})[k] || 0;
      rows.push({ split: [THEME.SPECIALS[k].name + " ×" + live, "NO LIMIT"] });
    });
    const t = th;
    t.show(() => { t.list("i", "", rows); t.onRow = null; });
  }

  function respondThread(po) {                                       // the sheet just ARRIVES (private)
    openTh("INCOMING OFFER");
    const list = (arr) => arr && arr.length
      ? arr.map((en) => THEME.itemName(en)).join(" · ") : "NOTHING";
    const t = th;
    t.show(() => {
      const rows = [
        { info: true, label: "THEY GIVE: " + list(po.give) },
        { info: true, label: "THEY WANT: " + list(po.want) },
        { info: true, label: "OFFERS MAY BLUFF — SETTLEMENT VERIFIES" },
        { dot: true },
        { label: "✓ ACCEPT", bright: true }, { label: "✕ DECLINE" }];
      t.list("OFFER", THEME.seatName(po.from, roster) + " OFFERS · PRIVATE", rows);
      t.onRow = async (i) => {
        if (!t.alive()) return;
        const ok = rows[i].label === "✓ ACCEPT";
        await t.lock(i);
        if (!t.alive()) return;
        closeTh();
        net.send({ type: "trade_respond", accept: ok });
      };
    });
  }

  /* ---- C3: specials sheets ---- */
  let seenDragnet = false;
  function warrantSheet(pick) {
    openTh("WARRANT");
    const t = th;
    t.show(() => {
      const rows = [{ info: true, label: "SEARCHING " + THEME.seatName(pick.target, roster) + " — TAKE ONE" }, { dot: true }];
      Object.entries(pick.hand || {}).forEach(([en, c]) => {
        if (c > 0) rows.push({ nm: en, label: iname(en), badge: "×" + c, bright: true,
          sub: THEME.ITEMS[en].blurb });
      });
      Object.entries(pick.specials || {}).forEach(([k, c]) => {
        if (c > 0) rows.push({ nm: k, label: THEME.SPECIALS[k].name, badge: "×" + c, bright: true,
          sub: THEME.SPECIALS[k].blurb });
      });
      rows.push({ dot: true }, { nm: "", label: "TAKE NOTHING", down: true, sub: "WALK AWAY" });
      t.list("TAKE", "", rows);
      t.onRow = async (i) => {
        if (!t.alive() || rows[i].nm == null) return;
        await t.lock(i);
        if (!t.alive()) return;
        closeTh();
        net.send({ type: "warrant_take", name: rows[i].nm });
      };
    });
  }
  function dragnetSheet(report) {
    seenDragnet = true;
    openTh("DRAGNET REPORT", "✕ CLOSE");
    const t = th;
    t.show(() => {
      const rows = [{ info: true, label: "EVERY KIT ON THE TRAIN — SPECIALS STAY DARK" }, { dot: true }];
      Object.entries(report || {}).forEach(([pid, hand]) => {
        // ONE ruled row per kit — the two-row layout overflowed at 12 players (spec §5).
        // Long hands fall back to 3-letter prefixes (PAS/SHA/GEI/POI/MAG/TER — distinct).
        const ent = Object.entries(hand || {}).filter(([, c]) => c > 0);
        let inv = ent.map(([en, c]) => iname(en) + "×" + c).join(" · ") || "EMPTY-HANDED";
        if (inv.length > 26) inv = ent.map(([en, c]) => iname(en).slice(0, 3) + "×" + c).join(" · ");
        rows.push({ split: [THEME.seatName(+pid, roster), inv] });
      });
      t.list("i", "", rows);
      t.onRow = null;
    });
  }
  function seizeSheet() {                                            // HANDLER v2: pick X NOW, silently
    openTh("HANDLER");
    const t = th;
    t.show(async () => {
      const id = await t.pickSeat("seize", curView.seize_ids || [], "THEIR SHOT — TAP THE REAL TARGET");
      if (id == null || !t.alive()) return;
      confirmStep("RE-AIM AT " + THEME.seatName(id, roster), THEME.SPECIALS.HANDLER.blurb,
        () => { seizeInFlight = true;                            // a SILENT success sends no view —
          setTimeout(() => { seizeInFlight = false; }, 4000);    // don't let the flag eat later errors
          net.send({ type: "handler_seize", target: id, gen: curView.gen }); });
    });
  }

  function holdChoiceThread() {                    // the conductor's 5:00 call (spec §4)
    if (scene._thread) return;                     // reconnect-safe: re-arrives with the view
    openTh("THE SIGNAL");
    const t = th;
    t.show(() => {
      const rows = [
        { info: true, label: "FIVE MINUTES AT THE SIGNAL — YOUR CALL, CONDUCTOR" },
        { dot: true },
        { k: "bot", label: "SEAT THE HOUSE", bright: true,
          sub: "THEIR CHAIR PLAYS ON AS A BOT" },
        { k: "end", label: "END THE LINE", down: true,
          sub: "CLOSE THE RECORD — NO VERDICT" }];
      t.list("HOLD", "", rows);
      t.onRow = async (i) => {
        if (!t.alive() || !rows[i].k) return;
        await t.lock(i);
        if (!t.alive()) return;
        closeTh();
        net.send({ type: "hold_choice", kind: rows[i].k });
      };
    });
  }

  /* ---- B3: the SHAKEDOWN sheet — pay 6 (full), pay 4 (silent), or sit out ---- */
  function taxThread() {
    const tiers = new Set((curView.legal || []).filter((a) => a.kind === "tax").map((a) => a.tier));
    openTh("SHAKEDOWN");
    const t = th;
    t.show(() => {
      const rows = [
        { info: true, label: "YOU ARE BEING SHAKEN DOWN" },
        { dot: true },
        { tier: 6, label: "PAY 6 — FULL TURN", bright: tiers.has(6), dim: !tiers.has(6),
          sub: "TALK, TRADE, EVERYTHING" },
        { tier: 4, label: "PAY 4 — SILENT TURN", bright: tiers.has(4), dim: !tiers.has(4),
          sub: "ITEMS + FLIP + SHOOT — NO TALK, NO TRADES" },
        { tier: 0, label: "SIT IT OUT", down: true, sub: "PAY NOTHING — SKIP THE TURN" }];
      t.list("TAX", "", rows);
      t.onRow = async (i) => {
        if (!t.alive()) return;
        const r = rows[i];
        if (r.tier == null) return;
        if (r.tier === 0) {
          await t.lock(i);
          if (!t.alive()) return;
          closeTh(); wait();
          net.send({ type: "tax", tier: 0, items: [] });
          return;
        }
        if (!tiers.has(r.tier)) return;
        await t.lock(i);
        if (t.alive()) taxPayStep(r.tier);
      };
    });
  }
  function taxPayStep(tier) {
    const t = th, chosen = {};
    const render = () => {
      const avail = curView.your_hand || {};
      const total = ORDER.reduce((s2, en) => s2 + (chosen[en] || 0) * THEME.ITEMS[en].pts, 0);
      const rows = ORDER.map((en) => ({ en,
        label: iname(en) + " · " + THEME.ITEMS[en].pts + " PTS",
        badge: chosen[en] ? "PAY ×" + chosen[en] : "×" + (avail[en] || 0),
        bright: !!chosen[en], dim: (avail[en] || 0) === 0 }));
      rows.push({ dot: true },
        { pay: true, label: "✓ PAY " + total + "/" + tier + " PTS",
          bright: total >= tier, dim: total < tier, sub: "OVERPAY IS SPENT — NO CHANGE" },
        { label: "◂ BACK", down: true });
      t.swap("PAY", "SETTLE THE SHAKEDOWN — TAP ITEMS", rows);
      t.onRow = async (i) => {
        if (!t.alive()) return;
        if (rows[i].down) { t.homeTo(); return; }
        if (rows[i].pay) {
          if (rows[i].dim) return;
          await t.lock(i);
          if (!t.alive()) return;
          const items = ORDER.flatMap((en) => Array(chosen[en] || 0).fill(en));
          closeTh(); wait();
          net.send({ type: "tax", tier, items });
          return;
        }
        const en = rows[i].en;
        chosen[en] = ((chosen[en] || 0) + 1) % (((curView.your_hand || {})[en] || 0) + 1);
        render();
      };
    };
    t.show(render);
  }

  function cancelSel() {
    noteOverride = null;
    scene.clearTargets(); scene.seatGlow([], false); closeTh();
    buildFace(); tick();
  }
  function wait() {
    scene.clearTargets(); scene.seatGlow([], false);
    scene.setAction("· · ·", false);
  }
  function sendAction(i) { wait(); net.send({ type: "action", i }); }

  /* ---- band timer: wall-clock tick (rAF-throttle safe — constraint 17) ---- */
  function computeNote(v) {
    if (!v || v.winner != null) return "";
    if (noteOverride) return noteOverride;                     // M11 forced-self line (Task 7)
    const living = v.players.filter((p) => p.alive);
    if (v.teams_active && living.length >= 3 && new Set(living.map((p) => p.team)).size === 1)
      return "ONE AGENCY HOLDS THE TRAIN — TURN SOMEONE, OR FACE THE GUN";   // M27b
    if (v.phase === "tax" && v.current === v.you)
      return "SHAKEDOWN — BUY YOUR TURN BACK, OR SIT IT OUT";
    if (v.phase === "aiming")
      return THEME.seatName(v.current, roster) + " IS TAKING AIM\u2026";
    return "";
  }
  function tick() {
    if (!curView || !scene || !scene.built || busy) return;    // never overwrite a playing beat
    if (curView.hold) {                                        // frozen car: only the hold
      scene.holdTick(curHoldLeft ? curHoldLeft() : null);      // clock breathes
      return;
    }
    const secs = leftFn ? leftFn() : null;
    const mine = curView.current === curView.you;
    scene.setBand({
      phase: curView.winner != null ? null : curView.phase,
      secs,
      name: curView.winner != null ? "" :
        (mine ? "YOUR TURN · " : "") + THEME.seatName(curView.current, roster),
      bonus: curView.bonus,
      invert: (curView.phase === "decision" || curView.phase === "tax" || curView.phase === "aiming") && curView.winner == null,
      note: computeNote(curView),
    });
  }
  setInterval(tick, 250);
  document.addEventListener("pointerdown", () => {
    if (busy) { CHOREO.skip(); return; }
    if (recordArmed) { recordArmed = false; showRecord(); }   // any tap off the winner scene
  }, true);

  /* ---- wiring ---- */
  const mono = (a, b) => $(a).addEventListener("input", () => { if ($(a).value.length) $(b).focus(); });
  $("contbtn").addEventListener("click", gotoDashboard);
  $("signinbtn").addEventListener("click", () => show("signin"));
  $("papersbtn").addEventListener("click", () => show("papers"));
  $("papersback").addEventListener("click", gotoTerminus);
  $("signinback").addEventListener("click", gotoTerminus);
  mono("pfi", "pli"); mono("sfi", "sli");
  let pick = 0;                                             // the chosen face, frame index
  for (let f = 0; f < 12; f++) {
    const c = document.createElement("div");
    c.className = "pcell" + (f === 0 ? " on" : "");
    faceCSS(c, f);
    c.addEventListener("click", () => {
      pick = f;
      $("pgrid").querySelectorAll(".pcell").forEach((el, k) => el.classList.toggle("on", k === f));
    });
    $("pgrid").appendChild(c);
  }
  $("issuebtn").addEventListener("click", async () => {
    const fi = $("pfi").value.trim(), li = $("pli").value.trim();
    if (!/^[a-z]$/i.test(fi) || !/^[a-z]$/i.test(li)) { banner("TWO LETTERS MAKE A MONOGRAM"); return; }
    try {
      const p = await api("/papers", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fi, li, portrait: pick }) });
      saveProfile(p);
      faceCSS($("iface"), p.portrait);
      $("imono").textContent = p.initials;
      $("ipid").textContent = p.pid;
      show("issued");
    } catch (e) { banner("⚠ " + e.message.toUpperCase()); }
  });
  $("issuedgo").addEventListener("click", gotoDashboard);
  let found = null;                                         // the looked-up papers, pre-confirm
  $("findbtn").addEventListener("click", async () => {
    try {
      found = await api("/papers?fi=" + encodeURIComponent($("sfi").value.trim())
        + "&li=" + encodeURIComponent($("sli").value.trim())
        + "&pid=" + encodeURIComponent($("spid").value.trim()));
      faceCSS($("cface"), found.portrait);
      $("cmono").textContent = found.initials;
      $("cpid").textContent = "DOCUMENT NO. " + found.pid;
      show("confirm");
    } catch (e) { banner("⚠ " + e.message.toUpperCase()); }
  });
  $("spid").addEventListener("keydown", (e) => { if (e.key === "Enter") $("findbtn").click(); });
  $("confirmgo").addEventListener("click", () => { saveProfile(found); gotoDashboard(); });
  $("confirmno").addEventListener("click", () => show("signin"));
  $("switchbtn").addEventListener("click", () => {
    delete localStorage.meridian_pid; delete localStorage.meridian_profile;
    delete localStorage.meridian_car;
    pid = null; profile = null; gotoTerminus();
  });
  $("nextbtn").addEventListener("click", () => location.reload());   // ws closes → last one
  $("newcarbtn").addEventListener("click", () => connect(""));       // out burns the record
  $("enterbtn").addEventListener("click", () => connect());
  $("code").addEventListener("keydown", (e) => { if (e.key === "Enter") connect(); });
  $("readybtn").addEventListener("click", () => net.send({ type: "ready", on: !myReady }));
  $("seatminus").addEventListener("click", () => net.send({ type: "seats", n: lobbySeats - 1 }));
  $("seatplus").addEventListener("click", () => net.send({ type: "seats", n: lobbySeats + 1 }));
  $("startbtn").addEventListener("click", () => {
    if (!lobbyAllReady) { banner("THE MANIFEST IS NOT READY"); return; }
    net.send({ type: "start" });
  });
  // land: an unfinished journey re-boards itself; otherwise the terminus
  if (pid && localStorage.meridian_car) connect(localStorage.meridian_car);
  else gotoTerminus();
  const sendChat = () => {
    const t = $("chatin").value.trim();
    if (t) { net.send({ type: "chat", text: t }); $("chatin").value = ""; }
  };
  $("chatsend").addEventListener("click", sendChat);
  $("chatin").addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });
})();

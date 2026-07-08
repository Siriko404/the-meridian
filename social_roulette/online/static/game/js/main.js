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
      log.scrollTop = log.scrollHeight;     // Task 6 adds: scene.setTicker(...)
    } else if (m.type === "error") {
      banner("⚠ " + m.msg);
    } else if (m.type === "end") {
      ended = true; endWinner = m.winner; drain();
    }
  }
  function bootGame() {
    if (game) return;
    show(null);
    SCENE.ready = (s) => { scene = s; drain(); };
    game = new Phaser.Game({
      type: Phaser.AUTO, parent: "stage", width: SCENE.W, height: SCENE.H,
      backgroundColor: "#000000", pixelArt: true,
      scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
      scene: SCENE.TableScene,
    });
  }

  /* ---- [DRAIN] v0: settle-render only; Task 6 adds the choreography ---- */
  async function drain() {
    if (busy || !scene) return;
    busy = true;
    while (queue.length) {
      const it = queue.shift();
      curView = it.view;
      scene.render(curView, roster);
    }
    busy = false;
  }

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

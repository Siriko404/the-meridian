/* WS glue + the gen gate + the countdown clock. Pure parts node-tested.
 * gen gate: the view carries `gen`; events are REPLAYED only when gen increased —
 * a join/reconnect rebroadcast must settle silently, a stale view must never rewind. */
(function (global) {
  "use strict";
  function genGate() {
    let last = -1;
    return function accept(view) {
      const g = typeof view.gen === "number" ? view.gen : -1;
      if (g > last) { last = g; return true; }
      return false;
    };
  }
  function countdown(view, nowMs) {
    // anchor the server↔client clock offset ONCE per view; recompute absolute remaining
    // every tick from wall clock (rAF throttles in background tabs — constraint 17).
    const off = (view.server_now || 0) - (nowMs == null ? Date.now() : nowMs) / 1000;
    return function left(tMs) {
      if (view.phase_ends_at == null) return null;
      const now = (tMs == null ? Date.now() : tMs) / 1000 + off;
      return Math.max(0, view.phase_ends_at - now);
    };
  }
  function connect(makeWS, onMsg) {
    const ws = makeWS();
    const send = (m) => { if (ws.readyState === 1) ws.send(JSON.stringify(m)); };
    ws.onmessage = (ev) => onMsg(JSON.parse(ev.data));
    return { ws, send };
  }
  const NET = { genGate, countdown, connect };
  global.NET = NET;
  if (typeof module !== "undefined" && module.exports) module.exports = NET;
})(typeof window !== "undefined" ? window : globalThis);

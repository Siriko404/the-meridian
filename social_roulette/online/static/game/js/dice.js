/* Dice-ceremony synthesis (spec M2/M16): fabricate hi/lo d6 rolls consistent with
 * the ANNOUNCED totals — the real rolls never reach the wire (spec §4.6, audit a3).
 * Pure + node-tested. Feasibility: k=ceil(total/6) dice; live>=0.3*total => k<=live. */
(function (global) {
  "use strict";
  function spread(sum, k, cap) {            // k values in 1..cap summing to `sum`, near-even
    const out = Array(k).fill(1);
    let rest = sum - k, guard = 6 * k;
    for (let i = 0; rest > 0 && guard > 0; i = (i + 1) % k, guard--) {
      if (out[i] < cap) { out[i]++; rest--; }
    }
    return out;
  }
  function synthDice(total, live) {
    total = Math.max(2, total | 0);
    const k = Math.ceil(total / 6);
    live = Math.min(Math.max(k, live | 0), total);   // clamp: k<=live<=total keeps it solvable
    const his = spread(total, k, 6);
    const los = Array(k).fill(1);
    let rest = live - k, guard = 6 * k;
    for (let i = 0; rest > 0 && guard > 0; i = (i + 1) % k, guard--) {
      if (los[i] < his[i]) { los[i]++; rest--; }     // per-slot cap = its hi => lo<=hi always
    }
    return his.map((h, i) => [h, los[i]]);
  }
  const DICE = { synthDice };
  global.DICE = DICE;
  if (typeof module !== "undefined" && module.exports) module.exports = DICE;
})(typeof window !== "undefined" ? window : globalThis);

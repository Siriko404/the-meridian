import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const NET = createRequire(import.meta.url)("../js/net.js");

test("genGate: replay only on strictly increasing gen (spec §4.6 note)", () => {
  const accept = NET.genGate();
  assert.equal(accept({ gen: 3 }), true);    // first view
  assert.equal(accept({ gen: 3 }), false);   // rebroadcast (join) — settle only
  assert.equal(accept({ gen: 2 }), false);   // stale — never rewind
  assert.equal(accept({ gen: 4 }), true);
  assert.equal(accept({}), false);           // missing gen = never replay
});

test("countdown: server-offset corrected, clamps at 0, null when no phase", () => {
  // client clock 100s, server says 90s, phase ends at server-105 => 15s remain
  const v = { server_now: 90, phase_ends_at: 105 };
  const left = NET.countdown(v, 100_000);
  assert.equal(left(100_000), 15);
  assert.equal(left(110_000), 5);
  assert.equal(left(130_000), 0);            // clamped, never negative
  assert.equal(NET.countdown({ server_now: 90, phase_ends_at: null }, 0)(0), null);
});

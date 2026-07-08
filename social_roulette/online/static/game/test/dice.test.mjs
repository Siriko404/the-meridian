import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const DICE = createRequire(import.meta.url)("../js/dice.js");

test("synthDice: valid decomposition across the whole legal band", () => {
  for (let total = 2; total <= 40; total++) {
    const lo = Math.max(1, Math.ceil(total * 0.30)), hi = Math.floor(total * 0.70);
    for (let live = lo; live <= hi; live++) {
      const rolls = DICE.synthDice(total, live);
      let sh = 0, sl = 0;
      for (const [h, l] of rolls) {
        assert.ok(h >= 1 && h <= 6 && l >= 1 && l <= 6, `die out of range t=${total} l=${live}`);
        assert.ok(l <= h, `lo>hi t=${total} l=${live}`);
        sh += h; sl += l;
      }
      assert.equal(sh, total); assert.equal(sl, live);
    }
  }
});

test("synthDice: garbage inputs never throw or loop", () => {
  for (const [t, l] of [[0, 0], [1, 5], [6, 0], [100, 1]]) DICE.synthDice(t, l);
});

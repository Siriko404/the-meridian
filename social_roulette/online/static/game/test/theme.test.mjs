import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const THEME = createRequire(import.meta.url)("../js/theme.js");   // UMD module.exports branch

test("all six engine enums are mapped to ratified names", () => {
  const want = { PASSPORT: "PASSPORT", TERMS: "TERMS", GEIGER: "GEIGER",
                 POISON: "POISON", MAGNET: "MAGNET", SHAKEDOWN: "SHAKEDOWN" };
  for (const [k, v] of Object.entries(want)) assert.equal(THEME.ITEMS[k].name, v);
});

test("points match the public POINT_VALUE table (game_guide:110)", () => {
  const pts = { PASSPORT: 6, SHAKEDOWN: 6, GEIGER: 5, POISON: 5, MAGNET: 4, TERMS: 4 };
  for (const [k, v] of Object.entries(pts)) assert.equal(THEME.ITEMS[k].pts, v);
});

test("teams: hairline frames (seat-card v2, 2026-07-10) — A full alpha, B half", () => {
  assert.equal(THEME.TEAMS.RED.plate, 0xffffff);
  assert.equal(THEME.TEAMS.RED.tk, 1);
  assert.equal(THEME.TEAMS.RED.fa, 1);
  assert.equal(THEME.TEAMS.BLUE.plate, 0x000000);
  assert.equal(THEME.TEAMS.BLUE.tk, 1);
  assert.equal(THEME.TEAMS.BLUE.fa, 0.5);
});

test("seatName: roster (string keys) wins, truncated 8 upper; bots get codenames", () => {
  assert.equal(THEME.seatName(0, { "0": "alexandra" }), "ALEXANDR");
  assert.equal(THEME.seatName(2, { "0": "a" }), THEME.CODENAMES[2]);
  assert.equal(THEME.seatName(3, null), THEME.CODENAMES[3]);
  assert.equal(THEME.CODENAMES.length, 8);
});

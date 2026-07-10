import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const THEME = createRequire(import.meta.url)("../js/theme.js");   // UMD module.exports branch

test("all six engine enums are mapped to ratified names", () => {
  const want = { CIGARETTES: "PASSPORT", IMMUNITY: "BLACKMAIL", MAGNIFIER: "SPYCAM",
                 SAW: "POISON", BEER: "MAGNET", HANDCUFFS: "SEDATIVE" };
  for (const [k, v] of Object.entries(want)) assert.equal(THEME.ITEMS[k].name, v);
});

test("points match the public POINT_VALUE table (game_guide:110)", () => {
  const pts = { CIGARETTES: 6, IMMUNITY: 6, MAGNIFIER: 5, SAW: 5, BEER: 4, HANDCUFFS: 4 };
  for (const [k, v] of Object.entries(pts)) assert.equal(THEME.ITEMS[k].pts, v);
});

test("teams: RED = bloc A white/4px, BLUE = bloc B black/2px", () => {
  assert.equal(THEME.TEAMS.RED.plate, 0xffffff);
  assert.equal(THEME.TEAMS.RED.tk, 4);
  assert.equal(THEME.TEAMS.BLUE.plate, 0x000000);
  assert.equal(THEME.TEAMS.BLUE.tk, 2);
});

test("seatName: roster (string keys) wins, truncated 8 upper; bots get codenames", () => {
  assert.equal(THEME.seatName(0, { "0": "alexandra" }), "ALEXANDR");
  assert.equal(THEME.seatName(2, { "0": "a" }), THEME.CODENAMES[2]);
  assert.equal(THEME.seatName(3, null), THEME.CODENAMES[3]);
  assert.equal(THEME.CODENAMES.length, 8);
});

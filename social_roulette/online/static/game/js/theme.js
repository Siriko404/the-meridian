/* THEME — the ONE display table (spec §2). 2026-07-10 rename sweep: engine enums,
 * protocol, and display all speak the FINAL names. UMD so node tests import it. */
(function (global) {
  "use strict";
  // icon = Mystery_Icons.png frame index. GEIGER/MAGNET/SHAKEDOWN indices are DRAFTS —
  // ratified (or swapped) at the Task-5 gallery gate via the icon strip in moments.html.
  const ITEMS = {
    PASSPORT:  { name: "PASSPORT",  icon: 37, pts: 6, blurb: "+1 COVER" },
    TERMS:     { name: "TERMS",     icon: 14, pts: 6, blurb: "TARGET CAN'T SHOOT YOU" },
    GEIGER:    { name: "GEIGER",    icon: 8,  pts: 5, blurb: "PEEK NEXT BULLET" },
    POISON:    { name: "POISON",    icon: 11, pts: 5, blurb: "NEXT SHOT x2" },
    MAGNET:    { name: "MAGNET",    icon: 5,  pts: 4, blurb: "EJECT CURRENT BULLET" },
    SHAKEDOWN: { name: "SHAKEDOWN", icon: 2,  pts: 4, blurb: "TARGET SKIPS A TURN" },
  };
  // TEAM = POLARITY (locked 2026-07-10): plates carry the team; frames are HAIRLINE
  // 1px — bloc A full alpha, bloc B half alpha ("0.5px", framelab row 2).
  const TEAMS = {
    RED:  { name: "AGENCY NORTH", plate: 0xffffff, text: "#000000", tk: 1, fa: 1 },
    BLUE: { name: "AGENCY SOUTH", plate: 0x000000, text: "#ffffff", tk: 1, fa: 0.5 },
  };
  const CODENAMES = ["V.K.", "C.W.", "J.L.", "N.D.", "W.N.", "H.Y.", "M.T.", "P.K."];  // bots wear monograms too
  const ICON = { revolver: 0, heart: 20, ledger: 37, briefcase: 40, envelope: 14,
                 poison: 11, phone: 38 };
  const MAX_COVER = 5, MAX_PER_TYPE = 3, MAX_TOTAL = 8;

  function itemName(en) { return ITEMS[en] ? ITEMS[en].name : String(en); }
  function seatName(seat, roster) {
    const n = roster && (roster[seat] != null ? roster[seat] : roster[String(seat)]);
    return n ? String(n).slice(0, 8).toUpperCase() : CODENAMES[seat % CODENAMES.length];
  }
  const THEME = { ITEMS, TEAMS, CODENAMES, ICON, MAX_COVER, MAX_PER_TYPE, MAX_TOTAL,
                  itemName, seatName, CREDITS: "ART: JJ99 · DARKMOONFIRE" };
  global.THEME = THEME;
  if (typeof module !== "undefined" && module.exports) module.exports = THEME;
})(typeof window !== "undefined" ? window : globalThis);

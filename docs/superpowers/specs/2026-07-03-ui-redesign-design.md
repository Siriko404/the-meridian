# Social Roulette — UI Redesign (pure B&W) Design

**Date:** 2026-07-03 · **Status:** brainstorm → (build pending) · Extends `2026-07-03-online-game-design.md`.

## Goal
Make the online game **simple, elegant, and beautiful to play/test**, with motion on
the random events (item draws, dice/chamber, team assignment, shooting, reveals).

## Aesthetic — LOCKED
```
· PURE BLACK & WHITE. #000 / #fff only. ZERO gray.
  ONE intentional exception: decoder NOISE is gray (#585858) so resolved
  white text pops (contrast). Nothing else is gray.
· NO EMOJI anywhere (emoji = color → banned). Use form/glyphs/letters.
· Minimal, elegant, high-contrast, tense/noir. The logo is one white line
  on black — the whole UI should feel the same.
· Depth via hairlines (1px #fff), negative space, and INVERSION (white↔black),
  never gray fills or shadows.
· Logo = the title mark. File: social_roulette/online/static/logo.jpeg (white-on-black).
```

## Layout
```
· Circular "roulette table": players on a ring, the gun + chamber in the CENTER,
  the barrel points at the current player.
· Teams by FORM, not color:  ● filled disc (team A)  ·  ○ hollow ring (team B).
  Both legible on black. Lives = pips. Dead = collapse to ✕.
· Your hand (item cards) + action buttons docked at the bottom.
· Reference mockup (static, scripted): static/mockup.html.
```

## Animation catalog
```
setup    coin-flip → teams · dice tumble → shells load the cylinder · cards dealt to you
turn     the gun/barrel rotates to the current player
SHOOT    aim → trigger → WHITE-FLASH full-screen inversion (LIVE)  |  quiet shudder (blank)
death    player disc collapses / dims to ✕
reload   cylinder refills · everyone draws 2 (cards fly out)
text     appear/disappear (items, turns, toasts) = the chosen decoder below
```
"Simple but good" = a FEW signature animations done well, not many mediocre.

## CHOSEN text-reveal — "Terminal binary decoder" (self-contained, no library)
Gray `0/1` noise resolves to WHITE letters left-to-right, a white block cursor
rides the resolve edge. ~750ms (1.4× the first draft). Use for any text that
appears (item names, "P3's turn", announcements). Monospace (stable char width).
```html
<style> .fx{font-family:ui-monospace,Menlo,Consolas,monospace}
        .fx .n{color:#585858;font-weight:400}   /* gray noise */
        .fx .cur{color:#fff}                     /* white cursor */ </style>
```
```js
const bit = () => Math.random() < .5 ? "0" : "1";
// reveal(el, "MAGNIFIER")  — el must be monospace (.fx)
function reveal(el, text, {dur = 750, cursor = true} = {}) {
  const n = text.length, t0 = performance.now(), rt = [];
  [...Array(n).keys()].filter(i => text[i] !== " ")
    .forEach((i, k, arr) => rt[i] = k / arr.length);          // lock time per char, L→R
  (function tick(t) {
    const p = (t - t0) / dur; let html = "", edge = true;
    for (let i = 0; i < n; i++) {
      if (text[i] === " ") { html += " "; continue; }
      if (p >= rt[i] + 0.05) html += text[i];                 // resolved = white
      else if (cursor && edge) { html += '<span class="cur">█</span>'; edge = false; }
      else html += '<span class="n">' + bit() + '</span>';    // noise = gray
    }
    el.innerHTML = html;
    p < 1.15 ? requestAnimationFrame(tick) : (el.textContent = text);
  })(t0);
}
```
Samples explored: `static/decoders_binary.html` (options "1 · L→R" and "4 · Terminal";
user replied "2" = the 2nd shown = **Terminal** — ⚠ did not match a label number, **confirm on resume**).
Earlier reveal explorations: `static/decoders.html`,
`static/demo_anim.html` (the **fill-sweep** there — masked bar sweeps, text inverts —
is kept for **commit buttons** like Shoot/Confirm).

## KEY architecture note (load-bearing for the build)
Animations show what *happened* — a state snapshot can't. The server currently
sends per-seat **state** after each move. For live animation it must also **stream
the EVENTS** (shot→shell+damage+killed, item, flip, death, reload) — the engine's
`recorder` ALREADY produces these; wire `Room`/`server` to emit the event delta with
each broadcast, and the client animates the queue then settles to the new view.
Setup animations (teams/dice/deal) have no events → play them cosmetically from the
start-state. (No engine changes; same seam as the online-game spec.)

## Out of scope (v1 redesign)
Sound · 3D · particle systems · per-letter physics. Keep it flat, monochrome, minimal.

## Next
Wire the aesthetic (circular table, form-teams, logo) + the Terminal decoder +
event-stream animations into `static/index.html` + `server.py`, then deploy.

**Gotcha:** `server.py` currently serves only `/` via `FileResponse` — there is **no static mount**,
so the logo file (and any asset) will 404 in the real UI. Add
`app.mount("/static", StaticFiles(directory=STATIC), name="static")` (from `fastapi.staticfiles`)
and reference `/static/logo.jpeg`. (The demos dodge this only because `http.server :8010` serves the dir directly.)

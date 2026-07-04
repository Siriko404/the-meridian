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

## BUILT — 2026-07-03 (mobile-locked; verified live in Chrome)
Shipped as the online UI. Pivoted mid-build to **mobile-first, LOCKED viewport** (user:
"played on mobile … fit on screen without need — even capability — for resizing or scrolling").

- **Files:** `static/index.html` (WS glue + tap-to-target state machine + anim queue),
  `static/sr_ui.css` (mobile-locked B&W), `static/sr_ui.js` (pure visual layer:
  `render`/`playEvents`/`setup`/`decoder`, no WS / no load-time side effects).
  Backend: `room.py` (event recorder), `server.py` (events broadcast + race-safe
  delta captured inside the lock + `/static` mount), `view.py` (structured
  `kind/item/target` on each legal action).
- **Lock:** `100svh` + `body{overflow:hidden}` + viewport-lock meta; `#app` phone
  frame `min(100vw,440px)`; ring sized by CONTAINER units (`cqh/cqw`, NOT `vw` —
  frame-relative, so desktop tests are faithful); `env(safe-area-inset-*)`.
- **Interaction:** 14 flat buttons → **tap-to-target** (verb → item picker → tap a
  seat). `(kind,item,target)` is unique across `legal_actions`, so each tap = ONE action.
- **Animations:** live shot = white-flash inversion · blank = shudder · death =
  collapse · reload/flip = toast; bot-cascade time budget + click-to-skip; `setup`
  plays to the ACTUAL first view; Terminal binary decoder for text.
- **Event stream (load-bearing correction):** the earlier "recorder ALREADY produces
  these" was only HALF-true — `Room` wired NO recorder (bots passed none; the human
  bypassed `take_policy_turn`). Now wired; events carry only PUBLIC fields (`extra`
  dropped → no Magnifier-peek leak). The just-fired shell is public (`game_guide:150-160`).
- **Verified:** live Chrome playthrough to a winner, 0 console errors; dock fits at
  688 and worst-case 620 with slack; 179 tests green.
- **Caveat:** zoom-lock is best-effort on iOS (Safari ignores `user-scalable=no`).

## Refinement rounds — 2026-07-03 (all committed on master, playtested live)
Run: `python -m uvicorn social_roulette.online.server:app --port 8015` → http://127.0.0.1:8015 (any port).

- **R2 rules+UX** (ce9cf67, 29b32fa): chamber counts CONFIDENTIAL — announced ONCE at load then
  hidden (`game_guide:159`; `view` drops `chamber`, counts ride announce/reload EVENTS); turn
  indicator = center DIAL + gliding pulse-dot (no arrow); immunity markers "P3M" above the
  recipient (`view.immune_from` = the `immunity_against` casters); slower labelled bot cascade.
- **R3 you-first + order** (80a9422): the human plays FIRST (rotate seating so no bot acts before
  the first human turn → no unseen / "stale-looking" opening state) and the ring is laid out in
  TURN ORDER (`view.order`) so the dot advances to ADJACENT seats.
- **R3 readability + timing** (06dcb81): ~2× bigger type (still fits 620); announce holds 5s; dot
  glow breathes once/min over 5s; toasts JS-timed (per-message hold).
- **R3 flip payment + beer** (f1aff76, 0a42cae): FLIP opens a PAYMENT PICKER — you choose which
  items pay (`room.flip` + `{type:'flip',target,items}`; `view` exposes flip `cost`; engine
  `pay_cost` re-validates). BEER toasts "SHELL OUT", clears a stale Magnifier peek, and
  re-announces if it empties the chamber.
- **Verified live** (single human + 4 bots, desktop Chrome at a phone-*frame*): flip picker
  (P1 BLUE→RED, chosen beers spent, cigarette KEPT); you-first + turn-order; bigger text fits; 5s
  announce; slower cascade. **181 tests pass** (8 RL modules UNCOLLECTABLE here — missing
  `gymnasium`/`sb3_contrib`; pre-existing, out of scope).
- **UNVERIFIED (do before deploy):** 2+ real humans / turn-passing between humans · reconnect
  mid-game · landscape · a real physical phone · the beer "SHELL OUT" toast (backend tested;
  toast path trusted but not seen this session).

## ⛔ OPEN — user decision #3b ("see 2 bullets"), do NOT build until answered
User: "players can see 2 bullets … know if next is final; never nature." This CONTRADICTS his own
earlier instruction (R2: counts confidential/hidden, `game_guide:159`, which IS implemented), and
the rule is in NO doc. Reconcile A/B/C before building:
- **(A)** keep hidden [current] · **(B)** always show REMAINING SHELL COUNT (not nature) ·
  **(C)** show only whether a NEXT shell exists.
Also: **#1 ratio is NOT a bug** — 20000 loads, 0 outside 30–70% (`chamber.py:13`); user to confirm
he saw the *remaining* ratio (only the *load* is banded, `game_guide:71`).

## Testing quirk (Chrome re-authorized; don't re-diagnose)
Driving via the MCP with the tab BACKGROUNDED throttles `requestAnimationFrame` → the setup
decoder stalls → `curView` stays null. Take a screenshot (foregrounds the tab) to let setup finish.
Not a real bug (real foreground phones run full speed).

## Next
Answer #3b (above). Then deploy to Render (needs user GitHub + Render signup; `/static` 404 FIXED).
Run locally: `python -m uvicorn social_roulette.online.server:app --port 8012`.

# UI v2 — Wartime-Spy Night Train, in Phaser 4 (full redesign)

**Date:** 2026-07-07 · **Status:** spec for user review · **Supersedes** the v1 web UI
(`static/index.html` + `sr_ui.*`) and extends `2026-07-03-online-game-design.md` (server core kept).
Rules source of truth: `game_guide.md`. Gap list source: `docs/RULES_AUDIT.md`.

## Goal

Replace the rejected v1 UI with a **Phaser 4 game client** that (a) implements the guide's full
Turn Structure — talk phase, decision phase, timers, fines, auto self-shoot (audit T2–T4), (b) gives
**every game moment a designed animation** (the dealer ceremony gap), (c) ships the **trade UI**
(E5), (d) wears the ratified **wartime-spy / sealed-night-train theme** (copyright re-theme), and
(e) fixes the audit's engine/view bugs (I9, C9, V3) at the source.

## Non-goals

Sound · LLM bots · smarter bots · durable rooms · spectator mode · native apps · Render deploy
(after v2 ships) · final game/agency/item names (drafts below; naming pass is a later user task).

---

## 1 · Locked foundations (ratified — do not re-litigate)

| Area | Decision |
|---|---|
| Stack | Phaser 4.2.0 (vendored) client · existing Python engine + FastAPI/WS server · per-seat views + event stream seam |
| Canvas | 390×844 design space, `Scale.FIT`, portrait phone-locked, `pixelArt:true` |
| Style | 1-bit noir pixel, **red = danger ONLY**; community assets (JJ99 portraits + Darkmoonfire icons, see `ATTRIBUTION.md`); **faces are SACRED** (never tint/invert/redraw); Claude never hand-draws figurative art |
| Menus | **Every screen-occupying menu opens from a tapped icon** (standing principle) |
| Team marker | Nameplate polarity + thick/thin frame on avatar AND plate (bloc A: white plate/black text/4px; bloc B: black plate/white text/2px). Turn = stroke brightness, never weight |
| Turn indicator | Fluted revolver-cylinder dial at table center; chambered bore points at current seat; click-step rotation (`Back.easeOut`, 420ms) |
| Scope | Full guide timers (60s talk / 30s decision / fines / auto self-shoot) · trade UI in · human plays first (v1 rotation kept) · **#3b = A**: chamber counts shown once at load/reload, never again |
| Type | Consolas/monospace, ≥13 design-px bold, `setResolution(2)` |

## 2 · Theme card (DISPLAY layer only — engine enums unchanged)

Setting: a sealed night train, **THE MERIDIAN**, last service through a world at war. Around the
dining-car table sit agents of two rival agencies. The dealer is **the Handler** (the engine).
Lives = **cover identities**. Elimination = **burned** (cover blown). A team flip = a **turned**
agent. Game name TBD (user decision, deferred — "THE MERIDIAN" names the train, not the game).

| Engine enum | Display (**RATIFIED 2026-07-08**) | Effect | Pts | Icon (sheet idx, draft) |
|---|---|---|---|---|
| CIGARETTES | **PASSPORT** | +1 life (restores a cover) | 6 | 37 ledger |
| IMMUNITY | **BLACKMAIL** | place: target can't shoot you (you have dirt on them) | 6 | 14 envelope |
| MAGNIFIER | **SPYCAM** | peek next shell | 5 | build-time pick (camera-like) |
| SAW | **POISON** | next shot ×2 (tips the round) | 5 | 11 poison |
| BEER | **MAGNET** | eject current shell (pulls the round) | 4 | build-time pick |
| HANDCUFFS | **SEDATIVE** | target skips next turn (out cold) | 4 | build-time pick (40 briefcase stays reserved for KIT) |

Teams (drafts): **AGENCY NORTH** (bloc A, white plate) vs **AGENCY SOUTH** (bloc B, black plate).
Humans wear their lobby name (truncated 8 chars, uppercase). Bots draw theme codenames from a fixed
list (drafts): VESPER, CROW, JACKAL, NOMAD, WREN, HALCYON, MOTH, PIKE.
The rename map lives in ONE client-side table (`THEME = {CIGARETTES:{name:"PASSPORT", icon:…}, …}`);
protocol and engine keep enum names. A final naming pass edits one table.

## 3 · Architecture

```
Python engine (pure, deterministic)      ← 3 bug fixes, no new concepts
   ↑ step / legal_actions
Room (sync state-machine, room.py)       ← NEW: phases, deadlines, fines, trade, chat gate
   ↑ called under per-room asyncio.Lock
FastAPI/WS server (server.py)            ← NEW: deadline timers, 3 msg types, roster
   ↓ per-seat view + public event stream (seam unchanged)
Phaser 4 client (static/game/)           ← NEW: replaces static/index.html UI
```

Client = pure renderer: queues `{events, view}` pairs, plays the event choreography (skippable),
settles to the view — v1's proven queue/drain/skip loop, ported. Server stays authoritative;
full state never serialized.

## 4 · Server — the phase machine (audit T2–T4, the missing social core)

### 4.1 Phases and legality (derived from guide:169-192, :65)

| Phase | Duration | Chat (all living) | Active player may |
|---|---|---|---|
| **TALK** | 60s | **open** | use items · **trade** · PROCEED (end talk early) |
| **DECISION** | 30s | **locked** ("Silence") | use items · **flip** · **shoot** |
| **BONUS** (self-blank) | 30s | locked | = one DECISION phase (items + flips + shoot; no talk/trade) — guide:189 |

- Flips are **decision-only** and shooting is **decision-only**: guide:169 lists talk-phase powers
  as "item use AND trades"; guide:172 lists decision powers as "item use and flips"; the shot is
  the decision. The killer's extra turn is a full turn (talk → decision), guide:65.
- Bonus turns chain: each self-blank grants a fresh 30s BONUS phase.
- **Bot turns have no phases or timers** — they resolve at the animation cascade's pace. Timers
  exist to bound *human* stalling; bots never stall. (Playability decision; guide assumes humans.)
- **Chat is gated server-side**: accepted only during a TALK phase, only from **living** players.
  Dead players are muted — a dead player may hold a live Magnifier peek (peeked, then died before
  that shell was fired) and could leak it. Spectate silently.

### 4.2 Timeout machinery (guide:175, :192)

```
DECISION deadline fires, no shot committed:
  ├─ player has ≥1 item → FINE: burn their cheapest item (by point value;
  │    ties broken by state.rng) → new 30s DECISION deadline → repeat
  └─ player has 0 items → AUTO SELF-SHOOT: engine step(Shoot(self))
TALK deadline fires → advance to DECISION (no fine — the fine is for failing to decide)
```

- "No action taken" (guide:175) is read as **no shot committed** — the turn only ends by shooting,
  so anything weaker permits an infinite stall (use one cheap item per window forever).
- Fines burn **cap-free** (a penalty, like sacrifice — guide:99) and emit a `fine` event.
- The fine is an **engine function** (`economy.fine_cheapest(state, pid)`) so the RNG tie-break
  rides `state.rng` (deterministic, replayable) and inventory invariants stay engine-owned.
- A disconnected human's turn runs the same clock: fines tick, then auto self-shoot. No bot
  substitution needed — the timers make walk-aways self-resolving.

### 4.3 Timer implementation

- **Room stays synchronous and unit-testable.** It stores `phase`, `phase_ends_at` (wall epoch s),
  and a `gen` counter (increments on every state mutation). It exposes pure transitions:
  `begin_turn()` (sets TALK or BONUS/DECISION per engine state), `proceed(seat)`,
  `on_talk_deadline()`, `on_decision_deadline()` (applies fine or auto-shoot). Tests call these
  directly — no sleeping, no sockets.
- The **server** owns one asyncio deadline task per room: capture `gen` when scheduling; on fire,
  take the room lock, no-op if `room.gen` moved (action already resolved the phase), else call the
  Room transition and broadcast. Every broadcast reschedules the next deadline.
- Client renders the countdown from `phase_ends_at` + `server_now` (clock-offset corrected);
  it never enforces anything.

### 4.4 Phase-filtered actions

`legal_actions` (engine) stays phase-blind. Room computes the engine list, then the view includes
only entries legal in the current phase (talk: UseItem+Trade; decision: UseItem+Flip+Shoot).
`apply()` re-validates both the index **and** the phase. `social_enabled=True` turns Trade on
(engine already supports it; random bots will occasionally gift — acceptable flavor).

### 4.5 Trade (audit E5) — bluffable offer/accept swap (user-designed 2026-07-08)

- **Only the active player trades**, TALK phase only, living **teammates** only.
- **Flow:** actor taps a teammate's avatar (tradable teammates glow) → **offer menu** opens:
  set what you GIVE and what you WANT (item types + counts). **Offers are NOT bound to your
  real inventory — bluffing is a designed mechanic.** The offer goes privately to that teammate,
  who gets an ACCEPT / DECLINE tray.
- **Settlement (on accept):** server checks both sides actually own their promised items AND the
  swap clears both inventories' caps (guide:138 "blocked"). Any failure → both parties get
  "TRADE CANCELLED — A PARTY LACKED THE GOODS" and nothing moves (the honest side thereby learns
  the other bluffed — bluffing carries exposure risk by design). Success → the swap applies
  **atomically** under the room lock as two engine gift steps (engine unchanged).
- One-way gift = an offer with an empty WANT side. One pending offer at a time; pending offers
  expire when the talk phase ends. Decline is silent to the rest of the table.
- **Privacy:** the negotiation and item identities are visible only to the two parties. The table
  publicly sees only a **settled** trade ("VESPER and WREN made an exchange", no contents) —
  Room strips items from the public event and enriches the two parties' copies. Cancelled or
  declined offers are never public.
- New WS messages: `{type:"trade_offer", to:<seat>, give:[names], want:[names]}` ·
  `{type:"trade_respond", accept:<bool>}`.

### 4.6 Protocol additions (view + messages)

View gains: `phase` (`"talk"|"decision"|null` — null while bots cascade), `phase_ends_at`,
`server_now`, `bonus` (bool), `extra_turn` (bool — killer's earned turn, Room-derived),
`saw_active` (public: the commit event was public), `use_counts` + `use_limit` (public, audit I10),
`teams_active` (bool, audit G3), `flipback_discount` (own view only, audit E4),
`roster` (seat→display name — v1 never sent names to the table).
New client→server: `proceed`, `trade_offer`, `trade_respond`. New event types: `fine`, `trade`. `item_counts` ships already but
becomes correct once corpses burn (below).

## 5 · Engine fixes (audit I9, C9, V3 — at the source)

| # | Fix | Where |
|---|---|---|
| I9 | 2nd same-caster Immunity on the same target = **illegal**, not a consumed no-op: filter in `legal_actions`, guard in `apply_item` | `actions.py`, `items.py` |
| C9 | On death, the dead player's placed Immunity **expires**: remove their id from every `immunity_against` set | `engine.take_shot` kill branch |
| V3 | On death, **burn the corpse's inventory** (`inventory = {}`) — guide:69; public `item_counts` then auto-corrects (today `view.py:48-51` counts burned items) | `engine.take_shot` kill branch |
| new | `economy.fine_cheapest(state, pid)` — burn cheapest item, rng tie-break, returns the item (None if broke) | `economy.py` |

All 181 existing tests must stay green; each fix lands with its own tests.

## 6 · Client — scenes and layout

### 6.1 Pre-game = themed HTML; game = Phaser

Join (name + code) and lobby stay **plain HTML overlays** restyled to the theme — text input, IME,
paste and autocomplete are free in HTML and cost real work in canvas. On `start`, the overlay drops
and the Phaser `TableScene` owns the screen. One page, one WS connection throughout.

### 6.2 TableScene layout (390×844)

```
┌──────────────────────────────┐
│ STATUS BAND  (destination-   │ phase · timer · whose turn · room code (tiny)
│ board type, decodes on change│
├──────────────────────────────┤
│                              │
│      5 seats on the arc      │ portrait tile + plate + heart pips
│      (cx 195, cy ~430)       │ + status chips (COVER/SKIP/BURNED)
│         ◉ cylinder dial      │
│                              │
├──────────────────────────────┤
│ peek chip│ ACTION STRIP │KIT │ verbs appear only on your turn, phase-filtered:
│ (private)│ SHOOT FLIP   │icon│ TALK → ITEM · TRADE · PROCEED   DECISION → SHOOT · FLIP · ITEM
├──────────┴──────────────┴────┤
│ chat ticker (1 line) · ☏ icon│ tap ☏ → chat sheet slides up (talk phases only)
└──────────────────────────────┘
```

Icon-gated trays (all slide over the dock, never cover the arc): **KIT** (briefcase — your items,
each with count, point value, uses-left; at-cap items greyed "SEALED UNTIL A DEATH"), **LEDGER**
(small icon by the band — the public counts panel: per-item total in play + uses left, audit V3/I10),
**CHAT** (phone icon — bottom sheet, input enabled only during talk), **TRADE** and **FLIP-PAYMENT**
trays (contextual, below). Spike's known risk: the KIT tray must clear the bottom seats — verify at
build; drop the arc's `cy` if it collides.

### 6.3 Interaction grammar (v1's proven tap-to-target, restyled)

Verb → (item picker if needed) → legal seats highlight with **red corner brackets** → tap seat →
confirm. `(kind, item, target)` uniquely keys a legal action (v1 invariant, kept). FLIP opens the
payment tray (pick which items pay, running total vs cost, flip-back 4 shown when your discount is
live — audit E4). TRADE (talk only): teammates glow → tap one → offer tray (GIVE/WANT) →
their accept → settle-or-cancel (4.5).

## 7 · THE MOMENT CATALOG (every game moment, its choreography)

Durations are design targets; the cascade is tap-to-skip (v1 behavior). Decoder text effect =
v1's terminal decoder, ported to Phaser (per-char timed reveal on a mono bitmap-style text).

**Setup ceremony** (from `match_start`, cosmetic replay):

| # | Moment | Choreography |
|---|---|---|
| M1 | Coin flip (odd split, S1) | White/black disc flips (scaleX tween), lands on the extra-seat agency; plates then stamp seat-by-seat (120ms stagger) — polarity snaps in |
| M2 | **Chamber load — the dice ceremony (S3)** | Two pip-dice tumble at center (geometric primitives); per roll the **higher** flies to a TOTAL counter, **lower** to LIVE; counters accumulate until live > players; "30–70% · SEALED" stamp; bores fill black one-by-one (order hidden); cylinder spin-shuffles with decelerating click-ticks |
| M3 | Announce (V6, #3b=A) | "N SHELLS · M LIVE" big type, 5s hold — then never again |
| M4 | Deal (S6) | Per seat: 3 quick d6 tumbles; **your** seat: item icons flip up + slide into KIT with name reveals; other seats: 3 card-backs fan and absorb into the tile |
| M5 | First turn | Cylinder heavy-clicks to seat 1; band decodes "TALK · 0:60" |

**Turn flow:**

| # | Moment | Choreography |
|---|---|---|
| M6 | Turn advance | Cylinder click-step to seat (ratified); active frame brightens; band: "\<NAME\> · TALK 0:60" |
| M7 | Talk phase (T2) | Countdown in band; chat icon pulses once (unlocked); actor sees PROCEED |
| M8 | Decision phase (T3) | Band **inverts** (white bg — pressure); "0:30" counts; chat locks; final 10s tick-pulse; **final 5s digits go red** (danger) |
| M9 | Timeout fine (T4) | "FINED · \<ITEM\>" stamp on actor's plate; the item icon falls from their tile and crumbles; timer resets 0:30 |
| M10 | Auto self-shoot (T4) | "NO ASSETS · THE HANDLER DECIDES" band → forced self-shot (M12) |
| M11 | Target pick | Legal seats get red corner brackets; tap → "\<VERB\> \<NAME\> — CONFIRM" strip |
| M12 | **Shot** | Cylinder micro-overwinds and locks (already pointing at the shooter) + 400ms hold (tension) → **LIVE:** 60ms full-white flash + camera shake + target tile recoil + pip(s) shatter + "−1"/"−2" floats (L2) · **BLANK:** dry click, small cylinder shudder, "CLICK" |
| M13 | Self-blank bonus (L3) | "CLICK" → actor plate stamps "BONUS TURN · SILENT" → fresh 30s DECISION |
| M14 | Death (C9) | Frame corners break apart; plate turns black, name struck; **red "BURNED" stamp**; face alpha→0.35 (pixels untouched — whole-object fade, never a tint); pips clear; their chips (COVER placed by them) dissolve table-wide |
| M15 | Killer's extra turn (C5) | Band: "EXTRA TURN · \<NAME\>" + full TALK phase re-opens |
| M16 | Reload (C1/C4) | Compressed M2 (~2× speed); death-reload prefixed "IN THEIR HONOR"; announce 5s (M3). After MAGNET-emptied reload: band "STILL YOUR SHOT" (C3) |
| M17 | Item draw (C2/S7) | Your 2 draws: die tumble → icon slides into KIT with name; **over-cap: the icon bounces off the KIT with "FULL"** (the silently-swallowed draw becomes visible); others: card-backs absorb |

**Items** (public use event → choreography; private results stay private):

| # | Item | Choreography |
|---|---|---|
| M18 | PASSPORT (heal) | Passport icon flies KIT→your pips; pip refills |
| M19 | SPYCAM (peek) | Camera icon to center, shutter blink — **your view only:** peek chip fills "NEXT: LIVE" (red) / "NEXT: BLANK" (white), persists until that shell moves (server Extras logic, unchanged); others see "\<NAME\> USED A SPYCAM" |
| M20 | POISON (saw, I4) | Red edge-glow on the cylinder + "×2 ARMED" chip pinned at the dial until the shot resolves (public state, visible to all) |
| M21 | BLACKMAIL (immunity) | Envelope chip flies caster→target; target plate gains "BLACKMAIL · \<caster\>" chip; clears when the target shoots — **or when the caster dies** (C9) |
| M22 | MAGNET (beer) | Shell pops out of the cylinder top, flies off-screen; "SHELL OUT"; empty → M16 |
| M23 | SEDATIVE (handcuffs, I6) | Chip "SEDATED" on target; **at the skip itself:** rotation pauses at their seat, "SKIPPED" stamp, chip clears, rotation continues — the invisible skip becomes a beat |
| M24 | Cap hit (I10) | Toast "\<ITEM\> EXHAUSTED — TABLE LIMIT"; icon greys in every KIT/LEDGER until a death resets |

**Economy + endgame:**

| # | Moment | Choreography |
|---|---|---|
| M25 | Flip | Payment tray → confirm → target's plate **inverts polarity live** (white↔black snap + frame weight swap) — the flip IS the visual; "\<A\> TURNED \<B\>" |
| M26 | Trade | Actor taps TRADE → teammates **glow** → tap one → offer tray (GIVE / WANT pickers, unbound from inventory) → counterparty's ACCEPT/DECLINE tray (private) → **settle:** card-backs fly BOTH ways publicly, real items render only for the two parties · **cancel:** private "TRADE CANCELLED" stamp to both (4.5) |
| M27 | Teams off (G3) | At 2 alive: "AGENCIES DISSOLVED · FREE FOR ALL" band; both plates equalize (black, white text, equal 3px frames) — team semantics visibly end |
| M28 | Winner | Winner's portrait centered, "LAST AGENT STANDING · \<NAME\>"; credits line (JJ99 · Darkmoonfire, per ATTRIBUTION.md) |

**Dev harness (the ratification gate):** `static/game/moments.html` replays the whole catalog
back-to-back on canned event data — every moment reviewable in-engine before live wiring, and it
stays as a regression gallery.

## 8 · Red inventory (red = danger only — the complete list)

Target brackets (M11) · final-5s countdown digits (M8) · pip-shatter particles (M12) ·
"×2 ARMED" glow/chip (M20) · "NEXT: LIVE" peek (M19) · "BURNED" stamp (M14). Nothing else is red.

## 9 · Decisions made in this spec (review these — everything else was pre-ratified)

| # | Decision | Basis |
|---|---|---|
| D1 | Flips + shots are **decision-phase only**; trades talk-only | guide:169/:172 parallel enumeration; bonus turn (:189) = "items and flip" confirms flips live in the silent phase |
| D2 | "Timer runs out with no action" = **no shot committed** | anti-stall intent; item-use can't end a turn, so any weaker reading allows infinite stalling |
| D3 | Trade = **bluffable offer/accept swap** — offers unbound from inventory; on accept the server validates both sides + caps, else "cancelled" warning to both; settles as two atomic gift steps (engine unchanged) | user-designed 2026-07-08 (supersedes the gifts-only draft); guide:137-138 (any terms; over-cap blocked) |
| D4 | Trade event public, **item identities private** to the two parties | "who holds which item" is hidden info (guide:154) |
| D5 | **Dead players are muted** | a dead player can hold a live peek → leak channel; spies who are burned leave the table |
| D6 | **Bots skip phases/timers** (cascade pace) | timers bound human stalling; 60s bot talk phases would make 1-human games unplayable |
| D7 | Chat locked outside talk phases for **everyone** (not just the actor) | guide:172 "Silence." at the table |
| D8 | Fines burn cap-free via engine `state.rng` | guide:99 (sacrifice ≠ use); determinism |
| D9 | Corpse inventory burned + placed Immunity expired **in the engine** at death | guide:69 says burned/expires; fixes V3+C9 at the source instead of patching the view |
| D10 | Real lobby names on plates; bots get theme codenames | plates showed "P0"–"P4" while names existed unused |
| D11 | Disconnected actor: clock runs → fines → auto self-shoot (no bot substitution) | timers already make stalls self-resolving; less machinery |
| D12 | Death look: red BURNED stamp + broken frame + whole-face alpha fade | faces-sacred rule: opacity fade of the untouched sprite, never pixel changes |

## 10 · Testing

- **Engine (pytest):** I9 illegal (legal_actions omits + apply_item raises) · death burns corpse
  inventory · death expires the dead caster's placed Immunity · `fine_cheapest` (cheapest by value,
  rng tie-break, None when broke) · existing 181 stay green.
- **Room (pytest, no sockets):** begin_turn sets TALK (or BONUS→DECISION) · proceed gates to actor ·
  talk-deadline → DECISION · decision-deadline → fine (+reset) → … → auto self-shoot when broke ·
  phase-filtered legal sets (no Shoot/Flip in talk view; no Trade in decision) · apply rejects
  phase-illegal actions · trade: offer gated (phase/team/alive/one-pending) · accept settles a
  valid swap atomically · bluffed give, bluffed want, and cap-breaking swaps each cancel with no
  state change · offers expire at talk-phase end · decline is private · chat gate
  (talk-only, living-only) · gen counter no-ops stale deadlines · extra_turn flag set/cleared ·
  trade privacy (public event stripped; parties enriched).
- **View:** new fields present · no-leak tests extended over trade events (no foreign hands, no
  shell order, no peek leak — existing invariant tests as the base).
- **Client:** `moments.html` gallery = visual ratification + regression; then one full live browser
  game to a winner (Chrome phone-frame, then a real phone).

## 11 · Build order (writing-plans input)

1. Engine fixes + tests (I9, C9/V3 burn, fine_cheapest).
2. Room phases/timers/fines/trade/chat-gate + gen counter + tests.
3. Protocol: view fields, `proceed`/`trade` messages, per-seat event enrichment, roster + tests.
4. Phaser core: boot/join/lobby HTML shell + TableScene static render from a live view (no motion).
5. Choreographer + **moments.html** gallery — user ratifies the catalog visually.
6. Wire live events → choreographer; port queue/drain/skip.
7. Trays: KIT/LEDGER/CHAT/TRADE/FLIP-payment; timers UI; peek chip.
8. Theme table, codenames, credits; v1 UI retired (`/` serves the new client; `/v1` keeps the old
   one until v2 is verified on a phone).
9. Full-game verification: Chrome phone-frame → real phone → 2-human room.

## 12 · Out of scope / deferred

Sound design · haptics · Render deploy (right after v2 verification) · final naming pass (game,
agencies, items, train livery) · LLM/social bots · spectators · persistence.

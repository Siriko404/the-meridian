# Sessions, Identity, and 12 Players — Design

**Date:** 2026-07-11 · **Rev 2** (convention-audit pass: every relevant file read end-to-end; 10 corrections folded in)
**Status:** Sections ratified by Sina 2026-07-11; Rev 2 fixes are convention corrections, not decision reversals.
**Extends:** `2026-07-07-ui-v2-phaser-design.md` (all its laws stand unless explicitly superseded here).
**Realizes ledger items:** #9 (login + ticket profile + waiting room). #20 (PWA) stays deferred.

---

## Ratified decisions (user answers)

| Decision | Ruling |
|---|---|
| Durability | Session file lives while the game is unfinished (players rejoin; a drop holds the game 5 minutes). Game over → players offered the state file for download; NEXT closes everything and deletes it. Instance-local JSONL suffices — the file's life IS the game's life. Storage swappable. |
| Auth | Initials + issued ID, no password. The ID is the credential. Impersonation risk accepted (friends). |
| Resume (mid-game drop) | Auto-resume with 3-second countdown when the dropped player rejoins. |
| Resume (cold restore) | All seated humans back + all hit READY → 3·2·1 (user's original ruling: "present and vote ready"). |
| Pause timeout | 5:00 expires → conductor chooses: seat becomes a bot, or end the session. |
| Player count | Conductor sets 5–12 in the waiting room. Empty seats become bots on depart. |

## §0 Convention charter (verified in source — binding on all new work)

**Aesthetics (DOM chrome):**
- Red is FORBIDDEN in overlay chrome (`game.css:1`) — red = danger only, in-game. All new pages are pure black/white.
- The `.ticket` idiom is the ONLY page container: 330px, `border:3px double #fff`, `.rule` hairlines, `.brand` Times-serif 32px ls-6, `.sub` 11px #aaa ls-5, `.lbl` 10px #777 ls-3, uppercase centered inputs, white-bg black-text buttons ls-6, `.hint` 11px #777, `.credits` 10px #555 (game.css:9–31).
- Fonts: Consolas mono base; Times serif for brand/code/monogram/member rows.
- Copy voice: UPPERCASE labels, train/espionage lexicon (CAR · BOARD · DEPART · MANIFEST · CONDUCTOR · "agents of the house"), middle-dot separators, sentence-case hints. Copy must match engine truth (ledger session_laws).
- In-world voice = `scene.toast` serif on canvas; `#banner` = harness voice only (handler_v2_session convention). Faces SACRED — alpha only, never tint (scene.js:98).
- Credits must name JJ99 · DARKMOONFIRE wherever portraits/icons appear (ATTRIBUTION.md).

**Architecture laws:**
- ONE page, ONE WS connection (ui-v2 §6.1). New screens = `section.overlay` blocks in `index.html` toggled by `show()` (main.js:20) — never separate routes.
- Pre-game = themed HTML; in-game = Phaser. State that must survive reconnect RIDES THE VIEW (pending_offer/warrant_pick precedent, room.py:303–308).
- Server: per-room `asyncio.Lock`; mutate → `_capture_payloads` under lock → `_broadcast_views` → `_schedule_deadline` (server.py:96–105). Room stays sync + unit-testable, no sockets.
- Client: gen gate at enqueue, countdown anchored at view ARRIVAL (timer-freeze law, main.js:49–51). New JS files register in the `FILES` cache-buster list (index.html:54).
- JS: IIFE + `"use strict"`, UMD export if node-tested, section-banner comments, comments cite laws/dates/audit ids. Python: docstrings citing rulings; `IllegalAction` messages in lowercase noir voice ("the moment has passed").
- Process: atomic commit per item; push only on Sina's word (push = deploy); master + uiv2-client synced; curl-confirm before sharing links; film/self-audit every new visual before presenting.

## §1 Screen map (overlays, one page)

```
#terminus (title ticket)
 ├─ #papers  — create: monogram inputs (existing .initials idiom) + portrait pick
 │            (the 12 JJ99 faces) → server issues ID → ticket shows the document → dashboard
 └─ #signin  — monogram + ID → server lookup → profile card "IS THIS YOU?" → CONFIRM → dashboard
        ↓
#dashboard (your ticket header: portrait · monogram · ID)
 ├─ ACTIVE JOURNEYS — unfinished games holding this profile's seat → REJOIN
 ├─ NEW CAR  — creates a room, you are conductor
 └─ JOIN     — code input (existing .codein idiom)
        ↓
#platform (waiting room) → GAME (Phaser) → end: M28 winnerScene (kept) → tap →
#record ticket: DOWNLOAD RECORD · NEXT (deletes server file → dashboard)
```

- **Auto-return:** localStorage `meridian_pid` + `meridian_car` (active game code). On load: pid known + active car → reconnect straight into the game (hold/3·2·1 if applicable); pid known, no car → #dashboard; nothing → #terminus. If the device remembers a profile, #terminus leads with "CONTINUE AS S.K." + a switch option.
- Current `#join` overlay dies; its `.initials`/`.codein` markup moves into #papers/#signin/#dashboard. `localStorage.meridian_token` is retired (profile id replaces the per-lobby token).
- Hardcoded "NIGHT SERVICE · CAR 4 · 5 SEATS" (index.html:13) becomes dynamic (seats from the dial).

## §2 Identity — "PAPERS"

- `data/profiles.jsonl`, append-only: `{"pid", "initials", "portrait", "created"}`. Dict at boot; append on create. `storage.py` owns all file I/O (swappable later).
- **pid format:** issued code `X-####` from unambiguous charset (no 0/O/1/I), e.g. `M-7K2F`. Uniqueness enforced at issue.
- **Portraits = the existing 12 JJ99 faces** (36×36 spritesheet already loaded as `"faces"`). The picker renders the sheet frames; server stores the frame index. Duplicates across profiles allowed; monogram plates remain the table identity (matches current codename behavior). Credits line stays on #terminus.
- Sign-in: initials + pid → server returns profile or "no such papers" (noir voice) → confirm card → dashboard.
- **Protocol:** `join` sends `{code, pid}` (server looks up initials/portrait from the profile store — client never asserts its own name). Roster broadcast gains portraits: `roster: {seat: name}` stays, new sibling `portraits: {seat: frame}`; `THEME.seatName` untouched; `paintSeat`/`winnerScene` use `portraits[seat]` with `id % 12` as fallback.

## §3 Waiting room — "PLATFORM"

| Element | Rule |
|---|---|
| Roster | MANIFEST list: portrait + monogram per boarder (`.member` row idiom, Times serif), `· CONDUCTOR` suffix kept, `· READY` state per row |
| Conductor | Room creator; leaves pre-departure → earliest remaining boarder inherits (existing `host` flag semantics) |
| Ready | READY toggle button for every human; all-ready required |
| Seats dial | Conductor-only stepper `5 – 12`, never below humans aboard; **joins beyond the dial are refused at `join` time** ("the car is full") — closes the current hole where the member cap is only checked after start (server.py:148) |
| DEPART | Conductor-only (`startbtn` kept), locked (greyed + server-rejected) until every human aboard is ready |
| Bot fill | On depart: `seats − humans` bots; hint copy stays "Empty seats become agents of the house" |

Server: `NUM = 5` (server.py:22) dies; `start` takes `num_players` from the lobby's dial. Lobby state message gains `{seats, ready: {...}}`.

## §4 Session lifecycle + hold

**Supersedes D11** (ui-v2 §9: "disconnected actor: clock runs → fines → auto self-shoot"). New law: a seated human's drop mid-game HOLDS the game for everyone. D11's fine/auto-shoot machinery still governs *connected* stalling, unchanged.

### Persistence
- Started games append to `data/sessions/<CODE>.jsonl` via `storage.py`:
  - line 1 meta: `{code, seats, members: [{pid, initials, portrait, seat}], created}`
  - one line per mutation: `{t, gen, snapshot: Room.to_dict()}` — written inside the existing lock, right after `_capture_payloads` (same critical section, no new races; ~KBs per line, append-only).
- `Room.to_dict()/from_dict()` cover: GameState (players with team/inventory/specials/immunity/flags, order, current_id, chamber incl. bullet order, use_counts, tax/poison/bonus state), rng via `random.Random.getstate()`, Extras per seat, and Room fields (phase, remaining time, pending_offer/warrant/handler/bot-shot/dragnet, feed, seating, human set, extra_turn, _turn, _notes).
- **The snapshot holds secrets** (bullet order, every hand). The download endpoint serves the file ONLY once `winner is not None` (or END THE LINE). No mid-game access, ever.
- Boot: `storage.py` scans `data/sessions/`, unfinished games restore as HELD lobbies. Cold restore = ready-vote (ratified). Files older than 7 days swept at boot.
- Waiting-room-only lobbies are not persisted.

### Hold (mid-game drop)
- Seated human's ws drops while `room.winner is None` → under the lock: `held_remaining = phase_ends_at − now`, `phase_ends_at = None`, deadline task cancelled, broadcast. A parked bot shot (`pending_bot_shot`) freezes with the phase — same deadline machinery.
- View gains `hold: {missing: [seats], since, deadline}` (rides the view — reconnect-safe by the standing pattern). Client: in-world full-board scrim + serif line `AGENT S.K. LEFT THE CAR — HOLDING AT SIGNAL — 4:32` counting 5:00 down (canvas, decode-in; NOT the DOM banner; red only if we classify the final stretch as danger — default white, per red-inventory law).
- Multiple droppers: hold lists all missing; resumes only when all are back.
- Rejoin (all back) → `3 · 2 · 1` beat → `phase_ends_at = now + held_remaining`, deadline re-armed, broadcast (countdown re-anchors at arrival — timer law holds).
- 5:00 expires → conductor's view gains the choice sheet (thread-menu grammar): `SEAT THE HOUSE` (missing seat's human flag drops — it plays as a bot from the next decision boundary; if mid-turn, the standard deadline machinery resolves the turn) or `END THE LINE` (session over → record ticket). Conductor missing → earliest connected human holds the choice.
- Chat frozen during a hold (server rejects, input disabled).

### End of the line
- Winner (or END THE LINE) → M28 winnerScene plays as today → tap → `#record` ticket: `DOWNLOAD RECORD` (GET `/session/<code>/record`, post-end only) · `NEXT` → server deletes the file + lobby, client clears `meridian_car`, → #dashboard.

### New protocol surface
- WS: `ready {on}`, `seats {n}` (conductor), `hold_choice {bot|end}` (conductor), `next` (post-end ack). `join` becomes `{code, pid}`.
- HTTP (pre-WS pages): `POST /papers` (create profile), `GET /papers?initials=&pid=` (sign-in lookup), `GET /journeys?pid=` (active games), `GET /session/<code>/record` (post-end only).

## §5 Twelve players

**Engine: proven.** `new_game` generic (`assert num_players >= 5`, engine.py:121), chamber scales with living count (chamber.py:5–16), 200/200 random-agent sims at 12 complete, `Room(num_players=12)` boots to talk.

**Verified UI defects to fix (the sweep is not optional polish):**
1. **Ring overlap:** seat pitch at n=12 ≈ 2·146·sin(π/12) ≈ **75.6px < the 78px tile** (scene.js:14,91). Fix: parametric seat size `S` (78 at n≤8, ~58 at n=12) with EVERY derived constant computed from S — tile, broken-corner ±39s, face scale, plate w2=39/h2, dot column x+48, chip column x−52, bracket ±44s, ant HALF=47, hit 88/94, stamp/arrow offsets. One derivation site, not a constant hunt.
2. **Bot monograms collide:** `CODENAMES` has 8 entries, `seat % 8` (theme.js:27,35) — extend the fixed list to 12 two-letter monograms (same "X.X." plate style).
3. **Dragnet sheet overflows:** 12 players × 2 rows ≈ 864px. Compact to one ruled row per player (`split` row idiom: name | inventory), or paginate — decide at build against the film.
4. Audit every N-seat surface at 5/8/12 with films: target pickers, trade lists, warrant sheet, ledger, monogram chip stacks, platform roster (DOM, scrolls), winner scene.
5. Faces: 12 frames = exactly 12 seats; humans wear chosen portraits, bots draw from the unused frames first (collision-free at any fill).

⚠ Pacing flag (stated, accepted): 12 humans × 90s turns ≈ 18 min per rotation.

## §6 Build order (each phase ships playable, film/test-verified)

| Phase | Delivers |
|---|---|
| **A** | `storage.py` + profiles + HTTP endpoints + overlay skeleton (#terminus/#papers/#signin/#dashboard), pid join, portraits in roster |
| **B** | Platform: ready gate, seats dial, join gating, DEPART lock, bot fill, NUM removal, dynamic sub copy |
| **C** | Session JSONL + hold/resume (both kinds) + conductor timeout choice + record ticket + boot restore + janitor |
| **D** | 12-player: parametric S geometry, codenames, dragnet sheet, films at 5/8/12, engine gate tests |

## Testing

- pytest: profile store round-trip · pid issue uniqueness · join gating vs dial · ready gate + depart lock · conductor inheritance · hold enters on drop (deadline cancelled) · resume clock math (held_remaining exact) · cold-restore ready-vote · timeout → bot conversion / end · snapshot round-trip `to_dict→from_dict` → identical `view()` for every seat · record endpoint denies while winner is None · janitor · Room invariants at 12.
- node: any new pure client logic (`*.test.mjs`).
- Films (capture/livepump + devcap): platform flow, hold overlay, 3·2·1, 12-seat board, dragnet at 12. Self-audit law applies before presenting.
- Live: curl-confirm on Render before sharing links.

## Non-goals

No passwords/email. No cross-instance durability (redeploy mid-game loses the game — we control deploys). No spectators; no mid-game joins beyond reclaiming your own seat. No PWA (item 20, later). Engine rules unchanged — transport/UI/lifecycle only.

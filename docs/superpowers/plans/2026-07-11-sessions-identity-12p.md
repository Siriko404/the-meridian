# Sessions + Identity + 12 Players — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline — user banned delegation for core implementation 2026-07-11). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Persistent resumable sessions with a papers/dashboard/platform flow, hold-on-disconnect, bot-fill up to 12 players, all inside the existing one-page WS architecture.

**Architecture:** New `storage.py` owns all file I/O (profiles.jsonl + sessions/<CODE>.jsonl). Server lobby grows ready/seats/hold states; Room gains to_dict/from_dict + hold clock. Client grows four ticket overlays and portrait-aware rendering; scene layout becomes seat-size-parametric.

**Tech Stack:** existing only — FastAPI/WS, sync Room, Phaser 4 vanilla JS. No new dependencies.

## Global Constraints (spec §0 — binding)

- Red FORBIDDEN in DOM chrome (game.css:1). Ticket idiom only. Uppercase noir copy, middle-dot separators.
- One page, one WS. New screens = `section.overlay` in index.html via `show()`.
- Reconnect state RIDES THE VIEW. Countdown anchors at view arrival. Gen gate at enqueue.
- Server mutations under per-room lock → `_capture_payloads` → `_broadcast_views`.
- Room stays sync/no-sockets. `IllegalAction` in lowercase noir voice.
- JS: IIFE + strict; UMD if node-tested; new files added to index.html `FILES` list.
- Faces sacred. scene.toast = in-world voice; #banner = harness only.
- Atomic commit per task. NO PUSH without Sina's word (push = deploy).
- Tests green before every commit: `.venv\Scripts\python.exe -m pytest tests/ -q` (263) + `node --test social_roulette/online/static/game/test/*.test.mjs` (8).

---

## Phase A — identity + overlay skeleton

### Task A1: storage.py (profiles)

**Files:** Create `social_roulette/online/storage.py`, `tests/test_storage.py`.

**Produces (API used by every later task):**
```python
DATA_DIR                                  # module-level, env-overridable for tests
load_profiles() -> dict[str, dict]        # pid -> {pid, initials, portrait, created}
create_profile(initials: str, portrait: int) -> dict   # issues pid, appends, returns profile
# pid format: X-#### from charset "ABCDEFGHJKLMNPQRSTUVWXYZ23456789" (no 0/O/1/I)
session_path(code) -> Path
session_write_meta(code, meta: dict)      # line 1
session_append(code, line: dict)          # one JSON line
session_read_meta(code) -> dict | None
session_read_last(code) -> dict | None    # last snapshot line
session_delete(code)
sessions_unfinished() -> list[dict]       # metas of files present (winner unknown = present)
sessions_sweep(max_age_days=7)
```

- [ ] Tests: pid charset/format/uniqueness (mock rng collision), create→load round-trip, append→read_last, meta first-line invariant, delete, sweep by mtime, journeys helper `journeys_for(pid)` returns codes whose meta.members contain pid.
- [ ] Implement (append-only files, `DATA_DIR` from `SR_DATA_DIR` env else `social_roulette/online/data/`; dir gitignored).
- [ ] pytest green → commit `feat(storage): profiles + session files`.

### Task A2: HTTP endpoints

**Files:** Modify `social_roulette/online/server.py`, create `tests/test_http_identity.py` (fastapi TestClient).

**Produces:**
- `POST /papers {initials, portrait}` → profile json (400 on bad initials `^[A-Z]{2}$` or portrait not 0–11)
- `GET /papers?initials=&pid=` → profile or 404 ("no such papers")
- `GET /journeys?pid=` → `[{code, seats, players:[initials], created}]` (unfinished only)
- `GET /session/{code}/record` → the JSONL file ONLY if that lobby's game has ended (winner set) or lobby gone but file marked ended; else 403 ("the line is still running")

- [ ] Tests for all four incl. the 403 guard.
- [ ] Implement; profiles loaded at startup into `PROFILES` dict.
- [ ] Green → commit `feat(server): papers/journeys/record endpoints`.

### Task A3: overlay skeleton (terminus/papers/signin/dashboard)

**Files:** Modify `social_roulette/online/static/game/index.html`, `social_roulette/online/static/game/game.css`, `social_roulette/online/static/game/js/main.js`.

**Screens (all `.ticket`, red-free, copy per spec §1):**
- `#terminus`: brand, "CONTINUE AS X.X." (if `localStorage.meridian_pid`) / "SIGN IN" / "NEW PAPERS", credits line (JJ99 · DARKMOONFIRE).
- `#papers`: monogram `.initials` inputs + portrait grid (12 frames cropped from the spritesheet via CSS background-position on 36px cells, ×2 scale) + ISSUE PAPERS → shows issued document (big pid in `.code` style, "WRITE IT DOWN — IT IS YOUR ONLY KEY") → CONTINUE.
- `#signin`: monogram + pid input → FIND MY PAPERS → confirm card (portrait, monogram, pid, "IS THIS YOU?") → SIGN IN / NOT ME.
- `#dashboard`: ticket header (portrait+monogram+pid), ACTIVE JOURNEYS list (fetch /journeys) with REJOIN per row, NEW CAR, JOIN + code input, SWITCH PAPERS (clears pid).
- Flow wiring in main.js: fetch calls, `localStorage.meridian_pid`, `meridian_car` set on join/cleared on NEXT; `meridian_token` removed.

- [ ] Build; self-audit law: screenshot each overlay at phone size (CDP), zoom, iterate before showing.
- [ ] node tests untouched-green; commit `feat(ui): papers/terminus/dashboard tickets`.

### Task A4: pid join + portraits on the wire

**Files:** Modify `server.py` (join handler), `main.js` (connect/handle), `scene.js` (paintSeat/winnerScene), `room.py` (nothing), `tests/test_server_join.py`.

**Protocol:** `{type:"join", code, pid}`; server resolves name= `initials` + portrait from PROFILES (unknown pid → error "papers not in order"). Member = `{pid, name, portrait, seat, ws, host, ready}`. `by_token` → `by_pid`. Broadcasts gain `portraits: {seat: frame}` beside roster.
**Client:** `scene.setPortraits(map)`; `paintSeat` face frame = `portraits[p.id] ?? p.id % 12`; winnerScene same. Bots: frames from the unused pool first.

- [ ] Server tests: join with pid, reconnect reclaims by pid, unknown pid error.
- [ ] Implement server + client.
- [ ] Green → commit `feat(identity): pid join, portraits ride the roster`.

## Phase B — platform (waiting room)

### Task B1: lobby state machine

**Files:** Modify `server.py`, create `tests/test_lobby.py`.

**Produces:** lobby msg `{type:"lobby", code, seats, members:[{name, portrait, seat, host, ready}]}`.
New WS msgs: `ready {on}` (any member, pre-start), `seats {n}` (host only, 5≤n≤12, n≥len(members)), `start` gated: host + all ready + room None.
Join gating: pre-start `len(lb.members) >= lb.seats` → error "the car is full". Host leaves pre-start → earliest member inherits (`host` flag moves, broadcast).
`Lobby` gains `seats=5`, member `ready=False`. `NUM` constant deleted; start: `Room(human_seats, seed, num_players=lb.seats)`.

- [ ] Tests: ready toggle broadcast, seats bounds (4→err, 13→err, below-humans→err), full-car join refusal, depart locked until all ready, host inheritance, bot count = seats−humans.
- [ ] Implement.
- [ ] Green → commit `feat(lobby): ready gate, seats dial, join gating, conductor inheritance`.

### Task B2: platform UI

**Files:** Modify `index.html` (#lobby → #platform), `game.css`, `main.js`.

- MANIFEST rows: portrait cell + monogram (`.member` serif) + `· CONDUCTOR` + `READY ✓/·` state.
- READY toggle button (all humans). Conductor extra: seats stepper `− 8 SEATS +` (5–12) and DEPART (greyed via `.locked` class until server says all ready; server still validates).
- Sub copy dynamic: `NIGHT SERVICE · CAR <code> · <seats> SEATS`.
- [ ] Build + screenshot self-audit; commit `feat(ui): platform manifest, ready, seats dial`.

## Phase C — persistence + hold

### Task C1: Room.to_dict/from_dict

**Files:** Modify `social_roulette/online/room.py`, `social_roulette/engine/*` ONLY if a field lacks access, create `tests/test_room_snapshot.py`.

**Schema (json-safe):** `{v:1, gen, phase, remaining, human, seating, extra_turn, feed, _turn, _notes, pending_offer, pending_warrant, handler, pending_bot_shot, _dragnet, state:{...players/order/current_id/chamber/use_counts/flags..., rng: rng.getstate() as list}, extras:{seat:...}}`. `remaining = phase_ends_at − now` at dump time (never absolute — restore re-bases). Sets → sorted lists; enum names as strings.

- [ ] Test: play a scripted sequence (items, trade, warrant, poison, bot turns) → `d = r.to_dict()` → `r2 = Room.from_dict(d, now_fn)` → for every seat `r2.view(s) == r.view(s)` (normalize phase_ends_at) and further identical steps produce identical events on both.
- [ ] Test: rng continuity — next shot identical after round-trip.
- [ ] Implement (`Recorder` gets a fresh instance on restore; archive continuity noted, accepted).
- [ ] Green → commit `feat(room): snapshot to_dict/from_dict`.

### Task C2: snapshot-per-mutation

**Files:** Modify `server.py`, `tests/test_session_files.py`.

- On `start`: `session_write_meta(code, {...members, seats, created})`.
- In every mutating handler (the `_capture_payloads` sites): after capture, still under lock, `session_append(code, {t, gen, snapshot})`. One helper `_persist(lb)` so it's one line per site.
- On end (winner broadcast): append `{ended: winner}` marker line.
- [ ] Tests: file grows per action; last line restores to current view; meta intact.
- [ ] Green → commit `feat(server): session journal per mutation`.

### Task C3: hold / resume (mid-game drop)

**Files:** Modify `room.py`, `server.py`, `main.js`, `scene.js`, `tests/test_hold.py`.

**Room:** `hold(missing:set)` → stores `held_remaining = phase_ends_at − now` (None-safe), `phase_ends_at = None`, `held_since = now`; `release()` → `phase_ends_at = now + 3.0 + held_remaining` (the 3s = the 3·2·1 beat window), clears hold; both no-op guarded. View gains `hold: {missing:[...], since, deadline: since+300}` while held. gen UNCHANGED (hold is not a game mutation; the view rebroadcast carries it).
**Server:** on ws disconnect of a seated human with live room → under lock `room.hold(...)`, cancel deadline task, `_persist`, broadcast. On rejoin: if all seated humans connected → `room.release()`, persist, broadcast (deadline re-arms via `_broadcast_views`). 5:00 server task per hold (gen-guarded like `_deadline`) → at expiry sets `hold_expired=True` on room, broadcast (conductor's view gains `hold_choice: true`).
**Client:** view.hold → full scrim (in-world, canvas): serif decode `AGENT S.K. LEFT THE CAR`, line 2 `HOLDING AT SIGNAL — M:SS` (wall-clock tick vs hold.deadline), band stands down. On release view: scrim drops, `3 · 2 · 1` decode beats, play resumes. Chat input disabled while held (server rejects too, "the car is held").

- [ ] Room tests: hold freezes remaining exactly; release re-bases (+3.0); double-hold/release no-ops; deadline never fires while held (server test with fake clock).
- [ ] Implement; film via capture.html new `hold` scenario.
- [ ] Green → commit `feat(hold): the car holds at signal`.

### Task C4: hold timeout → conductor choice

**Files:** Modify `room.py`, `server.py`, `main.js`, `tests/test_hold.py`.

- WS `hold_choice {kind: "bot"|"end"}` — accepted only from the conductor (or earliest connected human if conductor missing) while `hold_expired`.
- `"bot"`: for each missing seat: remove from `room.human`, member released (seat kept in meta for the record). Room releases; if it was the missing player's turn the standard deadline machinery resolves it (bots play via `_run_bots` on next mutation; if current seat is now bot, call the same path `start`-style: run `on_deadline` immediately under lock).
- `"end"`: room.winner stays None; lobby enters ENDED state; append `{ended: "abandoned"}`; broadcast `{type:"end", winner:null}` → client record ticket says `END OF THE LINE — NO VERDICT`.
- Client: conductor sheet via thread-menu grammar: rows `SEAT THE HOUSE` (sub: "their chair plays on as a bot") / `END THE LINE` (sub: "close the record — no verdict").
- [ ] Tests: choice gating (non-conductor rejected pre-expiry rejected), bot conversion plays on to a winner, end path serves record.
- [ ] Green → commit `feat(hold): conductor's choice at the 5:00 signal`.

### Task C5: boot restore + cold ready-vote

**Files:** Modify `server.py`, `tests/test_restore.py`.

- Startup hook: `sessions_sweep(7)`; for each unfinished session file: rebuild `Lobby` (code, seats, members from meta with ws=None, ready=False), `Room.from_dict(last snapshot)`, immediately `room.hold(all human seats)` — restored car waits HELD.
- Rejoins land in the held game (join → by_pid → view with hold). Cold rule: release requires all seated humans connected AND all sent `ready {on}` post-restore (vote — spec ruling). The 5:00 clock starts at FIRST rejoin, not at boot.
- [ ] Tests: restart-simulation (new LOBBIES dict, restore from files) → views identical; ready-vote release; janitor removes stale.
- [ ] Green → commit `feat(restore): held cars survive the server`.

### Task C6: record ticket (end screen)

**Files:** Modify `index.html`, `game.css`, `main.js`, `server.py`.

- After M28 winnerScene, any tap → `#record` ticket: `END OF THE LINE` / winner line (or `NO VERDICT`), `DOWNLOAD RECORD` (anchor to `/session/<code>/record`, download attr) · `NEXT`.
- WS `next` from any member → once ALL connected members sent it (or 60s), server deletes file + lobby; ack broadcast; client clears `meridian_car` → #dashboard. (Simpler alternative rejected: first NEXT deletes — would kill slower downloaders' link.)
- [ ] Implement + screenshot audit; commit `feat(ui): the record ticket`.

## Phase D — twelve players

### Task D1: codenames ×12

**Files:** Modify `theme.js`, `social_roulette/online/static/game/test/theme.test.mjs`.
- Extend CODENAMES to 12 unique monograms: add `"R.S.", "E.F.", "L.O.", "T.B."`.
- [ ] node test: 12 unique; commit `feat(theme): twelve codenames`.

### Task D2: parametric seat geometry

**Files:** Modify `scene.js`.

- One derivation site in `layout(order)`: `const S = n <= 8 ? 78 : 58;` and derived: `HALF_T = S/2` (tile/broken/plate w2), face scale `2 * S/78` (rounded to keep pixel crispness: use 2 at S=78, 1.5 at S=58), plate `h2` unchanged 13, plate gap `y + S/2 + 22`, dots `px = x + S/2 + 9`, chips `bx = x − S/2 − 13`, brackets `±(S/2+5)`, ants `HALF = S/2 + 8`, hits `S+10`. Store `this.S` so setChips/_paintDots/setTargets/setItemTargets/seatGlow/stampSeat read it.
- Ring radius bumps at n>8: `RX = 142, RY = 150` → `RX 150, RY 168` (still clear of band y≈100 and dock y=700: top seat y = 430−168−S/2 = 233 ✓, bottom 598+29=627 ✓).
- [ ] Verify by film: capture board at n=5, 8, 12 (new capture scenarios) — no overlap, chips on-screen at leftmost seat (x ≈ 45−29−13 = must stay ≥ 0: check, adjust chip column inward at S=58).
- [ ] Commit `feat(scene): seat-size parametric layout for 12`.

### Task D3: dragnet sheet at 12

**Files:** Modify `main.js` (dragnetSheet).
- Replace 2-row-per-player with ONE `split` row per player: `[seatName, inv-string truncated]`; header keeps the SPECIALS STAY DARK line. 12 split rows ≈ fits (info row + 12×~30 + padding ≈ 450px).
- [ ] Film at 12; commit `fix(ui): dragnet report holds twelve`.

### Task D4: 12p gate tests + full pass

**Files:** Create `tests/test_twelve.py`; modify `capture.html` (scenarios n8/n12).
- [ ] pytest: Room at 8 and 12 — full scripted game to winner via on_deadline loop; warrant/dragnet/handler legal at 12; lobby seats=12 end-to-end.
- [ ] Films: board 5/8/12, dragnet 12, platform 12 rows, hold overlay — self-audit each.
- [ ] Full suites green; commit `test(twelve): gates`.

### Task D5: docs + ledger + status

- [ ] Update `docs/FEEDBACK_LEDGER.json` (item 9 → status, new session block), `docs/PROJECT_STATUS.md` handoff.
- [ ] Commit `docs: sessions+identity+12p shipped`. NO PUSH until Sina's word.

## Self-review (done at write time)

- Spec coverage: §0→Global Constraints; §1→A3/A4; §2→A1/A2/A3; §3→B1/B2; §4→C1–C6; §5→D1–D4; testing section→ per-task tests; non-goals respected (no PWA, no new deps).
- Type consistency: storage API names used identically in A2/C2/C5/C6; `hold`/`release`/`held_remaining` consistent C3–C5; `portraits` map name consistent A4/B2.
- No placeholders: every task carries concrete tests, exact messages, exact geometry numbers.

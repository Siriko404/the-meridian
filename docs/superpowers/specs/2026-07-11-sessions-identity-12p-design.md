# Sessions, Identity, and 12 Players — Design

**Date:** 2026-07-11
**Status:** Ratified by Sina section-by-section (all 6 sections "Approve as written")
**Scope:** Three user mods unified into one architecture: (1) persistent session state + reconnect + waiting room + pause-on-disconnect + bot fill, (2) up to 12 players, (3) identity/sign-in pages with full page map.

---

## Ratified decisions (user answers, verbatim intent)

| Decision | Ruling |
|---|---|
| Durability | Session file lives while the game is unfinished (players can rejoin; a drop holds the game for 5 minutes). When the session is over, players are offered the state file for download; a NEXT button closes everything and deletes the file. Instance-local JSONL is sufficient — the file's life IS the game's life. Storage layer kept swappable. |
| Auth | Initials + issued ID, no password. The ID is the credential. Party game among friends; impersonation risk accepted. |
| Resume | Auto-resume with 3-second countdown when the dropped player rejoins. No ready-vote per drop. |
| Pause timeout | After 5:00 of holding, the conductor chooses: seat becomes a bot and play continues, or end the session. |
| Player count | Conductor sets 5–12 in the waiting room. Empty seats become bots on depart. |

---

## §1 Page map (the skeleton)

```
TERMINUS (title page)
 ├─ NEW PAPERS ── create: initials + portrait pick → server issues ID → shows TICKET document
 └─ SIGN IN ───── initials + ID → server lookup → "IS THIS YOU?" profile card → confirm
        ↓
 DASHBOARD ("your ticket" header)
 ├─ ACTIVE JOURNEYS — unfinished games holding this profile's seat → REJOIN
 ├─ NEW ROOM — creates a room, you are conductor
 └─ JOIN CODE — code input → waiting room
        ↓
 WAITING ROOM ("PLATFORM") → GAME → END SCREEN
                                      ├─ DOWNLOAD RECORD (session JSONL)
                                      └─ NEXT → server deletes file → dashboard
```

- **Auto-return:** the device stores `{profileId, activeGameCode}` in localStorage. A reload or reconnect anywhere lands the player back where they belong (game if running, waiting room if not departed, pause overlay if held). No retyping codes.
- If the device remembers a profile, TERMINUS shows "CONTINUE AS S.K." plus a switch-profile option.
- All pages are 1-bit noir themed, consistent with the existing game (white on black, red #c8102e = danger only).

## §2 Identity — "PAPERS"

- Server file `data/profiles.jsonl`, append-only: `{"id", "initials", "portrait", "created"}`.
  Loaded into a dict at boot; appended on create. Never deleted.
- **ID format:** short issued code, e.g. `M-7K2F` (letter-dash-4 alphanumeric, unambiguous charset — no 0/O/1/I).
- **Portraits:** a fixed list (~12) of 1-bit noir pixel portraits drawn as code (canvas/glyph art), theme-matched. Client picks by index; server stores the index.
- The profile ID **replaces** the current per-lobby random `token`. Lobby members are keyed by profile id. `localStorage.meridian_token` migration: old token dies; users create papers once.
- Sign-in flow: initials + ID → server returns the matching profile (or "no such papers") → client shows the profile card → user confirms → dashboard.

## §3 Waiting room — "PLATFORM"

| Element | Rule |
|---|---|
| Roster | Every boarder: portrait + initials; conductor gets a badge. Live-updates on join/leave. |
| Conductor | The room creator. If the conductor leaves pre-departure, the earliest remaining boarder inherits. |
| Ready | Every human toggles READY; state visible to all on the roster. |
| Seats dial | Conductor-only. Range 5–12, never below current humans aboard. Joining beyond the dial is refused ("car is full"). |
| DEPART | Conductor-only. **Locked** (visually and server-side) until every human aboard is ready. |
| Bot fill | On depart, `seats − humans` bots fill the gap; copy: "N SEATS TO AGENTS OF THE HOUSE". |

Server: `NUM = 5` hardcode dies. `start` uses the dial value as `num_players`.

## §4 Session lifecycle + pause

### Persistence
- Every **started** game appends to `data/sessions/<CODE>.jsonl`:
  - line 1: meta `{code, seats, members:[{pid, initials, portrait, seat}], seed, created}`
  - then one line per mutation: `{t, gen, snapshot}` where snapshot is the full serialized Room.
- Room gains `to_dict()` / `from_dict()` covering GameState, players, Extras, chamber, order/seating, phase + remaining time, pending structures (offer, warrant, handler, bot shot, dragnet), feed, and `rng` via `random.Random.getstate()` (JSON-encoded).
- Written under the existing per-room asyncio lock, after `_capture_payloads` — same critical section, no new races.
- On server boot: scan `data/sessions/`, restore each unfinished game as a **held** lobby (paused, waiting for members to rejoin). Members rejoin by profile id + code (or dashboard REJOIN). **Cold restore uses a ready vote** (user's original ruling: "continued when all players are present and vote ready to go"): all seated humans back + all hit READY → 3·2·1 → play resumes. (Auto-resume without a vote applies only to mid-game drops, per the ratified Q3 answer.)
- Once at least one human has rejoined a restored session, the 5:00 hold clock for the still-missing starts, with the same conductor choice at expiry. Session files older than 7 days are swept at boot (janitor).
- Waiting-room-only lobbies (not departed) are NOT persisted — players re-form if the server dies pre-departure.
- Storage behind a small module (`storage.py`) so a DB can replace files later without touching game logic.

### Pause (mid-game drop)
- A seated human's ws drops while the game is live → the room **freezes**: `held_remaining = phase_ends_at − now`, deadline task cancelled, `phase_ends_at = None`, broadcast a `hold` view.
- Overlay for everyone: `AGENT S.K. LOST — HOLDING AT SIGNAL — 4:32` counting down from **5:00**.
- Multiple droppers: hold until ALL are back; overlay lists the missing.
- Rejoin (all back) → 3·2·1 countdown → `phase_ends_at = now + held_remaining`, deadline re-armed, play continues exactly where it froze.
- **5:00 expires** → conductor-only choice on the overlay: **SEAT THE HOUSE** (missing player's seat becomes a bot; if it was their turn the bot plays on) or **END THE LINE** (session over → end screen). If the conductor is the one missing, the earliest connected human decides.
- Chat is frozen during a hold (scrim blocks input).

### End of session
- Winner declared (or END THE LINE) → end screen offers **DOWNLOAD RECORD** (serves the session JSONL) and **NEXT** → server deletes `sessions/<CODE>.jsonl`, clients return to dashboard, active-game pointer cleared.

## §5 Twelve players

- **Engine: proven.** `new_game` is generic (`assert num_players >= 5`); chamber scales with living count; 200/200 random-agent sims at 12 complete; `Room(num_players=12)` boots to talk phase.
- Server: player count flows from the waiting-room dial (5–12).
- **UI sweep at 12** — every surface that lays out N seats gets audited and film-verified at 5, 8, and 12:
  - ring layout (`seatAngle` is generic; tile size 78px shrinks at n>8),
  - target pickers, trade partner lists, warrant/dragnet/handler sheets, ledger columns, monogram stacks, roster in the waiting room.
- ⚠ Pacing flag (stated, accepted): 12 humans × 90s turns ≈ 18 min per rotation.

## §6 Build order

Each phase ships playable and is film/test-verified before the next starts.

| Phase | Delivers |
|---|---|
| **A** | Identity + page skeleton: profiles.jsonl, TERMINUS / NEW PAPERS / SIGN IN / DASHBOARD, localStorage migration, portraits |
| **B** | Waiting room v2: roster, ready gate, seats dial, locked DEPART, bot fill, NUM removal |
| **C** | Session persistence + hold/resume + end-screen download/delete + boot restore |
| **D** | 12-player UI sweep + engine gate tests at 8/12 |

## Testing

- Python: unit tests per phase (profile store, ready gate, hold/resume clock math, snapshot round-trip `to_dict→from_dict→view` equality, deadline re-arm after resume, conductor timeout paths, 12-player Room invariants).
- Client: existing node test harness for pure logic; capture.html / livepump.html films for every new visual (waiting room, hold overlay, 12-seat ring).
- Live: curl-confirm on Render before sharing links (standing law).

## Non-goals

- No passwords, no email, no real auth.
- No cross-instance durability (Render redeploy mid-game loses the game — we control deploys).
- No spectators, no mid-game human joins beyond reclaiming your own seat.
- Engine rules unchanged — this is transport/UI/lifecycle work only.

# Final-review fixes — branch `uiv2-server`

Governing spec: `docs/superpowers/specs/2026-07-07-ui-v2-phaser-design.md` (§4.1, §4.3, §4.5, §4.6).
Baseline before work: **230 passed**. Final: **236 passed** (230 + 6 new tests).

## Commit 1 — `fix(room): phase-machine integrity` (C1 + C2)

### C1 — non-turn-ending actions must NOT re-begin the phase
`social_roulette/online/room.py`

Before, `apply()` and `flip()` unconditionally ended with `_begin_phase_for_current()`, so an
item use during DECISION dropped the room back to a fresh 60s TALK (chat reopened, trades
reopened, the fine machinery never fired). Spec: decision is silent (§4.1); a mid-decision MAGNET
reload does NOT extend the window (§4.3).

- `apply()`: after building `last_events`, re-begin the phase ONLY when the delta ended the turn —
  `self.winner is not None or any(e.get("type") == "shot" for e in self.last_events)`. Otherwise
  leave `phase`/`phase_ends_at` untouched and bump `self.gen += 1` once. (The turn only ever
  advances/re-arms via a SHOT; fines/auto-shoot flow through the same shot path.)
- `flip()`: a flip never ends the turn → replaced the trailing `_begin_phase_for_current()` with a
  single `self.gen += 1`.
- Gen bumped exactly once per call either way (`_begin_phase_for_current` bumps internally; the
  else-branch / flip bump the counter directly, never double-bumping).
- `on_deadline`'s auto-shoot path already re-begins — left as-is.

### C2 — gate `flip()` to the decision phase
`social_roulette/online/room.py`

Added after the turn check in `flip()`:
`if self.phase != "decision": raise IllegalAction("flips happen in the decision phase")`.
Flips are decision-only (§4.1/D1); they previously settled during TALK.

Existing test `tests/test_online_room.py::test_flip_with_chosen_payment` flipped during what is now
TALK — inserted `r.proceed(seat)` to enter decision rather than weakening the gate.

### C1/C2 tests (TDD, each RED first) — `tests/test_room_phases.py`
- `test_item_use_during_decision_keeps_phase_and_deadline` — MAGNIFIER use in decision: phase stays
  `decision`, `phase_ends_at` unchanged, exactly one gen bump.
- `test_item_use_during_talk_keeps_talk_deadline` — item use in talk does not extend the talk window.
- `test_magnet_reload_during_decision_keeps_phase_and_deadline` — BEER emptying a 1-shell chamber
  reloads (reload event fires) but phase/deadline unchanged.
- `test_flip_gated_to_decision_phase` — flip in talk raises; after `proceed`, the same flip succeeds
  and does NOT reset the phase.
- Existing `test_self_blank_bonus_goes_straight_to_decision` still passes (self-blank self-shot is a
  shot → fresh decision).

RED evidence:
```
E   Failed: DID NOT RAISE IllegalAction        (flip gate, pre-fix)
5 failed, 7 deselected
```
GREEN: `tests/test_room_phases.py tests/test_online_room.py` → `17 passed`.

Files: `social_roulette/online/room.py`, `tests/test_online_room.py`, `tests/test_room_phases.py`.
SHA: 5936ed1

## Commit 2 — `fix(server): broadcast integrity + input hardening` (I1 + I2 + I3)

### I1 — capture per-seat broadcast payloads INSIDE the lock
`social_roulette/online/server.py`

`_broadcast_views` recomputed `events_for(seat)`/`view(seat)` outside any lock, with awaits between
sends — a concurrent handler/deadline could mutate the room mid-broadcast (per-seat delta
loss/duplication). Fix:
- New `_capture_payloads(lb)` snapshots `{seat: {"events": events_for(seat), **view(seat)}}` for all
  seated members; every mutating handler calls it INSIDE its `async with lb.lock:` block (action,
  flip, proceed, trade_offer, trade_respond, trade_withdraw, start, and `_deadline`'s acted path).
- `_broadcast_views(lb, payloads=None)`: mutating paths pass the lock-captured snapshot; the
  no-mutation join rebroadcast (`payloads is None`) computes fresh. `_schedule_deadline(lb)` still
  runs at the end. Roster left as-is.

### I2 — expose `gen` in the view
`social_roulette/online/room.py` — added `"gen": self.gen` to the dict `view()` merges.
Test `tests/test_room_phases.py::test_view_carries_increasing_gen` — gen present, strictly increases
across an action.
Spec: appended a Protocol note to the END of §4.6
(`docs/superpowers/specs/2026-07-07-ui-v2-phaser-design.md`):
"Views carry `gen`; clients replay `events` only when `gen` increased." (cite audit I2-final-review).

### I3 — malformed payloads must not kill the socket
`social_roulette/online/server.py` — wrapped the `int(...)` coercions (action `i`, flip `target`,
trade_offer `to`) in `try/except (ValueError, TypeError)` → `{"type":"error","msg":"bad payload"}`
+ `continue`, done outside the lock (pure parsing). Previously an uncaught ValueError killed the WS
receive loop.
Test `tests/test_online_server.py::test_malformed_payload_does_not_kill_socket` — `{"type":"action",
"i":"garbage"}` → `bad payload` error, then a `ping` still answers `pong`.

RED evidence:
```
E   ValueError: invalid literal for int() with base 10: 'garbage'   (server.py:146, pre-fix)
1 failed, 4 deselected
```

Files: `social_roulette/online/server.py`, `social_roulette/online/room.py`,
`tests/test_online_server.py`, `tests/test_room_phases.py`,
`docs/superpowers/specs/2026-07-07-ui-v2-phaser-design.md`.

## Final suite
```
./.venv/Scripts/python -m pytest -q
236 passed in ~6s
```

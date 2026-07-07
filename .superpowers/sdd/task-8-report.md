# Task 8 Report — Room deadlines

## Implemented
`Room.on_deadline() -> bool` in `social_roulette/online/room.py` — the server's timer-tick handler:
- No-op (returns `False`) when there is a winner, no active phase, or the clock is short of `phase_ends_at`.
- `talk` deadline → transitions to `decision` with a fresh `DECISION_S`, bumps `gen`, calls `_expire_offer()`, clears `last_events`, returns `True`.
- `decision` deadline with non-empty inventory → `fine_cheapest`, records `fine` event, publishes `{"type": "fine", "actor": seat}` (no item, D14), fresh `DECISION_S`, bumps `gen`, returns `True`.
- `decision` deadline when broke → auto `Shoot(self)` through the normal human-action path (`_emit_human_action` → extras sync → bots cascade), rebuilds `last_events` from new recorder rows, `_begin_phase_for_current()`, returns `True`.

Added `_expire_offer(self): pass` stub (Task 9 fills it). Imported `fine_cheapest` from `social_roulette.engine.economy` at top of room.py.

## Tested + Results
Appended 2 tests to `tests/test_room_phases.py` verbatim from brief:
- `test_talk_deadline_advances_to_decision`
- `test_decision_deadline_fines_then_auto_shoots`

Full suite: **220 passed** (baseline 218 + 2). No sleeps — all transitions driven by the injected list-based clock `t[0]`.

## TDD Evidence
- RED: `2 failed, 3 passed` — `AttributeError: 'Room' object has no attribute 'on_deadline'` on both new tests.
- GREEN: `220 passed in 5.33s`.

## Files Changed
- `social_roulette/online/room.py` — import + `on_deadline()` + `_expire_offer()` stub.
- `tests/test_room_phases.py` — 2 new tests appended.

## Self-Review
- Completeness: all brief branches (early no-op, talk→decision, fine, auto self-shoot) covered and tested.
- Quality: matches room.py style (n0 recorder-row slicing, `_anim`, extras sync, bot cascade); import follows existing engine-module import block.
- YAGNI: `_expire_offer` is a bare stub per brief; no speculative logic added.
- Tests verify real state transitions (inventory drained, fine event present, phase strings, seat advance / bonus / winner) via injected clock, no sleeps.

## Concerns
None. Code transcribed verbatim from brief; suite green.

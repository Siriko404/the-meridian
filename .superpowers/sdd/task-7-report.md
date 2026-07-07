# Task 7 Report — Room phase core: talk/decision state, injectable clock, PROCEED

## Status: DONE

## Implemented
`social_roulette/online/room.py` (only production file touched):
- Class attrs `TALK_S = 60.0`, `DECISION_S = 30.0`.
- `__init__` signature now `Room(human_seats, seed, num_players=5, now_fn=time.time)`.
  New fields set at top of body (before existing body runs): `self.now`, `self.gen`,
  `self.phase`, `self.phase_ends_at`. Entire existing `__init__` body preserved verbatim;
  `self._begin_phase_for_current()` appended after the existing `self.last_events = [self._announce()]`.
- `_grace()` — spec §4.3 phase-anchor: `min(sum(5.0 if type in (announce, reload) else 1.6), 20.0)`.
- `_begin_phase_for_current()` — increments `gen`; sets `phase=None`/`phase_ends_at=None` on winner;
  else DECISION when `state.bonus_pending`, TALK otherwise, deadline = `now() + grace + dur`.
- `proceed(seat)` — actor-only, talk-only; bumps `gen`, moves to `decision`, deadline = `now() + DECISION_S`
  (no grace), clears `last_events`. Raises `IllegalAction` for non-actor / not-in-talk.
- `_begin_phase_for_current()` called at the END of both `apply()` and `flip()` (after `self.last_events = ...`).
- Added `import time`.

All code taken verbatim from the brief's Step-3 sketch. Note on the one internal inconsistency in the
brief: the Interfaces summary lists `_begin_phase_for_current(grace=0.0)`, but the verbatim Step-3 code
defines it with no `grace` param and computes grace via the `_grace()` helper from `last_events`. The
verbatim code is fully self-consistent (proceed clears `last_events`, and never calls
`_begin_phase_for_current`, so it gets zero grace directly), passes all tests, and is the concrete
"use verbatim" instruction — so it was used. Method/field NAMES all match the Interfaces block exactly.

## Tested + Results
- New file `tests/test_room_phases.py` (3 tests, verbatim from brief).
- The Task-10 `view(seat)["bonus"]` assert is written commented: `# ... # re-enabled in Task 10`.
- New tests: 3 passed.
- Full suite: **209 passed** (relative baseline 206 + 3 new). All existing `tests/test_online_room.py` green.

## TDD Evidence
RED (before implementation):
```
E  TypeError: Room.__init__() got an unexpected keyword argument 'now_fn'
3 failed in 0.16s
```
GREEN (after implementation):
```
tests/test_room_phases.py .... 3 passed in 0.04s
full suite: 209 passed in 8.47s
```

## Files Changed
- `social_roulette/online/room.py` (additive: 2 class attrs, 4 init fields, 3 methods, 3 call sites, 1 import)
- `tests/test_room_phases.py` (new)

## Self-Review
- Completeness: every Interfaces name present and exact (`Room(... now_fn=time.time)`, `TALK_S`,
  `DECISION_S`, `phase`, `phase_ends_at`, `gen`, `proceed`, `_begin_phase_for_current`).
- YAGNI: no speculative extras; no deadline-transition/gating logic (belongs to Tasks 8-9).
- Tests verify real behavior: fresh-turn TALK deadline, PROCEED actor-only + no-grace decision +
  double-proceed rejection, self-blank bonus routing straight to decision after apply.
- Additive change: existing Room tests untouched and green.

## Concerns
- Minor brief internal inconsistency re `_begin_phase_for_current` signature (documented above);
  resolved in favor of the verbatim Step-3 code. If a later task expects a `grace=` kwarg, it is a
  one-line addition — flagging for Task 8/9 authors.
- Advisor tool was overloaded/unavailable this session, so the ambiguity above was resolved by the
  agent's own reasoning rather than confirmed.

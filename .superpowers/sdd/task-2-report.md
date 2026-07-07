# Task 2 Report: Engine death cleanup — burn corpse inventory, expire placed Immunity (C9/V3)

## What I implemented
In `social_roulette/engine/engine.py`, in the kill branch of `take_shot`, immediately after
`player_by_id(state, target_id).alive = False`, added corpse cleanup per guide:69:
- `victim.inventory = {}` — the dead player's items are burned.
- Loop over `state.players` discarding `target_id` from each `p.immunity_against` — Immunity tokens the victim placed on others expire.

Placed after `alive = False` and before the `state.order` rebuild, exactly as the brief specifies.

## What I tested + results
- New file `tests/test_death_cleanup.py` with the two verbatim brief tests:
  - `test_death_burns_corpse_inventory` — asserts victim inventory `== {}` after a fatal shot.
  - `test_death_expires_placed_immunity` — asserts victim no longer appears in another player's `immunity_against` after a fatal shot.
- Focused: 2 passed.
- Full suite: 206 passed (baseline 204 + 2 new). No regressions.

## TDD Evidence
### RED
Command: `./.venv/Scripts/python -m pytest tests/test_death_cleanup.py -q`
Output: 2 failed.
- `test_death_burns_corpse_inventory`: `assert {<Item.BEER: 1>: 2} == {}` — corpse still held its items (engine kept inventory on death).
- `test_death_expires_placed_immunity`: `assert 0 not in {0}` — the other player still had the dead victim (id 0) in `immunity_against` (placed Immunity was not expired).
These are the expected failures: pre-change engine neither burned inventory nor expired placed Immunity.

### GREEN
Command: `./.venv/Scripts/python -m pytest tests/test_death_cleanup.py -q` → 2 passed.
Command: `./.venv/Scripts/python -m pytest -q` → 206 passed in ~5s.

## Files changed
- `social_roulette/engine/engine.py` — +4 lines in `take_shot` kill branch (guide:69 cleanup).
- `tests/test_death_cleanup.py` — new test file (2 tests).

## Self-review findings
- Completeness: both brief requirements met (inventory burned, placed Immunity expired); verified against real engine state, not mocks.
- Edge case: the discard loop covers every player, including the victim itself, and `set.discard` is a no-op when absent — safe.
- Placement matches the brief exactly; note the assigned `victim` local shadows nothing and reuses `player_by_id`; kept as brief dictated for consistency.
- Discipline: no changes outside the kill branch; compact style with guide:69 citations matching codebase convention.

## Concerns
None. Brief's absolute count (185) was stale; true baseline 204 → 206 after 2 new tests, as corrected in the task instructions.

# Task 1 Report — Engine fix I9: second same-caster Immunity is illegal

## What I implemented
Closed the rules-audit gap where a second Immunity placed by the SAME caster on the
SAME target was offered in `legal_actions` and silently consumed as a wasted no-op.

- `social_roulette/engine/actions.py` (IMMUNITY branch of `legal_actions`): now skips
  any target `o` whose `immunity_against` set already contains `player_id`, so the
  duplicate placement is no longer offered.
- `social_roulette/engine/items.py` (IMMUNITY branch of `apply_item`): after the
  non-self target check, binds `t = player_by_id(state, target_id)`, raises
  `ValueError("immunity already placed by this caster")` if `player_id in t.immunity_against`,
  otherwise adds and consumes as before. `_consume` and the return dict are unchanged;
  the existing `player_by_id(...)` line was folded into the new `t` binding.

## What I tested and results
- Appended `test_second_same_caster_immunity_not_offered` to `tests/test_legal.py`
  (verbatim from brief).
- Appended `test_apply_second_same_caster_immunity_raises` to `tests/test_items.py`
  (verbatim from brief); asserts the 2nd `apply_item` raises and the inventory count
  stays at 1 (2nd not consumed).
- Full suite: `204 passed` (0 failures). Note: the repo has grown since the brief was
  authored (brief cited a 181 baseline); the two new tests are included and green.

## TDD Evidence
### RED
Command: `./.venv/Scripts/python -m pytest tests/test_legal.py tests/test_items.py -q`
Result: `2 failed, 16 passed`.
- `test_second_same_caster_immunity_not_offered`: `assert offers == []` failed —
  `Left contains one more item: UseItem(item=<Item.IMMUNITY: 6>, target_id=0)` (the
  illegal second placement was still being offered).
- `test_apply_second_same_caster_immunity_raises`: `Failed: DID NOT RAISE ValueError`
  (the second placement was accepted and consumed instead of rejected).
These are exactly the pre-fix behaviors the task describes.

### GREEN
Command: `./.venv/Scripts/python -m pytest -q`
Result: `204 passed in 26.47s`.
Focused re-run of the two new tests: `2 passed`.

## Files changed
- `social_roulette/engine/actions.py`
- `social_roulette/engine/items.py`
- `tests/test_legal.py` (append)
- `tests/test_items.py` (append)

## Self-review findings
- Completeness: both surfaces (offer-side `legal_actions`, apply-side `apply_item`)
  fixed; edge case of the count-not-consumed is asserted. Existing `test_no_self_target`
  still passes, so the non-self guard is intact.
- Quality: minimal, matches the surrounding compact style; reused `t` binding avoids a
  duplicate `player_by_id` call.
- Discipline: nothing beyond the brief; error message and control flow are verbatim.
- Testing: tests exercise real behavior (offer omission + raise + non-consumption).

## Issues or concerns
- Only nit: full-suite count is 204, not the brief's 183 — the suite has grown since
  the brief was written. No failures; not a concern for this task.
- Git emitted LF→CRLF warnings on commit (pre-existing repo line-ending config); harmless.

## Commit
`d7d87bc` — fix(engine): I9 - second same-caster Immunity illegal, not a consumed no-op

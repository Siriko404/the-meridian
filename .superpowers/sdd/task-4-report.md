# Task 4 Report: `economy.swap` — all-or-nothing two-way transfer (audit a5)

## Implemented
- Added `MAX_PER_TYPE, MAX_TOTAL` to the constants import in `social_roulette/engine/economy.py`.
- Appended `_post_swap(inv, gives, gets)` helper: builds the projected inventory (validates ownership on gives, applies gives then gets, enforces ≤3/type and ≤8 total), raising `ValueError` on any violation.
- Appended `swap(state, a_id, b_id, give_a, give_b) -> None`: computes both POST-swap inventories via `_post_swap` before mutating anything, then assigns both. Any failure raises before mutation, so nothing moves — all-or-nothing.

Both match the brief verbatim.

## Tested + results
Appended three tests to `tests/test_economy.py` verbatim:
- `test_swap_both_at_cap_same_type_succeeds` — the a5 counterexample: both sides at cap (3 SAW), swapping SAW-for-SAW is legal because post-swap == pre-swap. Two sequential gift steps would have silently dropped items at the cap.
- `test_swap_unowned_give_rejected` — giving an unowned item raises `ValueError`, inventories untouched.
- `test_swap_cap_break_rejected` — type-cap break (4th SAW) and total-cap break (9th item) both rejected; counterparty inventory untouched.

Full suite: **215 passed** (baseline 212 + 3 new).

## TDD Evidence
**RED** (`pytest tests/test_economy.py -q`):
```
FAILED tests/test_economy.py::test_swap_both_at_cap_same_type_succeeds - ImportError: cannot import name 'swap'
FAILED tests/test_economy.py::test_swap_unowned_give_rejected - ImportError: cannot import name 'swap'
FAILED tests/test_economy.py::test_swap_cap_break_rejected - ImportError: cannot import name 'swap'
3 failed, 7 passed in 0.09s
```
**GREEN** (`pytest -q`): `215 passed in 5.16s`

## Files changed
- `social_roulette/engine/economy.py` — import line + `_post_swap` + `swap`.
- `tests/test_economy.py` — three appended tests.

## Self-review
- Completeness: matches brief exactly; import, helper, and public fn all present.
- Quality: `_post_swap` is symmetric for both sides; validation precedes all mutation, guaranteeing atomicity.
- YAGNI: no extra surface beyond the brief.
- Tests verify real inventories: the both-at-cap case exercises the actual a5 counterexample (net-zero swap at cap); the cap-break test checks both per-type and total caps and asserts the counterparty is untouched after failure.

## Concerns
None. Brief's absolute count (190) was stale as noted in the task; relative +3 (212→215) holds.

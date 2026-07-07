# Task 10 Report — Per-seat events + full view contract (privacy enrichment, new fields)

## Implemented

**`social_roulette/online/room.py`**
- `_anim`: added `fine` → `{"type":"fine","actor"}` (item stripped, D14) and `draw` → `{"type":"draw","seq"}` branches; `seq` keys the per-seat enrichment lookup. Reload branch and generic fallback unchanged.
- `__init__`: `self.extra_turn = False` initialized early (alongside the existing `pending_offer`/`_trade_result`/`_last_trade_items`), before any path that can read it.
- `view(seat)`: extended the existing T9 wrapper (kept the `legal` phase filter) with `phase`, `phase_ends_at`, `server_now` (=`self.now()`), `bonus` (=`state.bonus_pending`), `extra_turn`, `saw_active`, `use_counts`, `use_limit` (=`consumption_limit`), `teams_active`, `flipback_discount` (own only), and `pending_offer` (only when the seat is a party).
- `events_for(seat)`: new. Copies `last_events`; `draw` events gain `you` = that seat's own `{attempted,received}` (looked up in the recorder row by `seq`, handling JSON string keys via `draws.get(str(seat)) or draws.get(seat)`), then `seq` is popped; `trade` events gain `items` ONLY for the two parties; a `{"type":"trade_private","kind":"declined"|"cancelled"}` is appended for the two parties when `_trade_result` says so.
- Recorder wiring: `_record_draws(ev)` and `_drain_skips()` helpers. `_record_draws` + `_drain_skips` called in both the Shoot and the UseItem/Beer branches of `_emit_human_action` (Beer branch now captures `ev`); `_drain_skips()` also called after `_run_bots()` in `apply`/`flip`/`on_deadline` (chronological ordering + residual safety net; idempotent via `.clear()`).
- `_derive_extra_turn()`: `extra_turn = winner is None and any(elimination in last_events with actor == current_id)`; called before `_begin_phase_for_current` in `apply`/`flip`/`on_deadline`.
- `_trade_result`/`_last_trade_items` cleared at the top of `apply`/`flip`/`proceed`/`trade_offer` (after guards/validation so an illegal call cannot prematurely wipe a party's private note).

**`social_roulette/sim/turn.py`**
- `_rec_draws(rec, turn_idx, res)` helper; called after the main-loop Shoot, the UseItem/Beer `else` branch, and the fallback shot — so bot cascades emit `draw` rows (all of them, even when a beer-then-shoot produces two refills in one turn). Added a `last_skipped` drain block after the reload/bonus block so bot-induced skips are recorded. All new work is gated on `rec` → rec-less training/eval callers are unaffected.

**Tests**
- `tests/test_room_privacy.py` (new, 3 tests): `test_view_carries_v2_fields`, `test_trade_event_public_strips_and_parties_enriched`, `test_no_foreign_hand_or_shell_order_in_any_view_or_events`. The no-leak test was strengthened beyond the brief's t=0 snapshot: it drives the whole match to completion via deadline auto-shoots and re-sweeps `view`+`events_for` for all 5 seats after every step (genuinely exercising real reloads → draw enrichment and eliminations), and asserts each seat's `draw` event carries only `{type, you}` — never a foreign seat's refill.
- `tests/test_room_phases.py`: re-enabled the commented `assert r.view(seat)["bonus"] is True`.
- `tests/test_online_events.py`: added `"seq"` to the allowed public-field set with a note (it is a public recorder row index popped by `events_for` before any client sees it; `events_for` is the T11 broadcast path).

## Tested + results
`./.venv/Scripts/python -m pytest -q` → **227 passed** (baseline 224 + 3 new).

## TDD Evidence
- **RED**: `pytest tests/test_room_privacy.py tests/test_room_phases.py::test_self_blank_bonus_goes_straight_to_decision` → 4 failed: `AttributeError: 'Room' object has no attribute 'events_for'`, `KeyError: 'bonus'`, and the two other privacy tests failing on the missing `events_for`/`view` fields.
- **GREEN**: after implementation, `pytest tests/test_room_privacy.py tests/test_room_phases.py` → 9 passed; full suite → 227 passed.

## Files changed
- `social_roulette/online/room.py`
- `social_roulette/sim/turn.py`
- `tests/test_room_privacy.py` (new)
- `tests/test_room_phases.py`
- `tests/test_online_events.py`

## Self-review
- **Completeness**: all 10+ view fields present; enrichment works both directions (draw → own refill; trade → parties' items + private note); no privacy leak — `events_for` copies rows and only ever inserts THAT seat's draw; the no-leak sweep runs across a full match, not just t=0.
- **Quality**: brief-mandated `seq` correlation key is minimal and public-safe; helpers keep `_emit_human_action`/`take_policy_turn` readable; no double-recording of skips (each drain `.clear()`s).
- **YAGNI**: no extra fields or endpoints beyond the contract; server.py untouched (T11 owns broadcasting/roster).
- **TDD**: RED captured before implementation, GREEN after.
- **Pristine output**: 227 passed, no warnings of substance (only a benign LF→CRLF git notice on turn.py).

## Concerns
- One out-of-plan test edit was required: `tests/test_online_events.py` asserts the raw `last_events` key set, which the brief-mandated `seq` field on draw events necessarily expands. Added `"seq"` to its allowed set (it is popped by `events_for` before reaching a client, so no client-facing leak). Flagged because the task brief did not anticipate this existing test.
- Bot-path `draw` rows are recorded at each shoot/beer step (per brief), so a draw row can precede the end-of-turn `reload` row in a bot's cascade — a minor animation-ordering nuance, chosen because it faithfully captures every refill (including multi-refill turns). The human path records reload-then-draw.

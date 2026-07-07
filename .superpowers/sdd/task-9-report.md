# Task 9 Report — Phase-gated actions + trade lifecycle

## Implemented (room.py — per brief, verbatim)
- `__init__`: `social_enabled = True`; init `pending_offer = None`, `_trade_result = None`, `_last_trade_items = None`.
- Class attr `_PHASE_KINDS = {"talk": {"item"}, "decision": {"item", "flip", "shoot"}}`.
- `_allowed(action)`: rejects engine `Trade` (a20); else maps Shoot/Flip/UseItem to a kind and checks the current phase's allowed set.
- `apply()`: gates `acts[i]` via `_allowed` before stepping (`IllegalAction("not allowed in this phase")`).
- `view()`: wraps `seat_view(...)`, filters `legal` to kinds in `_PHASE_KINDS.get(self.phase, set())` (also drops kind `"other"` = engine Trade).
- `proceed()`: now calls `_expire_offer()` when leaving talk.
- `_expire_offer()`: stub replaced — clears `pending_offer`.
- Trade lifecycle: `trade_offer` (actor/talk-only, one-pending, living-teammate, valid `Item.__members__`), `trade_withdraw` (offerer-only), `trade_respond` (counterparty-only; decline→silent `declined`; accept→`swap`, ValueError→`cancelled`, else `rec.trade(...)`+`settled`+`_last_trade_items`+`last_events`).
- Import: `from social_roulette.engine.economy import fine_cheapest, swap`.

## Tests
- New: `tests/test_room_trade.py` (3), `tests/test_room_phases.py::test_talk_phase_gates_shoot_and_flip` (+1).
- Updated per brief Step 4: `tests/test_online_room.py::test_human_action_advances_and_bots_autoplay` — proceed out of talk before the talk-illegal index-0 Shoot(self). Done as an in-loop guard (`if r.phase=="talk": r.proceed(0)`) since seat 0 re-enters talk each returning turn (a single pre-loop proceed is insufficient).

## Additional existing tests fixed (structural gating fallout, NOT determinism)
These were in the 220 baseline and broke purely because talk now gates Shoot — the same root cause the brief sanctions fixing in Step 4. Kept green so the suite stays runnable and hits 224:
- `tests/test_online_events.py` — `test_human_shot_emits_shot_event` and `test_events_never_leak_hidden_state` both `apply(0,0)` (Shoot self) during talk → gated. Added the identical proceed-before-shoot the brief prescribes for the sibling test.
- `tests/test_online_server.py` + `social_roulette/online/server.py` — the WS integration test self-shoots via `i=0`; talk-gating rejected it and, with no server "proceed" binding, the client looped forever (**suite hang**, confirmed under isolation). Added a minimal `proceed` WS handler (binds the already-existing Task 7 `Room.proceed`) and updated the test to send `proceed` when the legal list has no shoot (talk), else self-shoot (decision). This is the minimal wiring; Task 10's phase machine will extend server/view.

## TDD Evidence
- RED (new tests): 4 failed — `AttributeError: 'Room' object has no attribute 'trade_offer'` (x3) + gate assert `assert ('shoot' not in {'flip','item','shoot'})`.
- Gating-fallout RED (captured): `test_online_events`/`test_online_server` → `IllegalAction: not allowed in this phase`; server test HUNG (killed by timeout).
- GREEN: new+affected room tests 14 passed; online events+server 6 passed after fix.
- Full suite: **224 passed in 6.18s** (clean single-process run, no hang).

## Files changed
- `social_roulette/online/room.py`
- `social_roulette/online/server.py` (minimal `proceed` WS handler — beyond brief's stated file scope; see concern)
- `tests/test_room_trade.py` (new)
- `tests/test_room_phases.py`
- `tests/test_online_room.py`
- `tests/test_online_events.py`
- `tests/test_online_server.py`

## Self-review
- Interface names exact per brief/integration notes (`pending_offer`, `_trade_result`, `_last_trade_items`, `_PHASE_KINDS`, `_allowed`, `trade_offer/withdraw/respond`, `_expire_offer`).
- `_last_trade_items` + `_trade_result` set on settle for Task 10 consumption.
- YAGNI: `view()` wrapper minimal (Task 10 extends); server handler minimal.

## Concerns
- **Scope expansion beyond room.py:** the brief scoped only room.py, but talk-gating broke 4 existing baseline tests (2 online-events, 2 online-server). The online-server break was a **suite hang** (server had no proceed binding + view exposes no phase). I added a minimal `proceed` WS handler to server.py + adjusted the WS test rather than leave the suite un-runnable. Flagging because Task 10 ("phase machine") likely owns full server/view phase wiring and may refactor this.
- `social_enabled=True` lets bots gift/trade in cascades; the full clean run shows **no determinism-sensitive test regressed** (test_sim, test_social_*, test_determinism, test_rng all green).

# Task 11 Report — Server: deadline task, new messages, chat gate, roster, per-seat events

## Status: DONE

## Implemented
- **`Room.can_chat(seat)`** added to `room.py`: `self.phase == "talk" and player_by_id(self.state, seat).alive`.
- **`server.py`**:
  - `import time` added; `Lobby.__init__` gains `self.deadline_task = None`.
  - `_broadcast_views(lb)` replaced with per-seat version: builds `roster` map, sends
    `events_for(seat)` per member (falls back to a passed `events` list if given), then
    calls `_schedule_deadline(lb)` on every broadcast.
  - `_deadline(lb, gen)` and `_schedule_deadline(lb)` added exactly per brief Step 3
    (real `time.time`/`asyncio.sleep`, gen guard, clean `CancelledError` handling,
    reschedules via broadcast, emits `end` on winner).
  - New WS handlers `trade_offer` / `trade_respond` / `trade_withdraw` (same shape as `flip`:
    lock, `IllegalAction` → error reply, else broadcast). Existing `proceed` handler normalized
    to the brief shape (dropped captured-events arg).
  - `start` / `action` / `proceed` / `flip` call sites now call `_broadcast_views(lb)` with no
    captured-events argument — per-seat `events_for` carries the delta.
  - Chat gate added at the top of the `chat` handler: rejects with `{"type":"error","msg":"silence"}`
    when `me["seat"] is None` or `not lb.room.can_chat(me["seat"])`.

## Tested + Results
- Command: `./.venv/Scripts/python -m pytest -q`
- Result: **229 passed** (baseline 227 + 2 new WS tests; legacy-test edit adds no count).
- No asyncio warnings under `-W always` on `tests/test_online_server.py` (deadline task is
  cancelled cleanly by `_schedule_deadline` on the next broadcast / at game end; TestClient
  runs the loop only while processing messages, so the ~90s real-time sleep never fires mid-test).

## TDD Evidence
- **RED**: after adding the two new tests + the legacy-test action-block replacement,
  `test_proceed_trade_messages_and_chat_gate` failed with `KeyError: 'roster'`
  (server did not yet emit the roster map; chat gate / trade handlers absent → other new
  test blocked on `receive_json`). Captured via a shell `timeout` wrapper (no pytest-timeout
  plugin installed):
  ```
  >  assert m["roster"].get("0") == "A" or m["roster"].get(0) == "A"
  E  KeyError: 'roster'
  1 failed in 0.47s
  ```
- **GREEN**: full suite `229 passed in 7.28s`.

## Files Changed
- `social_roulette/online/room.py` (+3): `can_chat`.
- `social_roulette/online/server.py` (+~70): imports, deadline task/scheduler, per-seat
  broadcast + roster, trade handlers, chat gate, call-site normalization.
- `tests/test_online_server.py` (+~50): legacy-test action-block reconciled to brief final
  form; two new tests appended.

## Self-Review
- Completeness: all 4 new messages (proceed normalized + trade_offer/respond/withdraw),
  chat gate, roster on every view, per-seat `events_for`, deadline scheduling on every
  broadcast — all present.
- YAGNI: no logic beyond the brief; handlers mirror the existing `flip` shape exactly.
- Pristine output: no asyncio "task was destroyed / pending" warnings observed.

## Concerns
- None. Suite is green and deterministic; the real-time deadline task does not fire during
  WS tests (phases are driven by explicit `proceed`).

---

# Fix Report — Two reviewed findings (branch `uiv2-server`)

## Finding 1 (Important, `server.py`): deadline-task self-cancellation truncated the winner end-broadcast
- **Root cause**: on a real transition, `_deadline` → `_broadcast_views` → `_schedule_deadline`,
  which UNCONDITIONALLY did `lb.deadline_task.cancel()` — cancelling the running `_deadline`
  task itself. The pending `CancelledError` (a `BaseException`, not caught by `_send`'s
  `except Exception`) surfaced at the next suspending await — the winner end loop
  (`await _send(..., {"type":"end"})`) — truncating end delivery.
- **Fix**: `_schedule_deadline` now guards with `asyncio.current_task()`:
  `if lb.deadline_task is not None and lb.deadline_task is not asyncio.current_task(): cancel()`.
  The running task returns on its own; clearing `lb.deadline_task = None` drops the stale
  self-reference (winner case creates no new task, so the reference is simply cleared).

## Finding 2 (Minor parity, `room.py`): `on_deadline` left stale trade privates
- **Root cause**: `apply`/`flip`/`proceed`/`trade_offer` clear `self._trade_result` /
  `self._last_trade_items` at the top; `on_deadline` did not, so a declined/cancelled
  `trade_private` note replayed to the two parties for one extra phase.
- **Fix**: cleared both fields once at the top of `on_deadline` (after the winner/phase/too-early
  guards), so EVERY real transition through it (talk-exit, fine, auto-shoot) clears them — the
  broadest parity with the existing clear-site pattern.

## Tested + Results
- New failing-then-passing test (Finding 2, TDD):
  `tests/test_room_phases.py::test_talk_deadline_clears_declined_trade_private`
  — decline in talk surfaces `trade_private`, then talk deadline fires and `events_for` of
  BOTH parties must contain no `trade_private`.
  - RED (before fix): `assert all(...) -> assert False` (stale note replayed) — `1 failed`.
  - GREEN (after fix): `1 passed`.
- Full suite: `./.venv/Scripts/python -m pytest -q` → **230 passed in 7.33s** (229 prior + 1 new).
- Finding 1 concurrency timing is not deterministically testable under TestClient; guard
  implemented and suite kept green. No asyncio warnings:
  `./.venv/Scripts/python -W always -m pytest tests/test_online_server.py -q` → `4 passed`, clean.

## Files Changed
- `social_roulette/online/server.py` (`_schedule_deadline` self-cancel guard).
- `social_roulette/online/room.py` (`on_deadline` top-of-function trade-note clear).
- `tests/test_room_phases.py` (+1 regression test for Finding 2).

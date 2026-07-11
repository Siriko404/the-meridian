"""Hold-on-drop (spec 2026-07-11 §4, supersedes ui-v2 D11 for drops): a dropped
human freezes the car exactly where it was; rejoin resumes with a 3s beat."""
import json

import pytest

from social_roulette.online.room import Room


def _mk(seed=7, n=5):
    now = [1000.0]
    r = Room(human_seats={0, 1}, seed=seed, num_players=n, now_fn=lambda: now[0])
    return r, now


def test_hold_freezes_remaining_exactly():
    r, now = _mk()
    now[0] += 12.5
    left = r.phase_ends_at - now[0]
    r.hold({1})
    assert r.phase_ends_at is None and r.held_remaining == pytest.approx(left)
    assert r.view(0)["hold"]["missing"] == [1]
    now[0] += 999                                    # time passes at the signal…
    assert r.on_deadline() is False                  # …and no clock bites
    r.release()
    assert r.phase_ends_at == pytest.approx(now[0] + 3.0 + left)   # 3·2·1 beat window
    assert "hold" not in r.view(0)


def test_hold_gen_unchanged_and_repeat_calls_noop():
    r, now = _mk()
    g = r.gen
    r.hold({1})
    first = r.held_since
    r.hold({0, 1})                                   # second dropper refreshes the list only
    assert r.held_since == first and r.view(0)["hold"]["missing"] == [0, 1]
    assert r.gen == g                                # a hold is NOT a game mutation
    r.release()
    r.release()                                      # idempotent
    assert r.gen == g


def test_hold_expiry_flag_rides_the_view():
    r, now = _mk()
    r.hold({1})
    r.hold_expired = True
    r.hold_chooser = 0
    h = r.view(0)["hold"]
    assert h["expired"] is True and h["chooser"] == 0
    assert h["deadline"] == pytest.approx(r.held_since + 300.0)


def test_snapshot_during_hold_keeps_frozen_clock():
    r, now = _mk()
    now[0] += 10
    left = r.phase_ends_at - now[0]
    r.hold({1})
    d = json.loads(json.dumps(r.to_dict()))
    now[0] += 5000                                   # server was down a long time
    r2 = Room.from_dict(d, now_fn=lambda: now[0])
    r2.hold({0, 1})                                  # boot restore re-holds explicitly
    r2.release()
    assert r2.phase_ends_at == pytest.approx(now[0] + 3.0 + left)   # frozen seconds kept


def test_release_after_bot_conversion_lets_play_continue():
    r, now = _mk()
    now[0] += 5
    r.hold({1})
    r.human.discard(1)                               # SEAT THE HOUSE on the dropped seat
    r.release()
    for _ in range(400):                             # play runs to a verdict via deadlines
        if r.winner is not None:
            break
        now[0] += 200
        r.on_deadline()
    assert r.winner is not None

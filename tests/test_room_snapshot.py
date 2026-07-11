"""Room.to_dict/from_dict (spec 2026-07-11 §4): a restored room must show every
seat the SAME view and evolve IDENTICALLY (rng continuity) — the session file's
last line is the whole game."""
import json

import pytest

from social_roulette.online.room import Room, IllegalAction


def _mk(seed=7, n=5):
    now = [1000.0]
    r = Room(human_seats={0}, seed=seed, num_players=n, now_fn=lambda: now[0])
    return r, now


def _views(r, n):
    out = []
    for s in range(n):
        v = json.loads(json.dumps(r.view(s), default=str))
        out.append(v)
    return out


def _roundtrip(r, now):
    d = json.loads(json.dumps(r.to_dict()))       # through REAL json — the file format
    return Room.from_dict(d, now_fn=lambda: now[0])


@pytest.mark.parametrize("n", [5, 8, 12])
def test_round_trip_views_identical(n):
    r, now = _mk(seed=11, n=n)
    for _ in range(4):                            # march the human through deadlines
        now[0] += 200
        if r.winner is None:
            r.on_deadline()
    r2 = _roundtrip(r, now)
    assert _views(r, n) == _views(r2, n)


def test_round_trip_future_evolution_identical():
    r, now = _mk(seed=3)
    for _ in range(3):
        now[0] += 200
        r.on_deadline()
    r2 = _roundtrip(r, now)
    for _ in range(6):                            # rng continuity: both futures identical
        now[0] += 200
        if r.winner is None:
            r.on_deadline()
        if r2.winner is None:
            r2.on_deadline()
        assert _views(r, 5) == _views(r2, 5)
    assert r.winner == r2.winner


def test_round_trip_carries_pending_specials_state():
    r, now = _mk(seed=5)
    # the human opens with DRAGNET (talk phase, their turn by rotation law)
    assert r.phase == "talk" and r.current == 0
    r.use_special(0, "DRAGNET", None)
    r2 = _roundtrip(r, now)
    assert r2.view(0).get("dragnet_report") == r.view(0).get("dragnet_report")
    assert r2.view(0)["your_specials"]["DRAGNET"] == 0


def test_round_trip_preserves_phase_clock():
    r, now = _mk(seed=9)
    left = r.phase_ends_at - now[0]
    r2 = _roundtrip(r, now)
    assert abs((r2.phase_ends_at - now[0]) - left) < 1e-6
    assert r2.phase == r.phase and r2.gen == r.gen


def test_restored_room_accepts_actions():
    r, now = _mk(seed=13)
    r2 = _roundtrip(r, now)
    r2.proceed(0)                                 # talk -> decision on the restored room
    assert r2.phase in ("decision", "tax")
    with pytest.raises(IllegalAction):
        r2.proceed(0)                             # and still enforces the law

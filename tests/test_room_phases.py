import pytest
from social_roulette.online.room import Room, IllegalAction


def clockroom(**kw):
    t = [1000.0]
    r = Room(human_seats={0, 1, 2, 3, 4}, seed=0, now_fn=lambda: t[0], **kw)
    return r, t


def test_fresh_turn_starts_talk_with_deadline():
    r, t = clockroom()
    assert r.phase == "talk"
    assert r.phase_ends_at is not None and r.phase_ends_at >= t[0] + Room.TALK_S


def test_proceed_moves_to_decision_actor_only():
    r, t = clockroom()
    seat = r.current
    with pytest.raises(IllegalAction):
        r.proceed((seat + 1) % 5)
    g0 = r.gen
    r.proceed(seat)
    assert r.phase == "decision" and r.gen > g0
    assert r.phase_ends_at == pytest.approx(t[0] + Room.DECISION_S)   # proceed adds NO grace
    with pytest.raises(IllegalAction):
        r.proceed(seat)                                   # already in decision


def test_self_blank_bonus_goes_straight_to_decision():
    r, t = clockroom()
    from social_roulette.engine.constants import Shell
    seat = r.current
    r.state.chamber.shells[r.state.chamber.pos] = Shell.BLANK
    r.proceed(seat)
    i = next(a["i"] for a in r.view(seat)["legal"] if a["kind"] == "shoot" and a["target"] == seat)
    r.apply(seat, i)
    assert r.current == seat and r.state.bonus_pending
    assert r.phase == "decision"
    # assert r.view(seat)["bonus"] is True   # re-enabled in Task 10

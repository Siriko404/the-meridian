import pytest
from social_roulette.online.room import Room, IllegalAction
from social_roulette.engine.state import player_by_id
from social_roulette.engine.constants import Item


def clockroom():
    t = [1000.0]
    return Room(human_seats={0, 1, 2, 3, 4}, seed=0, now_fn=lambda: t[0]), t


def _teammate(r, seat):
    me = player_by_id(r.state, seat)
    return next(p.id for p in r.state.players
                if p.id != seat and p.alive and p.team == me.team)


def test_offer_accept_settles_swap():
    r, t = clockroom()
    seat = r.current
    mate = _teammate(r, seat)
    player_by_id(r.state, seat).inventory = {Item.BEER: 1}
    player_by_id(r.state, mate).inventory = {Item.SAW: 1}
    r.trade_offer(seat, mate, ["BEER"], ["SAW"])
    assert r.pending_offer["from"] == seat
    r.trade_respond(mate, True)
    assert player_by_id(r.state, seat).inventory == {Item.SAW: 1}
    assert player_by_id(r.state, mate).inventory == {Item.BEER: 1}
    assert r.pending_offer is None


def test_bluffed_offer_cancels_with_no_movement():
    r, t = clockroom()
    seat = r.current
    mate = _teammate(r, seat)
    player_by_id(r.state, seat).inventory = {}
    player_by_id(r.state, mate).inventory = {Item.SAW: 1}
    r.trade_offer(seat, mate, ["BEER"], ["SAW"])       # bluff: no beer owned
    r.trade_respond(mate, True)
    assert player_by_id(r.state, mate).inventory == {Item.SAW: 1}
    assert r.pending_offer is None


def test_offer_gates_and_lifecycle():
    r, t = clockroom()
    seat = r.current
    mate = _teammate(r, seat)
    enemy = next(p.id for p in r.state.players
                 if p.alive and p.team != player_by_id(r.state, seat).team)
    with pytest.raises(IllegalAction):
        r.trade_offer(seat, enemy, ["BEER"], [])       # not a teammate
    r.trade_offer(seat, mate, ["BEER"], [])
    with pytest.raises(IllegalAction):
        r.trade_offer(seat, mate, ["SAW"], [])         # one pending max
    r.trade_withdraw(seat)
    assert r.pending_offer is None
    r.trade_offer(seat, mate, ["BEER"], [])
    r.proceed(seat)                                    # talk ends -> offer expires
    assert r.pending_offer is None
    with pytest.raises(IllegalAction):
        r.trade_offer(seat, mate, ["BEER"], [])        # decision phase: no offers

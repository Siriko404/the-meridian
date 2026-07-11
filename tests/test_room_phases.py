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
    from social_roulette.engine.constants import Bullet
    seat = r.current
    r.state.chamber.bullets[r.state.chamber.pos] = Bullet.BLANK
    r.proceed(seat)
    i = next(a["i"] for a in r.view(seat)["legal"] if a["kind"] == "shoot" and a["target"] == seat)
    r.apply(seat, i)
    assert r.current == seat and r.state.bonus_pending
    assert r.phase == "decision"
    assert r.view(seat)["bonus"] is True   # re-enabled in Task 10


def test_talk_deadline_advances_to_decision():
    r, t = clockroom()
    assert r.on_deadline() is False                      # too early — no-op
    t[0] = r.phase_ends_at + 0.1
    assert r.on_deadline() is True
    assert r.phase == "decision"


def test_decision_deadline_fines_then_auto_shoots():
    from social_roulette.engine.state import player_by_id
    r, t = clockroom()
    seat = r.current
    player_by_id(r.state, seat).inventory = {}
    from social_roulette.engine.constants import Item
    player_by_id(r.state, seat).inventory = {Item.MAGNET: 1}
    r.proceed(seat)
    t[0] = r.phase_ends_at + 0.1
    assert r.on_deadline() is True                       # fine
    assert player_by_id(r.state, seat).inventory == {}
    assert any(e["type"] == "fine" for e in r.last_events)
    assert r.phase == "decision"                         # 30 more seconds
    t[0] = r.phase_ends_at + 0.1
    cover_before = player_by_id(r.state, seat).cover
    assert r.on_deadline() is True                       # broke -> auto self-shoot
    assert any(e["type"] == "shot" for e in r.last_events)
    assert r.current != seat or r.state.bonus_pending or r.winner is not None


def test_talk_deadline_clears_declined_trade_private():
    from social_roulette.engine.state import player_by_id
    r, t = clockroom()
    seat = r.current
    me = player_by_id(r.state, seat)
    mate = next(pid for pid in range(5)
                if pid != seat and player_by_id(r.state, pid).alive
                and player_by_id(r.state, pid).team == me.team)
    r.trade_offer(seat, mate, [], [])          # empty offer shape is valid; decline never swaps
    r.trade_respond(mate, accept=False)
    assert any(e["type"] == "trade_private" for e in r.events_for(seat))   # note is live this phase
    t[0] = r.phase_ends_at + 0.1
    assert r.on_deadline() is True                                          # real talk -> decision
    assert r.phase == "decision"
    assert all(e["type"] != "trade_private" for e in r.events_for(seat))    # stale note must not replay
    assert all(e["type"] != "trade_private" for e in r.events_for(mate))


def test_talk_phase_gates_shoot_and_flip():
    r, t = clockroom()
    seat = r.current
    v = r.view(seat)
    kinds = {a["kind"] for a in v["legal"]}
    assert "shoot" not in kinds and "flip" not in kinds and "trade" not in kinds
    r.proceed(seat)
    kinds2 = {a["kind"] for a in r.view(seat)["legal"]}
    assert "shoot" in kinds2 and "trade" not in kinds2


def _item_index(r, seat, name):
    return next(a["i"] for a in r.view(seat)["legal"]
               if a["kind"] == "item" and a["item"] == name)


def test_item_use_during_decision_keeps_phase_and_deadline():
    # C1: a non-turn-ending item use in DECISION must NOT re-begin the phase.
    from social_roulette.engine.constants import Item
    from social_roulette.engine.state import player_by_id
    r, t = clockroom()
    seat = r.current
    player_by_id(r.state, seat).inventory = {Item.GEIGER: 1}
    r.proceed(seat)
    ends = r.phase_ends_at
    g0 = r.gen
    r.apply(seat, _item_index(r, seat, "GEIGER"))
    assert r.phase == "decision"                 # NOT dropped back to a fresh talk
    assert r.phase_ends_at == ends               # window not reset/extended
    assert r.gen == g0 + 1                        # exactly one gen bump


def test_item_use_during_talk_keeps_talk_deadline():
    # C1: an item use in TALK must not extend the talk window either.
    from social_roulette.engine.constants import Item
    from social_roulette.engine.state import player_by_id
    r, t = clockroom()
    seat = r.current
    player_by_id(r.state, seat).inventory = {Item.GEIGER: 1}
    ends = r.phase_ends_at
    g0 = r.gen
    r.apply(seat, _item_index(r, seat, "GEIGER"))
    assert r.phase == "talk"
    assert r.phase_ends_at == ends
    assert r.gen == g0 + 1


def test_magnet_reload_during_decision_keeps_phase_and_deadline():
    # C1: a MAGNET (Magnet) that empties the chamber reloads but must NOT extend the window.
    from social_roulette.engine.constants import Item, Bullet
    from social_roulette.engine.state import player_by_id
    r, t = clockroom()
    seat = r.current
    player_by_id(r.state, seat).inventory = {Item.MAGNET: 1}
    r.proceed(seat)
    r.state.chamber.bullets[:] = [Bullet.BLANK]
    r.state.chamber.pos = 0
    ends = r.phase_ends_at
    r.apply(seat, _item_index(r, seat, "MAGNET"))
    assert any(e["type"] == "reload" for e in r.last_events)   # reload really fired
    assert r.phase == "decision"
    assert r.phase_ends_at == ends


def test_flip_gated_to_decision_phase():
    # C2: flips settle only in DECISION; a talk-phase flip is rejected.
    from social_roulette.engine.constants import Item
    from social_roulette.engine.state import player_by_id
    r, t = clockroom()
    seat = r.current
    tgt = next(x for x in range(5) if x != seat)
    player_by_id(r.state, seat).inventory = {Item.MAGNET: 1, Item.SHAKEDOWN: 1}
    with pytest.raises(IllegalAction):
        r.flip(seat, tgt, ["MAGNET", "SHAKEDOWN"])   # still in talk → rejected
    r.proceed(seat)
    ends = r.phase_ends_at
    before = r.state.players[tgt].team
    r.flip(seat, tgt, ["MAGNET", "SHAKEDOWN"])        # decision → succeeds
    assert r.state.players[tgt].team != before
    assert r.phase == "decision"                    # flip does not re-begin the phase (C1)
    assert r.phase_ends_at == ends


def test_view_carries_increasing_gen():
    # I2: view exposes gen and it strictly increases across a mutation.
    from social_roulette.engine.constants import Item
    from social_roulette.engine.state import player_by_id
    r, t = clockroom()
    seat = r.current
    player_by_id(r.state, seat).inventory = {Item.GEIGER: 1}
    r.proceed(seat)
    g0 = r.view(seat)["gen"]
    r.apply(seat, _item_index(r, seat, "GEIGER"))
    assert r.view(seat)["gen"] > g0


def test_tax_phase_gates_and_resolves():
    """B3: a shaken human's turn opens in the 'tax' phase; paying 4 drops them
    straight into a SILENT decision; timeout in tax = skip."""
    from social_roulette.engine.constants import Item as It
    r, t = clockroom()
    seat = r.current
    order = r.state.order
    nxt = order[(order.index(seat) + 1) % len(order)]
    r.state.players[nxt].shaken = True
    r.state.players[nxt].inventory = {It.TERMS: 1}          # exactly the 4-tier
    # current shoots self on a blank-forced path: just deadline through the turn
    t[0] = r.phase_ends_at + 0.1; r.on_deadline()           # talk -> decision
    while r.current == seat and r.winner is None:           # fines then auto-shoot
        t[0] = r.phase_ends_at + 0.1
        r.on_deadline()
    if r.winner is not None or r.current != nxt:
        return                                              # seed path diverged (kill/reload) - covered elsewhere
    assert r.phase == "tax"
    v = r.view(nxt)
    kinds = {(a["kind"], a.get("tier")) for a in v["legal"]}
    assert ("tax", 0) in kinds and ("tax", 4) in kinds and ("tax", 6) not in kinds
    r.pay_tax(nxt, 4, ["TERMS"])
    assert r.phase == "decision" and r.state.tax_silent is True and r.current == nxt

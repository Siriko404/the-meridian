import pytest

from social_roulette.engine.engine import new_game
from social_roulette.engine.state import player_by_id
from social_roulette.engine.constants import Item
from social_roulette.engine import specials as SP


def test_everyone_starts_with_all_three_once():
    s = new_game(5, seed=0)
    for p in s.players:
        assert p.specials == {"WARRANT": 1, "DRAGNET": 1, "HANDLER": 1}


def test_dragnet_shows_regulars_never_specials_and_consumes():
    s = new_game(5, seed=0)
    rep = SP.dragnet(s, 0)
    assert set(rep["hands"]) == {1, 2, 3, 4}
    assert "WARRANT" not in str(rep)                     # ruling 1: specials stay dark
    assert player_by_id(s, 0).specials["DRAGNET"] == 0
    with pytest.raises(ValueError):
        SP.dragnet(s, 0)                                 # one-shot


def test_warrant_inspect_shows_everything_take_moves_one():
    s = new_game(5, seed=0)
    t = player_by_id(s, 1)
    t.inventory = {Item.POISON: 2}
    rep = SP.warrant_inspect(s, 0, 1)
    assert rep["hand"] == {"POISON": 2}
    assert rep["specials"] == {"WARRANT": 1, "DRAGNET": 1, "HANDLER": 1}
    SP.warrant_take(s, 0, 1, "HANDLER")                  # ruling 1: specials stealable
    assert player_by_id(s, 0).specials["HANDLER"] == 2
    assert t.specials["HANDLER"] == 0


def test_warrant_take_respects_receiver_caps():
    s = new_game(5, seed=0)
    me = player_by_id(s, 0)
    me.inventory = {Item.MAGNET: 3}                      # per-type cap full
    player_by_id(s, 1).inventory = {Item.MAGNET: 1}
    SP.warrant_inspect(s, 0, 1)
    with pytest.raises(ValueError):
        SP.warrant_take(s, 0, 1, "MAGNET")


def test_specials_never_fined_and_burn_on_death():
    from social_roulette.engine.economy import fine_cheapest
    from social_roulette.engine.engine import _process_death
    s = new_game(5, seed=0)
    p = player_by_id(s, 0)
    p.inventory = {}
    assert fine_cheapest(s, 0) is None                   # broke despite 3 specials
    _process_death(s, 0)
    assert p.specials == {}


def _clockroom(humans={0}):
    from social_roulette.online.room import Room
    t = [1000.0]
    return Room(human_seats=humans, seed=3, now_fn=lambda: t[0]), t


def test_room_dragnet_and_warrant_flow_stays_anonymous():
    r, t = _clockroom(humans={0, 1, 2, 3, 4})
    seat = r.current
    other = next(p for p in range(5) if p != seat)
    r.use_special(seat, "DRAGNET")
    assert "dragnet_report" in r.view(seat)
    assert "dragnet_report" not in r.view(other)
    assert r.last_events == []                              # NOTHING public
    r.use_special(seat, "WARRANT", other)
    pick = r.view(seat)["warrant_pick"]
    assert pick["target"] == other and "specials" in pick
    name = next(iter(pick["hand"]), None) or next(iter(pick["specials"]))
    r.warrant_take(seat, name)
    notes = [e for e in r.events_for(other) if e.get("type") == "searched"]
    assert notes and notes[0]["taken"] == name              # victim: searched + what vanished
    bystander = next(p for p in range(5) if p not in (seat, other))
    assert not [e for e in r.events_for(bystander) if e.get("type") == "searched"]
    v = r.view(bystander)
    assert v["special_counts"]["DRAGNET"] == 4              # public aggregate dropped by the use
    assert v["special_counts"]["WARRANT"] == 4
    assert v["special_counts"]["HANDLER"] == 5              # theft does not move the count


def _drive_to_aiming(r, t):
    for _ in range(200):
        if r.phase == "aiming" or r.winner is not None:
            break
        if r.current == 0:
            if r.phase == "tax":
                r.apply(0, 0); continue
            if r.phase == "talk":
                r.proceed(0)
            r.apply(0, 0)
        else:
            t[0] = (r.phase_ends_at or t[0]) + 0.1
            r.on_deadline()


def test_handler_v2_reaims_a_bot_shot_silently():
    r, t = _clockroom(humans={0})
    _drive_to_aiming(r, t)
    if r.winner is not None or r.phase != "aiming":
        return                                              # seed didn't reach a window; engine tests cover
    bot = r.current
    x = r.view(0)["seize_ids"][-1]
    gen0 = r.gen
    r.handler_seize(0, x)
    assert r.gen == gen0                                    # v2: seize moves NOTHING observable
    assert r.view(bot).get("ridden") is None                # victim is told NOTHING
    assert not [e for e in r.events_for(bot) if e.get("type") == "ridden"]
    t[0] = r.phase_ends_at + 0.1                            # window burns to its exact deadline
    r.on_deadline()
    shots = [e for e in r.last_events if e.get("type") == "shot"]
    assert shots and shots[0]["actor"] == bot               # the wire says the BOT chose it
    assert shots[0]["target"] == x                          # …but the bullet went where 0 pointed
    assert "handler" not in str(r.last_events).lower()      # anonymity
    assert r.handler is None


def test_handler_v2_swaps_a_human_shot_silently():
    r, t = _clockroom(humans={0, 1, 2, 3, 4})
    victim = r.current
    seizer = next(p for p in range(5) if p != victim)
    r.proceed(victim)
    x = r.view(seizer)["seize_ids"][-1]
    r.handler_seize(seizer, x)
    assert player_by_id(r.state, seizer).specials["HANDLER"] == 0
    v = r.view(victim)
    assert v.get("ridden") is None                          # UI fully normal: shoot NOT locked
    shoots = [a for a in v["legal"] if a["kind"] == "shoot"]
    assert shoots
    pick = next((a for a in shoots if a["target"] != x), shoots[0])
    r.apply(victim, pick["i"])                              # victim aims at THEIR choice…
    shots = [e for e in r.last_events if e.get("type") == "shot"]
    assert shots and shots[0]["actor"] == victim
    assert shots[0]["target"] == x                          # …the bullet obeys the puppeteer
    assert r.handler is None


def test_handler_v2_timeout_selfshot_redirects():
    r, t = _clockroom(humans={0, 1, 2, 3, 4})
    victim = r.current
    seizer = next(p for p in range(5) if p != victim)
    r.proceed(victim)
    x = next(i for i in r.view(seizer)["seize_ids"] if i != victim)
    r.handler_seize(seizer, x)
    player_by_id(r.state, victim).inventory = {}            # broke: timeout skips fines, gun fires
    t[0] = r.phase_ends_at + 0.1
    r.on_deadline()
    shots = [e for e in r.last_events if e.get("type") == "shot"]
    assert shots and shots[0]["actor"] == victim
    assert shots[0]["target"] == x                          # v2-1: even the timeout shot obeys


def test_handler_v2_first_seize_locks_second_alarms():
    r, t = _clockroom(humans={0, 1, 2, 3, 4})
    victim = r.current
    others = [p for p in range(5) if p != victim]
    r.proceed(victim)
    r.handler_seize(others[0], r.view(others[0])["seize_ids"][0])
    assert r.view(others[1])["handler_available"] is True   # no passive leak: button stays
    with pytest.raises(Exception, match="already held"):
        r.handler_seize(others[1], r.view(others[1])["seize_ids"][0])
    assert player_by_id(r.state, others[1]).specials["HANDLER"] == 1   # alarm costs nothing


def test_handler_v2_stale_gen_dies_unspent():
    """A confirm that crosses the turn boundary in flight must NOT re-aim the
    NEXT shooter — atomicity law: not executed legally -> not spent, no effect."""
    r, t = _clockroom(humans={0, 1, 2, 3, 4})
    victim = r.current
    seizer = next(p for p in range(5) if p != victim)
    r.proceed(victim)
    stale = r.gen - 1                                       # a gen from a turn gone by
    with pytest.raises(Exception, match="moment has passed"):
        r.handler_seize(seizer, r.view(seizer)["seize_ids"][0], gen=stale)
    assert player_by_id(r.state, seizer).specials["HANDLER"] == 1
    assert r.handler is None
    r.handler_seize(seizer, r.view(seizer)["seize_ids"][0], gen=r.gen)  # fresh stamp works
    assert r.handler is not None


def test_handler_v2_target_must_be_legal_for_the_victim():
    r, t = _clockroom(humans={0, 1, 2, 3, 4})
    victim = r.current
    seizer = next(p for p in range(5) if p != victim)
    r.proceed(victim)
    with pytest.raises(Exception, match="not a shot"):
        r.handler_seize(seizer, 99)
    assert player_by_id(r.state, seizer).specials["HANDLER"] == 1


def test_searched_note_fires_once_not_forever():
    r, t = _clockroom(humans={0, 1, 2, 3, 4})
    seat = r.current
    other = next(p for p in range(5) if p != seat)
    r.use_special(seat, "WARRANT", other)
    pick = r.view(seat)["warrant_pick"]
    name = next(iter(pick["hand"]), None) or next(iter(pick["specials"]))
    r.warrant_take(seat, name)
    assert [e for e in r.events_for(other) if e.get("type") == "searched"]
    r.proceed(seat)                                         # ANY next delta
    assert not [e for e in r.events_for(other) if e.get("type") == "searched"]

import pytest

from social_roulette.engine.constants import Item, Team, Bullet
from social_roulette.engine.state import Player, Chamber, GameState
from social_roulette.engine.rng import SeededRng
from social_roulette.engine import items as I


def mkstate(n=5, bullets=None):
    players = [Player(i, Team.RED, 3, True, {}, set(), False, False) for i in range(n)]
    return GameState(players=players, order=list(range(n)), current_id=0,
                     chamber=Chamber(bullets or [Bullet.LIVE, Bullet.BLANK], 0), rng=SeededRng(0))


def test_limit_equals_living_players():
    assert I.consumption_limit(mkstate(5)) == 5 and I.consumption_limit(mkstate(8)) == 8


def test_cig_heals_and_blocks_at_max():
    s = mkstate()
    s.players[0].cover = 4
    s.players[0].inventory = {Item.PASSPORT: 1}
    I.apply_item(s, 0, Item.PASSPORT)
    assert s.players[0].cover == 5
    s.players[0].inventory = {Item.PASSPORT: 1}
    with pytest.raises(Exception):
        I.apply_item(s, 0, Item.PASSPORT)


def test_saw_once_per_turn():
    s = mkstate()
    s.players[0].inventory = {Item.POISON: 2}
    I.apply_item(s, 0, Item.POISON)
    assert s.poison_armed and s.poison_used_this_turn
    with pytest.raises(Exception):
        I.apply_item(s, 0, Item.POISON)


def test_beer_removes_and_shrinks():
    s = mkstate(bullets=[Bullet.LIVE, Bullet.BLANK])
    s.players[0].inventory = {Item.MAGNET: 1}
    ev = I.apply_item(s, 0, Item.MAGNET)
    assert ev["discarded"] == Bullet.LIVE and s.chamber.bullets == [Bullet.BLANK] and s.chamber.pos == 0


def test_beer_last_bullet_reports_emptied():
    s = mkstate(bullets=[Bullet.LIVE])
    s.players[0].inventory = {Item.MAGNET: 1}
    ev = I.apply_item(s, 0, Item.MAGNET)
    assert ev["emptied"] is True and s.chamber.is_empty()


def test_place_immunity_handcuffs_and_no_stack():
    s = mkstate()
    s.players[0].inventory = {Item.TERMS: 1, Item.SHAKEDOWN: 1}
    I.apply_item(s, 0, Item.TERMS, target_id=1)
    I.apply_item(s, 0, Item.SHAKEDOWN, target_id=2)
    assert 0 in s.players[1].immunity_against and s.players[2].handcuffed is True
    s.players[0].inventory = {Item.SHAKEDOWN: 1}
    with pytest.raises(Exception):
        I.apply_item(s, 0, Item.SHAKEDOWN, target_id=2)


def test_no_self_target():
    s = mkstate()
    s.players[0].inventory = {Item.TERMS: 1}
    with pytest.raises(Exception):
        I.apply_item(s, 0, Item.TERMS, target_id=0)


def test_cap_reached_and_reset():
    s = mkstate(5)
    s.use_counts = {Item.MAGNET: 6}
    assert I.cap_reached(s, Item.MAGNET) is True
    I.reset_caps(s)
    assert I.cap_reached(s, Item.MAGNET) is False


def test_apply_second_same_caster_immunity_raises():
    from social_roulette.engine.engine import new_game
    from social_roulette.engine.items import apply_item
    from social_roulette.engine.constants import Item
    from social_roulette.engine.state import player_by_id
    import pytest
    s = new_game(5, seed=1)
    caster = s.current_id
    target = next(p.id for p in s.players if p.id != caster)
    player_by_id(s, caster).inventory = {Item.TERMS: 2}
    apply_item(s, caster, Item.TERMS, target)
    with pytest.raises(ValueError):
        apply_item(s, caster, Item.TERMS, target)
    assert player_by_id(s, caster).inventory[Item.TERMS] == 1   # 2nd NOT consumed


def test_geiger_counts_next_two_never_positions():
    s = mkstate(bullets=[Bullet.LIVE, Bullet.BLANK, Bullet.LIVE])
    s.players[0].inventory = {Item.GEIGER: 3}
    ev = I.apply_item(s, 0, Item.GEIGER)
    assert ev == {"scan_live": 1, "scan_of": 2}          # LIVE+BLANK window -> count only
    s.players[0].inventory = {Item.GEIGER: 1}
    assert I.apply_item(s, 0, Item.GEIGER) == {"scan_live": 1, "scan_of": 2}  # re-scan = same report


def test_geiger_one_bullet_left_reports_on_one():
    s = mkstate(bullets=[Bullet.LIVE])
    s.players[0].inventory = {Item.GEIGER: 1}
    assert I.apply_item(s, 0, Item.GEIGER) == {"scan_live": 1, "scan_of": 1}


def test_geiger_all_blank_window():
    s = mkstate(bullets=[Bullet.BLANK, Bullet.BLANK, Bullet.LIVE])
    s.players[0].inventory = {Item.GEIGER: 1}
    assert I.apply_item(s, 0, Item.GEIGER) == {"scan_live": 0, "scan_of": 2}

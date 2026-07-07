import pytest

from social_roulette.engine.constants import Item, Team, Shell
from social_roulette.engine.state import Player, Chamber, GameState
from social_roulette.engine.rng import SeededRng
from social_roulette.engine import items as I


def mkstate(n=5, shells=None):
    players = [Player(i, Team.RED, 3, True, {}, set(), False, False) for i in range(n)]
    return GameState(players=players, order=list(range(n)), current_id=0,
                     chamber=Chamber(shells or [Shell.LIVE, Shell.BLANK], 0), rng=SeededRng(0))


def test_limit_floor_1_3():
    assert I.consumption_limit(mkstate(5)) == 6 and I.consumption_limit(mkstate(8)) == 10


def test_cig_heals_and_blocks_at_max():
    s = mkstate()
    s.players[0].lives = 4
    s.players[0].inventory = {Item.CIGARETTES: 1}
    I.apply_item(s, 0, Item.CIGARETTES)
    assert s.players[0].lives == 5
    s.players[0].inventory = {Item.CIGARETTES: 1}
    with pytest.raises(Exception):
        I.apply_item(s, 0, Item.CIGARETTES)


def test_saw_once_per_turn():
    s = mkstate()
    s.players[0].inventory = {Item.SAW: 2}
    I.apply_item(s, 0, Item.SAW)
    assert s.saw_active and s.saw_used_this_turn
    with pytest.raises(Exception):
        I.apply_item(s, 0, Item.SAW)


def test_beer_removes_and_shrinks():
    s = mkstate(shells=[Shell.LIVE, Shell.BLANK])
    s.players[0].inventory = {Item.BEER: 1}
    ev = I.apply_item(s, 0, Item.BEER)
    assert ev["discarded"] == Shell.LIVE and s.chamber.shells == [Shell.BLANK] and s.chamber.pos == 0


def test_beer_last_shell_reports_emptied():
    s = mkstate(shells=[Shell.LIVE])
    s.players[0].inventory = {Item.BEER: 1}
    ev = I.apply_item(s, 0, Item.BEER)
    assert ev["emptied"] is True and s.chamber.is_empty()


def test_place_immunity_handcuffs_and_no_stack():
    s = mkstate()
    s.players[0].inventory = {Item.IMMUNITY: 1, Item.HANDCUFFS: 1}
    I.apply_item(s, 0, Item.IMMUNITY, target_id=1)
    I.apply_item(s, 0, Item.HANDCUFFS, target_id=2)
    assert 0 in s.players[1].immunity_against and s.players[2].handcuffed is True
    s.players[0].inventory = {Item.HANDCUFFS: 1}
    with pytest.raises(Exception):
        I.apply_item(s, 0, Item.HANDCUFFS, target_id=2)


def test_no_self_target():
    s = mkstate()
    s.players[0].inventory = {Item.IMMUNITY: 1}
    with pytest.raises(Exception):
        I.apply_item(s, 0, Item.IMMUNITY, target_id=0)


def test_cap_reached_and_reset():
    s = mkstate(5)
    s.use_counts = {Item.BEER: 6}
    assert I.cap_reached(s, Item.BEER) is True
    I.reset_caps(s)
    assert I.cap_reached(s, Item.BEER) is False


def test_apply_second_same_caster_immunity_raises():
    from social_roulette.engine.engine import new_game
    from social_roulette.engine.items import apply_item
    from social_roulette.engine.constants import Item
    from social_roulette.engine.state import player_by_id
    import pytest
    s = new_game(5, seed=1)
    caster = s.current_id
    target = next(p.id for p in s.players if p.id != caster)
    player_by_id(s, caster).inventory = {Item.IMMUNITY: 2}
    apply_item(s, caster, Item.IMMUNITY, target)
    with pytest.raises(ValueError):
        apply_item(s, caster, Item.IMMUNITY, target)
    assert player_by_id(s, caster).inventory[Item.IMMUNITY] == 1   # 2nd NOT consumed

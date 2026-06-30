import pytest

from social_roulette.engine.constants import Item, Team, Shell
from social_roulette.engine.state import Player, Chamber, GameState
from social_roulette.engine.rng import SeededRng
from social_roulette.engine.endgame import (legal_targets, teams_active, winner,
                                            next_living_after, assert_legal_shot)
from social_roulette.engine.actions import legal_actions, Shoot, UseItem, Flip, cheapest_payment


def mkstate(teams, **kw):
    players = [Player(i, teams[i], 3, True, {}, set(), False, False) for i in range(len(teams))]
    s = GameState(players=players, order=list(range(len(teams))), current_id=0,
                  chamber=Chamber([Shell.LIVE], 0), rng=SeededRng(0))
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def test_self_always_legal():
    s = mkstate([Team.RED] * 5)
    assert 0 in legal_targets(s, 0)


def test_teammates_excluded_when_teams_active():
    s = mkstate([Team.RED, Team.RED, Team.BLUE, Team.BLUE, Team.BLUE])
    assert 1 not in legal_targets(s, 0) and 2 in legal_targets(s, 0)


def test_immunity_blocks_target():
    s = mkstate([Team.RED, Team.BLUE, Team.BLUE])
    s.players[0].immunity_against = {1}
    assert 1 not in legal_targets(s, 0)


def test_teams_off_under_three():
    s = mkstate([Team.RED, Team.BLUE])
    assert teams_active(s) is False and 1 in legal_targets(s, 0)


def test_assert_legal_shot_raises():
    s = mkstate([Team.RED, Team.RED, Team.BLUE])
    with pytest.raises(Exception):
        assert_legal_shot(s, 0, 1)


def test_next_living_after_cyclic():
    assert next_living_after([0, 1, 2, 3], {0, 2, 3}, 1) == 2
    assert next_living_after([0, 1, 2, 3], {0}, 2) == 0


def test_cheapest_payment_minimizes():
    p = Player(0, Team.RED, 3, True, {Item.BEER: 1, Item.IMMUNITY: 1}, set(), False, False)
    assert cheapest_payment(p, 5) == [Item.IMMUNITY]


def test_legal_actions_includes_items_and_shoot():
    s = mkstate([Team.RED, Team.BLUE, Team.BLUE])
    s.players[0].inventory = {Item.SAW: 1, Item.BEER: 1}
    acts = legal_actions(s, 0)
    assert any(isinstance(a, Shoot) for a in acts)
    assert any(isinstance(a, UseItem) and a.item == Item.SAW for a in acts)

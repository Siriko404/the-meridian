import pytest

from social_roulette.engine.constants import Item, Team, Bullet
from social_roulette.engine.state import Player, Chamber, GameState
from social_roulette.engine.rng import SeededRng
from social_roulette.engine.endgame import (legal_targets, teams_active, winner,
                                            next_living_after, assert_legal_shot)
from social_roulette.engine.actions import legal_actions, Shoot, UseItem, Flip, cheapest_payment


def mkstate(teams, **kw):
    players = [Player(i, teams[i], 3, True, {}, set(), False, False) for i in range(len(teams))]
    s = GameState(players=players, order=list(range(len(teams))), current_id=0,
                  chamber=Chamber([Bullet.LIVE], 0), rng=SeededRng(0))
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
    p = Player(0, Team.RED, 3, True, {Item.MAGNET: 1, Item.TERMS: 1}, set(), False, False)
    assert cheapest_payment(p, 5) == [Item.TERMS]


def test_legal_actions_includes_items_and_shoot():
    s = mkstate([Team.RED, Team.BLUE, Team.BLUE])
    s.players[0].inventory = {Item.POISON: 1, Item.MAGNET: 1}
    acts = legal_actions(s, 0)
    assert any(isinstance(a, Shoot) for a in acts)
    assert any(isinstance(a, UseItem) and a.item == Item.POISON for a in acts)


def test_handcuffs_never_offered_on_teammates():
    # 2026-07-10: the sleep item may not target teammates while teams are active;
    # the can't-shoot-me token (TERMS) stays legal on them.
    s = mkstate([Team.RED, Team.RED, Team.BLUE, Team.BLUE, Team.BLUE])
    s.players[0].inventory = {Item.SHAKEDOWN: 1, Item.TERMS: 1}
    acts = legal_actions(s, 0)
    cuff = {a.target_id for a in acts if isinstance(a, UseItem) and a.item == Item.SHAKEDOWN}
    imm = {a.target_id for a in acts if isinstance(a, UseItem) and a.item == Item.TERMS}
    assert 1 not in cuff and cuff == {2, 3, 4}
    assert 1 in imm


def test_handcuffs_free_for_all_when_teams_off():
    s = mkstate([Team.RED, Team.RED])                # < 3 living: teams dissolved
    s.players[0].inventory = {Item.SHAKEDOWN: 1}
    acts = legal_actions(s, 0)
    cuff = {a.target_id for a in acts if isinstance(a, UseItem) and a.item == Item.SHAKEDOWN}
    assert cuff == {1}


def test_second_same_caster_immunity_not_offered():
    from social_roulette.engine.engine import new_game
    from social_roulette.engine.actions import legal_actions, UseItem
    from social_roulette.engine.constants import Item
    s = new_game(5, seed=1)
    caster = s.current_id
    target = next(p.id for p in s.players if p.id != caster)
    s.players[caster].inventory = {Item.TERMS: 2}
    from social_roulette.engine.state import player_by_id
    player_by_id(s, target).immunity_against.add(caster)
    offers = [a for a in legal_actions(s, caster)
              if isinstance(a, UseItem) and a.item == Item.TERMS and a.target_id == target]
    assert offers == []

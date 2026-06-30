import pytest

from social_roulette.engine.constants import Item, Team
from social_roulette.engine.state import Player, Chamber, GameState
from social_roulette.engine.rng import SeededRng
from social_roulette.engine.economy import pay_cost, flip_team


def mkstate():
    players = [Player(i, Team.RED if i % 2 else Team.BLUE, 3, True, {}, set(), False, False) for i in range(5)]
    return GameState(players=players, order=list(range(5)), current_id=0, chamber=Chamber([], 0), rng=SeededRng(0))


def test_pay_burns_overpay():
    s = mkstate()
    s.players[0].inventory = {Item.IMMUNITY: 1}
    pay_cost(s, 0, 5, [Item.IMMUNITY])
    assert s.players[0].inventory == {}


def test_pay_rejects_insufficient():
    s = mkstate()
    s.players[0].inventory = {Item.BEER: 1}
    with pytest.raises(Exception):
        pay_cost(s, 0, 5, [Item.BEER])


def test_flip_other_costs_5_toggles_grants_discount():
    s = mkstate()
    s.players[0].inventory = {Item.MAGNIFIER: 1}
    before = s.players[1].team
    flip_team(s, 0, 1, [Item.MAGNIFIER])
    assert s.players[1].team != before and s.players[1].flipback_discount is True


def test_flipback_costs_4_consumes_discount():
    s = mkstate()
    s.players[1].flipback_discount = True
    s.players[1].inventory = {Item.BEER: 1}
    flip_team(s, 1, 1, [Item.BEER])
    assert s.players[1].flipback_discount is False


def test_flip_own_no_discount_costs_5():
    s = mkstate()
    s.players[1].inventory = {Item.MAGNIFIER: 1}
    flip_team(s, 1, 1, [Item.MAGNIFIER])
    assert s.players[1].flipback_discount is False

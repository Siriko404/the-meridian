from social_roulette.engine.constants import Team, Bullet
from social_roulette.engine.state import Player, Chamber, GameState
from social_roulette.engine.rng import SeededRng
from social_roulette.engine.shooting import resolve_shot


def mkstate(bullets, **kw):
    players = [Player(i, Team.RED, 3, True, {}, set(), False, False) for i in range(2)]
    s = GameState(players=players, order=[0, 1], current_id=0, chamber=Chamber(bullets, 0), rng=SeededRng(0))
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def test_live_costs_one():
    s = mkstate([Bullet.LIVE])
    ev = resolve_shot(s, 0, 1)
    assert ev["damage"] == 1 and s.players[1].cover == 2 and s.chamber.pos == 1


def test_poison_ticks_survivor_and_clears():
    s = mkstate([Bullet.LIVE], poison_armed=True)
    ev = resolve_shot(s, 0, 1)
    assert ev["damage"] == 1 and ev["poisoned"] is True
    assert s.players[1].cover == 2 and s.players[1].poison_tick == 0
    assert s.poison_armed is False


def test_poison_wasted_on_blank():
    s = mkstate([Bullet.BLANK], poison_armed=True)
    ev = resolve_shot(s, 0, 1)
    assert ev["damage"] == 0 and ev["poisoned"] is False
    assert s.players[1].cover == 3 and s.poison_armed is False and s.players[1].poison_tick is None


def test_self_blank_sets_bonus():
    s = mkstate([Bullet.BLANK])
    resolve_shot(s, 0, 0)
    assert s.bonus_pending is True


def test_self_live_no_bonus_immunity_expires():
    s = mkstate([Bullet.LIVE])
    s.players[0].immunity_against = {1}
    resolve_shot(s, 0, 0)
    assert s.bonus_pending is False and s.players[0].immunity_against == set()


def test_kill_floored_no_tick_on_corpse():
    s = mkstate([Bullet.LIVE], poison_armed=True)
    s.players[1].cover = 1
    ev = resolve_shot(s, 0, 1)
    assert ev["killed"] is True and s.players[1].cover == 0
    assert ev["poisoned"] is False and s.players[1].poison_tick is None

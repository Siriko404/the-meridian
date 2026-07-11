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


def test_saw_doubles_and_clears():
    s = mkstate([Bullet.LIVE], saw_active=True)
    ev = resolve_shot(s, 0, 1)
    assert ev["damage"] == 2 and s.players[1].cover == 1 and s.saw_active is False


def test_saw_wasted_on_blank():
    s = mkstate([Bullet.BLANK], saw_active=True)
    ev = resolve_shot(s, 0, 1)
    assert ev["damage"] == 0 and s.players[1].cover == 3 and s.saw_active is False


def test_self_blank_sets_bonus():
    s = mkstate([Bullet.BLANK])
    resolve_shot(s, 0, 0)
    assert s.bonus_pending is True


def test_self_live_no_bonus_immunity_expires():
    s = mkstate([Bullet.LIVE])
    s.players[0].immunity_against = {1}
    resolve_shot(s, 0, 0)
    assert s.bonus_pending is False and s.players[0].immunity_against == set()


def test_kill_floored():
    s = mkstate([Bullet.LIVE], saw_active=True)
    s.players[1].cover = 1
    ev = resolve_shot(s, 0, 1)
    assert ev["killed"] is True and s.players[1].cover == 0

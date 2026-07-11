import pytest

from social_roulette.engine.constants import Team, Bullet, Item
from social_roulette.engine.state import Player, Chamber, GameState
from social_roulette.engine.rng import SeededRng
from social_roulette.engine.engine import take_shot

ENEMY5 = [Team.RED, Team.RED, Team.BLUE, Team.BLUE, Team.BLUE]  # 0 may legally shoot 2,3,4


def mk(n, bullets, teams=None, **kw):
    teams = teams or [Team.RED] * n
    players = [Player(i, teams[i], 3, True, {}, set(), False, False) for i in range(n)]
    s = GameState(players=players, order=list(range(n)), current_id=0,
                  chamber=Chamber(bullets, 0), rng=SeededRng(1))
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def test_blank_other_advances():
    s = mk(5, [Bullet.BLANK], teams=ENEMY5)
    take_shot(s, 0, 2)
    assert s.current_id == 1


def test_self_blank_keeps_turn_bonus():
    s = mk(5, [Bullet.BLANK, Bullet.LIVE])
    take_shot(s, 0, 0)
    assert s.current_id == 0 and s.bonus_pending is True


def test_kill_gives_killer_extra_turn():
    s = mk(5, [Bullet.LIVE], teams=[Team.RED, Team.BLUE, Team.RED, Team.RED, Team.RED])
    s.players[1].lives = 1
    take_shot(s, 0, 1)
    assert s.players[1].alive is False and s.current_id == 0 and 1 not in s.order


def test_self_kill_with_saw_no_crash_no_extra_turn():
    s = mk(5, [Bullet.LIVE], saw_active=True)
    s.players[0].lives = 2
    take_shot(s, 0, 0)
    assert s.players[0].alive is False and 0 not in s.order and s.current_id == 1


def test_emptied_triggers_reload():
    s = mk(5, [Bullet.LIVE], teams=ENEMY5)
    take_shot(s, 0, 2)
    assert len(s.chamber.bullets) > 0 and s.chamber.pos == 0


def test_emptied_plus_bonus_reloads_and_keeps_player():
    s = mk(5, [Bullet.BLANK])
    take_shot(s, 0, 0)
    assert s.current_id == 0 and s.bonus_pending is True and len(s.chamber.bullets) > 0


def test_kill_and_emptied_draws_items():
    s = mk(5, [Bullet.LIVE], teams=[Team.RED, Team.BLUE, Team.RED, Team.RED, Team.RED])
    s.players[1].lives = 1
    before = sum(sum(p.inventory.values()) for p in s.players)
    take_shot(s, 0, 1)
    assert sum(sum(p.inventory.values()) for p in s.players) >= before and s.chamber.pos == 0


def test_handcuff_skipped_on_advance():
    s = mk(5, [Bullet.BLANK], teams=ENEMY5)
    s.players[1].handcuffed = True
    take_shot(s, 0, 2)
    assert s.current_id == 2 and s.players[1].handcuffed is False


def test_illegal_shot_raises():
    s = mk(3, [Bullet.LIVE], teams=[Team.RED, Team.RED, Team.BLUE])
    with pytest.raises(Exception):
        take_shot(s, 0, 1)


def test_winner_set_on_last_kill():
    s = mk(2, [Bullet.LIVE], teams=[Team.RED, Team.BLUE])
    s.players[1].lives = 1
    take_shot(s, 0, 1)
    assert s.winner == 0

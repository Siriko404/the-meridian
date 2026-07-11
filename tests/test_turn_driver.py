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
    s.players[1].cover = 1
    take_shot(s, 0, 1)
    assert s.players[1].alive is False and s.current_id == 0 and 1 not in s.order


def test_self_kill_with_poison_no_crash_no_extra_turn():
    s = mk(5, [Bullet.LIVE], poison_armed=True)
    s.players[0].cover = 1
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
    s.players[1].cover = 1
    before = sum(sum(p.inventory.values()) for p in s.players)
    take_shot(s, 0, 1)
    assert sum(sum(p.inventory.values()) for p in s.players) >= before and s.chamber.pos == 0


def test_shaken_player_holds_turn_taxed_and_can_skip():
    """B3: a shaken seat is no longer auto-skipped — their turn STARTS taxed;
    tier 0 (no pay) then skips them onward."""
    from social_roulette.engine.engine import step
    from social_roulette.engine.actions import PayTax, legal_actions
    s = mk(5, [Bullet.BLANK, Bullet.BLANK], teams=ENEMY5)
    s.players[1].shaken = True
    take_shot(s, 0, 2)
    assert s.current_id == 1 and s.players[1].shaken is False and s.tax_pending is True
    acts = legal_actions(s, 1)
    assert all(isinstance(a, PayTax) for a in acts)          # the tax gates everything
    step(s, 1, PayTax(0))
    assert s.current_id == 2 and s.tax_pending is False and 1 in s.last_skipped


def test_illegal_shot_raises():
    s = mk(3, [Bullet.LIVE], teams=[Team.RED, Team.RED, Team.BLUE])
    with pytest.raises(Exception):
        take_shot(s, 0, 1)


def test_winner_set_on_last_kill():
    s = mk(2, [Bullet.LIVE], teams=[Team.RED, Team.BLUE])
    s.players[1].cover = 1
    take_shot(s, 0, 1)
    assert s.winner == 0


def test_self_poison_tick_at_own_turn_start_passes_turn_on():
    """A self-poisoned player whose tick kills them the moment their turn starts
    must NOT stay current (corpse-turn bug, B2): the turn passes to the next living."""
    from social_roulette.engine.engine import _set_turn_to
    s = mk(5, [Bullet.BLANK] * 3)
    s.players[2].cover = 1
    s.players[2].poison_tick = 2          # self-poisoned earlier
    _set_turn_to(s, 2)
    assert s.players[2].alive is False
    from social_roulette.engine.state import player_by_id as _pbi
    assert s.current_id != 2 and _pbi(s, s.current_id).alive
    assert (2, 2, True) in s.last_ticks


def test_tax_pay_tiers_and_overpay_burn():
    from social_roulette.engine.engine import step
    from social_roulette.engine.actions import PayTax
    from social_roulette.engine.constants import Item
    from social_roulette.engine.state import player_by_id as pbi
    # pay 6 -> full turn (talk rights); overpay burns (9 pts for a 6 tax)
    s = mk(5, [Bullet.BLANK, Bullet.BLANK], teams=ENEMY5)
    s.players[1].shaken = True
    s.players[1].inventory = {Item.GEIGER: 1, Item.MAGNET: 1}     # 5 + 4 = 9
    take_shot(s, 0, 2)
    step(s, 1, PayTax(6, [Item.GEIGER, Item.MAGNET]))
    p = pbi(s, 1)
    assert s.current_id == 1 and s.tax_pending is False and s.tax_silent is False
    assert p.inventory == {}                                       # no refunds
    # pay 4 -> SILENT turn
    s = mk(5, [Bullet.BLANK, Bullet.BLANK], teams=ENEMY5)
    s.players[1].shaken = True
    s.players[1].inventory = {Item.TERMS: 1}                       # exactly 4
    take_shot(s, 0, 2)
    step(s, 1, PayTax(4, [Item.TERMS]))
    assert s.current_id == 1 and s.tax_silent is True

from social_roulette.engine.engine import new_game, step
from social_roulette.engine.actions import legal_actions, Trade, Shoot
from social_roulette.engine.constants import Item, Bullet, POINT_VALUE, MAX_PER_TYPE
from social_roulette.engine.state import player_by_id


def _mate_and_enemy(g, pid=0):
    me = player_by_id(g, pid)
    mate = next(p.id for p in g.players if p.id != pid and p.team == me.team)
    enemy = next(p.id for p in g.players if p.team != me.team)
    return mate, enemy


def test_gift_transfers_and_records_help():
    g = new_game(5, 0)
    g.social_enabled = True
    g.current_id = 0
    mate, enemy = _mate_and_enemy(g, 0)
    g.players[0].inventory = {Item.MAGNET: 1}
    player_by_id(g, mate).inventory = {}
    acts = legal_actions(g, 0)
    assert any(isinstance(a, Trade) and a.to_id == mate and a.items == [Item.MAGNET] for a in acts)
    assert not any(isinstance(a, Trade) and a.to_id == enemy for a in acts)   # teammate-only
    step(g, 0, Trade(mate, [Item.MAGNET]))
    assert g.players[0].inventory.get(Item.MAGNET, 0) == 0
    assert player_by_id(g, mate).inventory.get(Item.MAGNET, 0) == 1
    assert g.help[(mate, 0)] == POINT_VALUE[Item.MAGNET]


def test_gift_blocked_when_receiver_at_cap():
    g = new_game(5, 0)
    g.social_enabled = True
    g.current_id = 0
    mate, _ = _mate_and_enemy(g, 0)
    g.players[0].inventory = {Item.MAGNET: 1}
    player_by_id(g, mate).inventory = {Item.MAGNET: MAX_PER_TYPE}
    acts = legal_actions(g, 0)
    assert not any(isinstance(a, Trade) and a.to_id == mate and a.items == [Item.MAGNET] for a in acts)


def test_no_trade_when_social_disabled():
    g = new_game(5, 0)
    g.social_enabled = False
    g.current_id = 0
    g.players[0].inventory = {Item.MAGNET: 1}
    assert not any(isinstance(a, Trade) for a in legal_actions(g, 0))


def test_harm_recorded_on_enemy_hit_not_self():
    g = new_game(5, 3)
    enemy = next(p.id for p in g.players if p.team != g.players[0].team)
    g.chamber.bullets = [Bullet.LIVE, Bullet.LIVE]
    g.chamber.pos = 0
    g.saw_active = False
    player_by_id(g, enemy).lives = 3
    g.current_id = 0
    step(g, 0, Shoot(enemy))
    assert g.harm[(enemy, 0)] == 1
    assert (0, 0) not in g.harm       # a self-shot must never build harm memory

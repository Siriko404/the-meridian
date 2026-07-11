from social_roulette.engine.constants import Item, Team, Bullet
from social_roulette.engine.state import Player, Chamber, can_receive, inventory_total


def mkp(i=0, **kw):
    d = dict(id=i, team=Team.RED, cover=3, alive=True, inventory={}, immunity_against=set(),
             shaken=False, flipback_discount=False)
    d.update(kw)
    return Player(**d)


def test_can_receive_caps():
    p = mkp(inventory={Item.MAGNET: 3})
    assert can_receive(p, Item.MAGNET) is False and can_receive(p, Item.POISON) is True
    p.inventory = {Item.MAGNET: 3, Item.POISON: 3, Item.GEIGER: 2}
    assert inventory_total(p) == 8 and can_receive(p, Item.SHAKEDOWN) is False


def test_chamber_basics():
    c = Chamber(bullets=[Bullet.LIVE, Bullet.BLANK], pos=0)
    assert c.current() == Bullet.LIVE and not c.is_empty()
    c.pos = 2
    assert c.is_empty() and c.current() is None


from social_roulette.engine.engine import new_game, step
from social_roulette.engine.actions import UseItem, Shoot


def test_new_game_shape():
    s = new_game(5, seed=1)
    assert len(s.players) == 5 and all(p.cover == 3 for p in s.players)
    assert all(sum(p.inventory.values()) == 3 for p in s.players)
    assert sum(1 for x in s.chamber.bullets if x == Bullet.LIVE) > 5 and s.current_id == s.order[0]


def test_team_odd_seat_coinflips_across_seeds():
    reds = set()
    for seed in range(40):
        s = new_game(5, seed=seed)
        reds.add(sum(1 for p in s.players if p.team.name == "RED"))
    assert reds == {2, 3}


def test_step_beer_empty_reloads_midturn():
    s = new_game(5, seed=2)
    s.players[s.current_id].inventory = {Item.MAGNET: 1}
    s.chamber.bullets = [s.chamber.bullets[0]]
    s.chamber.pos = 0
    step(s, s.current_id, UseItem(Item.MAGNET))
    assert not s.chamber.is_empty()

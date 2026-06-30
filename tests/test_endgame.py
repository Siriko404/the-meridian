from social_roulette.engine.constants import Item, Team, Shell
from social_roulette.engine.state import Player, Chamber, can_receive, inventory_total


def mkp(i=0, **kw):
    d = dict(id=i, team=Team.RED, lives=3, alive=True, inventory={}, immunity_against=set(),
             handcuffed=False, flipback_discount=False)
    d.update(kw)
    return Player(**d)


def test_can_receive_caps():
    p = mkp(inventory={Item.BEER: 3})
    assert can_receive(p, Item.BEER) is False and can_receive(p, Item.SAW) is True
    p.inventory = {Item.BEER: 3, Item.SAW: 3, Item.MAGNIFIER: 2}
    assert inventory_total(p) == 8 and can_receive(p, Item.HANDCUFFS) is False


def test_chamber_basics():
    c = Chamber(shells=[Shell.LIVE, Shell.BLANK], pos=0)
    assert c.current() == Shell.LIVE and not c.is_empty()
    c.pos = 2
    assert c.is_empty() and c.current() is None

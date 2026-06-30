from social_roulette.engine.constants import Item, Team, Shell
from social_roulette.engine.state import Player, Chamber, GameState, living_players
from social_roulette.engine.rng import SeededRng
from social_roulette.engine import reload as R


def mkstate(n=5):
    players = [Player(i, Team.RED, 3, True, {}, set(), False, False) for i in range(n)]
    return GameState(players=players, order=list(range(n)), current_id=0,
                     chamber=Chamber([], 0), rng=SeededRng(3), use_counts={Item.BEER: 4})


def test_reload_empty_refills_and_items():
    s = mkstate(5)
    before = sum(sum(p.inventory.values()) for p in s.players)
    R.reload_on_empty(s)
    assert sum(1 for x in s.chamber.shells if x == Shell.LIVE) > len(living_players(s)) and s.chamber.pos == 0
    assert sum(sum(p.inventory.values()) for p in s.players) >= before


def test_reload_death_resets_caps():
    s = mkstate(5)
    R.reload_on_death(s)
    assert s.use_counts == {} and s.chamber.pos == 0


def test_draw_respects_caps():
    s = mkstate(5)
    for p in s.players:
        p.inventory = {Item.BEER: 3, Item.SAW: 3, Item.MAGNIFIER: 2}
    R.draw_items_for_all(s, 2)
    assert all(sum(p.inventory.values()) == 8 for p in s.players)

from social_roulette.engine.engine import new_game, take_shot, step, _set_turn_to
from social_roulette.engine.actions import UseItem
from social_roulette.engine.constants import Item, Bullet
from social_roulette.engine.state import player_by_id, living_players
from social_roulette.engine.reload import draw_items_for_all


def test_draw_items_for_all_reports_attempted_and_received():
    s = new_game(5, seed=0)
    p = player_by_id(s, 0)
    p.inventory = {Item.MAGNET: 3, Item.SHAKEDOWN: 3, Item.GEIGER: 2}   # 8 total: everything bounces
    draws = draw_items_for_all(s, 2)
    assert set(draws) == {q.id for q in living_players(s)}
    assert len(draws[0]["attempted"]) == 2 and draws[0]["received"] == []
    for pid, d in draws.items():
        assert set(d["received"]) <= set(d["attempted"])


def test_beer_emptying_chamber_returns_draws():
    s = new_game(5, seed=0)
    pid = s.current_id
    player_by_id(s, pid).inventory = {Item.MAGNET: 3}
    s.chamber.bullets = list(s.chamber.bullets[:1])     # one bullet left
    s.chamber.pos = 0
    ev = step(s, pid, UseItem(Item.MAGNET))
    assert ev["emptied"] is True and "draws" in ev and len(ev["draws"]) == 5


def test_skip_logged_when_handcuff_clears():
    s = new_game(5, seed=0)
    order = s.order
    cur = s.current_id
    nxt = order[(order.index(cur) + 1) % len(order)]
    player_by_id(s, nxt).handcuffed = True
    _set_turn_to(s, nxt)
    assert s.last_skipped == [nxt]
    assert player_by_id(s, nxt).handcuffed is False

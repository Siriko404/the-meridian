import json

from social_roulette.engine.engine import new_game
from social_roulette.engine.constants import Item
from social_roulette.online.view import seat_view, action_label
from social_roulette.engine.actions import Shoot, UseItem, Flip

EX = {"scan_live": None, "scan_of": 0, "announced_total": 10, "announced_live": 6}


def test_view_hides_other_hands_and_bullet_order():
    g = new_game(5, 0)
    g.current_id = 0
    v = seat_view(g, 0, EX)
    assert isinstance(v["your_hand"], dict)
    for p in v["players"]:
        assert "inventory" not in p and "hand" not in p and "items" not in p
        assert set(p.keys()) <= {"id", "team", "cover", "alive", "handcuffed", "immune_from"}
    blob = json.dumps(v)
    assert "LIVE" not in blob and "BLANK" not in blob
    # chamber counts are NEVER persistently sent (announced via events only, game_guide:159)
    assert "bullets" not in v and "chamber" not in v


def test_view_shows_only_own_scan():
    g = new_game(5, 0)
    g.current_id = 0
    seen = dict(EX)
    seen.update(scan_live=1, scan_of=2)
    assert seat_view(g, 0, seen)["scan"] == {"live": 1, "of": 2}
    assert seat_view(g, 0, EX)["scan"] is None


def test_view_legal_only_on_your_turn():
    g = new_game(5, 0)
    g.current_id = 0
    assert len(seat_view(g, 0, EX)["legal"]) > 0
    assert seat_view(g, 1, EX)["legal"] == []


def test_action_label():
    g = new_game(5, 0)
    assert action_label(g, Shoot(3)) == "Shoot P3"
    assert action_label(g, UseItem(Item.PASSPORT)) == "Use Passport"
    assert action_label(g, UseItem(Item.TERMS, 2)) == "Terms on P2"
    assert action_label(g, Flip(2)) == "Flip P2"

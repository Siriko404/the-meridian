import numpy as np

from social_roulette.engine.engine import new_game
from social_roulette.engine.constants import Item
from social_roulette.rl.obs import encode_obs, OBS_DIM

EXTRAS = {"known_next_shell": "unknown", "announced_total": 10, "announced_live": 6}


def test_obs_shape_and_dtype():
    s = new_game(5, seed=1)
    o = encode_obs(s, 0, EXTRAS)
    assert o.shape == (OBS_DIM,) and o.dtype == np.float32


def test_obs_hides_who_holds_what():
    # swap two opponents' inventories: global counts unchanged, who-holds-what changed.
    # obs must be identical -> it does not encode per-opponent holdings (only public totals).
    s = new_game(5, seed=1)
    base = encode_obs(s, 0, EXTRAS).copy()
    s.players[1].inventory, s.players[2].inventory = s.players[2].inventory, s.players[1].inventory
    assert np.array_equal(encode_obs(s, 0, EXTRAS), base)


def test_obs_reflects_own_inventory():
    s = new_game(5, seed=1)
    base = encode_obs(s, 0, EXTRAS).copy()
    s.players[0].inventory = dict(s.players[0].inventory)
    s.players[0].inventory[Item.SAW] = s.players[0].inventory.get(Item.SAW, 0) + 1
    assert not np.array_equal(encode_obs(s, 0, EXTRAS), base)


def test_obs_peek_slot_changes():
    s = new_game(5, seed=1)
    a = encode_obs(s, 0, {**EXTRAS, "known_next_shell": "unknown"})
    b = encode_obs(s, 0, {**EXTRAS, "known_next_shell": "live"})
    assert not np.array_equal(a, b)

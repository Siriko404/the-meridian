"""Ego-centric encoding: a policy must see the same structure from ANY seat
(self always slot 0; action targets relative). This is what makes a seat-0-trained
policy seat-invariant => usable as a self-play opponent."""
from social_roulette.engine.engine import new_game
from social_roulette.engine.actions import Shoot, legal_actions
from social_roulette.rl.obs import encode_obs, PER_SLOT
from social_roulette.rl.action_space import ActionCodec

EXTRAS = {"known_next_bullet": "unknown", "announced_total": 10, "announced_live": 6}


def test_self_is_always_slot0_for_any_seat():
    s = new_game(5, seed=4)
    for lid in range(5):
        o = encode_obs(s, lid, EXTRAS)
        assert o[1] == 1.0  # slot 0 is_self flag set
        for j in range(1, 5):
            assert o[j * PER_SLOT + 1] == 0.0  # no other slot is self


def test_decode_index_roundtrip_all_seats():
    s = new_game(5, seed=4)
    for lid in range(5):
        for a in legal_actions(s, lid):
            idx = ActionCodec._index_of(a, lid)
            assert idx is not None
            b = ActionCodec.decode(idx, s, lid)
            assert type(a) is type(b)
            assert getattr(a, "target_id", None) == getattr(b, "target_id", None)


def test_self_shoot_is_relative_index0_every_seat():
    s = new_game(5, seed=4)
    for lid in range(5):
        assert ActionCodec._index_of(Shoot(lid), lid) == 0
        assert ActionCodec.decode(0, s, lid).target_id == lid

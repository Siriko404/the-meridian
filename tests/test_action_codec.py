import numpy as np

from social_roulette.engine.engine import new_game
from social_roulette.engine.actions import Shoot
from social_roulette.rl.action_space import ActionCodec, ACTION_N
from social_roulette.comms.vocab import SPEAK_N


def test_action_n():
    assert ACTION_N == 24 + SPEAK_N


def test_shoot_decode_roundtrip():
    s = new_game(5, seed=1)
    a = ActionCodec.decode(2, s, 0)
    assert isinstance(a, Shoot) and a.target_id == 2


def test_mask_matches_legal_actions():
    s = new_game(5, seed=3)
    mask = ActionCodec.legal_mask(s, s.current_id, shoot_only=False)
    assert mask.shape == (ACTION_N,) and mask.dtype == np.bool_ and mask.any()
    for idx in np.flatnonzero(mask):
        a = ActionCodec.decode(int(idx), s, s.current_id)
        assert a is not None


def test_shoot_only_mask_limits_to_shoots():
    s = new_game(5, seed=3)
    mask = ActionCodec.legal_mask(s, s.current_id, shoot_only=True)
    assert mask[:5].any() and not mask[5:].any()

import numpy as np
from social_roulette.engine.engine import new_game, step
from social_roulette.engine.actions import Speak
from social_roulette.rl.obs import encode_obs, OBS_DIM, MSG_K, MSG_FEATURES

EX = {"scan_live": None, "scan_of": 0, "announced_total": 10, "announced_live": 6}


def test_obs_dim_includes_message_window():
    assert OBS_DIM == 62 + MSG_K * MSG_FEATURES


def test_message_changes_obs_and_is_relativized():
    s = new_game(5, 1)
    spk = s.current_id
    base = encode_obs(s, learner_id=0, extras=EX).copy()
    step(s, spk, Speak(act=1, target=(spk + 1) % 5, value=None))   # GANG_UP someone
    after = encode_obs(s, learner_id=0, extras=EX)
    assert not np.array_equal(after, base)            # heard it
    o0 = encode_obs(s, 0, EX)
    o1 = encode_obs(s, 1, EX)
    tail = MSG_K * MSG_FEATURES
    assert not np.array_equal(o0[-tail:], o1[-tail:])  # re-relativized per observer

import numpy as np
from social_roulette.rl.comms_eval import _swap_tail, _two_prop
from social_roulette.rl.obs import MSG_K, MSG_FEATURES, OBS_DIM

_TAIL = MSG_K * MSG_FEATURES


def test_swap_replaces_only_tail_with_given_window():
    obs = np.arange(OBS_DIM, dtype=np.float32)
    window = np.full(_TAIL, 7.0, dtype=np.float32)   # a real-but-other window
    out = _swap_tail(obs, window)
    assert out.shape == obs.shape
    assert np.array_equal(out[:-_TAIL], obs[:-_TAIL])   # head untouched
    assert np.array_equal(out[-_TAIL:], window)         # tail == swapped window


def test_two_prop_basic():
    r = _two_prop(60, 100, 40, 100)
    assert abs(r["delta"] - 0.2) < 1e-9 and r["z"] > 0 and r["pvalue"] < 0.05

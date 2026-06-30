import numpy as np
from social_roulette.rl.comms_eval import _scramble_tail, _two_prop
from social_roulette.rl.obs import MSG_K, MSG_FEATURES, OBS_DIM

_TAIL = MSG_K * MSG_FEATURES


def test_scramble_preserves_shape_head_and_has_flags():
    obs = np.arange(OBS_DIM, dtype=np.float32)
    obs[-_TAIL:].reshape(MSG_K, MSG_FEATURES)[:, 0] = \
        np.array([1, 1, 1, 0, 0, 0, 0, 0], dtype=np.float32)   # 3 messages present
    base = obs.copy()
    out = _scramble_tail(base, np.random.default_rng(0))
    assert out.shape == obs.shape
    # head (non-message part) untouched
    assert np.array_equal(out[:-_TAIL], base[:-_TAIL])
    # has-flag column preserved => same number of messages
    o = out[-_TAIL:].reshape(MSG_K, MSG_FEATURES)
    b = base[-_TAIL:].reshape(MSG_K, MSG_FEATURES)
    assert (o[:, 0] == b[:, 0]).all()


def test_two_prop_basic():
    r = _two_prop(60, 100, 40, 100)
    assert abs(r["delta"] - 0.2) < 1e-9 and r["z"] > 0 and r["pvalue"] < 0.05

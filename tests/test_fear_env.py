import numpy as np
from social_roulette.rl.fear_env import SocialRouletteFearEnv, FEAR_MAX
from social_roulette.rl.obs import OBS_DIM


def test_obs_has_fear_dim_in_unit_range():
    env = SocialRouletteFearEnv()
    obs, info = env.reset(seed=1)
    assert obs.shape == (OBS_DIM + 1,)
    assert 0.0 <= obs[-1] <= 1.0          # normalized fear weight


def test_fear_drawn_in_range():
    env = SocialRouletteFearEnv()
    for s in range(20):
        env.reset(seed=s)
        assert 0.0 <= env.fear <= FEAR_MAX


def test_terminal_reward_is_win1_or_negfear():
    env = SocialRouletteFearEnv()
    _, info = env.reset(seed=5)
    done, r = False, 0.0
    while not done:
        legal = np.flatnonzero(info["action_mask"])
        _, r, done, _, info = env.step(int(legal[0]))   # always self-shoot
    assert r == 1.0 or abs(r - (-env.fear)) < 1e-6

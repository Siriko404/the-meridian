import numpy as np
from social_roulette.sim.turn import random_policy
from social_roulette.rl.social_env import SocialRouletteSocialEnv
from social_roulette.rl.social_obs import SOCIAL_OBS_DIM
from social_roulette.rl.social_action_space import ACTION_N_SOCIAL


def _sampler(rng):
    return random_policy


def test_env_spaces():
    env = SocialRouletteSocialEnv(_sampler)
    obs, info = env.reset(seed=0)
    assert obs.shape == (SOCIAL_OBS_DIM,)
    assert env.action_space.n == ACTION_N_SOCIAL
    assert info["action_mask"].shape == (ACTION_N_SOCIAL,)
    assert info["action_mask"].any()


def test_env_social_flags_on():
    env = SocialRouletteSocialEnv(_sampler)
    env.reset(seed=1)
    assert env.state.comms_enabled and env.state.social_enabled


def test_env_random_rollout_terminates_with_pm1_reward():
    env = SocialRouletteSocialEnv(_sampler)
    for ep in range(5):
        obs, info = env.reset(seed=ep)
        done, r, steps = False, 0.0, 0
        while not done and steps < 500:
            legal = np.flatnonzero(info["action_mask"])
            obs, r, done, trunc, info = env.step(int(legal[0]))
            steps += 1
        assert done
        assert r in (1.0, -1.0)

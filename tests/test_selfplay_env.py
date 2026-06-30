import numpy as np
from social_roulette.rl.selfplay_env import SocialRouletteSelfPlayEnv
from social_roulette.sim.turn import random_policy
from social_roulette.rl.obs import OBS_DIM
from social_roulette.rl.action_space import ACTION_N


def _env():
    return SocialRouletteSelfPlayEnv(opponent_sampler=lambda rng: random_policy)


def test_reset_returns_well_formed_obs_and_mask():
    env = _env()
    obs, info = env.reset(seed=3)
    assert obs.shape == (OBS_DIM,)
    assert info["action_mask"].shape == (ACTION_N,)
    assert info["action_mask"].any()


def test_episode_terminates_with_terminal_reward():
    env = _env()
    _, info = env.reset(seed=5)
    rng = np.random.default_rng(0)
    term, r, steps = False, 0.0, 0
    while not term and steps < 5000:
        legal = np.flatnonzero(info["action_mask"])
        obs, r, term, trunc, info = env.step(int(rng.choice(legal)))
        steps += 1
    assert term
    assert r in (-1.0, 1.0)


def test_four_opponents_sampled_each_reset():
    seen = []

    def sampler(rng):
        seen.append(1)
        return random_policy

    env = SocialRouletteSelfPlayEnv(opponent_sampler=sampler)
    env.reset(seed=1)
    assert len(seen) == 4  # 5 players minus the learner

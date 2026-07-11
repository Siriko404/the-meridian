import numpy as np

from social_roulette.rl.env import SocialRouletteSingleEnv
from social_roulette.rl.obs import OBS_DIM
from social_roulette.rl.action_space import ACTION_N


def _play_episode(env, seed, pick=0):
    obs, info = env.reset(seed=seed)
    if env._terminal():
        return env._reward()
    r = 0.0
    done = False
    steps = 0
    while not done and steps < 10000:
        legal = np.flatnonzero(info["action_mask"])
        obs, r, done, trunc, info = env.step(int(legal[pick % len(legal)]))
        steps += 1
    return r


def test_reset_returns_obs_and_mask():
    env = SocialRouletteSingleEnv()
    obs, info = env.reset(seed=1)
    assert obs.shape == (OBS_DIM,) and obs.dtype == np.float32
    assert info["action_mask"].shape == (ACTION_N,)
    assert (env.state.current_id == 0 or env.state.winner is not None
            or not env.state.players[0].alive)


def test_episode_terminates_with_signed_reward():
    env = SocialRouletteSingleEnv(shoot_only=True)
    for seed in range(40):
        r = _play_episode(env, seed)
        assert r in (1.0, -1.0)


def test_full_action_episode_terminates():
    env = SocialRouletteSingleEnv(shoot_only=False)
    for seed in range(20):
        r = _play_episode(env, seed, pick=-1)
        assert r in (1.0, -1.0)


def test_learner_wins_are_possible_and_losses_too():
    # B2 made games longer (no x2 damage): a pure self-shooter (pick=0) now loses
    # ~always (0 wins / 400 seeds probed 2026-07-10), so possibility is asserted with
    # the aggressive policy (pick=-1: shoot the last legal other). 68W/82L at 150 seeds.
    env = SocialRouletteSingleEnv(shoot_only=True)
    results = [_play_episode(env, s, pick=-1) for s in range(150)]
    assert any(r == 1.0 for r in results) and any(r == -1.0 for r in results)

import pickle
import numpy as np

from social_roulette.rl.selfplay import build_selfplay_env_fn
from social_roulette.rl.action_space import ACTION_N


def test_env_fn_picklable_and_builds_and_steps():
    # opponent_paths=[] => random opponents (no torch model load); the thunk must
    # survive pickling or SubprocVecEnv (Windows spawn) cannot ship it to workers.
    fn = build_selfplay_env_fn(opponent_paths=[])
    fn = pickle.loads(pickle.dumps(fn))
    env = fn()
    obs, info = env.reset(seed=2)
    assert info["action_mask"].shape == (ACTION_N,)
    legal = np.flatnonzero(info["action_mask"])
    assert legal.size > 0
    env.step(int(legal[0]))  # steppable

"""Stage-2 checkpoint self-play — builders + throughput pilot.

Production wiring (factory / pool / env) is reused by the generation loop.
The `--pilot` path measures real steps/sec with model-backed opponents so the
training run can be sized to a wall-clock budget BEFORE committing compute
(advisor finding #1: model opponents can be 20-100x Stage-1's cost, not 4x).
"""
import argparse
import time

from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker

from social_roulette.rl.selfplay_env import SocialRouletteSelfPlayEnv
from social_roulette.rl.env import SocialRouletteSingleEnv
from social_roulette.rl.pool import CheckpointPool
from social_roulette.rl.policies import make_model_policy


def load_model_policy_factory(shoot_only=False, device="cpu"):
    """factory(path) -> seat policy backed by the MaskablePPO at `path`.
    Called once per checkpoint; CheckpointPool caches the result in RAM."""
    def factory(path):
        model = MaskablePPO.load(path, device=device)
        return make_model_policy(model, shoot_only)
    return factory


def build_pool(seed_paths, shoot_only=False, device="cpu"):
    pool = CheckpointPool(load_model_policy_factory(shoot_only, device))
    for p in seed_paths:
        pool.add(p)
    return pool


def make_selfplay_env(pool, shoot_only=False):
    env = SocialRouletteSelfPlayEnv(opponent_sampler=pool.sample, shoot_only=shoot_only)
    return ActionMasker(env, lambda e: e.unwrapped._mask())


def _timed_learn(env, steps, seed=0):
    model = MaskablePPO("MlpPolicy", env, device="cpu", verbose=0,
                        n_steps=2048, batch_size=256, gamma=0.999, seed=seed)
    t0 = time.perf_counter()
    model.learn(total_timesteps=steps)
    return steps / (time.perf_counter() - t0)


def pilot(seed_path, steps):
    print(f"[pilot] measuring {steps} steps/env on CPU ...")

    rand_env = ActionMasker(SocialRouletteSingleEnv(), lambda e: e.unwrapped._mask())
    r_rand = _timed_learn(rand_env, steps)
    print(f"  random opponents (Stage-1 env): {r_rand:7.1f} steps/sec")

    pool = build_pool([seed_path])
    sp_env = make_selfplay_env(pool)
    r_sp = _timed_learn(sp_env, steps)
    print(f"  model opponents (self-play)   : {r_sp:7.1f} steps/sec")

    factor = r_rand / r_sp if r_sp else float("inf")
    print(f"  slowdown factor               : {factor:5.1f}x")
    for target in (1_000_000, 4_000_000):
        mins = target / r_sp / 60
        print(f"  projected {target:>9,} steps      : {mins:7.1f} min ({mins/60:.1f} h)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--seed-model", default="models/stage1b")
    ap.add_argument("--steps", type=int, default=6144)
    a = ap.parse_args()
    if a.pilot:
        pilot(a.seed_model, a.steps)

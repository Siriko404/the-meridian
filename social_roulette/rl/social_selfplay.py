"""Stage-5 co-evolution driver — the 4th ingredient.

Comms-deaf/random opponents guarantee a cheap-talk null (Stage 3 proved it), so
alliances can only co-evolve if the WHOLE population trains with comms + gifts +
memory ON, from a FRESH seed (no warm-start from an asocial model — those carry no
social priors and their pool would be gift-deaf). Mirrors the Stage-2 parallel
self-play machinery (pool of frozen past selves, biased-recent sampling) but on
the social env / obs / codec, and reuses CheckpointPool unchanged.

Reward stays +1 win / -1 death: everything social must remain instrumental.
"""
import argparse
import functools
import os
import time

from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.vec_env import SubprocVecEnv

from social_roulette.rl.social_env import SocialRouletteSocialEnv, make_social_model_policy
from social_roulette.rl.pool import CheckpointPool
from social_roulette.observe.match import run_match
from social_roulette.sim.turn import random_policy


def load_social_policy_factory(device="cpu"):
    def factory(path):
        return make_social_model_policy(MaskablePPO.load(path, device=device))
    return factory


def build_social_pool(seed_paths, device="cpu"):
    pool = CheckpointPool(load_social_policy_factory(device))
    for p in seed_paths:
        pool.add(p)
    return pool


def _mask_fn(e):                      # module-level => picklable for SubprocVecEnv
    return e.unwrapped._mask()


def _build_masked_social_env(opponent_paths):
    """Runs inside each worker: builds its own social pool (own model copies)."""
    import torch
    torch.set_num_threads(1)
    if opponent_paths:
        sampler = build_social_pool(list(opponent_paths)).sample
    else:
        sampler = lambda rng: random_policy      # empty pool => random (still gifts/speaks: env sets flags)
    return ActionMasker(SocialRouletteSocialEnv(opponent_sampler=sampler), _mask_fn)


def make_vec_social_env(opponent_paths, n_envs):
    thunk = functools.partial(_build_masked_social_env, tuple(opponent_paths))
    return SubprocVecEnv([thunk for _ in range(n_envs)])


def _social_policy(path, device="cpu"):
    return make_social_model_policy(MaskablePPO.load(path, device=device))


def lone_vs_field(a_policy, b_policy, n, seed_offset=5_000_000, num_players=5):
    """Win-rate of one A-seat (id 0) vs a field of B, all social ON. Fair share = 0.20."""
    wins = 0
    for s in range(seed_offset, seed_offset + n):
        pols = {0: a_policy, **{seat: b_policy for seat in range(1, num_players)}}
        if run_match(s, pols, num_players=num_players, record=False, social=True)["winner"] == 0:
            wins += 1
    return wins / n


def train_fresh_seed(steps, out_path, n_envs=12, seed=0):
    """A from-scratch social seed vs random opponents (all-social-on)."""
    venv = make_vec_social_env([], n_envs)
    model = MaskablePPO("MlpPolicy", venv, device="cpu", verbose=1,
                        n_steps=2048, batch_size=256, gamma=0.999, seed=seed)
    t0 = time.perf_counter()
    model.learn(total_timesteps=steps)
    venv.close()
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    model.save(out_path)
    held = lone_vs_field(_social_policy(out_path), random_policy, 1000)
    print(f"[seed] saved {out_path} ({(time.perf_counter()-t0)/60:.1f} min)  "
          f"vs random = {held:.3f}", flush=True)
    return out_path


def run_social_selfplay(seed_model, n_gen, steps_per_gen, out_dir, n_envs=12,
                        canary_floor=0.55, canary_n=1000):
    """Parallel social self-play. Pool = [seed] + completed gens, frozen within a gen."""
    os.makedirs(out_dir, exist_ok=True)
    prev, gen_paths = seed_model, []
    for g in range(1, n_gen + 1):
        venv = make_vec_social_env([seed_model] + gen_paths, n_envs)
        model = MaskablePPO.load(prev, env=venv, device="cpu",
                                 n_steps=2048, batch_size=256, gamma=0.999)
        t0 = time.perf_counter()
        model.learn(total_timesteps=steps_per_gen)
        venv.close()
        path = os.path.join(out_dir, f"gen{g}")
        model.save(path)
        gen_paths.append(path)
        mins = (time.perf_counter() - t0) / 60
        held = lone_vs_field(_social_policy(path), random_policy, canary_n)
        print(f"[gen {g}] saved {path}  ({mins:.1f} min, {steps_per_gen/(mins*60):.0f} steps/s)  "
              f"vs random = {held:.3f}", flush=True)
        if g == 1 and held < canary_floor:
            print(f"[gen 1] CANARY FAIL {held:.3f} < {canary_floor} -> STOP", flush=True)
            return gen_paths
        prev = path
    return gen_paths


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="train a fresh from-scratch social seed")
    ap.add_argument("--run", action="store_true", help="run social self-play generations")
    ap.add_argument("--seed-model", default="models/stage5seed")
    ap.add_argument("--steps-per-gen", type=int, default=1_000_000)
    ap.add_argument("--gens", type=int, default=4)
    ap.add_argument("--n-envs", type=int, default=12)
    ap.add_argument("--out", default="models/stage5")
    a = ap.parse_args()
    if a.seed:
        train_fresh_seed(a.steps_per_gen, a.seed_model, a.n_envs)
    elif a.run:
        run_social_selfplay(a.seed_model, a.gens, a.steps_per_gen, a.out, a.n_envs)

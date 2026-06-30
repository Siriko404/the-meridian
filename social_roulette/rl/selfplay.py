"""Stage-2 checkpoint self-play — builders + throughput pilot.

Production wiring (factory / pool / env) is reused by the generation loop.
The `--pilot` path measures real steps/sec with model-backed opponents so the
training run can be sized to a wall-clock budget BEFORE committing compute
(advisor finding #1: model opponents can be 20-100x Stage-1's cost, not 4x).
"""
import argparse
import functools
import os
import time

from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.vec_env import SubprocVecEnv

from social_roulette.rl.selfplay_env import SocialRouletteSelfPlayEnv
from social_roulette.rl.env import SocialRouletteSingleEnv
from social_roulette.rl.pool import CheckpointPool
from social_roulette.rl.policies import make_model_policy
from social_roulette.observe.match import run_match
from social_roulette.sim.turn import random_policy


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


def _mask_fn(e):                      # module-level => picklable for SubprocVecEnv
    return e.unwrapped._mask()


def make_selfplay_env(pool, shoot_only=False):
    env = SocialRouletteSelfPlayEnv(opponent_sampler=pool.sample, shoot_only=shoot_only)
    return ActionMasker(env, _mask_fn)


# ---- parallel (SubprocVecEnv) -------------------------------------------------

def _build_masked_selfplay_env(opponent_paths, shoot_only):
    """Runs INSIDE each worker process. Builds its own pool (loads its own copy of
    the opponent models) so nothing unpicklable crosses the process boundary."""
    import torch
    torch.set_num_threads(1)          # 12 workers x 16 threads would thrash the box
    if opponent_paths:
        sampler = build_pool(list(opponent_paths), shoot_only).sample
    else:
        sampler = lambda rng: random_policy     # empty pool => random opponents
    env = SocialRouletteSelfPlayEnv(opponent_sampler=sampler, shoot_only=shoot_only)
    return ActionMasker(env, _mask_fn)


def build_selfplay_env_fn(opponent_paths, shoot_only=False):
    """Picklable thunk for one worker env (partial of a module-level fn)."""
    return functools.partial(_build_masked_selfplay_env, tuple(opponent_paths), shoot_only)


def make_vec_selfplay_env(opponent_paths, n_envs, shoot_only=False):
    return SubprocVecEnv([build_selfplay_env_fn(opponent_paths, shoot_only)
                          for _ in range(n_envs)])


def run_selfplay_parallel(seed_model, n_gen, steps_per_gen, out_dir, n_envs=12,
                          canary_floor=0.65, canary_n=1000):
    """Parallel checkpoint self-play. Pool = [seed_model] + completed gens; rebuilt
    each generation (frozen within a generation). Gen-1 canary gates on held-out
    random. Returns the list of saved generation paths."""
    os.makedirs(out_dir, exist_ok=True)
    prev, gen_paths = seed_model, []
    for g in range(1, n_gen + 1):
        pool_paths = [seed_model] + gen_paths
        venv = make_vec_selfplay_env(pool_paths, n_envs)
        model = MaskablePPO.load(prev, env=venv, device="cpu",
                                 n_steps=2048, batch_size=256, gamma=0.999)
        t0 = time.perf_counter()
        model.learn(total_timesteps=steps_per_gen)
        venv.close()
        path = os.path.join(out_dir, f"gen{g}")
        model.save(path)
        gen_paths.append(path)
        mins = (time.perf_counter() - t0) / 60
        held = lone_vs_field(_model_policy(path), random_policy, canary_n)
        sps = steps_per_gen / (mins * 60)
        print(f"[gen {g}] saved {path}  ({mins:.1f} min, {sps:.0f} steps/s)  "
              f"held-out vs random = {held:.3f}", flush=True)
        if g == 1 and held < canary_floor:
            print(f"[gen 1] CANARY FAIL: {held:.3f} < {canary_floor} -> STOP", flush=True)
            return gen_paths
        prev = path
    return gen_paths


def lone_vs_field(a_policy, b_policy, n, seed_offset=2_000_000, num_players=5):
    """Win-rate of ONE A-seat (id 0) against a field of (num_players-1) B-seats.
    Pairwise, interpretable skill measure; fair share = 1/num_players (0.20 at 5)."""
    wins = 0
    for s in range(seed_offset, seed_offset + n):
        pols = {0: a_policy}
        for seat in range(1, num_players):
            pols[seat] = b_policy
        if run_match(s, pols, num_players=num_players, record=False)["winner"] == 0:
            wins += 1
    return wins / n


def _model_policy(path, shoot_only=False, device="cpu"):
    return make_model_policy(MaskablePPO.load(path, device=device), shoot_only)


def pairwise_matrix(labelled_policies, n=2000, seed_offset=2_000_000):
    """labelled_policies: list[(label, policy)]. Returns {a_label: {b_label: winrate}}."""
    out = {}
    for a_lab, a_pol in labelled_policies:
        out[a_lab] = {}
        for b_lab, b_pol in labelled_policies:
            out[a_lab][b_lab] = lone_vs_field(a_pol, b_pol, n, seed_offset)
    return out


def run_selfplay(seed_model, n_gen, steps_per_gen, out_dir,
                 canary_floor=0.65, canary_n=1000):
    """Train n_gen generations of checkpoint self-play, warm-started from seed_model.
    Pool seed = {seed_model}; each generation appends its snapshot. Gates after gen 1
    on held-out random (catches overfit-to-one-opponent collapse)."""
    os.makedirs(out_dir, exist_ok=True)
    pool = build_pool([seed_model])
    prev, gen_paths = seed_model, []
    for g in range(1, n_gen + 1):
        env = make_selfplay_env(pool)
        model = MaskablePPO.load(prev, env=env, device="cpu")
        t0 = time.perf_counter()
        model.learn(total_timesteps=steps_per_gen)
        path = os.path.join(out_dir, f"gen{g}")
        model.save(path)
        gen_paths.append(path)
        mins = (time.perf_counter() - t0) / 60
        held = lone_vs_field(_model_policy(path), random_policy, canary_n)
        print(f"[gen {g}] saved {path}  ({mins:.1f} min)  held-out vs random = {held:.3f}")
        if g == 1 and held < canary_floor:
            print(f"[gen 1] CANARY FAIL: {held:.3f} < {canary_floor} "
                  f"(overfit to single opponent). STOPPING.")
            return gen_paths
        pool.add(path)
        prev = path
    return gen_paths


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


def per_seat_winrate(a_path, n=300, seed_offset=2_000_000, num_players=5):
    """Win-rate of the policy when placed in EACH seat vs a random field.
    Flat across seats == seat-invariant (the ego-centric fix worked)."""
    a = _model_policy(a_path)
    out = []
    for seat in range(num_players):
        w = sum(1 for s in range(seed_offset, seed_offset + n)
                if run_match(s, {k: (a if k == seat else random_policy)
                                 for k in range(num_players)},
                             num_players=num_players, record=False)["winner"] == seat)
        out.append(round(w / n, 3))
    return out


def smoke_report(seed_model, gen_paths, n=1000):
    s1 = _model_policy(seed_model)
    rows = [("stage1b vs 4x random  (ref ~0.74)", lone_vs_field(s1, random_policy, n)),
            ("stage1b vs 4x stage1b (symmetry ~0.20)", lone_vs_field(s1, s1, n))]
    prev_pol, prev_lab = s1, "stage1b"
    for i, p in enumerate(gen_paths, 1):
        gp = _model_policy(p)
        rows.append((f"gen{i} vs 4x random   (held-out)", lone_vs_field(gp, random_policy, n)))
        rows.append((f"gen{i} vs 4x stage1b  (skill vs base)", lone_vs_field(gp, s1, n)))
        rows.append((f"gen{i} vs 4x {prev_lab:8s}(beats predecessor?)", lone_vs_field(gp, prev_pol, n)))
        prev_pol, prev_lab = gp, f"gen{i}"
    print(f"\n=== Stage-2 report (n={n}) ===", flush=True)
    for lab, wr in rows:
        print(f"  {lab}: {wr:.3f}", flush=True)
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--par-pilot", action="store_true", help="parallel throughput check")
    ap.add_argument("--retrain-seed", action="store_true", help="train fresh seat-invariant seed vs random")
    ap.add_argument("--per-seat", default=None, help="path to a model: report per-seat win-rate vs random")
    ap.add_argument("--run-parallel", action="store_true")
    ap.add_argument("--seed-model", default="models/stage1b")
    ap.add_argument("--steps", type=int, default=6144)
    ap.add_argument("--gens", type=int, default=4)
    ap.add_argument("--steps-per-gen", type=int, default=1_000_000)
    ap.add_argument("--n-envs", type=int, default=12)
    ap.add_argument("--out", default="models/stage2")
    a = ap.parse_args()
    if a.pilot:
        pilot(a.seed_model, a.steps)
    elif a.par_pilot:
        venv = make_vec_selfplay_env([a.seed_model], a.n_envs)
        model = MaskablePPO("MlpPolicy", venv, device="cpu", verbose=0,
                            n_steps=2048, batch_size=256, gamma=0.999, seed=0)
        t0 = time.perf_counter()
        model.learn(total_timesteps=a.steps)
        venv.close()
        sps = a.steps / (time.perf_counter() - t0)
        print(f"[par-pilot] {a.n_envs} envs: {sps:7.0f} steps/sec  "
              f"(1M = {1e6/sps/60:.1f} min, 4M = {4e6/sps/60:.1f} min)")
    elif a.retrain_seed:
        venv = make_vec_selfplay_env([], a.n_envs)   # empty pool => random opponents
        model = MaskablePPO("MlpPolicy", venv, device="cpu", verbose=1,
                            n_steps=2048, batch_size=256, gamma=0.999, seed=0)
        model.learn(total_timesteps=a.steps_per_gen)
        venv.close()
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        model.save(a.out)
        print("saved", a.out, "per-seat vs random:", per_seat_winrate(a.out), flush=True)
    elif a.per_seat:
        print("per-seat vs random:", per_seat_winrate(a.per_seat), flush=True)
    elif a.run_parallel:
        paths = run_selfplay_parallel(a.seed_model, a.gens, a.steps_per_gen, a.out, a.n_envs)
        if paths:
            smoke_report(a.seed_model, paths)

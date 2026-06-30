"""Stage-4 fear experiment: train one fear-conditioned population, then measure
whether cautious behavior rises with the fear weight (the ONE number).

PASS = self-shot rate falls and/or heal rate rises monotonically with fear.
FAIL = the knob is inert (behavior flat in fear) => stop.
"""
import argparse
import functools
import json
import time

import numpy as np
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.vec_env import SubprocVecEnv

from social_roulette.rl.fear_env import SocialRouletteFearEnv, FEAR_MAX
from social_roulette.rl.obs import encode_obs
from social_roulette.rl.action_space import ActionCodec
from social_roulette.observe.match import run_match


def _mask_fn(e):
    return e.unwrapped._mask()


def _build_fear_env():
    import torch
    torch.set_num_threads(1)
    return ActionMasker(SocialRouletteFearEnv(), _mask_fn)


def make_vec_fear_env(n_envs):
    return SubprocVecEnv([functools.partial(_build_fear_env) for _ in range(n_envs)])


def train_fear(steps, out_path, n_envs=12):
    venv = make_vec_fear_env(n_envs)
    model = MaskablePPO("MlpPolicy", venv, device="cpu", verbose=1,
                        n_steps=2048, batch_size=256, gamma=0.999, seed=0)
    t0 = time.perf_counter()
    model.learn(total_timesteps=steps)
    venv.close()
    model.save(out_path)
    print(f"saved {out_path} ({(time.perf_counter()-t0)/60:.1f} min)", flush=True)


def _fear_policy(model, fear, fear_max=FEAR_MAX):
    def pol(state, pid, extras):
        obs = np.concatenate([encode_obs(state, pid, extras.d()),
                              [np.float32(fear / fear_max)]]).astype(np.float32)
        mask = ActionCodec.legal_mask(state, pid, False)
        idx = model.predict(obs, action_masks=mask, deterministic=True)[0]
        return ActionCodec.decode(int(idx), state, pid)
    return pol


def behavior_vs_fear(model_path, fears=(0.0, 0.75, 1.5, 2.25, 3.0), n=400, seed_offset=4_000_000):
    model = MaskablePPO.load(model_path, device="cpu")
    rows = []
    for f in fears:
        pol = _fear_policy(model, f)
        shots = self_shots = heals = wins = 0
        for s in range(seed_offset, seed_offset + n):
            res = run_match(s, {0: pol}, record=True)
            if res["winner"] == 0:
                wins += 1
            for r in res["rows"]:
                if r["actor"] != 0:
                    continue
                if r["type"] == "shot":
                    shots += 1
                    e = json.loads(r["extra"]) if r["extra"] else {}
                    if e.get("self"):
                        self_shots += 1
                elif r["type"] == "item_used" and r["item"] == "CIGARETTES":
                    heals += 1
        rows.append({"fear": f, "self_shot_rate": round(self_shots / max(shots, 1), 3),
                     "heal_per_game": round(heals / n, 3), "winrate": round(wins / n, 3)})
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--steps", type=int, default=1_000_000)
    ap.add_argument("--n-envs", type=int, default=12)
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--out", default="models/fear")
    a = ap.parse_args()
    if a.train:
        train_fear(a.steps, a.out, a.n_envs)
    if a.measure:
        print("BEHAVIOR vs FEAR:", flush=True)
        for row in behavior_vs_fear(a.out, n=a.n):
            print("  ", row, flush=True)

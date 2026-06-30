import argparse

import numpy as np
from scipy.stats import binomtest
from sb3_contrib import MaskablePPO

from social_roulette.rl.env import SocialRouletteSingleEnv


def evaluate(model_path, n=5000, seed_offset=1_000_000, shoot_only=False):
    model = MaskablePPO.load(model_path, device="cpu")
    env = SocialRouletteSingleEnv(shoot_only=shoot_only)
    wins = 0
    for i in range(n):
        obs, info = env.reset(seed=seed_offset + i)
        done = env._terminal()
        r = env._reward() if done else 0.0
        while not done:
            a, _ = model.predict(obs, action_masks=info["action_mask"], deterministic=True)
            obs, r, done, trunc, info = env.step(int(a))
        wins += 1 if r == 1.0 else 0
    wr = wins / n
    p = binomtest(wins, n, 0.20, alternative="greater").pvalue
    return {"win_rate": wr, "p_value": p, "wins": wins, "n": n}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--shoot-only", action="store_true")
    ap.add_argument("--n", type=int, default=5000)
    a = ap.parse_args()
    res = evaluate(a.model, n=a.n, shoot_only=a.shoot_only)
    print(f"win_rate={res['win_rate']:.4f}  ({res['wins']}/{res['n']})  p(>0.20)={res['p_value']:.3e}")

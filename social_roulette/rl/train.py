import argparse
import os

from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker

from social_roulette.rl.env import SocialRouletteSingleEnv


def _mask_fn(env):
    return env._mask()


def make_env(shoot_only):
    return ActionMasker(SocialRouletteSingleEnv(shoot_only=shoot_only), _mask_fn)


def train(shoot_only, steps, out_path):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    env = make_env(shoot_only)
    model = MaskablePPO("MlpPolicy", env, device="cpu", verbose=1,
                        n_steps=2048, batch_size=256, gamma=0.999, seed=0)
    model.learn(total_timesteps=steps)
    model.save(out_path)
    print("saved", out_path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--shoot-only", action="store_true")
    ap.add_argument("--steps", type=int, default=300000)
    ap.add_argument("--out", default="models/stage1a")
    a = ap.parse_args()
    train(a.shoot_only, a.steps, a.out)

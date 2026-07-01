"""Stage-5 emergence metrics.

Stage 3 taught the hard lesson: input-sensitivity != use. The load-bearing test
is therefore an OUTCOME ABLATION — does an agent that can SEE its memory / CAN
gift actually win more than the same weights with that pathway removed? Everything
else here is descriptive (does trade even happen, is it reciprocated, do coalitions
dissolve toward the endgame) and is labelled as such — descriptive counts are a
hypothesis, the ablation is the evidence.

All games: a full field of the SAME social policy, comms+gifts+memory ON.
"""
import argparse
import math
from collections import Counter

from sb3_contrib import MaskablePPO

from social_roulette.observe.match import run_match
from social_roulette.rl.social_obs import social_encode_obs, MEM_DIM
from social_roulette.rl.social_action_space import SocialActionCodec
from social_roulette.rl.action_space import ACTION_N as BASE_N
from social_roulette.rl.social_selfplay import lone_vs_field, _social_policy


def _two_prop(p1, n1, p2, n2):
    """z, p(two-sided) for H0: p1 == p2."""
    x1, x2 = p1 * n1, p2 * n2
    p = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0, 1.0
    z = (p1 - p2) / se
    return z, math.erfc(abs(z) / math.sqrt(2))


def _mem_ablated_policy(model):
    def pol(state, pid, extras):
        obs = social_encode_obs(state, pid, extras.d()).copy()
        obs[-MEM_DIM:] = 0.0                       # amnesiac: memory pathway removed
        mask = SocialActionCodec.legal_mask(state, pid, False)
        idx, _ = model.predict(obs, action_masks=mask, deterministic=True)
        return SocialActionCodec.decode(int(idx), state, pid)
    return pol


def _giftoff_policy(model):
    def pol(state, pid, extras):
        obs = social_encode_obs(state, pid, extras.d())
        mask = SocialActionCodec.legal_mask(state, pid, False)
        mask[BASE_N:] = False                      # gifting forbidden
        idx, _ = model.predict(obs, action_masks=mask, deterministic=True)
        return SocialActionCodec.decode(int(idx), state, pid)
    return pol


def outcome_ablation(model_path, n=2500):
    """Win-rate of seat 0 vs a field of the intact policy, for 3 seat-0 variants.
    If memory/gifts are USED for gain: intact > ablated. Fair share = 0.20."""
    model = MaskablePPO.load(model_path, device="cpu")
    field = _social_policy(model_path)
    wr_intact = lone_vs_field(field, field, n)
    wr_memoff = lone_vs_field(_mem_ablated_policy(model), field, n)
    wr_giftoff = lone_vs_field(_giftoff_policy(model), field, n)
    z_m, p_m = _two_prop(wr_intact, n, wr_memoff, n)
    z_g, p_g = _two_prop(wr_intact, n, wr_giftoff, n)
    return {
        "intact": round(wr_intact, 4),
        "memory_off": round(wr_memoff, 4), "d_memory": round(wr_intact - wr_memoff, 4),
        "p_memory": round(p_m, 4),
        "gift_off": round(wr_giftoff, 4), "d_gift": round(wr_intact - wr_giftoff, 4),
        "p_gift": round(p_g, 4),
        "n": n,
    }


def descriptive(model_path, n=500, seed_offset=6_000_000):
    """Does trade happen, get reciprocated, and taper toward the endgame? Descriptive."""
    pol = _social_policy(model_path)
    total_gifts = 0
    recip_pairs = recip_hits = 0
    by_alive = Counter()
    for s in range(seed_offset, seed_offset + n):
        rows = run_match(s, {k: pol for k in range(5)}, record=True, social=True)["rows"]
        elim_seqs = sorted(r["seq"] for r in rows if r["type"] == "elimination")
        pairs = set()
        for r in rows:
            if r["type"] == "gift":
                total_gifts += 1
                pairs.add((r["actor"], r["target"]))
                alive = 5 - sum(1 for e in elim_seqs if e < r["seq"])
                by_alive[alive] += 1
        for (g, rc) in pairs:
            recip_pairs += 1
            if (rc, g) in pairs:
                recip_hits += 1
    return {
        "gifts_per_game": round(total_gifts / n, 3),
        "reciprocity_rate": round(recip_hits / max(recip_pairs, 1), 3),
        "gifts_by_alive": {k: by_alive[k] for k in sorted(by_alive)},
        "n": n,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--n", type=int, default=2500)
    ap.add_argument("--descriptive-n", type=int, default=500)
    a = ap.parse_args()
    print("OUTCOME ABLATION:", outcome_ablation(a.model, a.n), flush=True)
    print("DESCRIPTIVE:", descriptive(a.model, a.descriptive_n), flush=True)

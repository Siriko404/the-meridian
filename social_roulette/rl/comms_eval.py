"""Stage-3 measurement: does the agent USE the emoji channel?

PRIMARY (high power) — `response_shift`: at every learner decision, compare the
action chosen on the REAL message window vs the same state with the message tail
SCRAMBLED (content decorrelated from state, marginal preserved). The flip-rate is
measured per-decision => thousands of samples. flip-rate ~ 0 => the policy ignores
messages (the expected cheap-talk null). flip-rate >> 0 => decisions depend on what
was said.

SECONDARY (confirmation) — `winrate_ablation`: does that dependence help WINNING?
Lone agent with real vs scrambled incoming messages, vs a field of the same model.
Two-proportion test; pre-register n >= 2500 (Stage-2 lesson: small effects need n).
"""
import math

import numpy as np
from sb3_contrib import MaskablePPO

from social_roulette.observe.match import run_match
from social_roulette.rl.obs import encode_obs, MSG_K, MSG_FEATURES
from social_roulette.rl.action_space import ActionCodec

_TAIL = MSG_K * MSG_FEATURES
_CACHE = {}


def _load(path):
    if path not in _CACHE:
        _CACHE[path] = MaskablePPO.load(path, device="cpu")
    return _CACHE[path]


def _scramble_tail(obs, rng):
    """Decorrelate message content from state: shuffle features 1..4 (speaker_rel,
    act, target_rel, value) independently across the K slots; keep col 0 (has-flag)
    so the NUMBER of messages is unchanged (marginal preserved)."""
    tail = obs[-_TAIL:].reshape(MSG_K, MSG_FEATURES).copy()
    for c in range(1, MSG_FEATURES):
        rng.shuffle(tail[:, c])
    out = obs.copy()
    out[-_TAIL:] = tail.reshape(-1)
    return out


def _predict(model, obs, mask):
    return int(model.predict(obs, action_masks=mask, deterministic=True)[0])


def _instrumented_policy(model, tally, rng):
    """Returns the REAL-obs action; tallies whether scrambling the message tail
    would have flipped the decision."""
    def pol(state, pid, extras):
        obs = encode_obs(state, pid, extras.d())
        mask = ActionCodec.legal_mask(state, pid, False)
        a_real = _predict(model, obs, mask)
        a_scr = _predict(model, _scramble_tail(obs, rng), mask)
        tally["n"] += 1
        if a_real != a_scr:
            tally["flips"] += 1
        return ActionCodec.decode(a_real, state, pid)
    return pol


def _scrambling_policy(model, rng):
    """Acts on the SCRAMBLED message window (the receiver-ablation agent)."""
    def pol(state, pid, extras):
        obs = _scramble_tail(encode_obs(state, pid, extras.d()), rng)
        mask = ActionCodec.legal_mask(state, pid, False)
        return ActionCodec.decode(_predict(model, obs, mask), state, pid)
    return pol


def _model_policy(model):
    def pol(state, pid, extras):
        obs = encode_obs(state, pid, extras.d())
        mask = ActionCodec.legal_mask(state, pid, False)
        return ActionCodec.decode(_predict(model, obs, mask), state, pid)
    return pol


def _two_prop(k1, n1, k2, n2):
    from scipy.stats import norm
    if min(n1, n2) == 0:
        return {"delta": 0.0, "z": 0.0, "pvalue": 1.0}
    p1, p2 = k1 / n1, k2 / n2
    pool = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2)) or 1e-9
    z = (p1 - p2) / se
    return {"delta": p1 - p2, "z": z, "pvalue": float(1 - norm.cdf(abs(z)))}


def response_shift(model_path, n_games, seed_offset=3_000_000):
    """PRIMARY metric. All 5 seats = the model (so learned messages flow); comms on."""
    model = _load(model_path)
    tally = {"n": 0, "flips": 0}
    for s in range(seed_offset, seed_offset + n_games):
        pol = _instrumented_policy(model, tally, np.random.default_rng(s))
        run_match(s, {i: pol for i in range(5)}, record=False, comms=True)
    n = max(tally["n"], 1)
    flip_rate = tally["flips"] / n
    # binomial CI half-width (95%) as a noise yardstick
    half = 1.96 * math.sqrt(flip_rate * (1 - flip_rate) / n)
    return {"decisions": tally["n"], "flips": tally["flips"],
            "flip_rate": flip_rate, "ci95_halfwidth": half}


def winrate_ablation(model_path, n_games, seed_offset=3_000_000, num_players=5):
    """SECONDARY metric. Lone seat-0 agent vs a field of the same model, comms on.
    intact = seat-0 hears real messages; scrambled = seat-0's incoming messages
    decorrelated. Lower win-rate when scrambled => it relied on what it heard."""
    model = _load(model_path)
    field = _model_policy(model)
    intact_wins = scr_wins = 0
    for s in range(seed_offset, seed_offset + n_games):
        pols_i = {i: field for i in range(num_players)}
        if run_match(s, pols_i, num_players=num_players, record=False, comms=True)["winner"] == 0:
            intact_wins += 1
        pols_s = dict(pols_i)
        pols_s[0] = _scrambling_policy(model, np.random.default_rng(s))
        if run_match(s, pols_s, num_players=num_players, record=False, comms=True)["winner"] == 0:
            scr_wins += 1
    stats = _two_prop(intact_wins, n_games, scr_wins, n_games)
    return {"intact": intact_wins / n_games, "receiver_scrambled": scr_wins / n_games,
            "n": n_games, **stats}

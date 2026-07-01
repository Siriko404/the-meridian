"""Stage-5 observation: base obs + per-opponent interaction MEMORY.

The Stage-3 cheap-talk null and the Stage-4 fear null share a root cause the
advisor named: history a policy cannot SEE, it cannot condition on. Reciprocity,
trust, and revenge are unlearnable while the obs is memoryless. So we append, for
each of the 4 opponents (ego-centric relative seat), two running scalars:

  harm  = damage that opponent has dealt ME      -> substrate for revenge / threat
  help  = gift point-value that opponent gave ME  -> substrate for reciprocity / trust

This makes the relevant history Markov-sufficient IN the observation, so a
feed-forward policy can make cooperation *representable*. (Whether it becomes
*learnable* is the payoff-horizon question handled by the short-deal primitives.)
Kept minimal (2 features x 4 opponents = 8 dims) to avoid drowning the signal in
a high-dim obs — the same dilution that may have sunk fear.
"""
import numpy as np

from social_roulette.rl.obs import encode_obs, OBS_DIM, N_SLOTS

HARM_SCALE = 6.0    # ~ a full kill's worth of damage
HELP_SCALE = 12.0   # ~ two premium gifts
MEM_DIM = (N_SLOTS - 1) * 2
SOCIAL_OBS_DIM = OBS_DIM + MEM_DIM


def memory_features(state, learner_id):
    out = []
    for j in range(1, N_SLOTS):                 # skip slot 0 (self); ego-centric others
        other = (learner_id + j) % N_SLOTS
        h = state.harm.get((learner_id, other), 0)
        g = state.help.get((learner_id, other), 0)
        out += [min(1.0, h / HARM_SCALE), min(1.0, g / HELP_SCALE)]
    return np.asarray(out, dtype=np.float32)


def social_encode_obs(state, learner_id, extras):
    """extras = the Extras.d() dict, same as encode_obs expects."""
    base = encode_obs(state, learner_id, extras)
    return np.concatenate([base, memory_features(state, learner_id)]).astype(np.float32)

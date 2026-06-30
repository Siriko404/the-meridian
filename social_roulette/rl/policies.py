"""Model-backed seat policies (depend on rl.obs + rl.action_space).

Kept in rl/ (not observe/) so rl modules can import it without an
rl -> observe -> rl cycle.
"""
from social_roulette.rl.obs import encode_obs
from social_roulette.rl.action_space import ActionCodec


def make_model_policy(model, shoot_only=False):
    """Wrap a trained model as a take_policy_turn-compatible seat policy."""
    def pol(state, pid, extras):
        obs = encode_obs(state, pid, extras.d())
        mask = ActionCodec.legal_mask(state, pid, shoot_only)
        idx, _ = model.predict(obs, action_masks=mask, deterministic=True)
        return ActionCodec.decode(int(idx), state, pid)
    return pol

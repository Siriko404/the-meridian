"""Stage-5 action codec: the base 39 actions + a GIFT sub-action.

Layout is APPEND-ONLY on top of the base codec so we reuse it wholesale:
  0 .. 38   base ActionCodec (24 game + 15 speak)  — identical semantics
  39 .. 62  gift = 4 relative targets (r=1..4) x 6 item types

A gift decodes to Trade(abs_target, [item]) — engine transfers one item to a
teammate (legal_actions gates teammate-only + receiver-under-cap + social flag),
so the mask, not the codec, enforces legality. ACTION_N_SOCIAL = 63.
"""
import numpy as np

from social_roulette.engine.constants import Item
from social_roulette.engine.actions import Trade, legal_actions
from social_roulette.rl.action_space import ActionCodec, ACTION_N as BASE_N, _abs_seat, _rel

GIFT_ITEMS = [Item.MAGNET, Item.SHAKEDOWN, Item.GEIGER, Item.POISON, Item.PASSPORT, Item.TERMS]
N_GIFT_TARGETS = 4                      # relative offsets r = 1..4 (never self)
GIFT_N = N_GIFT_TARGETS * len(GIFT_ITEMS)
ACTION_N_SOCIAL = BASE_N + GIFT_N       # 39 + 24 = 63


class SocialActionCodec:
    @staticmethod
    def decode(idx, state, learner_id):
        if idx < BASE_N:
            return ActionCodec.decode(idx, state, learner_id)
        g = idx - BASE_N
        r = g // len(GIFT_ITEMS) + 1                 # 1..4
        item = GIFT_ITEMS[g % len(GIFT_ITEMS)]
        return Trade(_abs_seat(learner_id, r), [item])

    @staticmethod
    def _index_of(action, learner_id):
        if isinstance(action, Trade):
            r = _rel(learner_id, action.to_id)       # 1..4
            return BASE_N + (r - 1) * len(GIFT_ITEMS) + GIFT_ITEMS.index(action.items[0])
        return ActionCodec._index_of(action, learner_id)

    @staticmethod
    def legal_mask(state, learner_id, shoot_only=False):
        mask = np.zeros(ACTION_N_SOCIAL, dtype=np.bool_)
        mask[:BASE_N] = ActionCodec.legal_mask(state, learner_id, shoot_only)
        if not shoot_only:
            for a in legal_actions(state, learner_id):
                if isinstance(a, Trade):
                    mask[SocialActionCodec._index_of(a, learner_id)] = True
        return mask

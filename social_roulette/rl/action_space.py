import numpy as np

from social_roulette.engine.constants import Item
from social_roulette.engine.actions import Shoot, UseItem, Flip, cheapest_payment, legal_actions
from social_roulette.engine.state import player_by_id

ACTION_N = 24
NONTARGET = [Item.CIGARETTES, Item.MAGNIFIER, Item.SAW, Item.BEER]  # indices 5..8


class ActionCodec:
    @staticmethod
    def decode(idx, state, learner_id):
        if idx < 5:
            return Shoot(idx)
        if idx < 9:
            return UseItem(NONTARGET[idx - 5])
        if idx < 14:
            return UseItem(Item.IMMUNITY, idx - 9)
        if idx < 19:
            return UseItem(Item.HANDCUFFS, idx - 14)
        k = idx - 19
        p = player_by_id(state, learner_id)
        cost = 4 if (k == learner_id and p.flipback_discount) else 5
        return Flip(k, cheapest_payment(p, cost) or [])

    @staticmethod
    def _index_of(action):
        if isinstance(action, Shoot):
            return action.target_id
        if isinstance(action, UseItem):
            if action.item in NONTARGET:
                return 5 + NONTARGET.index(action.item)
            if action.item == Item.IMMUNITY:
                return 9 + action.target_id
            if action.item == Item.HANDCUFFS:
                return 14 + action.target_id
        if isinstance(action, Flip):
            return 19 + action.target_id
        return None

    @staticmethod
    def legal_mask(state, learner_id, shoot_only=False):
        mask = np.zeros(ACTION_N, dtype=np.bool_)
        for a in legal_actions(state, learner_id):
            i = ActionCodec._index_of(a)
            if i is not None:
                mask[i] = True
        if shoot_only:
            mask[5:] = False
        return mask

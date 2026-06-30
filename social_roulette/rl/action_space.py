import numpy as np

from social_roulette.engine.constants import Item
from social_roulette.engine.actions import Shoot, UseItem, Flip, Speak, cheapest_payment, legal_actions
from social_roulette.engine.state import player_by_id
from social_roulette.comms.vocab import SPEAK_TABLE, SPEAK_N, speak_index

N_SEATS = 5
ACTION_N = 24 + SPEAK_N
NONTARGET = [Item.CIGARETTES, Item.MAGNIFIER, Item.SAW, Item.BEER]  # indices 5..8

# Targets are EGO-CENTRIC: index r=0..4 is a relative offset; the absolute seat is
# (learner_id + r) % N_SEATS. r=0 is always self. This makes a seat-0-trained policy
# play identically from any seat (required for self-play opponents).


def _abs_seat(learner_id, r):
    return (learner_id + r) % N_SEATS


def _rel(learner_id, target_id):
    return (target_id - learner_id) % N_SEATS


class ActionCodec:
    @staticmethod
    def decode(idx, state, learner_id):
        if idx >= 24:
            act, who_rel, value = SPEAK_TABLE[idx - 24]
            target = _abs_seat(learner_id, who_rel) if who_rel is not None else None
            return Speak(act, target, value)
        if idx < 5:
            return Shoot(_abs_seat(learner_id, idx))
        if idx < 9:
            return UseItem(NONTARGET[idx - 5])
        if idx < 14:
            return UseItem(Item.IMMUNITY, _abs_seat(learner_id, idx - 9))
        if idx < 19:
            return UseItem(Item.HANDCUFFS, _abs_seat(learner_id, idx - 14))
        k = _abs_seat(learner_id, idx - 19)
        p = player_by_id(state, learner_id)
        cost = 4 if (k == learner_id and p.flipback_discount) else 5
        return Flip(k, cheapest_payment(p, cost) or [])

    @staticmethod
    def _index_of(action, learner_id):
        if isinstance(action, Speak):
            who_rel = _rel(learner_id, action.target) if action.target is not None else None
            return 24 + speak_index(action.act, who_rel, action.value)
        if isinstance(action, Shoot):
            return _rel(learner_id, action.target_id)
        if isinstance(action, UseItem):
            if action.item in NONTARGET:
                return 5 + NONTARGET.index(action.item)
            if action.item == Item.IMMUNITY:
                return 9 + _rel(learner_id, action.target_id)
            if action.item == Item.HANDCUFFS:
                return 14 + _rel(learner_id, action.target_id)
        if isinstance(action, Flip):
            return 19 + _rel(learner_id, action.target_id)
        return None

    @staticmethod
    def legal_mask(state, learner_id, shoot_only=False):
        mask = np.zeros(ACTION_N, dtype=np.bool_)
        for a in legal_actions(state, learner_id):
            i = ActionCodec._index_of(a, learner_id)
            if i is not None:
                mask[i] = True
        if shoot_only:
            mask[5:] = False
        return mask

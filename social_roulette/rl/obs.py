import numpy as np

from social_roulette.engine.constants import Item, MAX_COVER
from social_roulette.engine.state import player_by_id
from social_roulette.engine.endgame import teams_active
from social_roulette.comms.vocab import ACT_N

ITEMS = [Item.MAGNET, Item.SHAKEDOWN, Item.GEIGER, Item.POISON, Item.PASSPORT, Item.TERMS]
N_SLOTS = 5
PER_SLOT = 9       # alive, is_self, is_ally, is_enemy, cover, shaken, poisoned, learner_immunized_them, they_immunized_learner
GLOBALS = 22       # own_cover(1) own_inv(6) flipback(1) scan(3) item_counts(6) ann_total(1) ann_live(1) fired(1) poison_armed(1) bonus(1)
MSG_K = 8          # last-K messages heard
MSG_FEATURES = 5   # has, speaker_rel, act, target_rel, value (re-relativized per listener)
OBS_DIM = N_SLOTS * PER_SLOT + GLOBALS + MSG_K * MSG_FEATURES


def _scan_feats(ex):
    """3 floats (same width the old peek one-hot used): scanned?, live/2, of/2."""
    if ex.get("scan_live") is None:
        return [0.0, 0.0, 0.0]
    return [1.0, ex["scan_live"] / 2.0, ex["scan_of"] / 2.0]


def encode_obs(state, learner_id, extras):
    me = player_by_id(state, learner_id)
    ta = teams_active(state)
    vec = []
    for j in range(N_SLOTS):
        k = (learner_id + j) % N_SLOTS     # ego-centric: slot 0 = self, others rotate
        p = player_by_id(state, k)
        is_self = (k == learner_id)
        is_ally = (not is_self) and ta and p.team == me.team
        is_enemy = (not is_self) and (not is_ally)
        vec += [
            1.0 if p.alive else 0.0,
            1.0 if is_self else 0.0,
            1.0 if is_ally else 0.0,
            1.0 if is_enemy else 0.0,
            p.cover / MAX_COVER,
            1.0 if p.shaken else 0.0,
            1.0 if p.poison_tick is not None else 0.0,
            1.0 if learner_id in p.immunity_against else 0.0,
            1.0 if k in me.immunity_against else 0.0,
        ]
    vec.append(me.cover / MAX_COVER)
    vec += [me.inventory.get(it, 0) / 3.0 for it in ITEMS]
    vec.append(1.0 if me.flipback_discount else 0.0)
    vec += _scan_feats(extras)
    counts = {it: 0 for it in ITEMS}
    for p in state.players:
        for it, c in p.inventory.items():
            counts[it] += c
    vec += [counts[it] / (5 * 3.0) for it in ITEMS]
    vec.append((extras["announced_total"] or 0) / 30.0)
    vec.append((extras["announced_live"] or 0) / 30.0)
    vec.append(state.chamber.pos / 30.0)
    vec.append(1.0 if state.poison_armed else 0.0)
    vec.append(1.0 if state.bonus_pending else 0.0)
    recent = state.messages[-MSG_K:]
    for _ in range(MSG_K - len(recent)):
        vec += [0.0] * MSG_FEATURES
    for m in recent:
        spk_rel = (m.speaker - learner_id) % N_SLOTS
        tgt_rel = ((m.target - learner_id) % N_SLOTS) if m.target is not None else 0
        vec += [1.0, spk_rel / N_SLOTS, m.act / ACT_N, tgt_rel / N_SLOTS,
                0.0 if m.value is None else float(m.value)]
    return np.asarray(vec, dtype=np.float32)

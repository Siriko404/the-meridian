import numpy as np

from social_roulette.engine.constants import Item, MAX_LIVES
from social_roulette.engine.state import player_by_id
from social_roulette.engine.endgame import teams_active

ITEMS = [Item.BEER, Item.HANDCUFFS, Item.MAGNIFIER, Item.SAW, Item.CIGARETTES, Item.IMMUNITY]
N_SLOTS = 5
PER_SLOT = 8       # alive, is_self, is_ally, is_enemy, lives, handcuffed, learner_immunized_them, they_immunized_learner
GLOBALS = 22       # own_lives(1) own_inv(6) flipback(1) peek(3) item_counts(6) ann_total(1) ann_live(1) fired(1) saw(1) bonus(1)
OBS_DIM = N_SLOTS * PER_SLOT + GLOBALS


def _peek_onehot(v):
    return [1.0 if v == "live" else 0.0, 1.0 if v == "blank" else 0.0, 1.0 if v == "unknown" else 0.0]


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
            p.lives / MAX_LIVES,
            1.0 if p.handcuffed else 0.0,
            1.0 if learner_id in p.immunity_against else 0.0,
            1.0 if k in me.immunity_against else 0.0,
        ]
    vec.append(me.lives / MAX_LIVES)
    vec += [me.inventory.get(it, 0) / 3.0 for it in ITEMS]
    vec.append(1.0 if me.flipback_discount else 0.0)
    vec += _peek_onehot(extras["known_next_shell"])
    counts = {it: 0 for it in ITEMS}
    for p in state.players:
        for it, c in p.inventory.items():
            counts[it] += c
    vec += [counts[it] / (5 * 3.0) for it in ITEMS]
    vec.append((extras["announced_total"] or 0) / 30.0)
    vec.append((extras["announced_live"] or 0) / 30.0)
    vec.append(state.chamber.pos / 30.0)
    vec.append(1.0 if state.saw_active else 0.0)
    vec.append(1.0 if state.bonus_pending else 0.0)
    return np.asarray(vec, dtype=np.float32)

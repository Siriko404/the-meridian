import math

from .constants import Item, MAX_LIVES, CONSUMPTION_MULT
from .state import player_by_id, living_players


def consumption_limit(state):
    return math.floor(len(living_players(state)) * CONSUMPTION_MULT)


def cap_reached(state, item):
    return state.use_counts.get(item, 0) >= consumption_limit(state)


def reset_caps(state):
    state.use_counts = {}


def _consume(state, p, item):
    p.inventory[item] -= 1
    if p.inventory[item] == 0:
        del p.inventory[item]
    state.use_counts[item] = state.use_counts.get(item, 0) + 1


def apply_item(state, player_id, item, target_id=None):
    p = player_by_id(state, player_id)
    if item == Item.CIGARETTES:
        if p.lives >= MAX_LIVES:
            raise ValueError("cigarettes unusable at max life")
        p.lives += 1
        _consume(state, p, item)
        return {"healed": 1}
    if item == Item.MAGNIFIER:
        _consume(state, p, item)
        return {"peek": state.chamber.current()}
    if item == Item.SAW:
        if state.saw_used_this_turn:
            raise ValueError("saw already used this turn")
        state.saw_active = True
        state.saw_used_this_turn = True
        _consume(state, p, item)
        return {"saw": True}
    if item == Item.BEER:
        shell = state.chamber.current()
        if shell is not None:
            del state.chamber.shells[state.chamber.pos]
        _consume(state, p, item)
        return {"discarded": shell, "emptied": state.chamber.is_empty()}
    if item == Item.IMMUNITY:
        if target_id is None or target_id == player_id:
            raise ValueError("immunity needs non-self target")
        player_by_id(state, target_id).immunity_against.add(player_id)
        _consume(state, p, item)
        return {"immunity_on": target_id}
    if item == Item.HANDCUFFS:
        if target_id is None or target_id == player_id:
            raise ValueError("handcuffs need non-self target")
        t = player_by_id(state, target_id)
        if t.handcuffed:
            raise ValueError("already handcuffed (no stacking)")
        t.handcuffed = True
        _consume(state, p, item)
        return {"handcuffed": target_id}
    raise ValueError(f"unknown item {item}")

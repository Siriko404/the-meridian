import math

from .constants import Item, Bullet, MAX_COVER, CONSUMPTION_MULT
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
    if item == Item.PASSPORT:
        if p.cover >= MAX_COVER:
            raise ValueError("passport unusable at max life")
        p.cover += 1
        _consume(state, p, item)
        return {"healed": 1}
    if item == Item.GEIGER:
        # Census, not a peek (itemsession 2026-07-10): how many of the next
        # min(2, remaining) bullets are LIVE — never which. Private to the user.
        _consume(state, p, item)
        window = state.chamber.bullets[state.chamber.pos:state.chamber.pos + 2]
        live = sum(1 for b in window if b == Bullet.LIVE)
        return {"scan_live": live, "scan_of": len(window)}
    if item == Item.POISON:
        if state.poison_used_this_turn:
            raise ValueError("poison already used this turn")
        state.poison_armed = True
        state.poison_used_this_turn = True
        _consume(state, p, item)
        return {"poison": True}
    if item == Item.MAGNET:
        bullet = state.chamber.current()
        if bullet is not None:
            del state.chamber.bullets[state.chamber.pos]
        _consume(state, p, item)
        return {"discarded": bullet, "emptied": state.chamber.is_empty()}
    if item == Item.TERMS:
        if target_id is None or target_id == player_id:
            raise ValueError("terms need non-self target")
        t = player_by_id(state, target_id)
        if player_id in t.immunity_against:
            raise ValueError("terms already placed by this caster")
        t.immunity_against.add(player_id)
        _consume(state, p, item)
        return {"immunity_on": target_id}
    if item == Item.SHAKEDOWN:
        if target_id is None or target_id == player_id:
            raise ValueError("handcuffs need non-self target")
        t = player_by_id(state, target_id)
        if t.shaken:
            raise ValueError("already shaken (no stacking)")
        t.shaken = True
        _consume(state, p, item)
        return {"shaken": target_id}
    raise ValueError(f"unknown item {item}")

from .constants import ITEM_TABLE
from .state import living_players, can_receive
from .chamber import load_chamber
from .items import reset_caps


def draw_items_for_all(state, n=2):
    draws = {}
    for p in living_players(state):
        rec = {"attempted": [], "received": []}
        for _ in range(n):
            item = ITEM_TABLE[state.rng.randint(1, 6)]
            rec["attempted"].append(item)
            if can_receive(p, item):
                p.inventory[item] = p.inventory.get(item, 0) + 1
                rec["received"].append(item)
        draws[p.id] = rec
    return draws


def reload_on_empty(state):
    state.chamber = load_chamber(state.rng, len(living_players(state)))
    return draw_items_for_all(state, 2)


def reload_on_death(state):
    state.chamber = load_chamber(state.rng, len(living_players(state)))
    reset_caps(state)

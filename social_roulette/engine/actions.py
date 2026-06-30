from dataclasses import dataclass, field

from .constants import Item, POINT_VALUE, MAX_LIVES
from .state import player_by_id, living_players
from .items import cap_reached
from .endgame import legal_targets


@dataclass
class UseItem:
    item: object
    target_id: int = None


@dataclass
class Flip:
    target_id: int
    sacrifice: list = field(default_factory=list)


@dataclass
class Trade:
    to_id: int
    items: list = field(default_factory=list)


@dataclass
class Shoot:
    target_id: int


@dataclass
class EndSubactions:
    pass


def cheapest_payment(player, cost):
    items = []
    for it, c in player.inventory.items():
        items += [it] * c
    items.sort(key=lambda it: POINT_VALUE[it], reverse=True)
    chosen = []
    total = 0
    for it in items:
        if total >= cost:
            break
        chosen.append(it)
        total += POINT_VALUE[it]
    return chosen if total >= cost else None


def legal_actions(state, player_id):
    p = player_by_id(state, player_id)
    acts = [Shoot(t) for t in legal_targets(state, player_id)]
    others = [q.id for q in living_players(state) if q.id != player_id]
    for it in list(p.inventory):
        if cap_reached(state, it):
            continue
        if it == Item.CIGARETTES:
            if p.lives < MAX_LIVES:
                acts.append(UseItem(it))
        elif it == Item.SAW:
            if not state.saw_used_this_turn:
                acts.append(UseItem(it))
        elif it in (Item.MAGNIFIER, Item.BEER):
            acts.append(UseItem(it))
        elif it == Item.IMMUNITY:
            for o in others:
                acts.append(UseItem(it, o))
        elif it == Item.HANDCUFFS:
            for o in others:
                if not player_by_id(state, o).handcuffed:
                    acts.append(UseItem(it, o))
    for q in living_players(state):
        pay = cheapest_payment(p, 4 if (q.id == player_id and p.flipback_discount) else 5)
        if pay is not None:
            acts.append(Flip(q.id, pay))
    return acts

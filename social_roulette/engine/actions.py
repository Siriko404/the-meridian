from dataclasses import dataclass, field

from .constants import Item, POINT_VALUE, MAX_LIVES
from .state import player_by_id, living_players, can_receive
from .items import cap_reached
from .endgame import legal_targets

MSG_CAP = 2


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


@dataclass
class Speak:
    act: int
    target: int = None     # absolute seat id, or None
    value: int = None      # 0/1, or None


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
    if state.comms_enabled and not state.bonus_pending and state.msgs_this_turn < MSG_CAP:
        from social_roulette.comms.vocab import SPEAK_TABLE
        n = len(state.players)
        for act, who_rel, value in SPEAK_TABLE:
            target = (player_id + who_rel) % n if who_rel is not None else None
            if target is not None and not player_by_id(state, target).alive:
                continue
            acts.append(Speak(act, target, value))
    if state.social_enabled and not state.bonus_pending:
        for it in list(p.inventory):
            for q in others:
                mate = player_by_id(state, q)
                if mate.team == p.team and can_receive(mate, it):
                    acts.append(Trade(q, [it]))
    return acts

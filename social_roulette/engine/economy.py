from .constants import POINT_VALUE, Team
from .state import player_by_id


def pay_cost(state, player_id, cost, sacrifice):
    p = player_by_id(state, player_id)
    owned = dict(p.inventory)
    for it in sacrifice:
        if owned.get(it, 0) <= 0:
            raise ValueError("cannot sacrifice unowned item")
        owned[it] -= 1
    if sum(POINT_VALUE[it] for it in sacrifice) < cost:
        raise ValueError("insufficient payment")
    for it in sacrifice:
        p.inventory[it] -= 1
        if p.inventory[it] == 0:
            del p.inventory[it]


def flip_team(state, payer_id, target_id, sacrifice):
    target = player_by_id(state, target_id)
    discounted = (payer_id == target_id and target.flipback_discount)
    pay_cost(state, payer_id, 4 if discounted else 5, sacrifice)
    target.team = Team.RED if target.team == Team.BLUE else Team.BLUE
    if discounted:
        target.flipback_discount = False
    elif payer_id != target_id:
        target.flipback_discount = True

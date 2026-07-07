from .constants import POINT_VALUE, Team, MAX_PER_TYPE, MAX_TOTAL
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


def fine_cheapest(state, player_id):
    """Timeout fine (guide:175): burn the player's cheapest item by point value,
    ties broken by state.rng. Cap-free (a penalty, like sacrifice). None if broke."""
    p = player_by_id(state, player_id)
    if not p.inventory:
        return None
    low = min(POINT_VALUE[it] for it in p.inventory)
    ties = sorted((it for it in p.inventory if POINT_VALUE[it] == low), key=lambda it: it.name)
    item = state.rng.choice(ties)
    p.inventory[item] -= 1
    if p.inventory[item] == 0:
        del p.inventory[item]
    return item


def _post_swap(inv, gives, gets):
    out = dict(inv)
    for it in gives:
        if out.get(it, 0) <= 0:
            raise ValueError("cannot give unowned item")
        out[it] -= 1
        if out[it] == 0:
            del out[it]
    for it in gets:
        out[it] = out.get(it, 0) + 1
    if any(c > MAX_PER_TYPE for c in out.values()) or sum(out.values()) > MAX_TOTAL:
        raise ValueError("swap breaks inventory caps")
    return out


def swap(state, a_id, b_id, give_a, give_b):
    """All-or-nothing two-way transfer (spec 4.5, audit a5): validated against the
    POST-swap inventories; no mid-flight can_receive re-checks; nothing moves on failure."""
    a = player_by_id(state, a_id)
    b = player_by_id(state, b_id)
    new_a = _post_swap(a.inventory, give_a, give_b)
    new_b = _post_swap(b.inventory, give_b, give_a)
    a.inventory = new_a
    b.inventory = new_b

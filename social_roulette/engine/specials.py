"""SPECIALS — the second rail (itemsession 2026-07-10).

Every player holds all three at game start; never drawn or recharged; one-shot;
0 pts (un-finable, un-spendable — fine_cheapest and pay_cost read `inventory`,
which specials never enter); tradable; usable on anyone including teammates.
ALL specials are ANONYMOUS: no public event carries them.

  WARRANT  inspect one player's FULL hand (regulars + specials), take ONE thing
  DRAGNET  privately see every player's REGULAR items (specials stay dark)
  HANDLER  reactive — steals a shot call; lives in the online room, not here
"""
from .constants import Item
from .state import player_by_id, living_players, can_receive

WARRANT = "WARRANT"
DRAGNET = "DRAGNET"
HANDLER = "HANDLER"
SPECIALS = (WARRANT, DRAGNET, HANDLER)


def starting_specials():
    return {WARRANT: 1, DRAGNET: 1, HANDLER: 1}


def _spend(p, kind):
    if p.specials.get(kind, 0) < 1:
        raise ValueError(f"no {kind} left")
    p.specials[kind] -= 1


def dragnet(state, pid):
    """Consume DRAGNET: every player's regular hand — specials NOT shown (ruling 1)."""
    p = player_by_id(state, pid)
    _spend(p, DRAGNET)
    return {"hands": {q.id: {it.name: c for it, c in q.inventory.items()}
                      for q in living_players(state) if q.id != pid}}


def warrant_inspect(state, pid, target_id):
    """Consume WARRANT: the search happens now — full hand INCLUDING specials.
    The take is a second step (interactive for humans)."""
    if target_id == pid:
        raise ValueError("warrant needs another player")
    p = player_by_id(state, pid)
    t = player_by_id(state, target_id)
    if not t.alive:
        raise ValueError("cannot search the dead")
    _spend(p, WARRANT)
    return {"target": target_id,
            "hand": {it.name: c for it, c in t.inventory.items()},
            "specials": {k: c for k, c in t.specials.items() if c > 0}}


def warrant_take(state, pid, target_id, name):
    """Second step: take ONE thing seen by the inspection. `name` is an Item name
    or a special kind; None/"" = take nothing (walk away)."""
    if not name:
        return {"took": None}
    p = player_by_id(state, pid)
    t = player_by_id(state, target_id)
    if name in SPECIALS:
        if t.specials.get(name, 0) < 1:
            raise ValueError("they no longer hold that")
        t.specials[name] -= 1
        p.specials[name] = p.specials.get(name, 0) + 1
        return {"took": name}
    it = Item[name]
    if t.inventory.get(it, 0) < 1:
        raise ValueError("they no longer hold that")
    if not can_receive(p, it):
        raise ValueError("no room in your kit")
    t.inventory[it] -= 1
    if t.inventory[it] == 0:
        del t.inventory[it]
    p.inventory[it] = p.inventory.get(it, 0) + 1
    return {"took": name}

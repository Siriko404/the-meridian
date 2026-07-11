"""Per-seat view serializer — the ONLY game state a client ever receives.

Public info + that seat's own hand + its own Geiger peek + its own legal
actions. The full GameState (other players' hands, the bullet order) is never
serialized. Faithful to game_guide "Information & Visibility".
"""
from social_roulette.engine.state import player_by_id
from social_roulette.engine.actions import Shoot, UseItem, Flip, PayTax, legal_actions

ITEMS = ["MAGNET", "SHAKEDOWN", "GEIGER", "POISON", "PASSPORT", "TERMS"]


def _title(name):
    return name.capitalize()


def action_label(state, action):
    if isinstance(action, PayTax):
        return {6: "Pay 6 - full turn", 4: "Pay 4 - silent turn"}.get(action.tier, "Skip the turn")
    if isinstance(action, Shoot):
        return "Shoot yourself" if action.target_id == state.current_id else f"Shoot P{action.target_id}"
    if isinstance(action, UseItem):
        base = f"Use {_title(action.item.name)}"
        return f"{_title(action.item.name)} on P{action.target_id}" if action.target_id is not None else base
    if isinstance(action, Flip):
        return f"Flip P{action.target_id}"
    return str(action)


def action_shape(action):
    """Structured form so the mobile UI maps a verb + a seat-tap to ONE legal
    action (kind, item, target) — no label-string parsing. (kind,item,target) is
    unique across a turn's legal actions: see engine.actions.legal_actions."""
    if isinstance(action, Shoot):
        return {"kind": "shoot", "item": None, "target": action.target_id}
    if isinstance(action, UseItem):
        return {"kind": "item", "item": action.item.name, "target": action.target_id}
    if isinstance(action, Flip):
        return {"kind": "flip", "item": None, "target": action.target_id}
    if isinstance(action, PayTax):
        return {"kind": "tax", "item": None, "target": None, "tier": action.tier}
    return {"kind": "other", "item": None, "target": None}


def seat_view(state, seat, ex, feed=None, seating=None):
    me = player_by_id(state, seat)
    # immune_from = the caster ids this player is BARRED from shooting (public, like flips).
    # P1.immune_from=[3] renders "P3" above P1 → P3 put immunity on P1; clears when P1 shoots.
    players = [{"id": p.id, "team": p.team.name, "cover": p.cover, "alive": p.alive,
                "shaken": p.shaken, "poisoned": p.poison_tick is not None,
                "immune_from": sorted(p.immunity_against)}
               for p in state.players]
    counts = {it: 0 for it in ITEMS}
    for p in state.players:
        for it, c in p.inventory.items():
            counts[it.name] += c
    legal = []
    if state.winner is None and state.current_id == seat:
        for i, a in enumerate(legal_actions(state, seat)):
            entry = {"i": i, "label": action_label(state, a), **action_shape(a)}
            if isinstance(a, Flip):   # point cost the client's payment picker must cover (4 = flip-back)
                entry["cost"] = 4 if (a.target_id == seat and me.flipback_discount) else 5
            legal.append(entry)
    return {
        "you": seat,
        "players": players,
        # fixed physical seating (turn order) — the ring is laid out by this so turns advance
        # to ADJACENT seats and the turn-dot proceeds in order (game_guide:166, public).
        "order": list(seating) if seating is not None else [p.id for p in state.players],
        "your_hand": {it.name: c for it, c in me.inventory.items()},
        "item_counts": counts,
        # NO persistent chamber counts — game_guide:159 announces total/live ONCE at load, then
        # players track depletion from memory. Counts ride the announce/reload EVENTS only.
        # own GEIGER scan of the next-2 window (private): {"live","of"} or None
        "scan": ({"live": ex["scan_live"], "of": ex["scan_of"]}
                 if ex.get("scan_live") is not None else None),
        "current": state.current_id,
        "winner": state.winner,
        "legal": legal,
        "feed": list(feed or []),
    }

"""Per-seat view serializer — the ONLY game state a client ever receives.

Public info + that seat's own hand + its own Magnifier peek + its own legal
actions. The full GameState (other players' hands, the shell order) is never
serialized. Faithful to game_guide "Information & Visibility".
"""
from social_roulette.engine.state import player_by_id
from social_roulette.engine.actions import Shoot, UseItem, Flip, legal_actions

ITEMS = ["BEER", "HANDCUFFS", "MAGNIFIER", "SAW", "CIGARETTES", "IMMUNITY"]


def _title(name):
    return name.capitalize()


def action_label(state, action):
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
    return {"kind": "other", "item": None, "target": None}


def seat_view(state, seat, ex, feed=None):
    me = player_by_id(state, seat)
    players = [{"id": p.id, "team": p.team.name, "lives": p.lives,
                "alive": p.alive, "handcuffed": p.handcuffed} for p in state.players]
    counts = {it: 0 for it in ITEMS}
    for p in state.players:
        for it, c in p.inventory.items():
            counts[it.name] += c
    legal = []
    if state.winner is None and state.current_id == seat:
        legal = [{"i": i, "label": action_label(state, a), **action_shape(a)}
                 for i, a in enumerate(legal_actions(state, seat))]
    return {
        "you": seat,
        "players": players,
        "your_hand": {it.name: c for it, c in me.inventory.items()},
        "item_counts": counts,
        "chamber": {"total": ex["announced_total"], "live": ex["announced_live"], "fired": state.chamber.pos},
        "peek": ex["known_next_shell"],
        "current": state.current_id,
        "winner": state.winner,
        "legal": legal,
        "feed": list(feed or []),
    }

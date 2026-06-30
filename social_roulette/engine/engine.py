from .state import player_by_id, living_ids
from .shooting import resolve_shot
from .reload import reload_on_empty, reload_on_death, draw_items_for_all
from .endgame import assert_legal_shot, winner, next_living_after


def _on_turn_start(state, pid):
    state.saw_used_this_turn = False


def _set_turn_to(state, start_id):
    living = living_ids(state)
    cur = start_id
    for _ in range(len(state.order) + 1):
        p = player_by_id(state, cur)
        if p.handcuffed:
            p.handcuffed = False
            cur = next_living_after(state.order, living, cur)
            continue
        state.current_id = cur
        _on_turn_start(state, cur)
        return
    state.current_id = start_id
    _on_turn_start(state, start_id)


def _advance_turn(state, from_id):
    player_by_id(state, from_id).flipback_discount = False
    living = living_ids(state)
    if len(living) <= 1:
        return
    _set_turn_to(state, next_living_after(state.order, living, from_id))


def take_shot(state, shooter_id, target_id):
    assert_legal_shot(state, shooter_id, target_id)
    ev = resolve_shot(state, shooter_id, target_id)
    emptied = state.chamber.is_empty()
    if ev["killed"]:
        order_before = list(state.order)
        player_by_id(state, target_id).alive = False
        state.order = [pid for pid in order_before if pid != target_id]
        reload_on_death(state)
        if emptied:
            draw_items_for_all(state, 2)
        state.bonus_pending = False
        state.saw_used_this_turn = False
        state.winner = winner(state)
        if state.winner is not None:
            return ev
        if shooter_id == target_id:
            _set_turn_to(state, next_living_after(order_before, living_ids(state), target_id))
        else:
            _set_turn_to(state, shooter_id)
        return ev
    if emptied:
        reload_on_empty(state)
    if state.bonus_pending:
        state.saw_used_this_turn = False
        return ev
    _advance_turn(state, shooter_id)
    state.winner = winner(state)
    return ev

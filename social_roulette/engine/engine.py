from .constants import Team, ITEM_TABLE, START_LIVES, Item
from .state import player_by_id, living_ids, Player, Chamber, GameState
from .rng import SeededRng
from .chamber import load_chamber
from .shooting import resolve_shot
from .items import apply_item, cap_reached
from .economy import flip_team
from .reload import reload_on_empty, reload_on_death, draw_items_for_all
from .endgame import assert_legal_shot, winner, next_living_after
from .actions import UseItem, Flip, Trade, Shoot, EndSubactions


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


def new_game(num_players, seed):
    assert num_players >= 5
    rng = SeededRng(seed)
    half = num_players // 2
    extra = num_players - 2 * half
    counts = {Team.RED: half, Team.BLUE: half}
    if extra:
        counts[Team.RED if rng.randint(0, 1) == 0 else Team.BLUE] += 1
    teams = [Team.RED] * counts[Team.RED] + [Team.BLUE] * counts[Team.BLUE]
    rng.shuffle(teams)
    players = []
    for i in range(num_players):
        inv = {}
        for _ in range(3):
            it = ITEM_TABLE[rng.randint(1, 6)]
            inv[it] = inv.get(it, 0) + 1
        players.append(Player(i, teams[i], START_LIVES, True, inv, set(), False, False))
    order = list(range(num_players))
    rng.shuffle(order)
    chamber = load_chamber(rng, num_players)
    return GameState(players=players, order=order, current_id=order[0], chamber=chamber, rng=rng)


def step(state, player_id, action):
    if isinstance(action, Shoot):
        return take_shot(state, player_id, action.target_id)
    if isinstance(action, UseItem):
        if cap_reached(state, action.item):
            raise ValueError("consumption cap reached")
        ev = apply_item(state, player_id, action.item, action.target_id)
        if action.item == Item.BEER and state.chamber.is_empty():
            reload_on_empty(state)
        return ev
    if isinstance(action, Flip):
        return flip_team(state, player_id, action.target_id, action.sacrifice)
    if isinstance(action, EndSubactions):
        return {}
    if isinstance(action, Trade):
        raise NotImplementedError("trade is Stage 1")
    raise ValueError(f"unknown action {action}")

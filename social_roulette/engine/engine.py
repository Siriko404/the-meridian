from .constants import Team, ITEM_TABLE, START_LIVES, Item, POINT_VALUE
from .state import player_by_id, living_ids, can_receive, Player, Chamber, GameState, Msg
from .rng import SeededRng
from .chamber import load_chamber
from .shooting import resolve_shot
from .items import apply_item, cap_reached
from .economy import flip_team
from .reload import reload_on_empty, reload_on_death, draw_items_for_all
from .endgame import assert_legal_shot, winner, next_living_after
from .actions import UseItem, Flip, Trade, Shoot, EndSubactions, Speak


def _on_turn_start(state, pid):
    state.saw_used_this_turn = False
    state.msgs_this_turn = 0


def _set_turn_to(state, start_id):
    living = living_ids(state)
    cur = start_id
    for _ in range(len(state.order) + 1):
        p = player_by_id(state, cur)
        if p.handcuffed:
            state.last_skipped.append(cur)
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
    if ev["damage"] > 0 and shooter_id != target_id:
        key = (target_id, shooter_id)
        state.harm[key] = state.harm.get(key, 0) + ev["damage"]
    emptied = state.chamber.is_empty()
    if ev["killed"]:
        order_before = list(state.order)
        player_by_id(state, target_id).alive = False
        victim = player_by_id(state, target_id)
        victim.inventory = {}                       # guide:69 — items burned
        for p in state.players:                     # guide:69 — their placed Terms expires
            p.immunity_against.discard(target_id)
        state.order = [pid for pid in order_before if pid != target_id]
        reload_on_death(state)
        if emptied:
            ev["draws"] = draw_items_for_all(state, 2)
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
        ev["draws"] = reload_on_empty(state)
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
        if action.item == Item.MAGNET and state.chamber.is_empty():
            ev["draws"] = reload_on_empty(state)
        return ev
    if isinstance(action, Flip):
        return flip_team(state, player_id, action.target_id, action.sacrifice)
    if isinstance(action, EndSubactions):
        return {}
    if isinstance(action, Speak):
        state.messages.append(Msg(turn=len(state.messages), speaker=player_id,
                                  act=action.act, target=action.target, value=action.value))
        state.msgs_this_turn += 1
        return {}
    if isinstance(action, Trade):
        giver = player_by_id(state, player_id)
        receiver = player_by_id(state, action.to_id)
        moved = []
        for it in action.items:
            if giver.inventory.get(it, 0) > 0 and can_receive(receiver, it):
                giver.inventory[it] -= 1
                if giver.inventory[it] == 0:
                    del giver.inventory[it]
                receiver.inventory[it] = receiver.inventory.get(it, 0) + 1
                moved.append(it)
        if moved:
            key = (action.to_id, player_id)
            state.help[key] = state.help.get(key, 0) + sum(POINT_VALUE[it] for it in moved)
        return {"gift": [it.name for it in moved], "to": action.to_id}
    raise ValueError(f"unknown action {action}")

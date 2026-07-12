from .constants import Team, ITEM_TABLE, START_COVER, Item, POINT_VALUE
from .state import player_by_id, living_ids, can_receive, Player, Chamber, GameState, Msg
from .rng import SeededRng
from .chamber import load_chamber
from .shooting import resolve_shot
from .items import apply_item, cap_reached
from .economy import flip_team, pay_cost
from .reload import reload_on_empty, reload_on_death
from .endgame import assert_legal_shot, winner, next_living_after
from .actions import UseItem, Flip, Trade, Shoot, EndSubactions, Speak, PayTax
from .specials import starting_specials


def _process_death(state, victim_id):
    """Shared death bookkeeping (shot AND poison-tick kills): burn the corpse's
    items, expire the Terms they placed, drop them from the rotation, honor-reload,
    update winner. RELOAD = REDRAW: the death reload deals 2 to every living player;
    the batch is returned — the caller routes it (ev["draws"] / last_draws buffer)."""
    victim = player_by_id(state, victim_id)
    victim.alive = False
    victim.inventory = {}                       # guide:69 — items burned
    victim.specials = {}                        # unused specials burn with the corpse
    for p in state.players:                     # guide:69 — their placed Terms expires
        p.immunity_against.discard(victim_id)
    state.order = [pid for pid in state.order if pid != victim_id]
    draws = reload_on_death(state)
    state.winner = winner(state)
    return draws


def _fire_ticks(state, poisoner_id):
    """Fire every pending poison tick owed to `poisoner_id` — their turn started, or
    they died (itemsession ruling: a dead poisoner's tick fires immediately). A tick
    kill cascades: the dead victim's own owed ticks (as poisoner) fire in turn.
    NO extra turn for a tick kill. Rows buffer in state.last_ticks (drained like skips)."""
    queue = [poisoner_id]
    while queue:
        pid = queue.pop(0)
        for v in [p for p in state.players if p.alive]:
            if v.poison_tick == pid:
                v.poison_tick = None
                v.cover = max(0, v.cover - 1)
                key = (v.id, pid)
                state.harm[key] = state.harm.get(key, 0) + 1
                killed = v.cover == 0
                state.last_ticks.append((v.id, pid, killed))
                if killed:
                    state.last_draws.append(_process_death(state, v.id))
                    if state.winner is not None:
                        return
                    queue.append(v.id)


def _on_turn_start(state, pid):
    state.poison_used_this_turn = False
    state.tax_silent = False
    state.msgs_this_turn = 0
    _fire_ticks(state, pid)


def _set_turn_to(state, start_id):
    cur = start_id
    for _ in range(2 * len(state.players) + 2):
        living = living_ids(state)
        if cur is None or not living:
            return
        p = player_by_id(state, cur)
        if not p.alive:                          # a tick corpse — pass on
            cur = next_living_after(state.order, living, cur)
            continue
        state.current_id = cur
        if p.shaken:                             # B3: the tax gates the turn — no auto-skip
            p.shaken = False
            state.tax_pending = True
        _on_turn_start(state, cur)               # fires ticks — a SELF-poisoned cur can die here
        if state.winner is not None or player_by_id(state, cur).alive:
            return
        cur = next_living_after(state.order, living_ids(state), cur)
    state.current_id = start_id


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
        # RELOAD = REDRAW: the death IS the reload — one batch of 2, even when the
        # fatal shot also drained the chamber (one reload, one payout — user ruling)
        ev["draws"] = _process_death(state, target_id)
        _fire_ticks(state, target_id)               # a dead poisoner's tick fires NOW (B2 ruling)
        state.bonus_pending = False
        state.poison_used_this_turn = False
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
        state.poison_used_this_turn = False
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
        players.append(Player(i, teams[i], START_COVER, True, inv, set(), False, False,
                              specials=starting_specials()))
    order = list(range(num_players))
    rng.shuffle(order)
    chamber = load_chamber(rng, num_players)
    return GameState(players=players, order=order, current_id=order[0], chamber=chamber, rng=rng)


def step(state, player_id, action):
    if isinstance(action, PayTax):
        if not (state.tax_pending and state.current_id == player_id):
            raise ValueError("no tax to pay")
        if action.tier == 0:
            state.tax_pending = False
            state.last_skipped.append(player_id)
            _advance_turn(state, player_id)
            state.winner = winner(state)
            return {"tax": "skip"}
        if action.tier not in (4, 6):
            raise ValueError("tax tier must be 0, 4 or 6")
        pay_cost(state, player_id, action.tier, action.sacrifice)
        state.tax_pending = False
        state.tax_silent = (action.tier == 4)
        return {"tax": action.tier}
    if state.tax_pending and state.current_id == player_id:
        raise ValueError("resolve the shakedown first")
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

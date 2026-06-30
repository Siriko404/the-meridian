from social_roulette.engine.engine import new_game
from social_roulette.sim.turn import take_policy_turn, random_policy, Extras


def _fresh(seed=7, n=5):
    state = new_game(n, seed)
    extras = {i: Extras() for i in range(n)}
    for e in extras.values():
        e.sync(state)
    return state, extras


def test_take_policy_turn_drives_full_game_to_winner():
    state, extras = _fresh()
    turns = 0
    while state.winner is None and turns < 20000:
        take_policy_turn(state, state.current_id, random_policy, extras)
        turns += 1
    assert state.winner is not None
    assert 0 <= state.winner < 5


def test_take_policy_turn_returns_dead_list():
    state, extras = _fresh()
    res = take_policy_turn(state, state.current_id, random_policy, extras)
    assert "dead" in res and isinstance(res["dead"], list)

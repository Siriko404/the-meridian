import hashlib

from social_roulette.engine.engine import new_game, step, take_shot
from social_roulette.engine.actions import legal_actions, Shoot
from social_roulette.engine.endgame import legal_targets


def take_random_turn(state, pid, max_sub=40):
    """Play one full turn for pid: random legal sub-actions until a shot commits."""
    for _ in range(max_sub):
        action = state.rng.choice(legal_actions(state, pid))
        if isinstance(action, Shoot):
            return take_shot(state, pid, action.target_id)
        step(state, pid, action)
    return take_shot(state, pid, state.rng.choice(legal_targets(state, pid)))


def play_game(num_players, seed, max_turns=20000):
    state = new_game(num_players, seed)
    h = hashlib.sha256()
    turns = 0
    while state.winner is None and turns < max_turns:
        pid = state.current_id
        ev = take_random_turn(state, pid)
        h.update(repr((pid, ev["bullet"].name, ev["damage"], ev["killed"])).encode())
        turns += 1
    if state.winner is None:
        raise RuntimeError("game did not terminate")
    return {"winner": state.winner, "turns": turns, "history_hash": h.hexdigest()}

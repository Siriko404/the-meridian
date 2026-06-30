import hashlib

from social_roulette.engine.engine import new_game, step, take_shot
from social_roulette.engine.actions import legal_actions, Shoot
from social_roulette.engine.endgame import legal_targets


def play_game(num_players, seed, max_turns=20000, max_sub=40):
    state = new_game(num_players, seed)
    h = hashlib.sha256()
    turns = 0
    while state.winner is None and turns < max_turns:
        pid = state.current_id
        shot = False
        for _ in range(max_sub):
            action = state.rng.choice(legal_actions(state, pid))
            if isinstance(action, Shoot):
                ev = take_shot(state, pid, action.target_id)
                h.update(repr((pid, action.target_id, ev["shell"].name, ev["damage"], ev["killed"])).encode())
                shot = True
                break
            step(state, pid, action)
        if not shot:
            tgt = state.rng.choice(legal_targets(state, pid))
            ev = take_shot(state, pid, tgt)
            h.update(repr((pid, tgt, ev["shell"].name, ev["damage"], ev["killed"])).encode())
        turns += 1
    if state.winner is None:
        raise RuntimeError("game did not terminate")
    return {"winner": state.winner, "turns": turns, "history_hash": h.hexdigest()}

"""run_match — the one canonical full-table match runner.

Plays a full game with arbitrary per-seat policies and (optionally) records every
event. Turn execution is delegated to `sim.turn.take_policy_turn`, the SAME
primitive Stage-2 self-play uses — so recorded/eval games run identical opponent
code to training. Recording is optional => zero overhead when off.

policy signature:  policy(state, pid, extras) -> engine action (Shoot/UseItem/Flip)
"""
from social_roulette.engine.engine import new_game
from social_roulette.sim.turn import take_policy_turn, random_policy, Extras
from social_roulette.rl.policies import make_model_policy  # re-export for callers
from .recorder import Recorder

# Back-compat aliases (older imports expected these names here).
_Extras = Extras

__all__ = ["run_match", "random_policy", "make_model_policy", "Extras"]


def run_match(seed, policies=None, num_players=5, match_id=None, record=True, max_turns=4000,
              comms=False, social=False):
    policies = policies or {}
    state = new_game(num_players, seed)
    state.comms_enabled = comms or social
    state.social_enabled = social
    extras = {i: Extras() for i in range(num_players)}
    for e in extras.values():
        e.sync(state)
    rec = Recorder(match_id if match_id is not None else seed) if record else None
    if rec:
        rec.match_start(state.players, num_players, seed, extras[0].total, extras[0].live)

    t = 0
    while state.winner is None and t < max_turns:
        pid = state.current_id
        pol = policies.get(pid, random_policy)
        take_policy_turn(state, pid, pol, extras, rec=rec, turn_idx=t)
        t += 1

    if rec:
        rec.match_end(t, state.winner)
    return {"winner": state.winner, "turns": t, "rows": rec.rows if rec else None}

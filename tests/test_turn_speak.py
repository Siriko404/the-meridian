from social_roulette.engine.engine import new_game
from social_roulette.sim.turn import take_policy_turn, Extras
from social_roulette.engine.actions import Speak, legal_actions, Shoot
from social_roulette.observe.events import MESSAGE
from social_roulette.observe.recorder import Recorder


def _talky_policy(state, pid, extras):
    for a in legal_actions(state, pid):
        if isinstance(a, Speak):
            return a
    return next(a for a in legal_actions(state, pid) if isinstance(a, Shoot))


def test_take_policy_turn_records_message():
    s = new_game(5, 1)
    s.comms_enabled = True
    extras = {i: Extras() for i in range(5)}
    for e in extras.values():
        e.sync(s)
    rec = Recorder(0)
    take_policy_turn(s, s.current_id, _talky_policy, extras, rec=rec, turn_idx=0)
    assert any(r["type"] == MESSAGE for r in rec.rows)
    assert len(s.messages) >= 1

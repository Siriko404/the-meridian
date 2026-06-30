from social_roulette.engine.engine import new_game, step
from social_roulette.engine.actions import Speak, legal_actions, MSG_CAP


def test_step_speak_appends_message():
    s = new_game(5, 1)
    pid = s.current_id
    step(s, pid, Speak(act=4, target=None, value=None))   # AGREE
    assert len(s.messages) == 1 and s.msgs_this_turn == 1
    m = s.messages[0]
    assert m.speaker == pid and m.act == 4


def test_speak_options_present_then_capped():
    s = new_game(5, 1)
    pid = s.current_id
    assert any(isinstance(a, Speak) for a in legal_actions(s, pid))
    for _ in range(MSG_CAP):
        step(s, pid, Speak(act=4, target=None, value=None))
    assert not any(isinstance(a, Speak) for a in legal_actions(s, pid))


def test_speak_silent_on_bonus_turn():
    s = new_game(5, 1)
    s.bonus_pending = True
    assert not any(isinstance(a, Speak) for a in legal_actions(s, s.current_id))

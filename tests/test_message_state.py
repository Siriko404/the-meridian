from social_roulette.engine.engine import new_game, take_shot
from social_roulette.engine.state import Msg
from social_roulette.engine.endgame import legal_targets


def test_state_has_message_fields():
    s = new_game(5, 1)
    assert s.messages == [] and s.msgs_this_turn == 0


def test_msgs_this_turn_resets_on_turn_advance():
    s = new_game(5, 1)
    s.msgs_this_turn = 2
    shooter = s.current_id
    tgt = next(t for t in legal_targets(s, shooter) if t != shooter)
    take_shot(s, shooter, tgt)          # advances to a new turn
    assert s.msgs_this_turn == 0


def test_msg_dataclass_fields():
    m = Msg(turn=3, speaker=0, act=1, target=2, value=None)
    assert (m.turn, m.speaker, m.act, m.target, m.value) == (3, 0, 1, 2, None)

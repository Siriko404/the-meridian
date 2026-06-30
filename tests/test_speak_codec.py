from social_roulette.engine.engine import new_game
from social_roulette.engine.actions import Speak
from social_roulette.rl.action_space import ActionCodec, ACTION_N
from social_roulette.comms.vocab import SPEAK_N


def test_action_n_grew_by_speak():
    assert ACTION_N == 24 + SPEAK_N


def test_decode_speak_roundtrips_target_to_absolute():
    s = new_game(5, 1)
    lid = s.current_id
    for idx in range(24, ACTION_N):
        a = ActionCodec.decode(idx, s, lid)
        assert isinstance(a, Speak)
        assert ActionCodec._index_of(a, lid) == idx


def test_mask_includes_speak_in_talk_phase():
    s = new_game(5, 1)
    m = ActionCodec.legal_mask(s, s.current_id, shoot_only=False)
    assert m.shape == (ACTION_N,) and m[24:].any()

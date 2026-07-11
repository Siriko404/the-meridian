from social_roulette.engine.engine import new_game
from social_roulette.rl.obs import OBS_DIM
from social_roulette.rl.social_obs import (
    social_encode_obs, memory_features, SOCIAL_OBS_DIM, MEM_DIM, HARM_SCALE)

EX = {"known_next_bullet": "unknown", "announced_total": 0, "announced_live": 0}


def test_social_obs_dim():
    assert MEM_DIM == 8
    assert SOCIAL_OBS_DIM == OBS_DIM + 8
    g = new_game(5, 0)
    assert social_encode_obs(g, 0, EX).shape == (SOCIAL_OBS_DIM,)


def test_memory_zero_at_start():
    g = new_game(5, 0)
    assert not memory_features(g, 0).any()


def test_harm_appears_at_relative_slot():
    g = new_game(5, 0)
    other = 2
    g.harm[(0, other)] = 3
    mem = memory_features(g, 0)
    j = (other - 0) % 5                    # relative offset of `other` from learner 0
    assert mem[(j - 1) * 2] == min(1.0, 3 / HARM_SCALE)

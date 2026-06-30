import pytest

from social_roulette.sim.random_agent import play_game


@pytest.mark.parametrize("seed", [0, 1, 7, 42, 99, 123, 500])
def test_same_seed_same_game(seed):
    a = play_game(8, seed)
    b = play_game(8, seed)
    assert a["winner"] == b["winner"] and a["history_hash"] == b["history_hash"] and a["turns"] == b["turns"]

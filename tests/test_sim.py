import pytest

from social_roulette.sim.random_agent import play_game


@pytest.mark.parametrize("seed", range(60))
def test_every_full_action_game_terminates(seed):
    for n in (5, 7, 10):
        res = play_game(num_players=n, seed=seed)
        assert res["winner"] is not None and res["turns"] < 20000

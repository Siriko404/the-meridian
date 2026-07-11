from social_roulette.engine.engine import new_game
from social_roulette.sim.random_agent import take_random_turn, play_game


def test_take_random_turn_advances_or_ends_game():
    s = new_game(5, seed=4)
    start = s.current_id
    take_random_turn(s, start)
    assert (s.winner is not None or s.current_id != start
            or any(p.cover < 3 for p in s.players) or s.bonus_pending)


def test_play_game_still_terminates():
    for seed in range(30):
        assert play_game(5, seed)["winner"] is not None

from social_roulette.rl.selfplay import lone_vs_field
from social_roulette.sim.turn import random_policy


def test_random_lone_vs_random_field_is_near_chance():
    # 1 random seat vs 4 random seats over symmetric 5-player games => ~0.20.
    wr = lone_vs_field(random_policy, random_policy, n=400, seed_offset=2_000_000)
    assert 0.12 < wr < 0.28


def test_eval_is_deterministic_given_seeds():
    a = lone_vs_field(random_policy, random_policy, n=120, seed_offset=2_000_000)
    b = lone_vs_field(random_policy, random_policy, n=120, seed_offset=2_000_000)
    assert a == b

from social_roulette.engine.rng import SeededRng
from social_roulette.engine.constants import Bullet, LIVE_FRACTION_MIN, LIVE_FRACTION_MAX
from social_roulette.engine.chamber import load_chamber


def test_load_invariants_across_seeds():
    for seed in range(200):
        for living in (5, 6, 8, 10):
            c = load_chamber(SeededRng(seed), living)
            total = len(c.bullets)
            live = sum(1 for s in c.bullets if s == Bullet.LIVE)
            assert live > living and LIVE_FRACTION_MIN <= live / total <= LIVE_FRACTION_MAX and c.pos == 0


def test_load_deterministic():
    assert load_chamber(SeededRng(123), 8).bullets == load_chamber(SeededRng(123), 8).bullets

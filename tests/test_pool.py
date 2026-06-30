import numpy as np
from social_roulette.rl.pool import CheckpointPool


def _factory(path):
    return lambda state, pid, extras: ("policy", path)


def test_single_entry_pool_always_samples_it():
    pool = CheckpointPool(_factory)
    pool.add("ckpt0")
    rng = np.random.default_rng(0)
    for _ in range(10):
        pol = pool.sample(rng)
        assert pol(None, 0, None) == ("policy", "ckpt0")


def test_caches_policy_per_path():
    calls = []

    def factory(path):
        calls.append(path)
        return lambda *a: path

    pool = CheckpointPool(factory)
    pool.add("a")
    pool.add("b")
    rng = np.random.default_rng(0)
    for _ in range(50):
        pool.sample(rng)
    assert calls.count("a") <= 1 and calls.count("b") <= 1


def test_sample_biases_recent():
    pool = CheckpointPool(_factory)
    for i in range(10):
        pool.add(f"c{i}")
    rng = np.random.default_rng(0)
    picks = [pool.sample(rng)(None, 0, None)[1] for _ in range(2000)]
    recent = sum(1 for p in picks if int(p[1:]) >= 5)
    assert recent > 1200  # newest half clearly over-sampled vs uniform (1000)


def test_empty_pool_raises():
    pool = CheckpointPool(_factory)
    rng = np.random.default_rng(0)
    try:
        pool.sample(rng)
        assert False, "expected ValueError"
    except ValueError:
        pass

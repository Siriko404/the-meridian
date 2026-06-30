"""CheckpointPool — frozen past selves sampled as Stage-2 opponents.

RAM-caches each checkpoint's policy (loading a model zip per reset() would
dominate wall-clock — advisor finding #1). Sampling biases recent checkpoints
(the current frontier) while sprinkling old ones to damp rock-paper-scissors
cycling (AlphaStar / OpenAI Five pattern).

`policy_factory(path) -> policy` is injected so the pool stays torch-free and
unit-testable; production passes a factory that loads a MaskablePPO and wraps it
with make_model_policy.
"""
import math


class CheckpointPool:
    def __init__(self, policy_factory, recent_frac=0.5, p_recent=0.8):
        self._factory = policy_factory
        self._paths = []          # ordered oldest -> newest
        self._cache = {}          # path -> policy callable (built once)
        self.recent_frac = recent_frac
        self.p_recent = p_recent

    def add(self, path):
        self._paths.append(path)

    def __len__(self):
        return len(self._paths)

    def _policy(self, path):
        if path not in self._cache:
            self._cache[path] = self._factory(path)
        return self._cache[path]

    def sample(self, rng):
        n = len(self._paths)
        if n == 0:
            raise ValueError("empty pool")
        if n == 1:
            return self._policy(self._paths[0])
        k = max(1, math.ceil(n * self.recent_frac))
        if rng.random() < self.p_recent:
            idx = n - 1 - int(rng.integers(0, k))   # uniform over last k
        else:
            idx = int(rng.integers(0, n))           # uniform over all
        return self._policy(self._paths[idx])

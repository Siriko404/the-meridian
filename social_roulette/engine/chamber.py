from .constants import Shell, LIVE_FRACTION_MIN, LIVE_FRACTION_MAX
from .state import Chamber


def load_chamber(rng, living_count, max_redos=1000):
    for _ in range(max_redos):
        total = 0
        live = 0
        while live <= living_count:
            d1, d2 = rng.roll_two_dice()
            total += max(d1, d2)
            live += min(d1, d2)
        if LIVE_FRACTION_MIN <= live / total <= LIVE_FRACTION_MAX:
            shells = [Shell.LIVE] * live + [Shell.BLANK] * (total - live)
            rng.shuffle(shells)
            return Chamber(shells=shells, pos=0)
    raise RuntimeError("load_chamber: could not satisfy invariants")

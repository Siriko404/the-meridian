from .constants import (Bullet, LIVE_FRACTION_MIN, LIVE_FRACTION_MAX,
                        CHAMBER_CAP_MULT, CHAMBER_CAP_FLOOR)
from .state import Chamber


def load_chamber(rng, living_count, max_redos=1000):
    cap = max(CHAMBER_CAP_MULT * living_count, CHAMBER_CAP_FLOOR)
    for _ in range(max_redos):
        total = 0
        live = 0
        while live <= living_count:
            d1, d2 = rng.roll_two_dice()
            total += max(d1, d2)
            live += min(d1, d2)
        if total <= cap and LIVE_FRACTION_MIN <= live / total <= LIVE_FRACTION_MAX:
            bullets = [Bullet.LIVE] * live + [Bullet.BLANK] * (total - live)
            rng.shuffle(bullets)
            return Chamber(bullets=bullets, pos=0)
    raise RuntimeError("load_chamber: could not satisfy invariants")

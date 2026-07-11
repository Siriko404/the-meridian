from social_roulette.engine import constants as C
from social_roulette.engine.rng import SeededRng


def test_constants_match_spec():
    assert {i.name for i in C.Item} == {"MAGNET", "SHAKEDOWN", "GEIGER", "POISON", "PASSPORT", "TERMS"}
    assert C.ITEM_TABLE == {1: C.Item.MAGNET, 2: C.Item.SHAKEDOWN, 3: C.Item.GEIGER,
                            4: C.Item.POISON, 5: C.Item.PASSPORT, 6: C.Item.TERMS}
    assert C.POINT_VALUE[C.Item.TERMS] == 6 and C.POINT_VALUE[C.Item.PASSPORT] == 6
    assert C.POINT_VALUE[C.Item.GEIGER] == 5 and C.POINT_VALUE[C.Item.POISON] == 5
    assert C.POINT_VALUE[C.Item.MAGNET] == 4 and C.POINT_VALUE[C.Item.SHAKEDOWN] == 4
    assert (C.MAX_PER_TYPE, C.MAX_TOTAL, C.START_COVER, C.MAX_COVER, C.MIN_PLAYERS) == (3, 8, 3, 5, 5)


def test_rng_deterministic():
    a, b = SeededRng(42), SeededRng(42)
    assert [a.roll_two_dice() for _ in range(20)] == [b.roll_two_dice() for _ in range(20)]


def test_rng_dice_range():
    r = SeededRng(1)
    for _ in range(100):
        d1, d2 = r.roll_two_dice()
        assert 1 <= d1 <= 6 and 1 <= d2 <= 6


def test_rng_shuffle_deterministic():
    a, b = SeededRng(7), SeededRng(7)
    x, y = list(range(10)), list(range(10))
    a.shuffle(x)
    b.shuffle(y)
    assert x == y

from enum import Enum, auto


class Item(Enum):
    MAGNET = auto()
    SHAKEDOWN = auto()
    GEIGER = auto()
    POISON = auto()
    PASSPORT = auto()
    TERMS = auto()


class Team(Enum):
    RED = auto()
    BLUE = auto()


class Bullet(Enum):
    LIVE = auto()
    BLANK = auto()


POINT_VALUE = {          # ladder ratified 2026-07-10 (itemsession): TERMS<->SHAKEDOWN swapped
    Item.PASSPORT: 6,
    Item.SHAKEDOWN: 6,
    Item.GEIGER: 5,
    Item.POISON: 5,
    Item.MAGNET: 4,
    Item.TERMS: 4,
}
ITEM_TABLE = {
    1: Item.MAGNET,
    2: Item.SHAKEDOWN,
    3: Item.GEIGER,
    4: Item.POISON,
    5: Item.PASSPORT,
    6: Item.TERMS,
}
MAX_PER_TYPE = 3
MAX_TOTAL = 8
START_COVER = 3
MAX_COVER = 5
CONSUMPTION_MULT = 1.0   # user 2026-07-10: cap = exactly the living-player count
MIN_PLAYERS = 5
LIVE_FRACTION_MIN = 0.30
LIVE_FRACTION_MAX = 0.70

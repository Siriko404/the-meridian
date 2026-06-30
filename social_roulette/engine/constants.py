from enum import Enum, auto


class Item(Enum):
    BEER = auto()
    HANDCUFFS = auto()
    MAGNIFIER = auto()
    SAW = auto()
    CIGARETTES = auto()
    IMMUNITY = auto()


class Team(Enum):
    RED = auto()
    BLUE = auto()


class Shell(Enum):
    LIVE = auto()
    BLANK = auto()


POINT_VALUE = {
    Item.IMMUNITY: 6,
    Item.CIGARETTES: 6,
    Item.MAGNIFIER: 5,
    Item.SAW: 5,
    Item.BEER: 4,
    Item.HANDCUFFS: 4,
}
ITEM_TABLE = {
    1: Item.BEER,
    2: Item.HANDCUFFS,
    3: Item.MAGNIFIER,
    4: Item.SAW,
    5: Item.CIGARETTES,
    6: Item.IMMUNITY,
}
MAX_PER_TYPE = 3
MAX_TOTAL = 8
START_LIVES = 3
MAX_LIVES = 5
CONSUMPTION_MULT = 1.3
MIN_PLAYERS = 5
LIVE_FRACTION_MIN = 0.30
LIVE_FRACTION_MAX = 0.70

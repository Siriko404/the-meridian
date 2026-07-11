"""v1 emoji vocabulary — compositional [ACT][WHO][VALUE].

5 acts, 15 concrete speak options. WHO is a RELATIVE seat offset (1..4); the
engine maps it to an absolute target. Lying = emitting a false claim (no token).
`render` turns an act + public name into the human chatroom line.
"""
from enum import IntEnum


class Act(IntEnum):
    SHOOT_INTENT = 0
    GANG_UP = 1
    NEXT_BULLET = 2
    TRUCE = 3
    AGREE = 4


ACT_N = 5
_WHO = (1, 2, 3, 4)


def _build_table():
    t = []
    for a in (Act.SHOOT_INTENT, Act.GANG_UP):
        t += [(a, w, None) for w in _WHO]
    t += [(Act.NEXT_BULLET, None, v) for v in (1, 0)]   # live, blank
    t += [(Act.TRUCE, w, None) for w in _WHO]
    t += [(Act.AGREE, None, None)]
    return t


SPEAK_TABLE = _build_table()
SPEAK_N = len(SPEAK_TABLE)
_INDEX = {(a, w, v): i for i, (a, w, v) in enumerate(SPEAK_TABLE)}


def speak_index(act, who_rel, value):
    return _INDEX[(Act(act), who_rel, value)]


def render(act, who_name, value):
    a = Act(act)
    if a == Act.SHOOT_INTENT:
        return f"I'll shoot {who_name}"
    if a == Act.GANG_UP:
        return f"everyone shoot {who_name}"
    if a == Act.NEXT_BULLET:
        return f"next bullet is {'live' if value else 'blank'}"
    if a == Act.TRUCE:
        return f"truce, {who_name}"
    return "agreed"

import pytest
from social_roulette.online.room import Room, IllegalAction


def test_all_bots_reaches_winner():
    r = Room(human_seats=set(), seed=0)          # everyone a bot => plays to completion in __init__
    assert r.winner is not None


def test_human_turn_has_legal_and_rejects_bad_input():
    r = Room(human_seats={0, 1, 2, 3, 4}, seed=0)   # all humans, nobody auto-plays
    seat = r.current
    assert len(r.view(seat)["legal"]) > 0
    with pytest.raises(IllegalAction):
        r.apply(seat, 9999)                      # index out of range
    with pytest.raises(IllegalAction):
        r.apply((seat + 1) % 5, 0)               # not that seat's turn


def test_human_action_advances_and_bots_autoplay():
    r = Room(human_seats={0}, seed=0)            # seat 0 human, rest bots
    assert r.current == 0 and r.winner is None   # leading bots auto-played in __init__
    for _ in range(200):
        if r.winner is not None:
            break
        if r.current == 0:
            r.apply(0, 0)                        # index 0 == Shoot(self)
    assert r.winner is not None

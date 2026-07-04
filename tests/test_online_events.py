"""Event-stream contract: Room.apply must expose the animatable events that
happened during the action (+ any bot turns it triggered), and NEVER leak
hidden info (shell order, foreign peeks) through them."""
from social_roulette.online.room import Room


def test_first_view_carries_only_the_announce():
    """Leading/all-bot turns run in __init__ are NOT streamed. The ONE thing the first
    view carries is the public opening chamber announce (game_guide:159), never the
    running count in the persistent view."""
    r = Room(human_seats=set(), seed=0)     # everyone a bot => finishes in __init__
    assert r.winner is not None
    assert len(r.last_events) == 1 and r.last_events[0]["type"] == "announce"
    a = r.last_events[0]
    assert a["total"] > 0 and 0 <= a["live"] <= a["total"]


def test_human_shot_emits_shot_event():
    """A human Shoot yields a 'shot' event carrying the public outcome
    (fired shell / damage / killed) — everything a client needs to animate."""
    r = Room(human_seats={0}, seed=0)        # seat 0 human, rest bots
    assert r.current == 0
    r.apply(0, 0)                            # index 0 == Shoot(self)
    shots = [e for e in r.last_events if e["type"] == "shot"]
    assert shots, "human shot must emit a 'shot' event"
    s = shots[0]
    assert s["actor"] == 0
    assert s["shell"] in ("LIVE", "BLANK")
    assert isinstance(s["killed"], bool)


def test_events_never_leak_hidden_state():
    """Streamed events expose only public animation fields — no recorder `extra`
    blob (which can carry a Magnifier peek) and no shell-order array."""
    r = Room(human_seats={0}, seed=0)
    for _ in range(200):
        if r.winner is not None:
            break
        if r.current == 0:
            r.apply(0, 0)
        for e in r.last_events:
            assert "extra" not in e                             # no raw extra blob (no peek leak)
            assert "shells" not in e                            # no shell order
            assert set(e).issubset(
                {"type", "actor", "target", "shell", "damage", "killed", "item", "total", "live"})

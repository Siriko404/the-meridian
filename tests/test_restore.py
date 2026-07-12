"""Boot restore + the cold ready-vote (spec 2026-07-11 §4): held cars survive
the server; play resumes only when everyone is present AND votes ready."""
import asyncio
import time

import pytest

from social_roulette.online import server, storage
from social_roulette.online.room import Room


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    server.LOBBIES.clear()
    return tmp_path


class FakeWS:
    def __init__(self):
        self.sent = []

    async def send_json(self, m):
        self.sent.append(m)


def _seed_session(code="REST", n=5):
    wall = [1000.0]
    r = Room(human_seats={0, 1}, seed=4, num_players=n, now_fn=lambda: wall[0])
    wall[0] += 20                                      # burn 20s of the talk clock
    storage.session_write_meta(code, {"code": code, "seats": n, "created": 1.0,
        "members": [{"pid": "AA-1", "initials": "A.A.", "portrait": 0, "seat": 0},
                    {"pid": "BB-2", "initials": "B.B.", "portrait": 1, "seat": 1}]})
    storage.session_append(code, {"t": 1.0, "gen": r.gen, "snapshot": r.to_dict()})
    return r, wall


def test_restore_builds_held_cold_lobby():
    r, wall = _seed_session()
    left = r.phase_ends_at - wall[0]
    server.restore_sessions()
    lb = server.LOBBIES["REST"]
    assert lb.cold is True
    assert lb.room.held_since is not None              # held until the vote
    assert lb.room.held_remaining == pytest.approx(left, abs=0.01)
    assert [m["pid"] for m in lb.members] == ["AA-1", "BB-2"]
    assert lb.members[0]["host"] is True               # the original conductor
    assert all(m["ws"] is None for m in lb.members)


def test_cold_release_needs_presence_and_votes():
    async def run():
        _seed_session()
        server.restore_sessions()
        lb = server.LOBBIES["REST"]
        left = lb.room.held_remaining
        lb.members[0]["ws"] = FakeWS()
        lb.members[0]["ready"] = True
        await server._try_cold_release(lb)             # B still missing
        assert lb.cold is True and lb.room.held_since is not None
        lb.members[1]["ws"] = FakeWS()
        await server._try_cold_release(lb)             # B aboard but not ready
        assert lb.cold is True
        lb.members[1]["ready"] = True
        await server._try_cold_release(lb)             # all present + all voted
        assert lb.cold is False and lb.room.held_since is None
        assert lb.room.phase_ends_at == pytest.approx(time.time() + 3.0 + left, abs=1.0)
        if lb.deadline_task:
            lb.deadline_task.cancel()
    asyncio.run(run())


def test_cold_vote_tally_rides_the_view():
    async def run():
        _seed_session()
        server.restore_sessions()
        lb = server.LOBBIES["REST"]
        lb.members[0]["ws"] = FakeWS()
        lb.members[0]["ready"] = True
        await server._broadcast_views(lb)
        msg = lb.members[0]["ws"].sent[-1]
        assert msg["hold_vote"]["cold"] is True
        assert msg["hold_vote"]["ready"] == {0: True, 1: False}
        assert msg["hold"]["missing"] == [0, 1]        # room-level hold list (restore holds all)
    asyncio.run(run())


def test_cold_touch_stamps_the_signal_clock_at_first_rejoin():
    async def run():
        _seed_session()
        server.restore_sessions()
        lb = server.LOBBIES["REST"]
        old = lb.room.held_since
        lb.members[0]["ws"] = FakeWS()
        server._cold_touch(lb)
        assert lb.room.held_since >= time.time() - 2   # re-stamped NOW, not at boot
        assert lb.room.held_since != old
        assert lb.hold_task is not None
        lb.hold_task.cancel()
    asyncio.run(run())


def test_sync_hold_never_releases_a_cold_car():
    async def run():
        _seed_session()
        server.restore_sessions()
        lb = server.LOBBIES["REST"]
        lb.members[0]["ws"] = FakeWS()
        lb.members[1]["ws"] = FakeWS()                 # everyone present, nobody voted
        await server._sync_hold(lb)
        assert lb.cold is True and lb.room.held_since is not None
    asyncio.run(run())


def test_restore_skips_ended_and_sweeps_stale(tmp_path):
    _seed_session("DONE")
    storage.session_append("DONE", {"ended": 0})
    server.restore_sessions()
    assert "DONE" not in server.LOBBIES

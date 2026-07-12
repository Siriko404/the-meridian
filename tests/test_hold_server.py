"""Hold machinery at the server layer (spec 2026-07-11 §4), tested the
test_server_deadline way: hand-built lobbies on ONE event loop. (Starlette's
TestClient gives every websocket its own loop — the cross-socket lb.lock then
hangs; a harness artifact, uvicorn runs one loop.)"""
import asyncio

import pytest

from social_roulette.online import server, storage
from social_roulette.online.room import Room


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    return tmp_path


class FakeWS:
    def __init__(self):
        self.sent = []

    async def send_json(self, m):
        self.sent.append(m)


def _member(pid, seat, host=False, ws=None):
    return {"pid": pid, "name": pid[0] + "." + pid[1] + ".", "portrait": seat,
            "seat": seat, "ws": ws, "host": host, "ready": True}


def _lobby(wall, humans=(0, 1)):
    lb = server.Lobby("HOLDX")
    lb.members = [_member("AA-1", 0, host=True, ws=FakeWS()),
                  _member("BB-2", 1, ws=FakeWS())]
    lb.room = Room(human_seats=set(humans), seed=1, now_fn=lambda: wall[0])
    storage.session_write_meta(lb.code, {"code": lb.code, "seats": 5, "members": []})
    return lb


def test_drop_holds_and_rejoin_releases():
    async def run():
        wall = [1000.0]
        lb = _lobby(wall)
        left = lb.room.phase_ends_at - wall[0]
        lb.members[1]["ws"] = None                    # b drops off the car
        await server._sync_hold(lb)
        assert lb.room.held_since is not None
        assert lb.room.hold_missing == {1}
        assert lb.room.hold_chooser == 0              # the conductor owns the call
        a_view = lb.members[0]["ws"].sent[-1]
        assert a_view["hold"]["missing"] == [1]       # everyone SEES the hold
        assert a_view["phase_ends_at"] is None        # frozen clock rides the view
        lb.members[1]["ws"] = FakeWS()                # b returns with the same papers
        await server._sync_hold(lb)
        assert lb.room.held_since is None
        assert lb.room.phase_ends_at == pytest.approx(wall[0] + 3.0 + left)
        assert "hold" not in lb.members[1]["ws"].sent[-1]
        if lb.deadline_task:                          # broadcast re-armed the deadline
            lb.deadline_task.cancel()
    asyncio.run(run())


def test_second_dropper_updates_the_hold():
    async def run():
        wall = [1000.0]
        lb = _lobby(wall)
        lb.members[1]["ws"] = None
        await server._sync_hold(lb)
        first = lb.room.held_since
        lb.members[0]["ws"] = None                    # the conductor drops too
        await server._sync_hold(lb)
        assert lb.room.held_since == first            # one hold, refreshed list
        assert lb.room.hold_missing == {0, 1}
        assert lb.room.hold_chooser is None           # nobody left to choose
    asyncio.run(run())


def test_hold_watch_expires_and_appoints_chooser():
    async def run():
        wall = [1000.0]
        lb = _lobby(wall)
        lb.members[1]["ws"] = None
        await server._sync_hold(lb)
        if lb.hold_task:
            lb.hold_task.cancel()                     # drive the watcher by hand
        import time as _t
        lb.room.held_since = _t.time() - Room.HOLD_S - 1     # 5:00 already elapsed
        await server._hold_watch(lb, lb.room.held_since)
        assert lb.room.hold_expired is True
        assert lb.room.hold_chooser == 0
        assert lb.members[0]["ws"].sent[-1]["hold"]["expired"] is True
    asyncio.run(run())


def test_choice_bot_seats_the_house_and_play_continues():
    async def run():
        wall = [1000.0]
        lb = _lobby(wall)
        lb.members[1]["ws"] = None
        await server._sync_hold(lb)
        lb.room.hold_expired = True
        err, payloads, ended = await server._apply_hold_choice(lb, 0, "bot")
        assert err is None and ended is False and payloads is not None
        assert 1 not in lb.room.human                 # the cover plays on as the house
        assert lb.house_seats[1]["name"] == "B.B."
        assert all(m["seat"] != 1 for m in lb.members)
        await server._broadcast_views(lb, payloads)
        roster = lb.members[0]["ws"].sent[-1]["roster"]
        assert roster.get(1) == "B.B."                # identity never flickers
        for _ in range(400):                          # deadlines drive it to a verdict
            if lb.room.winner is not None:
                break
            wall[0] += 200
            if lb.room.on_deadline():
                pass
        assert lb.room.winner is not None
        if lb.deadline_task:
            lb.deadline_task.cancel()
    asyncio.run(run())


def test_choice_end_closes_and_opens_the_record():
    async def run():
        wall = [1000.0]
        lb = _lobby(wall)
        lb.members[1]["ws"] = None
        await server._sync_hold(lb)
        lb.room.hold_expired = True
        err, payloads, ended = await server._apply_hold_choice(lb, 0, "end")
        assert err is None and ended is True
        assert lb.room is None
        st, path = server.record_check("HOLDX")
        assert st == 200 and path.exists()            # abandoned record downloads
    asyncio.run(run())


def test_choice_gating():
    async def run():
        wall = [1000.0]
        lb = _lobby(wall)
        lb.members[1]["ws"] = None
        await server._sync_hold(lb)
        err, _, _ = await server._apply_hold_choice(lb, 0, "bot")   # not expired yet
        assert err == "not your call"
        lb.room.hold_expired = True
        err, _, _ = await server._apply_hold_choice(lb, 1, "bot")   # not the chooser
        assert err == "not your call"
        err, _, _ = await server._apply_hold_choice(lb, 0, "nope")
        assert err == "bad payload"
    asyncio.run(run())


def test_deadline_task_never_fires_while_held():
    async def run():
        wall = [1000.0]
        lb = _lobby(wall)
        lb.members[1]["ws"] = None
        await server._sync_hold(lb)
        assert lb.deadline_task is None               # cancelled at the hold
        wall[0] += 9999
        assert lb.room.on_deadline() is False         # and the room itself refuses
    asyncio.run(run())

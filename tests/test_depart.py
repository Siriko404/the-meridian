"""The disconnect guard (timer-freeze bug, 2026-07-12). A phone reload leaves
the OLD socket lingering; the new one reclaims the seat first. When the stale
socket finally dies, its cleanup must not touch the live one — without the
guard it nulled the reclaimed ws, held the car, and the deaf client's talk
band froze at 0:30 (30 + max(0, expired)). One-loop style (test_hold_server)."""
import asyncio

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
        self.closed = False

    async def send_json(self, m):
        self.sent.append(m)

    async def close(self):
        self.closed = True


def _member(pid, seat, host=False, ws=None):
    return {"pid": pid, "name": pid[0] + "." + pid[1] + ".", "portrait": seat,
            "seat": seat, "ws": ws, "host": host, "ready": True}


def _lobby(wall, room=True):
    lb = server.Lobby("DPRT")
    lb.members = [_member("AA-1", 0, host=True, ws=FakeWS()),
                  _member("BB-2", 1, ws=FakeWS())]
    if room:
        lb.room = Room(human_seats={0, 1}, seed=1, now_fn=lambda: wall[0])
    else:
        lb.members = [dict(m, seat=None) for m in lb.members]
    storage.session_write_meta(lb.code, {"code": lb.code, "seats": 5, "members": []})
    server.LOBBIES[lb.code] = lb
    return lb


def test_stale_close_mid_game_is_ignored():
    async def run():
        wall = [1000.0]
        lb = _lobby(wall)
        stale, live = FakeWS(), lb.members[0]["ws"]   # seat already reclaimed by `live`
        await server._depart(lb, lb.members[0], stale)
        assert lb.members[0]["ws"] is live            # the live socket survives
        assert lb.room.held_since is None             # and the car never holds
    asyncio.run(run())


def test_current_close_mid_game_still_holds():
    async def run():
        wall = [1000.0]
        lb = _lobby(wall)
        ws = lb.members[0]["ws"]
        await server._depart(lb, lb.members[0], ws)
        assert lb.members[0]["ws"] is None
        assert lb.room.held_since is not None
        if lb.hold_task:
            lb.hold_task.cancel()
    asyncio.run(run())


def test_stale_close_pre_start_keeps_the_member():
    async def run():
        lb = _lobby([1000.0], room=False)
        await server._depart(lb, lb.members[0], FakeWS())
        assert len(lb.members) == 2                   # nobody stepped off
        assert lb.code in server.LOBBIES
    asyncio.run(run())


def test_stale_close_post_end_keeps_member_and_record():
    async def run():
        wall = [1000.0]
        lb = _lobby(wall)
        lb.room.state.winner = 0
        await server._depart(lb, lb.members[0], FakeWS())
        assert len(lb.members) == 2
        assert storage.session_read_meta(lb.code) is not None   # record not burned
    asyncio.run(run())

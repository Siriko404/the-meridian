"""The server _deadline task must never exit leaving NO pending task while the
room is alive. asyncio.sleep runs on the loop's MONOTONIC clock but the phase
deadline is WALL clock (room.phase_ends_at); an early wake makes
room.on_deadline() return False, and without a reschedule the phase timer is
dead forever — nobody is fined or auto-shot until an unrelated broadcast."""
import asyncio

from social_roulette.online import server
from social_roulette.online.room import Room


def _lobby(wall):
    lb = server.Lobby("TEST")
    lb.members = [{"name": "P", "token": "tok", "seat": 0, "ws": None, "host": True}]
    lb.room = Room(human_seats={0}, seed=1, now_fn=lambda: wall[0])
    return lb


async def _cancel(task):
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def test_deadline_early_wake_leaves_a_live_task(monkeypatch):
    async def run():
        wall = [1000.0]
        lb = _lobby(wall)
        ends = lb.room.phase_ends_at
        # skew: the sleep's wall read is PAST the deadline (returns immediately)
        # while the room's re-check still reads a hair BEFORE it (early wake).
        wall[0] = ends - 0.002
        monkeypatch.setattr(server.time, "time", lambda: ends + 0.003)
        await server._deadline(lb, lb.room.gen)
        assert lb.room.phase == "talk"                    # early wake: nothing acted...
        task = lb.deadline_task
        assert task is not None and not task.done()       # ...but a deadline task must LIVE ON
        await _cancel(task)
    asyncio.run(run())


def test_deadline_due_still_fires_and_reschedules(monkeypatch):
    async def run():
        wall = [1000.0]
        lb = _lobby(wall)
        ends = lb.room.phase_ends_at
        wall[0] = ends + 0.1                              # genuinely due on BOTH clocks
        monkeypatch.setattr(server.time, "time", lambda: wall[0])
        await server._deadline(lb, lb.room.gen)
        assert lb.room.phase == "decision"                # talk deadline advanced the phase
        task = lb.deadline_task
        assert task is not None and not task.done()       # and the next deadline is armed
        await _cancel(task)
    asyncio.run(run())

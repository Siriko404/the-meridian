"""Waiting-room state machine over the real WS server (spec 2026-07-11 §3):
ready gate, seats dial, join gating, DEPART lock, conductor inheritance."""
import pytest
from starlette.testclient import TestClient

from social_roulette.online import server, storage
from social_roulette.online.server import app


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    server.PROFILES.clear()
    server.LOBBIES.clear()
    return tmp_path


def _pid(fi="a", li="b"):
    return server.papers_create(fi, li, 0)[1]["pid"]


def _drain_until(ws, typ, tries=30):
    for _ in range(tries):
        m = ws.receive_json()
        if m["type"] == typ:
            return m
    raise AssertionError("never saw " + typ)


def test_depart_locked_until_all_ready():
    c = TestClient(app)
    with c.websocket_connect("/ws") as a, c.websocket_connect("/ws") as b:
        a.send_json({"type": "join", "code": "CAR1", "pid": _pid("a", "a")})
        _drain_until(a, "lobby")
        b.send_json({"type": "join", "code": "CAR1", "pid": _pid("b", "b")})
        _drain_until(b, "lobby")
        a.send_json({"type": "ready", "on": True})
        _drain_until(a, "lobby")
        a.send_json({"type": "start"})                      # b not ready → locked
        m = _drain_until(a, "error")
        assert m["msg"] == "the manifest is not ready"
        b.send_json({"type": "ready", "on": True})
        _drain_until(a, "lobby")
        a.send_json({"type": "start"})
        v = _drain_until(a, "view")
        assert v["you"] == 0 and len(v["players"]) == 5     # dial default 5 → 3 bots


def test_seats_dial_bounds_and_bot_fill():
    c = TestClient(app)
    with c.websocket_connect("/ws") as a:
        a.send_json({"type": "join", "code": "CAR2", "pid": _pid()})
        _drain_until(a, "lobby")
        for bad in (4, 13, "x"):
            a.send_json({"type": "seats", "n": bad})
            assert _drain_until(a, "error")["type"] == "error"
        a.send_json({"type": "seats", "n": 12})
        assert _drain_until(a, "lobby")["seats"] == 12
        a.send_json({"type": "ready", "on": True})
        _drain_until(a, "lobby")
        a.send_json({"type": "start"})
        v = _drain_until(a, "view")
        assert len(v["players"]) == 12                      # 1 human + 11 bots
        assert len(v["portraits"]) == 12


def test_dial_never_below_boarders_and_car_full():
    c = TestClient(app)
    socks = []
    try:
        pids = [_pid(ch, ch) for ch in "abcdef"]
        for i in range(5):
            s = c.websocket_connect("/ws").__enter__()
            socks.append(s)
            s.send_json({"type": "join", "code": "CAR3", "pid": pids[i]})
            _drain_until(s, "lobby")
        socks[0].send_json({"type": "seats", "n": 6})       # grow: legal
        _drain_until(socks[0], "lobby")
        socks[0].send_json({"type": "seats", "n": 5})       # 5 aboard: legal floor
        _drain_until(socks[0], "lobby")
        s6 = c.websocket_connect("/ws").__enter__()
        socks.append(s6)
        s6.send_json({"type": "join", "code": "CAR3", "pid": pids[5]})
        m = _drain_until(s6, "error")
        assert m["msg"] == "the car is full"                # dial gates BOARDING (the old
    finally:                                                # hole let ghosts pile in pre-start)
        for s in socks:
            s.__exit__(None, None, None)


def test_conductor_inheritance_on_leave():
    c = TestClient(app)
    with c.websocket_connect("/ws") as a:
        a.send_json({"type": "join", "code": "CAR4", "pid": _pid("a", "a")})
        _drain_until(a, "lobby")
        with c.websocket_connect("/ws") as b:
            b.send_json({"type": "join", "code": "CAR4", "pid": _pid("b", "b")})
            m = _drain_until(b, "lobby")
            assert m["host"] is False
            # conductor a walks off pre-departure…
        # …a's socket closed; b inherits the whistle
        b_lobby = None
        with c.websocket_connect("/ws") as b2:
            b2.send_json({"type": "join", "code": "CAR4", "pid": _pid("c", "c")})
            b_lobby = _drain_until(b2, "lobby")
        assert any(x["host"] for x in b_lobby["members"])


def test_empty_car_returns_to_the_yard():
    c = TestClient(app)
    with c.websocket_connect("/ws") as a:
        a.send_json({"type": "join", "code": "CAR5", "pid": _pid()})
        _drain_until(a, "lobby")
        assert "CAR5" in server.LOBBIES
    # sole boarder left pre-departure — the lobby must not leak
    import time
    for _ in range(50):
        if "CAR5" not in server.LOBBIES:
            break
        time.sleep(0.05)
    assert "CAR5" not in server.LOBBIES

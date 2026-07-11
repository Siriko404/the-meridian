"""Session journal (spec 2026-07-11 §4): meta at departure, one snapshot per
mutation, ended marker at the winner — and the last line restores the game."""
import pytest
from starlette.testclient import TestClient

from social_roulette.online import server, storage
from social_roulette.online.room import Room
from social_roulette.online.server import app


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    server.PROFILES.clear()
    server.LOBBIES.clear()
    return tmp_path


def _pid():
    return server.papers_create("a", "b", 0)[1]["pid"]


def _count_lines(code):
    with open(storage.session_path(code), encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def test_journal_grows_per_play_and_last_line_restores():
    c = TestClient(app)
    with c.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "code": "JRNL", "pid": _pid()})
        acted = False
        for _ in range(60):
            m = ws.receive_json()
            if m["type"] == "joined":
                ws.send_json({"type": "ready", "on": True})
                ws.send_json({"type": "start"})
            elif m["type"] == "view":
                meta = storage.session_read_meta("JRNL")
                assert meta["seats"] == 5 and meta["members"][0]["initials"] == "A.B."
                if not acted and m["current"] == m["you"] and m.get("phase") == "talk":
                    acted = True
                    before = _count_lines("JRNL")
                    ws.send_json({"type": "proceed"})
                elif acted:
                    assert _count_lines("JRNL") > before          # one line per play
                    last = storage.session_read_last("JRNL")
                    r2 = Room.from_dict(last["snapshot"])
                    assert r2.view(0)["phase"] == m["phase"]      # the file IS the game
                    assert r2.gen == m["gen"]
                    break
        assert acted


def test_ended_marker_closes_the_record():
    c = TestClient(app)
    with c.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "code": "JEND", "pid": _pid()})
        winner = None
        for _ in range(1000):
            m = ws.receive_json()
            if m["type"] == "joined":
                ws.send_json({"type": "ready", "on": True})
                ws.send_json({"type": "start"})
            elif m["type"] == "view":
                if m["winner"] is None:                           # sealed while running (the
                    assert server.record_check("JEND")[0] == 403  # final view rides after the
                if m["current"] == m["you"] and m["winner"] is None:   # ended marker)
                    if m.get("phase") == "talk":
                        ws.send_json({"type": "proceed"})
                    elif m.get("phase") == "decision" and m["legal"]:
                        a = next(x for x in m["legal"]
                                 if x["kind"] == "shoot" and x["target"] == m["you"])
                        ws.send_json({"type": "action", "i": a["i"]})
            elif m["type"] == "end":
                winner = m["winner"]
                break
        assert winner is not None
    assert storage.session_is_ended("JEND")
    st, path = server.record_check("JEND")
    assert st == 200 and path.exists()                            # record opens at the end

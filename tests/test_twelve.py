"""Twelve-player gates (spec 2026-07-11 §5): full games complete at 8 and 12,
specials work at 12, and the lobby dial carries 12 end-to-end."""
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


@pytest.mark.parametrize("n", [8, 12])
def test_full_room_game_completes(n):
    now = [1000.0]
    r = Room(human_seats={0}, seed=21, num_players=n, now_fn=lambda: now[0])
    for _ in range(3000):                              # deadlines drive the human; bots chain
        if r.winner is not None:
            break
        now[0] += 200
        r.on_deadline()
    assert r.winner is not None


def test_specials_legal_at_twelve():
    now = [1000.0]
    r = Room(human_seats={0}, seed=2, num_players=12, now_fn=lambda: now[0])
    assert r.phase == "talk" and r.current == 0        # rotation law: human opens
    r.use_special(0, "DRAGNET", None)
    rep = r.view(0)["dragnet_report"]
    assert len(rep) == 11                              # every OTHER kit on the train
    r.use_special(0, "WARRANT", 5)
    assert r.view(0)["warrant_pick"]["target"] == 5


def test_lobby_dial_twelve_end_to_end():
    c = TestClient(app)
    pid = server.papers_create("a", "b", 3)[1]["pid"]
    with c.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "code": "TWLV", "pid": pid})
        ws.send_json({"type": "seats", "n": 12})
        ws.send_json({"type": "ready", "on": True})
        ws.send_json({"type": "start"})
        for _ in range(40):
            m = ws.receive_json()
            if m["type"] == "view":
                assert len(m["players"]) == 12
                assert len(m["portraits"]) == 12       # every seat wears a face
                assert len(set(m["portraits"].values())) == 12   # all twelve distinct
                assert m["order"] and len(m["order"]) == 12
                break
        else:
            raise AssertionError("never saw the 12-seat view")

import json

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


def _pid(fi="a", li="b", portrait=0):
    return server.papers_create(fi, li, portrait)[1]["pid"]


def test_full_game_over_ws_no_leak():
    """Drive a whole game through the real WS server as seat 0 (rest bots);
    assert it reaches a winner, streams animatable events, and never leaks a
    foreign hand or the hidden bullet ORDER. (The single JUST-FIRED bullet IS
    public per game_guide 'Information & Visibility' and rides the event stream.)"""
    c = TestClient(app)
    with c.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "code": "TESTROOM", "pid": _pid()})
        winner = None
        saw_shot_event = False
        for _ in range(1000):
            m = ws.receive_json()
            if m["type"] == "joined":
                ws.send_json({"type": "ready", "on": True}); ws.send_json({"type": "start"})
            elif m["type"] == "view":
                blob = json.dumps(m)
                assert "bullets" not in blob                           # hidden bullet ORDER never sent
                assert "inventory" not in blob                        # no foreign hands
                assert "chamber" not in m                             # no persistent running count (game_guide:159)
                for e in m.get("events", []):
                    assert "extra" not in e                           # no raw extra (Geiger peek) leak
                    if e["type"] == "shot":
                        assert e["bullet"] in ("LIVE", "BLANK")
                        saw_shot_event = True
                if m["current"] == m["you"] and m["winner"] is None:
                    if m.get("phase") == "talk":
                        ws.send_json({"type": "proceed"})             # end talk early
                    elif m.get("phase") == "decision" and m["legal"]:
                        a = next(x for x in m["legal"]
                                 if x["kind"] == "shoot" and x["target"] == m["you"])
                        ws.send_json({"type": "action", "i": a["i"]})  # self-shoot
            elif m["type"] == "end":
                winner = m["winner"]
                break
        assert winner is not None
        assert saw_shot_event, "the event stream must carry at least one shot to animate"


def test_illegal_action_rejected_over_ws():
    c = TestClient(app)
    with c.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "code": "TESTROOM2", "pid": _pid()})
        got_error = False
        for _ in range(50):
            m = ws.receive_json()
            if m["type"] == "joined":
                ws.send_json({"type": "ready", "on": True}); ws.send_json({"type": "start"})
            elif m["type"] == "view":
                ws.send_json({"type": "action", "i": 9999})           # out of range
            elif m["type"] == "error":
                got_error = True
                break
        assert got_error


def test_proceed_trade_messages_and_chat_gate():
    """Phases over the wire: talk view -> proceed -> decision view; chat is
    rejected outside talk; roster rides every view."""
    c = TestClient(app)
    with c.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "code": "TESTROOM3", "pid": _pid()})
        saw_decision = False
        for _ in range(200):
            m = ws.receive_json()
            if m["type"] == "joined":
                ws.send_json({"type": "ready", "on": True}); ws.send_json({"type": "start"})
            elif m["type"] == "view":
                assert m["roster"].get("0") == "A.B." or m["roster"].get(0) == "A.B."
                # every seat wears a face; the human keeps their chosen frame (0)
                assert len(m["portraits"]) == 5
                assert m["portraits"].get("0") == 0 or m["portraits"].get(0) == 0
                if m["current"] == m["you"] and m.get("phase") == "talk":
                    ws.send_json({"type": "proceed"})
                elif m.get("phase") == "decision":
                    saw_decision = True
                    ws.send_json({"type": "chat", "text": "psst"})    # silence!
            elif m["type"] == "error":
                assert m["msg"] == "silence"
                break
        assert saw_decision


def test_malformed_payload_does_not_kill_socket():
    """I3: a bad int coercion (action i) must not crash the WS loop — the server
    answers 'bad payload' and the socket still services a subsequent ping."""
    c = TestClient(app)
    with c.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "code": "TESTROOM5", "pid": _pid()})
        started = False
        for _ in range(50):
            m = ws.receive_json()
            if m["type"] == "joined":
                ws.send_json({"type": "ready", "on": True}); ws.send_json({"type": "start"})
            elif m["type"] == "view" and not started:
                started = True
                ws.send_json({"type": "action", "i": "garbage"})   # non-int -> bad payload
            elif m["type"] == "error":
                assert m["msg"] == "bad payload"
                ws.send_json({"type": "ping"})                     # socket must still be alive
            elif m["type"] == "pong":
                break
        else:
            assert False, "never received pong after malformed payload"


def test_trade_offer_rejected_outside_talk_over_ws():
    c = TestClient(app)
    with c.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "code": "TESTROOM4", "pid": _pid()})
        got_error = False
        for _ in range(100):
            m = ws.receive_json()
            if m["type"] == "joined":
                ws.send_json({"type": "ready", "on": True}); ws.send_json({"type": "start"})
            elif m["type"] == "view" and m["current"] == m["you"]:
                if m.get("phase") == "talk":
                    ws.send_json({"type": "proceed"})
                elif m.get("phase") == "decision":
                    ws.send_json({"type": "trade_offer", "to": 1, "give": ["MAGNET"], "want": []})
            elif m["type"] == "error":
                got_error = True                     # decision phase / bot teammate - rejected
                break
        assert got_error


def test_join_without_papers_is_refused():
    c = TestClient(app)
    with c.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "code": "TESTROOM6", "pid": "M-FAKE"})
        m = ws.receive_json()
        assert m["type"] == "error" and m["msg"] == "papers not in order"


def test_reconnect_by_pid_reclaims_seat():
    c = TestClient(app)
    pid = _pid()
    with c.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "code": "TESTROOM7", "pid": pid})
        seat = None
        for _ in range(20):
            m = ws.receive_json()
            if m["type"] == "joined":
                ws.send_json({"type": "ready", "on": True}); ws.send_json({"type": "start"})
            elif m["type"] == "view":
                seat = m["you"]
                break
        assert seat is not None
    with c.websocket_connect("/ws") as ws:      # same papers, fresh socket
        ws.send_json({"type": "join", "code": "TESTROOM7", "pid": pid})
        for _ in range(20):
            m = ws.receive_json()
            if m["type"] == "joined":
                assert m["seat"] == seat        # the seat was held for the papers
                break
        else:
            assert False, "never rejoined"


def test_root_serves_v2_client():
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "MERIDIAN" in r.text            # v2 page brand


def test_v1_client_still_reachable():
    client = TestClient(app)
    r = client.get("/v1")
    assert r.status_code == 200
    assert "sr_ui" in r.text               # old page keeps its stylesheet

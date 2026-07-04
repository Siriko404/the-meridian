import json
from starlette.testclient import TestClient
from social_roulette.online.server import app


def test_full_game_over_ws_no_leak():
    """Drive a whole game through the real WS server as seat 0 (rest bots);
    assert it reaches a winner, streams animatable events, and never leaks a
    foreign hand or the hidden shell ORDER. (The single JUST-FIRED shell IS
    public per game_guide 'Information & Visibility' and rides the event stream.)"""
    c = TestClient(app)
    with c.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "code": "TESTROOM", "name": "A"})
        winner = None
        saw_shot_event = False
        for _ in range(1000):
            m = ws.receive_json()
            if m["type"] == "joined":
                ws.send_json({"type": "start"})
            elif m["type"] == "view":
                blob = json.dumps(m)
                assert "shells" not in blob                           # hidden shell ORDER never sent
                assert "inventory" not in blob                        # no foreign hands
                for e in m.get("events", []):
                    assert "extra" not in e                           # no raw extra (Magnifier peek) leak
                    if e["type"] == "shot":
                        assert e["shell"] in ("LIVE", "BLANK")
                        saw_shot_event = True
                if m["current"] == m["you"] and m["winner"] is None and m["legal"]:
                    ws.send_json({"type": "action", "i": 0})          # self-shoot
            elif m["type"] == "end":
                winner = m["winner"]
                break
        assert winner is not None
        assert saw_shot_event, "the event stream must carry at least one shot to animate"


def test_illegal_action_rejected_over_ws():
    c = TestClient(app)
    with c.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "code": "TESTROOM2", "name": "A"})
        got_error = False
        for _ in range(50):
            m = ws.receive_json()
            if m["type"] == "joined":
                ws.send_json({"type": "start"})
            elif m["type"] == "view":
                ws.send_json({"type": "action", "i": 9999})           # out of range
            elif m["type"] == "error":
                got_error = True
                break
        assert got_error

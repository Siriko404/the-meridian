import json
from starlette.testclient import TestClient
from social_roulette.online.server import app


def test_full_game_over_ws_no_leak():
    """Drive a whole game through the real WS server as seat 0 (rest bots);
    assert it reaches a winner AND no view frame ever leaks a foreign hand or the shell order."""
    c = TestClient(app)
    with c.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "code": "TESTROOM", "name": "A"})
        winner = None
        for _ in range(1000):
            m = ws.receive_json()
            if m["type"] == "joined":
                ws.send_json({"type": "start"})
            elif m["type"] == "view":
                blob = json.dumps(m)
                assert "LIVE" not in blob and "BLANK" not in blob     # shell order never sent
                assert "inventory" not in blob                        # no foreign hands
                if m["current"] == m["you"] and m["winner"] is None and m["legal"]:
                    ws.send_json({"type": "action", "i": 0})          # self-shoot
            elif m["type"] == "end":
                winner = m["winner"]
                break
        assert winner is not None


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

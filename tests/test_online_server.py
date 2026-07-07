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
                assert "chamber" not in m                             # no persistent running count (game_guide:159)
                for e in m.get("events", []):
                    assert "extra" not in e                           # no raw extra (Magnifier peek) leak
                    if e["type"] == "shot":
                        assert e["shell"] in ("LIVE", "BLANK")
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


def test_proceed_trade_messages_and_chat_gate():
    """Phases over the wire: talk view -> proceed -> decision view; chat is
    rejected outside talk; roster rides every view."""
    c = TestClient(app)
    with c.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "code": "TESTROOM3", "name": "A"})
        saw_decision = False
        for _ in range(200):
            m = ws.receive_json()
            if m["type"] == "joined":
                ws.send_json({"type": "start"})
            elif m["type"] == "view":
                assert m["roster"].get("0") == "A" or m["roster"].get(0) == "A"
                if m["current"] == m["you"] and m.get("phase") == "talk":
                    ws.send_json({"type": "proceed"})
                elif m.get("phase") == "decision":
                    saw_decision = True
                    ws.send_json({"type": "chat", "text": "psst"})    # silence!
            elif m["type"] == "error":
                assert m["msg"] == "silence"
                break
        assert saw_decision


def test_trade_offer_rejected_outside_talk_over_ws():
    c = TestClient(app)
    with c.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "code": "TESTROOM4", "name": "A"})
        got_error = False
        for _ in range(100):
            m = ws.receive_json()
            if m["type"] == "joined":
                ws.send_json({"type": "start"})
            elif m["type"] == "view" and m["current"] == m["you"]:
                if m.get("phase") == "talk":
                    ws.send_json({"type": "proceed"})
                elif m.get("phase") == "decision":
                    ws.send_json({"type": "trade_offer", "to": 1, "give": ["BEER"], "want": []})
            elif m["type"] == "error":
                got_error = True                     # decision phase / bot teammate — rejected
                break
        assert got_error

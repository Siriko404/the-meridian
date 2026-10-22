"""Regression tests for the online-server security fixes. Each fails on the code it replaced."""
import os

import pytest
from starlette.testclient import TestClient

from social_roulette.online import server, storage


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    server.PROFILES.clear()
    server._HITS.clear()
    return tmp_path


@pytest.mark.parametrize("code", ["../profiles", "..", "a/b", "A.B", "", "X" * 17, "AB CD", "a\x00b"])
def test_session_path_refuses_anything_but_letters_and_digits(code):
    with pytest.raises(ValueError):
        storage.session_path(code)


def test_session_path_accepts_normal_codes():
    assert storage.session_path("AB12").name == "AB12.jsonl"
    assert storage.session_path("A3F9").parent.name == "sessions"


def test_record_check_refuses_traversal_codes():
    assert server.record_check("../profiles")[0] == 404


def test_join_with_a_path_as_code_is_refused_and_writes_nothing(data_dir):
    _, p = server.papers_create("s", "k", 1)
    before = sorted(os.listdir(data_dir))
    c = TestClient(server.app)
    with c.websocket_connect("/ws") as ws:
        ws.send_json({"type": "join", "code": "../profiles", "pid": p["pid"]})
        reply = ws.receive_json()
    assert reply["type"] == "error"
    assert sorted(os.listdir(data_dir)) == before
    assert "../PROFILES" not in server.LOBBIES and "../profiles".upper() not in server.LOBBIES


def test_journeys_do_not_leak_other_members_papers_numbers():
    _, a = server.papers_create("a", "a", 1)
    _, b = server.papers_create("b", "b", 2)
    storage.session_write_meta("AAAA", {"code": "AAAA", "seats": 6, "created": 1.0,
                                        "members": [{"pid": a["pid"], "initials": "A.A."},
                                                    {"pid": b["pid"], "initials": "B.B."}]})
    st, body = server.journeys(a["pid"])
    assert st == 200 and body["journeys"] == [{"code": "AAAA", "seats": 6, "created": 1.0}]
    assert b["pid"] not in str(body)


def test_issuing_papers_is_rate_limited():
    c = TestClient(server.app)
    codes = [c.post("/papers", json={"fi": "A", "li": "B", "portrait": 1}).status_code for _ in range(12)]
    assert codes[:10] == [200] * 10
    assert codes[10:] == [429, 429]


def test_papers_lookup_is_rate_limited():
    c = TestClient(server.app)
    codes = [c.get("/papers?fi=A&li=B&pid=ZZZZZ").status_code for _ in range(32)]
    assert 429 in codes and codes[0] == 404


def test_legacy_page_escapes_server_text():
    page = open(os.path.join(os.path.dirname(server.__file__), "static", "index.html"), encoding="utf-8").read()
    assert "${esc(m.text)}" in page and "${esc(m.from)}" in page and "${esc(x.name)}" in page
    assert "${m.text}" not in page

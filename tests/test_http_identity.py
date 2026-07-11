import pytest

from social_roulette.online import server, storage


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    server.PROFILES.clear()
    return tmp_path


def test_papers_create_valid():
    st, body = server.papers_create("s", "k", 4)
    assert st == 200
    assert body["initials"] == "S.K." and body["portrait"] == 4
    assert body["pid"] in server.PROFILES              # hot store updated


@pytest.mark.parametrize("fi,li,portrait", [
    ("", "k", 0), ("sk", "k", 0), ("1", "k", 0),
    ("s", "k", -1), ("s", "k", 12), ("s", "k", "x"),
])
def test_papers_create_rejects_bad_input(fi, li, portrait):
    st, body = server.papers_create(fi, li, portrait)
    assert st == 400


def test_papers_lookup_found_and_confirmed_fields():
    _, p = server.papers_create("s", "k", 2)
    st, body = server.papers_lookup("s", "k", p["pid"].lower())   # case-forgiving
    assert st == 200 and body["pid"] == p["pid"]


def test_papers_lookup_wrong_initials_is_404():
    _, p = server.papers_create("s", "k", 2)
    st, body = server.papers_lookup("a", "b", p["pid"])
    assert st == 404 and body["msg"] == "no such papers"


def test_journeys_lists_only_this_pid():
    _, p = server.papers_create("s", "k", 2)
    storage.session_write_meta("AAAA", {"code": "AAAA", "seats": 6,
                                        "members": [{"pid": p["pid"], "initials": "S.K."}],
                                        "created": 1.0})
    storage.session_write_meta("BBBB", {"code": "BBBB", "seats": 5,
                                        "members": [{"pid": "X-XXXX", "initials": "A.B."}],
                                        "created": 1.0})
    st, body = server.journeys(p["pid"])
    assert st == 200
    assert [j["code"] for j in body["journeys"]] == ["AAAA"]


def test_record_denied_while_running_served_after_end():
    storage.session_write_meta("AAAA", {"code": "AAAA", "members": []})
    st, _ = server.record_check("AAAA")
    assert st == 403                                    # secrets: bullet order, hands
    storage.session_append("AAAA", {"ended": 0})
    st, path = server.record_check("AAAA")
    assert st == 200 and path == storage.session_path("AAAA")
    assert server.record_check("ZZZZ")[0] == 404

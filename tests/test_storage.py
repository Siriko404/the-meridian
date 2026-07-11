import json
import os
import time

import pytest

from social_roulette.online import storage


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    return tmp_path


# ---- papers (profiles) ----

def test_pid_format_unambiguous_charset():
    pid = storage.issue_pid()
    assert len(pid) == 6 and pid[1] == "-"
    for ch in pid.replace("-", ""):
        assert ch in storage.PID_CHARSET
        assert ch not in "0O1I"                       # unambiguous by design (spec S2)


def test_create_profile_persists_and_reloads():
    p = storage.create_profile("S.K.", 4)
    assert p["initials"] == "S.K." and p["portrait"] == 4 and p["pid"]
    assert storage.load_profiles()[p["pid"]] == p


def test_create_profile_appends_not_overwrites():
    a = storage.create_profile("A.A.", 0)
    b = storage.create_profile("B.B.", 1)
    profs = storage.load_profiles()
    assert set(profs) == {a["pid"], b["pid"]}


def test_issue_pid_never_collides_with_existing():
    p = storage.create_profile("A.A.", 0)
    seen = {p["pid"]}
    for _ in range(50):
        pid = storage.issue_pid(existing=seen)
        assert pid not in seen
        seen.add(pid)


# ---- session files ----

def test_meta_is_first_line_and_snapshots_append():
    storage.session_write_meta("AB12", {"code": "AB12", "seats": 6, "members": []})
    storage.session_append("AB12", {"gen": 1, "snapshot": {"x": 1}})
    storage.session_append("AB12", {"gen": 2, "snapshot": {"x": 2}})
    assert storage.session_read_meta("AB12")["seats"] == 6
    assert storage.session_read_last("AB12")["gen"] == 2


def test_read_missing_session_is_none():
    assert storage.session_read_meta("ZZZZ") is None
    assert storage.session_read_last("ZZZZ") is None


def test_session_delete():
    storage.session_write_meta("AB12", {"code": "AB12"})
    storage.session_delete("AB12")
    assert storage.session_read_meta("AB12") is None
    storage.session_delete("AB12")                    # idempotent


def test_unfinished_lists_metas_and_skips_ended():
    storage.session_write_meta("AAAA", {"code": "AAAA", "members": []})
    storage.session_write_meta("BBBB", {"code": "BBBB", "members": []})
    storage.session_append("BBBB", {"ended": 0})      # verdict line closes the record
    codes = [m["code"] for m in storage.sessions_unfinished()]
    assert codes == ["AAAA"]


def test_journeys_for_pid():
    storage.session_write_meta("AAAA", {"code": "AAAA", "members": [{"pid": "M-7K2F"}]})
    storage.session_write_meta("BBBB", {"code": "BBBB", "members": [{"pid": "X-XXXX"}]})
    assert [m["code"] for m in storage.journeys_for("M-7K2F")] == ["AAAA"]
    assert storage.journeys_for("nope") == []


def test_sweep_removes_only_stale(data_dir):
    storage.session_write_meta("OLDD", {"code": "OLDD"})
    storage.session_write_meta("NEWW", {"code": "NEWW"})
    old = storage.session_path("OLDD")
    stale = time.time() - 8 * 86400
    os.utime(old, (stale, stale))
    storage.sessions_sweep(max_age_days=7)
    assert storage.session_read_meta("OLDD") is None
    assert storage.session_read_meta("NEWW") is not None


def test_session_lines_are_json(data_dir):
    storage.session_write_meta("AB12", {"code": "AB12"})
    storage.session_append("AB12", {"gen": 1})
    with open(storage.session_path("AB12"), encoding="utf-8") as f:
        for line in f:
            json.loads(line)

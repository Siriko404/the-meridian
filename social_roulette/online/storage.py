"""File persistence for papers (profiles) and session records (spec 2026-07-11 §2/§4).

All file I/O lives here so a database can replace the files without touching
game logic. Two stores:
  data/profiles.jsonl        append-only: one profile per line, never deleted
  data/sessions/<CODE>.jsonl line 1 = meta, then one line per room mutation;
                             an {"ended": ...} line closes the record; the file
                             lives exactly as long as its game (deleted at NEXT).
"""
import json
import os
import re
import secrets
import time
from pathlib import Path

DATA_DIR = Path(os.environ.get("SR_DATA_DIR") or Path(__file__).parent / "data")

# no 0/O/1/I — the pid is read aloud and typed on phones (spec §2)
PID_CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _profiles_path():
    return Path(DATA_DIR) / "profiles.jsonl"


def _sessions_dir():
    return Path(DATA_DIR) / "sessions"


def issue_pid(existing=None):
    while True:
        pid = (secrets.choice(PID_CHARSET) + "-"
               + "".join(secrets.choice(PID_CHARSET) for _ in range(4)))
        if not existing or pid not in existing:
            return pid


def load_profiles():
    path = _profiles_path()
    if not path.exists():
        return {}
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                p = json.loads(line)
                out[p["pid"]] = p
    return out


def create_profile(initials, portrait):
    profs = load_profiles()
    p = {"pid": issue_pid(existing=profs), "initials": initials,
         "portrait": int(portrait), "created": time.time()}
    path = _profiles_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(p) + "\n")
    return p


# ---- session records ----

CODE_RE = re.compile(r"[A-Z0-9]{1,16}")


def session_path(code):
    # The code names a file. Never let it carry a path ("../profiles") or other punctuation.
    if not isinstance(code, str) or not CODE_RE.fullmatch(code):
        raise ValueError("unsafe session code")
    return _sessions_dir() / (code + ".jsonl")


def session_write_meta(code, meta):
    path = session_path(code)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(meta) + "\n")


def session_append(code, line):
    path = session_path(code)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")


def session_read_meta(code):
    path = session_path(code)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        first = f.readline()
    return json.loads(first) if first.strip() else None


def session_read_last(code):
    path = session_path(code)
    if not path.exists():
        return None
    last = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last = line
    return json.loads(last) if last else None


def session_delete(code):
    try:
        session_path(code).unlink()
    except FileNotFoundError:
        pass


def session_is_ended(code):
    last = session_read_last(code)
    return bool(last and "ended" in last)


def sessions_unfinished():
    d = _sessions_dir()
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("*.jsonl")):
        code = p.stem
        if not session_is_ended(code):
            meta = session_read_meta(code)
            if meta:
                out.append(meta)
    return out


def journeys_for(pid):
    return [m for m in sessions_unfinished()
            if any(mm.get("pid") == pid for mm in m.get("members", []))]


def sessions_sweep(max_age_days=7):
    d = _sessions_dir()
    if not d.exists():
        return
    cutoff = time.time() - max_age_days * 86400
    for p in d.glob("*.jsonl"):
        if p.stat().st_mtime < cutoff:
            p.unlink()

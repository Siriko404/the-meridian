from social_roulette.observe.match import run_match
from social_roulette.observe import store, text_replay, health
from social_roulette.observe.events import COLUMNS


def test_run_match_produces_well_formed_events():
    res = run_match(1, {}, record=True)
    rows = res["rows"]
    assert rows[0]["type"] == "match_start" and rows[-1]["type"] == "match_end"
    assert res["winner"] is not None
    for r in rows:
        assert set(r.keys()) == set(COLUMNS)


def test_parquet_roundtrip_and_render(tmp_path):
    store.record_matches(str(tmp_path), range(5), batch_size=2)
    rows = store.read_match(str(tmp_path), 3)
    assert rows and rows[0]["type"] == "match_start"
    txt = text_replay.render(rows)
    assert "WINNER" in txt or "no winner" in txt


def test_health_streams_stats(tmp_path):
    store.record_matches(str(tmp_path), range(20), batch_size=10)
    out = health.health(str(tmp_path), learner_id=0)
    assert "matches=20" in out and "mechanic firing" in out

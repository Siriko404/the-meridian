from social_roulette.observe.match import run_match
from social_roulette.sim.turn import random_policy
from social_roulette.rl.social_selfplay import lone_vs_field


def test_social_match_records_gifts():
    """With social ON, a random field actually gifts (engine + turn wiring live)."""
    assert any(
        any(r["type"] == "gift" for r in run_match(s, {}, record=True, social=True)["rows"])
        for s in range(20)
    )


def test_no_gifts_when_social_off():
    rows = run_match(0, {}, record=True, social=False)["rows"]
    assert not any(r["type"] == "gift" for r in rows)


def test_lone_vs_field_random_near_fair_share():
    wr = lone_vs_field(random_policy, random_policy, 120)
    assert 0.08 < wr < 0.34            # ~0.20 fair share, loose bound

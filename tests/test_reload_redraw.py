"""RELOAD = REDRAW (user ruling 2026-07-12): the chamber reloads on empty AND on
death; EVERY reload deals 2 draws to each living player. A kill that also empties
the chamber is ONE reload -> ONE batch of 2. Chamber totals cap at max(2*living, 6)
so reloads come around more often (the 6-floor keeps the 2-player duel loadable)."""
import pytest

from social_roulette.engine.chamber import load_chamber
from social_roulette.engine.constants import Bullet, LIVE_FRACTION_MIN, LIVE_FRACTION_MAX
from social_roulette.engine.engine import new_game, take_shot
from social_roulette.engine.reload import reload_on_death
from social_roulette.engine.rng import SeededRng
from social_roulette.engine.state import living_players


# ---- chamber cap ----

@pytest.mark.parametrize("n", [2, 3, 5, 8, 12])
def test_chamber_total_capped_at_twice_living(n):
    for seed in range(100):
        ch = load_chamber(SeededRng(seed), n)
        total = len(ch.bullets)
        live = sum(1 for b in ch.bullets if b == Bullet.LIVE)
        assert total <= max(2 * n, 6)
        assert live > n                                   # kill-everyone invariant holds
        assert LIVE_FRACTION_MIN <= live / total <= LIVE_FRACTION_MAX


# ---- reload_on_death now deals ----

def test_reload_on_death_returns_two_draws_per_living():
    g = new_game(5, seed=7)
    draws = reload_on_death(g)
    assert set(draws) == {p.id for p in living_players(g)}
    for d in draws.values():
        assert len(d["attempted"]) == 2


# ---- shot-death path ----

def _first_kill(seed, n=5):
    """Drive legal shots until someone dies; return (state, ev)."""
    from social_roulette.engine.endgame import legal_targets
    g = new_game(n, seed=seed)
    for _ in range(400):
        shooter = g.current_id
        target = legal_targets(g, shooter)[0]
        ev = take_shot(g, shooter, target)
        if ev["killed"]:
            return g, ev
        if g.winner is not None:
            break
    raise AssertionError("no kill happened")


def test_kill_deals_two_draws_to_the_living():
    g, ev = _first_kill(seed=3)
    assert ev.get("draws"), "a death is a reload -> a redraw"
    assert set(ev["draws"]) == {p.id for p in living_players(g)}
    for d in ev["draws"].values():
        assert len(d["attempted"]) == 2                   # ONE batch of 2 — never 4


def test_kill_that_empties_chamber_is_one_batch():
    # every kill reloads the chamber; even when the fatal shot ALSO drained it,
    # attempted stays 2 per player across many seeds (no double payout)
    for seed in range(30):
        _, ev = _first_kill(seed=seed)
        for d in ev["draws"].values():
            assert len(d["attempted"]) == 2


# ---- poison-tick death path ----

def test_tick_death_buffers_a_draw_batch():
    from social_roulette.engine.engine import _fire_ticks
    g = new_game(5, seed=11)
    victim = next(p for p in living_players(g) if p.id != g.current_id)
    victim.cover = 1
    victim.poison_tick = g.current_id                     # owes a tick to current
    g.last_draws.clear()
    _fire_ticks(g, g.current_id)
    assert not victim.alive
    assert len(g.last_draws) == 1                         # one death -> one buffered batch
    batch = g.last_draws[0]
    assert set(batch) == {p.id for p in living_players(g)}
    for d in batch.values():
        assert len(d["attempted"]) == 2

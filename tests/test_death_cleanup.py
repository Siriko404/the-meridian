from social_roulette.engine.engine import new_game, take_shot
from social_roulette.engine.constants import Item, Shell
from social_roulette.engine.state import player_by_id


def _stage_kill(seed=0):
    """Arrange: current player shoots a 1-life enemy with a LIVE shell queued."""
    s = new_game(5, seed=seed)
    shooter = s.current_id
    victim = next(p.id for p in s.players
                  if p.id != shooter and p.team != player_by_id(s, shooter).team)
    player_by_id(s, victim).lives = 1
    player_by_id(s, victim).inventory = {Item.BEER: 2}
    # the victim had placed Immunity on someone
    other = next(p.id for p in s.players if p.id not in (shooter, victim))
    player_by_id(s, other).immunity_against.add(victim)
    s.chamber.shells[s.chamber.pos] = Shell.LIVE
    return s, shooter, victim, other


def test_death_burns_corpse_inventory():
    s, shooter, victim, _ = _stage_kill()
    take_shot(s, shooter, victim)
    assert player_by_id(s, victim).inventory == {}


def test_death_expires_placed_immunity():
    s, shooter, victim, other = _stage_kill()
    take_shot(s, shooter, victim)
    assert victim not in player_by_id(s, other).immunity_against

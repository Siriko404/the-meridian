from .constants import Bullet
from .state import player_by_id


def resolve_shot(state, shooter_id, target_id):
    shooter = player_by_id(state, shooter_id)
    target = player_by_id(state, target_id)
    bullet = state.chamber.current()
    damage = 0
    if bullet == Bullet.LIVE:
        damage = 2 if state.saw_active else 1
        target.cover = max(0, target.cover - damage)
    state.chamber.pos += 1
    state.saw_active = False
    shooter.immunity_against = set()
    state.bonus_pending = (shooter_id == target_id and bullet == Bullet.BLANK)
    return {"bullet": bullet, "damage": damage, "killed": target.cover == 0}

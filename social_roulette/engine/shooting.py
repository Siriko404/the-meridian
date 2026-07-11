from .constants import Bullet
from .state import player_by_id


def resolve_shot(state, shooter_id, target_id):
    shooter = player_by_id(state, shooter_id)
    target = player_by_id(state, target_id)
    bullet = state.chamber.current()
    damage = 0
    poisoned = False
    if bullet == Bullet.LIVE:
        damage = 1
        target.cover = max(0, target.cover - damage)
        # POISON (itemsession 2026-07-10): 1 now + 1 more at the poisoner's NEXT
        # turn start. Survivors only; max ONE pending tick per victim (no stacking).
        if state.poison_armed and target.cover > 0 and target.poison_tick is None:
            target.poison_tick = shooter_id
            poisoned = True
    state.chamber.pos += 1
    state.poison_armed = False               # a blank wastes it (saw precedent)
    shooter.immunity_against = set()
    state.bonus_pending = (shooter_id == target_id and bullet == Bullet.BLANK)
    return {"bullet": bullet, "damage": damage, "killed": target.cover == 0, "poisoned": poisoned}

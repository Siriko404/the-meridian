from .constants import Shell
from .state import player_by_id


def resolve_shot(state, shooter_id, target_id):
    shooter = player_by_id(state, shooter_id)
    target = player_by_id(state, target_id)
    shell = state.chamber.current()
    damage = 0
    if shell == Shell.LIVE:
        damage = 2 if state.saw_active else 1
        target.lives = max(0, target.lives - damage)
    state.chamber.pos += 1
    state.saw_active = False
    shooter.immunity_against = set()
    state.bonus_pending = (shooter_id == target_id and shell == Shell.BLANK)
    return {"shell": shell, "damage": damage, "killed": target.lives == 0}

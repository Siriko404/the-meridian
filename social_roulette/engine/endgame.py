from .state import living_players, player_by_id


def teams_active(state):
    return len(living_players(state)) >= 3


def winner(state):
    liv = living_players(state)
    return liv[0].id if len(liv) == 1 else None


def legal_targets(state, shooter_id):
    shooter = player_by_id(state, shooter_id)
    out = [shooter_id]
    for p in living_players(state):
        if p.id == shooter_id or p.id in shooter.immunity_against:
            continue
        if teams_active(state) and p.team == shooter.team:
            continue
        out.append(p.id)
    return out


def next_living_after(order, living, pid):
    n = len(order)
    i = order.index(pid) if pid in order else -1
    for k in range(1, n + 1):
        cand = order[(i + k) % n]
        if cand in living:
            return cand
    return None


def assert_legal_shot(state, shooter_id, target_id):
    if target_id not in legal_targets(state, shooter_id):
        raise ValueError(f"illegal shot {shooter_id}->{target_id}")

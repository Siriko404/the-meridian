"""take_policy_turn — the ONE shared turn primitive.

Plays a single full turn for `pid` using `policy`, mutating state. Optionally
emits events via `rec`. The SAME function drives both Stage-2 training opponents
and eval/observation, so eval can never measure a different opponent than
training used.

policy signature:  policy(state, pid, extras) -> engine action (Shoot/UseItem/Flip)
extras_map:        {seat_id: Extras} — every seat re-syncs announced counts after
                   each sub-action (a reload changes the chamber for everyone).
"""
from social_roulette.engine.engine import step
from social_roulette.engine.constants import Bullet, Item
from social_roulette.engine.state import living_ids, player_by_id
from social_roulette.engine.actions import legal_actions, Shoot, Flip, Speak, Trade
from social_roulette.engine.endgame import legal_targets


class Extras:
    """Per-seat observable memory (announced chamber counts + a known peeked bullet)."""
    def __init__(self):
        self.known = "unknown"
        self.total = 0
        self.live = 0
        self._lc = None
        self._lp = 0

    def sync(self, state):
        ch = state.chamber
        if ch is not self._lc:
            self._lc = ch
            self.total = len(ch.bullets)
            self.live = sum(1 for s in ch.bullets if s == Bullet.LIVE)
            self.known = "unknown"
            self._lp = ch.pos
        elif ch.pos != self._lp:
            self.known = "unknown"
            self._lp = ch.pos

    def peek(self, state):
        c = state.chamber.current()
        self.known = "live" if c == Bullet.LIVE else ("blank" if c == Bullet.BLANK else "unknown")

    def d(self):
        return {"known_next_bullet": self.known, "announced_total": self.total, "announced_live": self.live}


def random_policy(state, pid, extras):
    return state.rng.choice(legal_actions(state, pid))


def _sanv(v):
    if isinstance(v, (Bullet, Item)):
        return v.name
    if isinstance(v, dict):
        return {k: _sanv(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_sanv(x) for x in v]
    return v


def _san(effect):
    return {k: _sanv(v) for k, v in (effect or {}).items()}


def _rec_draws(rec, turn_idx, res):
    """Record a reload's per-seat refill (bot path) so the online view can hand each
    seat ONLY its own attempted/received. No-op when the step produced no draws."""
    if rec and isinstance(res, dict) and res.get("draws"):
        rec.draw(turn_idx, {pid: {"attempted": [i.name for i in d["attempted"]],
                                  "received": [i.name for i in d["received"]]}
                            for pid, d in res["draws"].items()})


def take_policy_turn(state, pid, policy, extras_map, rec=None, turn_idx=0):
    me = player_by_id(state, pid)
    ex = extras_map[pid]
    alive_before = living_ids(state)
    ch_before = state.chamber
    if rec:
        rec.turn_start(turn_idx, pid, me.team.name, me.lives)

    shot_done = False
    for _ in range(40):
        a = policy(state, pid, ex)
        if isinstance(a, Shoot):
            saw = state.saw_active
            ev = step(state, pid, a)
            if rec:
                rec.shot(turn_idx, pid, a.target_id, ev["bullet"].name, ev["damage"], ev["killed"], saw)
            _rec_draws(rec, turn_idx, ev)
            shot_done = True
            break
        if isinstance(a, Speak):
            step(state, pid, a)
            if rec:
                rec.message(turn_idx, pid, a.act, a.target, a.value)
            for e in extras_map.values():
                e.sync(state)
            continue
        if isinstance(a, Flip):
            tgt = a.target_id
            step(state, pid, a)
            if rec:
                rec.flip(turn_idx, pid, tgt, [it.name for it in a.sacrifice], player_by_id(state, tgt).team.name)
        elif isinstance(a, Trade):
            to = a.to_id
            step(state, pid, a)
            if rec:
                rec.gift(turn_idx, pid, to, [it.name for it in a.items])
        else:
            is_mag = a.item == Item.GEIGER
            res = step(state, pid, a)
            if is_mag:
                ex.peek(state)
            if rec:
                rec.item_used(turn_idx, pid, a.item.name, a.target_id, _san(res))
            _rec_draws(rec, turn_idx, res)
        for e in extras_map.values():
            e.sync(state)
    if not shot_done:
        tgt = state.rng.choice(legal_targets(state, pid))
        saw = state.saw_active
        ev = step(state, pid, Shoot(tgt))
        if rec:
            rec.shot(turn_idx, pid, tgt, ev["bullet"].name, ev["damage"], ev["killed"], saw)
        _rec_draws(rec, turn_idx, ev)

    dead = sorted(alive_before - living_ids(state))
    if rec:
        for d in dead:
            rec.elimination(turn_idx, d, pid)
        if state.chamber is not ch_before and state.winner is None:
            live = sum(1 for s in state.chamber.bullets if s == Bullet.LIVE)
            rec.reload(turn_idx, "death" if dead else "empty", len(state.chamber.bullets), live)
        if state.bonus_pending and state.current_id == pid:
            rec.bonus(turn_idx, pid)
    if state.last_skipped and rec:
        for pid_s in state.last_skipped:
            rec.skip(turn_idx, pid_s)
        state.last_skipped.clear()
    for e in extras_map.values():
        e.sync(state)
    return {"dead": dead}

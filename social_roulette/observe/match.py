"""run_match — the one canonical full-table match runner.

Plays a full game with arbitrary per-seat policies and (optionally) records every
event. Reused by observation now and by Stage-2 self-play later. Recording is
optional => zero overhead when off.

policy signature:  policy(state, pid, extras) -> engine action (Shoot/UseItem/Flip)
"""
from social_roulette.engine.engine import new_game, step
from social_roulette.engine.constants import Shell, Item
from social_roulette.engine.state import living_ids, player_by_id
from social_roulette.engine.actions import legal_actions, Shoot, UseItem, Flip
from social_roulette.engine.endgame import legal_targets
from social_roulette.rl.obs import encode_obs
from social_roulette.rl.action_space import ActionCodec
from .recorder import Recorder


class _Extras:
    """Per-seat observable memory (announced chamber counts + a known peeked shell)."""
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
            self.total = len(ch.shells)
            self.live = sum(1 for s in ch.shells if s == Shell.LIVE)
            self.known = "unknown"
            self._lp = ch.pos
        elif ch.pos != self._lp:
            self.known = "unknown"
            self._lp = ch.pos

    def peek(self, state):
        c = state.chamber.current()
        self.known = "live" if c == Shell.LIVE else ("blank" if c == Shell.BLANK else "unknown")

    def d(self):
        return {"known_next_shell": self.known, "announced_total": self.total, "announced_live": self.live}


def random_policy(state, pid, extras):
    return state.rng.choice(legal_actions(state, pid))


def make_model_policy(model, shoot_only=False):
    def pol(state, pid, extras):
        obs = encode_obs(state, pid, extras.d())
        mask = ActionCodec.legal_mask(state, pid, shoot_only)
        idx, _ = model.predict(obs, action_masks=mask, deterministic=True)
        return ActionCodec.decode(int(idx), state, pid)
    return pol


def _san(effect):
    out = {}
    for k, v in (effect or {}).items():
        out[k] = v.name if isinstance(v, Shell) else v
    return out


def run_match(seed, policies=None, num_players=5, match_id=None, record=True, max_turns=4000):
    policies = policies or {}
    state = new_game(num_players, seed)
    extras = {i: _Extras() for i in range(num_players)}
    for e in extras.values():
        e.sync(state)
    rec = Recorder(match_id if match_id is not None else seed) if record else None
    if rec:
        rec.match_start(state.players, num_players, seed, extras[0].total, extras[0].live)

    t = 0
    while state.winner is None and t < max_turns:
        pid = state.current_id
        me = player_by_id(state, pid)
        pol = policies.get(pid, random_policy)
        ex = extras[pid]
        alive_before = living_ids(state)
        ch_before = state.chamber
        if rec:
            rec.turn_start(t, pid, me.team.name, me.lives)

        shot_done = False
        for _ in range(40):
            a = pol(state, pid, ex)
            if isinstance(a, Shoot):
                saw = state.saw_active
                ev = step(state, pid, a)
                if rec:
                    rec.shot(t, pid, a.target_id, ev["shell"].name, ev["damage"], ev["killed"], saw)
                shot_done = True
                break
            if isinstance(a, Flip):
                tgt = a.target_id
                step(state, pid, a)
                if rec:
                    rec.flip(t, pid, tgt, [it.name for it in a.sacrifice], player_by_id(state, tgt).team.name)
            else:
                is_mag = a.item == Item.MAGNIFIER
                res = step(state, pid, a)
                if is_mag:
                    ex.peek(state)
                if rec:
                    rec.item_used(t, pid, a.item.name, a.target_id, _san(res))
            for e in extras.values():
                e.sync(state)
        if not shot_done:
            tgt = state.rng.choice(legal_targets(state, pid))
            saw = state.saw_active
            ev = step(state, pid, Shoot(tgt))
            if rec:
                rec.shot(t, pid, tgt, ev["shell"].name, ev["damage"], ev["killed"], saw)

        dead = sorted(alive_before - living_ids(state))
        if rec:
            for d in dead:
                rec.elimination(t, d, pid)
            if state.chamber is not ch_before and state.winner is None:
                live = sum(1 for s in state.chamber.shells if s == Shell.LIVE)
                rec.reload(t, "death" if dead else "empty", len(state.chamber.shells), live)
            if state.bonus_pending and state.current_id == pid:
                rec.bonus(t, pid)
        for e in extras.values():
            e.sync(state)
        t += 1

    if rec:
        rec.match_end(t, state.winner)
    return {"winner": state.winner, "turns": t, "rows": rec.rows if rec else None}

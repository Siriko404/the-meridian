"""Room — the pure, synchronous game state-machine. No asyncio, no network.

Humans act ONE engine.step at a time (an action is legal until they shoot; the
engine then advances the turn). Bot seats run the existing take_policy_turn.
The async server wraps this class; all game logic and every invariant live here
so they are unit-testable without a socket.

Every apply() also records the animatable EVENTS it caused (the human's own
action + any bot turns it triggered) into `last_events`: the client replays
them, then settles to the new per-seat view. Events carry only PUBLIC fields
(fired shell, damage, death, flip) — never the hidden shell order or a peek.
"""
import json

from social_roulette.engine.engine import new_game, step as engine_step
from social_roulette.engine.constants import Item, Shell
from social_roulette.engine.actions import legal_actions, Shoot, Flip
from social_roulette.engine.state import player_by_id, living_ids
from social_roulette.sim.turn import take_policy_turn, random_policy, Extras
from social_roulette.observe.recorder import Recorder
from social_roulette.online.view import seat_view

# public animation fields kept from a recorder row (drop `extra` — it can carry a
# Magnifier peek — and the bookkeeping columns the client never animates).
_ANIM_KEYS = ("type", "actor", "target", "shell", "damage", "killed", "item")


def _anim(row):
    # A reload is a fresh LOAD → its announced total/live are PUBLIC (game_guide:159).
    # Surface just those two from `extra`; every other event still drops `extra` (no peek leak).
    if row["type"] == "reload":
        ex = json.loads(row["extra"]) if row.get("extra") else {}
        return {"type": "reload", "total": ex.get("new_total"), "live": ex.get("new_live")}
    return {k: row[k] for k in _ANIM_KEYS if k in ("type", "actor") or row.get(k) is not None}


class IllegalAction(Exception):
    pass


class Room:
    def __init__(self, human_seats, seed, num_players=5):
        self.human = set(human_seats)
        self.state = new_game(num_players, seed)
        self.state.comms_enabled = False
        self.state.social_enabled = False
        if self.human:
            # Rotate the (random) seating so the turn STARTS at a human: nobody plays before the
            # first human turn, so no state is applied unseen (a bot immunity/flip/shot the human
            # never witnessed would otherwise look like stale data on the opening board).
            order = self.state.order
            fh = next(pid for pid in order if pid in self.human)
            i = order.index(fh)
            self.state.order = order[i:] + order[:i]
            self.state.current_id = self.state.order[0]
        self.seating = list(self.state.order)   # FIXED physical circle — the ring is laid out by this,
        self.extras = {i: Extras() for i in range(num_players)}   # so turns advance to ADJACENT seats.
        for e in self.extras.values():
            e.sync(self.state)
        self.feed = []
        self.rec = Recorder(seed)
        self._turn = 0
        self.last_events = []
        self._run_bots()               # no-op when a human leads; else auto-plays leading bots
        # the first view carries only the public opening announce (game_guide:159 "announced at load").
        self.last_events = [self._announce()]

    def _announce(self):
        ch = self.state.chamber
        return {"type": "announce", "total": len(ch.shells),
                "live": sum(1 for s in ch.shells if s == Shell.LIVE)}

    @property
    def winner(self):
        return self.state.winner

    @property
    def current(self):
        return self.state.current_id

    def is_bot(self, seat):
        return seat not in self.human

    def view(self, seat):
        return seat_view(self.state, seat, self.extras[seat].d(), self.feed, self.seating)

    def apply(self, seat, i):
        if self.winner is not None or seat != self.state.current_id:
            raise IllegalAction("not your turn")
        acts = legal_actions(self.state, seat)
        if not (0 <= i < len(acts)):
            raise IllegalAction("no such action")
        n0 = len(self.rec.rows)
        self._emit_human_action(seat, acts[i])
        for e in self.extras.values():
            e.sync(self.state)
        self._run_bots()
        self.last_events = [_anim(r) for r in self.rec.rows[n0:]]

    def _emit_human_action(self, seat, action):
        """Step the engine for the human's one committed action and record the
        matching event(s), mirroring take_policy_turn's per-sub-action emission."""
        alive_before = living_ids(self.state)
        ch_before = self.state.chamber
        if isinstance(action, Shoot):
            saw = self.state.saw_active
            ev = engine_step(self.state, seat, action)
            self.rec.shot(self._turn, seat, action.target_id, ev["shell"].name,
                          ev["damage"], ev["killed"], saw)
            for d in sorted(alive_before - living_ids(self.state)):
                self.rec.elimination(self._turn, d, seat)
            if self.state.chamber is not ch_before and self.state.winner is None:
                live = sum(1 for s in self.state.chamber.shells if s == Shell.LIVE)
                self.rec.reload(self._turn, "death" if len(living_ids(self.state)) < len(alive_before) else "empty",
                                len(self.state.chamber.shells), live)
        elif isinstance(action, Flip):
            tgt = action.target_id
            engine_step(self.state, seat, action)
            self.rec.flip(self._turn, seat, tgt, [it.name for it in action.sacrifice],
                          player_by_id(self.state, tgt).team.name)
        else:                                       # UseItem (Trade/Speak impossible: social/comms disabled)
            engine_step(self.state, seat, action)
            if getattr(action, "item", None) == Item.MAGNIFIER:
                self.extras[seat].peek(self.state)
            self.rec.item_used(self._turn, seat, action.item.name, action.target_id, {})

    def _run_bots(self):
        while self.state.winner is None and self.is_bot(self.state.current_id):
            self._turn += 1
            take_policy_turn(self.state, self.state.current_id, random_policy, self.extras,
                             rec=self.rec, turn_idx=self._turn)

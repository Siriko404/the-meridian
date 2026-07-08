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
import time

from social_roulette.engine.engine import new_game, step as engine_step
from social_roulette.engine.constants import Item, Shell
from social_roulette.engine.actions import legal_actions, Shoot, Flip
from social_roulette.engine.state import player_by_id, living_ids
from social_roulette.engine.economy import fine_cheapest, swap
from social_roulette.sim.turn import take_policy_turn, random_policy, Extras
from social_roulette.observe.recorder import Recorder
from social_roulette.online.view import seat_view

# public animation fields kept from a recorder row (drop `extra` — it can carry a
# Magnifier peek — and the bookkeeping columns the client never animates).
_ANIM_KEYS = ("type", "actor", "target", "shell", "damage", "killed", "item")


def _anim(row):
    # A reload is a fresh LOAD → its announced total/live are PUBLIC (game_guide:159).
    # Surface just those two from `extra`; every other event still drops `extra` (no peek leak).
    t = row["type"]
    if t == "reload":
        ex = json.loads(row["extra"]) if row.get("extra") else {}
        return {"type": "reload", "total": ex.get("new_total"), "live": ex.get("new_live")}
    if t == "fine":
        return {"type": "fine", "actor": row["actor"]}                # public: NO item (D14)
    if t == "draw":
        return {"type": "draw", "seq": row["seq"]}                    # seq keys the per-seat enrichment lookup
    return {k: row[k] for k in _ANIM_KEYS if k in ("type", "actor") or row.get(k) is not None}


class IllegalAction(Exception):
    pass


class Room:
    TALK_S = 60.0
    DECISION_S = 30.0
    _PHASE_KINDS = {"talk": {"item"}, "decision": {"item", "flip", "shoot"}}

    def __init__(self, human_seats, seed, num_players=5, now_fn=time.time):
        self.now = now_fn
        self.gen = 0
        self.phase = None
        self.phase_ends_at = None
        self.human = set(human_seats)
        self.state = new_game(num_players, seed)
        self.state.comms_enabled = False
        self.state.social_enabled = False    # RULE: every transfer is offer->accept, turn-holder only.
        # Engine-level Trade would let bots hand items UNILATERALLY (no consent) — forbidden in play.
        self.pending_offer = None
        self._trade_result = None
        self._last_trade_items = None
        self.extra_turn = False          # set true when a kill grants the killer another turn (read by view)
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
        self._begin_phase_for_current()

    def _grace(self):
        return min(sum(5.0 if e.get("type") in ("announce", "reload") else 1.6
                       for e in self.last_events), 20.0)

    def _begin_phase_for_current(self):
        self.gen += 1
        if self.winner is not None:
            self.phase = None
            self.phase_ends_at = None
            return
        dur = self.DECISION_S if self.state.bonus_pending else self.TALK_S
        self.phase = "decision" if self.state.bonus_pending else "talk"
        self.phase_ends_at = self.now() + self._grace() + dur

    def can_chat(self, seat):
        return self.phase == "talk" and player_by_id(self.state, seat).alive

    def proceed(self, seat):
        if self.winner is not None or seat != self.state.current_id:
            raise IllegalAction("not your turn")
        if self.phase != "talk":
            raise IllegalAction("not in talk phase")
        self._trade_result = None
        self._last_trade_items = None
        self.gen += 1
        self.phase = "decision"
        self.phase_ends_at = self.now() + self.DECISION_S
        self._expire_offer()          # leaving talk voids any pending offer
        self.last_events = []

    def on_deadline(self):
        if self.winner is not None or self.phase is None:
            return False
        if self.now() < self.phase_ends_at:
            return False
        self._trade_result = None          # any REAL transition clears a stale trade note (parity with apply/proceed)
        self._last_trade_items = None
        if self.phase == "talk":
            self.gen += 1
            self.phase = "decision"
            self.phase_ends_at = self.now() + self.DECISION_S
            self._expire_offer()          # defined Task 9; stub `pass` for now
            self.last_events = []
            return True
        seat = self.state.current_id
        fined = fine_cheapest(self.state, seat)
        if fined is not None:
            self.gen += 1
            self.rec.fine(self._turn, seat, fined.name)
            self.last_events = [{"type": "fine", "actor": seat}]     # public: NO item (D14)
            self.phase_ends_at = self.now() + self.DECISION_S
            return True
        n0 = len(self.rec.rows)
        self._emit_human_action(seat, Shoot(seat))
        for e in self.extras.values():
            e.sync(self.state)
        self._run_bots()
        self._drain_skips()
        self.last_events = [_anim(r) for r in self.rec.rows[n0:]]
        self._derive_extra_turn()
        self._begin_phase_for_current()
        return True

    def _expire_offer(self):
        self.pending_offer = None

    def _allowed(self, action):
        from social_roulette.engine.actions import Trade as _Trade
        if isinstance(action, _Trade):
            return False                                  # humans trade via offers only (a20)
        kind = ("shoot" if isinstance(action, Shoot) else
                "flip" if isinstance(action, Flip) else "item")
        return kind in self._PHASE_KINDS.get(self.phase, set())

    def trade_offer(self, seat, to, give, want):
        if self.winner is not None or seat != self.state.current_id:
            raise IllegalAction("not your turn")
        if self.phase != "talk":
            raise IllegalAction("trades happen in the talk phase")
        if self.pending_offer is not None:
            raise IllegalAction("an offer is already pending")
        me = player_by_id(self.state, seat)
        mate = player_by_id(self.state, to)
        if not mate.alive or to == seat or mate.team != me.team:
            raise IllegalAction("can only trade with a living teammate")
        for n in list(give) + list(want):
            if n not in Item.__members__:
                raise IllegalAction("bad item name")
        self._trade_result = None
        self._last_trade_items = None
        self.gen += 1
        self.pending_offer = {"from": seat, "to": to, "give": list(give), "want": list(want)}

    def trade_withdraw(self, seat):
        if self.pending_offer is None or self.pending_offer["from"] != seat:
            raise IllegalAction("no offer of yours is pending")
        self.gen += 1
        self.pending_offer = None

    def trade_respond(self, seat, accept):
        if self.pending_offer is None or self.pending_offer["to"] != seat:
            raise IllegalAction("no offer for you is pending")
        off = self.pending_offer
        self.gen += 1
        self.pending_offer = None
        if not accept:
            self._trade_result = {"kind": "declined", "parties": (off["from"], off["to"])}
            return
        give = [Item[n] for n in off["give"]]
        want = [Item[n] for n in off["want"]]
        try:
            swap(self.state, off["from"], off["to"], give, want)
        except ValueError:
            self._trade_result = {"kind": "cancelled", "parties": (off["from"], off["to"])}
            return
        self.rec.trade(self._turn, off["from"], off["to"], off["give"], off["want"])
        self._trade_result = {"kind": "settled", "parties": (off["from"], off["to"])}
        self._last_trade_items = {"give": off["give"], "want": off["want"]}
        self.last_events = [{"type": "trade", "actor": off["from"], "target": off["to"]}]

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
        from social_roulette.engine.items import consumption_limit
        from social_roulette.engine.endgame import teams_active
        v = seat_view(self.state, seat, self.extras[seat].d(), self.feed, self.seating)
        allowed = self._PHASE_KINDS.get(self.phase, set())
        v["legal"] = [a for a in v["legal"] if a["kind"] in allowed]   # drops engine Trade (kind "other") too
        me = player_by_id(self.state, seat)
        v.update({
            "gen": self.gen,
            "phase": self.phase, "phase_ends_at": self.phase_ends_at, "server_now": self.now(),
            "bonus": self.state.bonus_pending, "extra_turn": self.extra_turn,
            "saw_active": self.state.saw_active,
            "use_counts": {it.name: c for it, c in self.state.use_counts.items()},
            "use_limit": consumption_limit(self.state),
            "teams_active": teams_active(self.state),
            "flipback_discount": me.flipback_discount,     # own discount only — never another seat's
        })
        if self.pending_offer and seat in (self.pending_offer["from"], self.pending_offer["to"]):
            v["pending_offer"] = dict(self.pending_offer)
        return v

    def events_for(self, seat):
        """Per-seat enrichment of the shared public `last_events`: a draw event gains
        THIS seat's own refill; a settled trade gains its items ONLY for the two
        parties; and a declined/cancelled offer surfaces a private note to the parties.
        Never leaks another seat's hand or the shell order."""
        out = []
        for e in self.last_events:
            e = dict(e)
            if e["type"] == "draw":
                row = next((r for r in self.rec.rows if r["seq"] == e.get("seq")), None)
                if row:
                    draws = json.loads(row["extra"])["draws"]
                    mine = draws.get(str(seat)) or draws.get(seat)   # JSON round-trip stringifies keys
                    if mine:
                        e["you"] = mine
                e.pop("seq", None)
            if e["type"] == "trade" and seat in (e.get("actor"), e.get("target")):
                if self._last_trade_items is not None:
                    e["items"] = self._last_trade_items
            out.append(e)
        tr = self._trade_result
        if tr and tr["kind"] in ("declined", "cancelled") and seat in tr["parties"]:
            out.append({"type": "trade_private", "kind": tr["kind"]})
        return out

    def apply(self, seat, i):
        if self.winner is not None or seat != self.state.current_id:
            raise IllegalAction("not your turn")
        acts = legal_actions(self.state, seat)
        if not (0 <= i < len(acts)):
            raise IllegalAction("no such action")
        if not self._allowed(acts[i]):
            raise IllegalAction("not allowed in this phase")
        self._trade_result = None
        self._last_trade_items = None
        n0 = len(self.rec.rows)
        self._emit_human_action(seat, acts[i])
        for e in self.extras.values():
            e.sync(self.state)
        self._run_bots()
        self._drain_skips()
        self.last_events = [_anim(r) for r in self.rec.rows[n0:]]
        self._derive_extra_turn()
        # The turn only resolves via a SHOT (fines/auto-shoot flow through the same shot
        # path). A non-turn-ending action (item use, incl. a MAGNET reload) must NOT re-begin
        # the phase — that would drop DECISION back to a fresh 60s TALK (§4.1/§4.3). Re-begin
        # only when the delta actually ended the turn; otherwise just bump gen once.
        if self.winner is not None or any(e.get("type") == "shot" for e in self.last_events):
            self._begin_phase_for_current()
        else:
            self.gen += 1

    def flip(self, seat, target_id, item_names):
        """A flip with a player-CHOSEN payment. The engine's pay_cost re-validates that
        the sacrifice is owned and its point value covers the cost (4 flip-back, else 5)."""
        if self.winner is not None or seat != self.state.current_id:
            raise IllegalAction("not your turn")
        if self.phase != "decision":
            raise IllegalAction("flips happen in the decision phase")
        if target_id not in living_ids(self.state):
            raise IllegalAction("bad flip target")
        try:
            sacrifice = [Item[n] for n in item_names]
        except KeyError:
            raise IllegalAction("bad payment item")
        self._trade_result = None
        self._last_trade_items = None
        n0 = len(self.rec.rows)
        try:
            engine_step(self.state, seat, Flip(target_id, sacrifice))
        except ValueError as e:
            raise IllegalAction(str(e))
        self.rec.flip(self._turn, seat, target_id, [it.name for it in sacrifice],
                      player_by_id(self.state, target_id).team.name)
        for e in self.extras.values():
            e.sync(self.state)
        self._run_bots()
        self._drain_skips()
        self.last_events = [_anim(r) for r in self.rec.rows[n0:]]
        self._derive_extra_turn()
        self.gen += 1                 # a flip never ends the turn → never re-begin the phase (C1/§4.1)

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
            self._record_draws(ev)
            self._drain_skips()
        elif isinstance(action, Flip):
            tgt = action.target_id
            engine_step(self.state, seat, action)
            self.rec.flip(self._turn, seat, tgt, [it.name for it in action.sacrifice],
                          player_by_id(self.state, tgt).team.name)
        else:                                       # UseItem (Trade/Speak impossible: social/comms disabled)
            it = getattr(action, "item", None)
            ev = engine_step(self.state, seat, action)
            if it == Item.MAGNIFIER:
                self.extras[seat].peek(self.state)
            elif it == Item.BEER:
                self.extras[seat].known = "unknown"     # the peeked shell was ejected → clear the stale peek
            self.rec.item_used(self._turn, seat, action.item.name, action.target_id, {})
            if self.state.chamber is not ch_before and self.state.winner is None:   # Beer emptied it → reload
                live = sum(1 for s in self.state.chamber.shells if s == Shell.LIVE)
                self.rec.reload(self._turn, "empty", len(self.state.chamber.shells), live)
            self._record_draws(ev)
            self._drain_skips()

    def _record_draws(self, ev):
        """A reload refill (empty/beer/self-death) fans out per-seat draws — record them
        so events_for can hand each seat ONLY its own attempted/received (privacy)."""
        if ev and ev.get("draws"):
            self.rec.draw(self._turn, {pid: {"attempted": [i.name for i in d["attempted"]],
                                             "received": [i.name for i in d["received"]]}
                                       for pid, d in ev["draws"].items()})

    def _drain_skips(self):
        """A handcuffed seat skipped at turn-advance is a PUBLIC event — flush the
        engine's buffer into skip rows (chronologically after the action that caused it)."""
        for pid in self.state.last_skipped:
            self.rec.skip(self._turn, pid)
        self.state.last_skipped.clear()

    def _derive_extra_turn(self):
        """True when this delta killed someone AND the killer still holds the turn
        (a bonus turn) — the UI shows a 'go again' cue. Never true once the match ends."""
        self.extra_turn = self.winner is None and any(
            e.get("type") == "elimination" and e.get("actor") == self.state.current_id
            for e in self.last_events)

    def _run_bots(self):
        while self.state.winner is None and self.is_bot(self.state.current_id):
            self._turn += 1
            take_policy_turn(self.state, self.state.current_id, random_policy, self.extras,
                             rec=self.rec, turn_idx=self._turn)

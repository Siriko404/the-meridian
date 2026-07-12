"""Room — the pure, synchronous game state-machine. No asyncio, no network.

Humans act ONE engine.step at a time (an action is legal until they shoot; the
engine then advances the turn). Bot seats run the existing take_policy_turn.
The async server wraps this class; all game logic and every invariant live here
so they are unit-testable without a socket.

Every apply() also records the animatable EVENTS it caused (the human's own
action + any bot turns it triggered) into `last_events`: the client replays
them, then settles to the new per-seat view. Events carry only PUBLIC fields
(fired bullet, damage, death, flip) — never the hidden bullet order or a peek.
"""
import json
import random
import time

from social_roulette.engine.engine import new_game, step as engine_step
from social_roulette.engine.constants import Item, Bullet
from social_roulette.engine.actions import legal_actions, Shoot, Flip, PayTax
from social_roulette.engine.state import player_by_id, living_ids
from social_roulette.engine.economy import fine_cheapest, swap
from social_roulette.engine import specials as SP
from social_roulette.engine.endgame import legal_targets
from social_roulette.sim.turn import take_policy_turn, random_policy, Extras
from social_roulette.observe.recorder import Recorder
from social_roulette.online.view import seat_view

# public animation fields kept from a recorder row (drop `extra` — it can carry a
# Geiger peek — and the bookkeeping columns the client never animates).
_ANIM_KEYS = ("type", "actor", "target", "bullet", "damage", "killed", "item")


def _anim(row):
    # A reload is a fresh LOAD → its announced total/live are PUBLIC (game_guide:159).
    # Surface just those two from `extra`; every other event still drops `extra` (no peek leak).
    t = row["type"]
    if t == "reload":
        ex = json.loads(row["extra"]) if row.get("extra") else {}
        return {"type": "reload", "total": ex.get("new_total"), "live": ex.get("new_live")}
    if t == "fine":
        return {"type": "fine", "actor": row["actor"]}                # public: NO item (D14)
    if t == "tax":
        ex = json.loads(row["extra"]) if row.get("extra") else {}
        return {"type": "tax", "actor": row["actor"], "tier": ex.get("tier")}
    if t == "special":
        return None                                       # anonymity law: no public trace
    if t == "draw":
        return {"type": "draw", "seq": row["seq"]}                    # seq keys the per-seat enrichment lookup
    out = {k: row[k] for k in _ANIM_KEYS if k in ("type", "actor") or row.get(k) is not None}
    if t == "item_used":
        out["type"] = "item"       # the client/fixture vocabulary (recorder rows say item_used)
        if row.get("item") == "MAGNET":
            out["seq"] = row["seq"]                                   # ejected value: actor-only enrichment (B4)
    return out


class IllegalAction(Exception):
    pass


def _rng_dump(r):
    st = r.getstate()
    return [st[0], list(st[1]), st[2]]


def _rng_load(d):
    r = random.Random()
    r.setstate((d[0], tuple(d[1]), d[2]))
    return r


class Room:
    TALK_S = 60.0
    DECISION_S = 30.0
    AIMING_S = 5.0                  # bot pre-shot window a HANDLER can seize (option b)
    _PHASE_KINDS = {"talk": {"item"}, "decision": {"item", "flip", "shoot"}, "tax": {"tax"}}

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
        self._notes = []                 # per-delta PRIVATE payloads: (seat, dict) — anonymity law
        self.pending_warrant = None      # {"user","target","hand","specials"} until the take
        self.handler = None              # {"by","victim"} while a HANDLER holds the trigger
        self.pending_bot_shot = None     # (bot_pid, target) parked during the aiming window
        self._dragnet = {}               # seat -> last report (rides the view; private)
        self.held_since = None           # hold-on-drop (spec §4, supersedes D11 for drops):
        self.held_remaining = None       # frozen phase seconds while humans are off the car
        self.hold_missing = set()        # their seats; play resumes when all are back
        self.hold_expired = False        # 5:00 passed — the conductor must choose
        self.hold_chooser = None         # seat that owns the choice (server appoints)
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
        if self.pending_bot_shot is not None:          # a bot is aiming — the window owns the phase
            self.phase = "aiming"
            return
        if self.state.tax_pending:                     # B3: resolve the shakedown first
            self.phase = "tax"
            self.phase_ends_at = self.now() + self._grace() + self.DECISION_S
            return
        silent = self.state.bonus_pending or self.state.tax_silent
        dur = self.DECISION_S if silent else self.TALK_S
        self.phase = "decision" if silent else "talk"
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
        self._notes = []
        self.gen += 1
        self.phase = "decision"
        self.phase_ends_at = self.now() + self.DECISION_S
        self._expire_offer()          # leaving talk voids any pending offer
        self.last_events = []

    def on_deadline(self):
        if self.winner is not None or self.phase is None:
            return False
        if self.held_since is not None or self.phase_ends_at is None:
            return False                   # the car is HELD — no clock bites (spec §4)
        if self.now() < self.phase_ends_at:
            return False
        self._trade_result = None          # any REAL transition clears a stale trade note (parity with apply/proceed)
        self._last_trade_items = None
        self._notes = []                   # private notes live for ONE delta — never replayed
        if self.phase == "talk":
            self.gen += 1
            self.phase = "decision"
            self.phase_ends_at = self.now() + self.DECISION_S
            self._expire_offer()          # defined Task 9; stub `pass` for now
            self.last_events = []
            return True
        if self.phase == "aiming" and self.pending_bot_shot is not None:
            pid, tgt = self.pending_bot_shot
            tgt = self._seized_target(pid, tgt)    # v2: fires AT the deadline either way —
            self.pending_bot_shot = None           # an early shot would leak the seize
            n0 = len(self.rec.rows)
            self._emit_human_action(pid, Shoot(tgt))
            for e in self.extras.values():
                e.sync(self.state)
            self._run_bots()
            self._drain_skips()
            self.last_events = [a for a in (_anim(r) for r in self.rec.rows[n0:]) if a]
            self._derive_extra_turn()
            self._begin_phase_for_current()
            return True
        seat = self.state.current_id
        if self.phase == "tax":
            n0 = len(self.rec.rows)
            self._emit_human_action(seat, PayTax(0))       # timeout = unpaid = skip
            for e in self.extras.values():
                e.sync(self.state)
            self._run_bots()
            self._drain_skips()
            self.last_events = [a for a in (_anim(r) for r in self.rec.rows[n0:]) if a]
            self._derive_extra_turn()
            self._begin_phase_for_current()
            return True
        fined = fine_cheapest(self.state, seat)
        if fined is not None:
            self.gen += 1
            self.rec.fine(self._turn, seat, fined.name)
            self.last_events = [{"type": "fine", "actor": seat}]     # public: NO item (D14)
            self.phase_ends_at = self.now() + self.DECISION_S
            return True
        n0 = len(self.rec.rows)
        self._emit_human_action(seat, Shoot(self._seized_target(seat, seat)))
        # v2-1: even the timeout auto-shot obeys a seized trigger
        for e in self.extras.values():
            e.sync(self.state)
        self._run_bots()
        self._drain_skips()
        self.last_events = [a for a in (_anim(r) for r in self.rec.rows[n0:]) if a]
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
                "flip" if isinstance(action, Flip) else
                "tax" if isinstance(action, PayTax) else "item")
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
        self._notes = []
        self.gen += 1
        self.last_events = []          # a gen bump REBROADCASTS — stale beats must not replay
        self.pending_offer = {"from": seat, "to": to, "give": list(give), "want": list(want)}

    def trade_withdraw(self, seat):
        if self.pending_offer is None or self.pending_offer["from"] != seat:
            raise IllegalAction("no offer of yours is pending")
        self._notes = []
        self.gen += 1
        self.last_events = []          # a gen bump REBROADCASTS — stale beats must not replay
        self.pending_offer = None

    def trade_respond(self, seat, accept):
        if self.pending_offer is None or self.pending_offer["to"] != seat:
            raise IllegalAction("no offer for you is pending")
        off = self.pending_offer
        self._notes = []
        self.gen += 1
        self.last_events = []          # settle re-sets it below; decline/cancel carry only the private note
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
        return {"type": "announce", "total": len(ch.bullets),
                "live": sum(1 for s in ch.bullets if s == Bullet.LIVE)}

    @property
    def winner(self):
        return self.state.winner

    @property
    def current(self):
        return self.state.current_id

    # ---- hold (spec 2026-07-11 §4): a dropped human freezes the car for everyone.
    #      Supersedes ui-v2 D11 for DROPS; D11's fine/auto-shot machinery still
    #      governs connected stalling untouched. gen does NOT move — a hold is
    #      not a game mutation, it rides the view like every reconnect-safe state.

    HOLD_S = 300.0                       # 5:00 at signal, then the conductor chooses

    def hold(self, missing):
        self.hold_missing = set(missing)
        if self.held_since is not None:  # already held — refresh the missing list only
            return
        self.held_since = self.now()
        self.hold_expired = False
        if self.held_remaining is None:  # a restore may arrive pre-frozen (from_dict)
            self.held_remaining = (None if self.phase_ends_at is None
                                   else max(0.0, self.phase_ends_at - self.now()))
        self.phase_ends_at = None        # nothing fires while the car is held

    def release(self):
        if self.held_since is None:
            return
        if self.held_remaining is not None:
            # +3.0 — the 3·2·1 countdown beat plays before the clock bites again
            self.phase_ends_at = self.now() + 3.0 + self.held_remaining
        self.held_since = None
        self.held_remaining = None
        self.hold_missing = set()
        self.hold_expired = False
        self.hold_chooser = None

    # ---- snapshot (spec 2026-07-11 §4): the session file's last line IS the game ----

    def to_dict(self):
        """Serialize everything needed to resume play mid-game. JSON-safe; enums
        travel by NAME; the rng travels via random.Random.getstate() so a restored
        room draws the SAME future (rng continuity). `messages` are not carried —
        comms are engine-off online (comms_enabled=False, __init__). The Recorder
        archive is not carried either: a restored room records a fresh archive."""
        st = self.state
        return {
            "v": 1,
            "gen": self.gen,
            "phase": self.phase,
            "remaining": (None if self.phase_ends_at is None
                          else self.phase_ends_at - self.now()),
            "held_remaining": self.held_remaining,   # a crash DURING a hold keeps the frozen clock
            "human": sorted(self.human),
            "seating": list(self.seating),
            "extra_turn": self.extra_turn,
            "feed": list(self.feed),
            "turn": self._turn,
            "notes": [[s, n] for s, n in self._notes],
            "pending_offer": self.pending_offer,
            "trade_result": self._trade_result,
            "last_trade_items": self._last_trade_items,
            "pending_warrant": self.pending_warrant,
            "handler": self.handler,
            "pending_bot_shot": (list(self.pending_bot_shot)
                                 if self.pending_bot_shot is not None else None),
            "dragnet": {str(k): v for k, v in self._dragnet.items()},
            "extras": {str(s): {"scan_live": e.scan_live, "scan_of": e.scan_of,
                                "total": e.total, "live": e.live,
                                "lp": e._lp, "ln": e._ln}
                       for s, e in self.extras.items()},
            "state": {
                "players": [{
                    "id": p.id, "team": p.team.name, "cover": p.cover, "alive": p.alive,
                    "inventory": {it.name: c for it, c in p.inventory.items()},
                    "immunity_against": sorted(p.immunity_against),
                    "shaken": p.shaken, "flipback_discount": p.flipback_discount,
                    "poison_tick": p.poison_tick, "specials": dict(p.specials),
                } for p in st.players],
                "order": list(st.order),
                "current_id": st.current_id,
                "chamber": {"bullets": [b.name for b in st.chamber.bullets],
                            "pos": st.chamber.pos},
                "rng": _rng_dump(st.rng._r),
                "use_counts": {it.name: c for it, c in st.use_counts.items()},
                "poison_armed": st.poison_armed,
                "poison_used_this_turn": st.poison_used_this_turn,
                "bonus_pending": st.bonus_pending,
                "winner": st.winner,
                "msgs_this_turn": st.msgs_this_turn,
                "tax_pending": st.tax_pending,
                "tax_silent": st.tax_silent,
                "comms_enabled": st.comms_enabled,
                "social_enabled": st.social_enabled,
                "harm": [[k[0], k[1], v] for k, v in st.harm.items()],
                "help": [[k[0], k[1], v] for k, v in st.help.items()],
                "last_skipped": list(st.last_skipped),
                "last_ticks": [list(t) for t in st.last_ticks],
            },
        }

    @classmethod
    def from_dict(cls, d, now_fn=time.time):
        from social_roulette.engine.state import GameState, Player, Chamber
        from social_roulette.engine.constants import Team
        from social_roulette.engine.rng import SeededRng
        sd = d["state"]
        players = [Player(
            id=p["id"], team=Team[p["team"]], cover=p["cover"], alive=p["alive"],
            inventory={Item[k]: v for k, v in p["inventory"].items()},
            immunity_against=set(p["immunity_against"]),
            shaken=p["shaken"], flipback_discount=p["flipback_discount"],
            poison_tick=p["poison_tick"], specials=dict(p["specials"]),
        ) for p in sd["players"]]
        chamber = Chamber(bullets=[Bullet[b] for b in sd["chamber"]["bullets"]],
                          pos=sd["chamber"]["pos"])
        rng = SeededRng(0)
        rng._r = _rng_load(sd["rng"])
        state = GameState(players=players, order=list(sd["order"]),
                          current_id=sd["current_id"], chamber=chamber, rng=rng)
        state.use_counts = {Item[k]: v for k, v in sd["use_counts"].items()}
        state.poison_armed = sd["poison_armed"]
        state.poison_used_this_turn = sd["poison_used_this_turn"]
        state.bonus_pending = sd["bonus_pending"]
        state.winner = sd["winner"]
        state.msgs_this_turn = sd["msgs_this_turn"]
        state.tax_pending = sd["tax_pending"]
        state.tax_silent = sd["tax_silent"]
        state.comms_enabled = sd["comms_enabled"]
        state.social_enabled = sd["social_enabled"]
        state.harm = {(a, b): v for a, b, v in sd["harm"]}
        state.help = {(a, b): v for a, b, v in sd["help"]}
        state.last_skipped = list(sd["last_skipped"])
        state.last_ticks = [tuple(t) for t in sd["last_ticks"]]
        r = object.__new__(cls)
        r.now = now_fn
        r.gen = d["gen"]
        r.phase = d["phase"]
        r.phase_ends_at = None if d["remaining"] is None else now_fn() + d["remaining"]
        r.human = set(d["human"])
        r.state = state
        r.pending_offer = d["pending_offer"]
        r._trade_result = d["trade_result"]
        r._last_trade_items = d["last_trade_items"]
        r.extra_turn = d["extra_turn"]
        r._notes = [(s, n) for s, n in d["notes"]]
        r.pending_warrant = d["pending_warrant"]
        r.handler = d["handler"]
        r.pending_bot_shot = tuple(d["pending_bot_shot"]) if d["pending_bot_shot"] else None
        r._dragnet = {int(k): {int(pid): hand for pid, hand in v.items()}
                      for k, v in d["dragnet"].items()}   # JSON stringified both key layers
        r.seating = list(d["seating"])
        r.extras = {}
        for s, ed in d["extras"].items():
            e = Extras()
            e.scan_live = ed["scan_live"]
            e.scan_of = ed["scan_of"]
            e.total = ed["total"]
            e.live = ed["live"]
            e._lc = state.chamber          # SAME logical chamber — scans stay valid
            e._lp = ed["lp"]
            e._ln = ed["ln"]
            r.extras[int(s)] = e
        r.feed = list(d["feed"])
        r.rec = Recorder(0)                # fresh archive on restore (docstring above)
        r._turn = d["turn"]
        r.last_events = []                 # a restore settles silently — no beats replay
        r.held_since = None                # a restored car is re-held EXPLICITLY (boot path)
        r.held_remaining = d.get("held_remaining")
        r.hold_missing = set()
        r.hold_expired = False
        r.hold_chooser = None
        return r

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
            "poison_armed": self.state.poison_armed,
            "use_counts": {it.name: c for it, c in self.state.use_counts.items()},
            "use_limit": consumption_limit(self.state),
            "teams_active": teams_active(self.state),
            "flipback_discount": me.flipback_discount,     # own discount only — never another seat's
        })
        if self.pending_offer and seat in (self.pending_offer["from"], self.pending_offer["to"]):
            v["pending_offer"] = dict(self.pending_offer)
        if self.pending_warrant and self.pending_warrant["user"] == seat:
            v["warrant_pick"] = {k: self.pending_warrant[k] for k in ("target", "hand", "specials")}
        if seat in self._dragnet:
            v["dragnet_report"] = self._dragnet[seat]
        # v2: the shooter is NEVER flagged, and a live seize must not hide the button
        # from other holders (a vanishing button would leak it) — they alarm on attempt.
        v["handler_available"] = (
            self.winner is None
            and self.phase in ("decision", "aiming")
            and seat != self.state.current_id
            and player_by_id(self.state, seat).alive
            and player_by_id(self.state, seat).specials.get("HANDLER", 0) > 0)
        if v["handler_available"]:
            v["seize_ids"] = legal_targets(self.state, self.state.current_id)
        if self.held_since is not None:      # rides EVERY view — reconnect-safe (standing law)
            v["hold"] = {"missing": sorted(self.hold_missing), "since": self.held_since,
                         "deadline": self.held_since + self.HOLD_S,
                         "expired": self.hold_expired, "chooser": self.hold_chooser}
        return v

    def events_for(self, seat):
        """Per-seat enrichment of the shared public `last_events`: a draw event gains
        THIS seat's own refill; a settled trade gains its items ONLY for the two
        parties; and a declined/cancelled offer surfaces a private note to the parties.
        Never leaks another seat's hand or the bullet order."""
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
            if e["type"] == "item" and e.get("item") == "MAGNET":
                if e.get("actor") == seat and e.get("seq") is not None:
                    row = next((r for r in self.rec.rows if r["seq"] == e["seq"]), None)
                    ex = json.loads(row["extra"]) if row and row.get("extra") else {}
                    if ex.get("discarded"):
                        e["you"] = {"ejected": ex["discarded"]}
                e.pop("seq", None)
            if e["type"] == "trade" and seat in (e.get("actor"), e.get("target")):
                if self._last_trade_items is not None:
                    e["items"] = self._last_trade_items
            out.append(e)
        tr = self._trade_result
        if tr and tr["kind"] in ("declined", "cancelled") and seat in tr["parties"]:
            out.append({"type": "trade_private", "kind": tr["kind"]})
        for (who, payload) in self._notes:
            if who == seat:
                out.append(dict(payload))
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
        self._notes = []
        act = acts[i]
        if isinstance(act, Shoot):                       # v2: a seized trigger obeys the
            act = Shoot(self._seized_target(seat, act.target_id))   # puppeteer, silently
        n0 = len(self.rec.rows)
        self._emit_human_action(seat, act)
        for e in self.extras.values():
            e.sync(self.state)
        self._run_bots()
        self._drain_skips()
        self.last_events = [a for a in (_anim(r) for r in self.rec.rows[n0:]) if a]
        self._derive_extra_turn()
        # The turn only resolves via a SHOT (fines/auto-shoot flow through the same shot
        # path). A non-turn-ending action (item use, incl. a MAGNET reload) must NOT re-begin
        # the phase — that would drop DECISION back to a fresh 60s TALK (§4.1/§4.3). Re-begin
        # only when the delta actually ended the turn; otherwise just bump gen once.
        if self.winner is not None or any(e.get("type") in ("shot", "tax") for e in self.last_events):
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
        self._notes = []
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
        self.last_events = [a for a in (_anim(r) for r in self.rec.rows[n0:]) if a]
        self._derive_extra_turn()
        self.gen += 1                 # a flip never ends the turn → never re-begin the phase (C1/§4.1)

    def _finish_delta(self, n0):
        for e in self.extras.values():
            e.sync(self.state)
        self._run_bots()
        self._drain_skips()
        self.last_events = [a for a in (_anim(r) for r in self.rec.rows[n0:]) if a]
        self._derive_extra_turn()
        self._begin_phase_for_current()

    def use_special(self, seat, kind, target=None):
        """WARRANT / DRAGNET — own turn, talk or decision phase. ANONYMOUS: no
        public event; results ride private notes / the view."""
        if self.winner is not None or seat != self.state.current_id:
            raise IllegalAction("not your turn")
        if self.phase not in ("talk", "decision"):
            raise IllegalAction("not now")
        self._trade_result = None
        self._last_trade_items = None
        self._notes = []
        try:
            if kind == "DRAGNET":
                rep = SP.dragnet(self.state, seat)
                self._dragnet[seat] = rep["hands"]
                self.rec.special(self._turn, seat, kind)
            elif kind == "WARRANT":
                if self.pending_warrant is not None:
                    raise IllegalAction("a warrant is already open")
                rep = SP.warrant_inspect(self.state, seat, int(target))
                self.pending_warrant = {"user": seat, **rep}
                self.rec.special(self._turn, seat, kind, int(target))
            else:
                raise IllegalAction("unknown special")
        except ValueError as e:
            raise IllegalAction(str(e))
        self.gen += 1
        self.last_events = []              # NOTHING public — anonymity law

    def warrant_take(self, seat, name):
        pw = self.pending_warrant
        if pw is None or pw["user"] != seat:
            raise IllegalAction("no warrant of yours is open")
        try:
            res = SP.warrant_take(self.state, seat, pw["target"], name or None)
        except ValueError as e:
            raise IllegalAction(str(e))
        self.pending_warrant = None
        self._notes = [(pw["target"], {"type": "searched", "taken": res["took"]})]
        self.gen += 1
        self.last_events = []

    def handler_seize(self, seat, target, gen=None):
        """v2 (2026-07-11): ONE atomic move during ANOTHER player's decision/aiming —
        consume your HANDLER and silently re-aim their coming shot at `target`
        (a shot THEY could legally take). The shooter is told NOTHING: no note,
        no lock, no gen bump — the table sees nothing until the bullet lands.
        First seize locks the trigger; later attempts alarm PRIVATELY (the error).
        `gen` stamps WHICH turn the seizer was aiming at — a confirm that crosses
        the turn boundary in flight must die, never re-aim the NEXT shooter
        (atomicity law: not executed legally -> not spent, no effect)."""
        p = player_by_id(self.state, seat)
        victim = self.state.current_id
        if gen is not None and int(gen) != self.gen:
            raise IllegalAction("the moment has passed")
        if (self.winner is not None or not p.alive or seat == victim
                or self.phase not in ("decision", "aiming")):
            raise IllegalAction("nothing to seize")
        if self.handler is not None:
            raise IllegalAction("the trigger is already held")
        if p.specials.get("HANDLER", 0) < 1:
            raise IllegalAction("no handler left")
        if target not in legal_targets(self.state, victim):
            raise IllegalAction("not a shot they could take")
        p.specials["HANDLER"] -= 1
        self.handler = {"by": seat, "victim": victim, "target": int(target)}
        self.rec.special(self._turn, seat, "HANDLER", victim, aim=int(target))
        # NO gen bump, NO event, NO note — even the ledger's aggregate count must not
        # move until the next natural delta (the shot). Timer untouched — SECRECY LAW.

    def _seized_target(self, shooter, fallback):
        """The puppeteer's pick if this shooter's trigger is held, else the shooter's
        own choice. Consumes the seize — every turn ends in exactly one shot."""
        if self.handler is not None and self.handler["victim"] == shooter:
            fallback = self.handler["target"]
        self.handler = None
        return fallback

    def pay_tax(self, seat, tier, item_names):
        """Resolve your shakedown with a CHOSEN payment (tier 6/4) or skip (0)."""
        if self.winner is not None or seat != self.state.current_id:
            raise IllegalAction("not your turn")
        if self.phase != "tax":
            raise IllegalAction("no shakedown to settle")
        try:
            sacrifice = [Item[n] for n in item_names or []]
        except KeyError:
            raise IllegalAction("bad payment item")
        self._trade_result = None
        self._last_trade_items = None
        self._notes = []
        n0 = len(self.rec.rows)
        try:
            self._emit_human_action(seat, PayTax(int(tier), sacrifice))
        except ValueError as e:
            raise IllegalAction(str(e))
        for e in self.extras.values():
            e.sync(self.state)
        self._run_bots()
        self._drain_skips()
        self.last_events = [a for a in (_anim(r) for r in self.rec.rows[n0:]) if a]
        self._derive_extra_turn()
        self._begin_phase_for_current()

    def _emit_human_action(self, seat, action):
        """Step the engine for the human's one committed action and record the
        matching event(s), mirroring take_policy_turn's per-sub-action emission."""
        alive_before = living_ids(self.state)
        ch_before = self.state.chamber
        if isinstance(action, Shoot):
            armed = self.state.poison_armed
            ev = engine_step(self.state, seat, action)
            self.rec.shot(self._turn, seat, action.target_id, ev["bullet"].name,
                          ev["damage"], ev["killed"], armed)
            tick_dead = {v for (v, _, k) in self.state.last_ticks if k}
            for d in sorted(alive_before - living_ids(self.state)):
                if d not in tick_dead:
                    self.rec.elimination(self._turn, d, seat)
            self._drain_ticks()
            if self.state.chamber is not ch_before and self.state.winner is None:
                live = sum(1 for s in self.state.chamber.bullets if s == Bullet.LIVE)
                self.rec.reload(self._turn, "death" if len(living_ids(self.state)) < len(alive_before) else "empty",
                                len(self.state.chamber.bullets), live)
            self._record_draws(ev)
            self._drain_skips()
        elif isinstance(action, PayTax):
            engine_step(self.state, seat, action)
            self.rec.tax(self._turn, seat, action.tier)
            self._drain_skips()                             # tier 0 logs the skip
        elif isinstance(action, Flip):
            tgt = action.target_id
            engine_step(self.state, seat, action)
            self.rec.flip(self._turn, seat, tgt, [it.name for it in action.sacrifice],
                          player_by_id(self.state, tgt).team.name)
        else:                                       # UseItem (Trade/Speak impossible: social/comms disabled)
            it = getattr(action, "item", None)
            ev = engine_step(self.state, seat, action)
            if it == Item.GEIGER:
                self.extras[seat].scan(ev)
            # MAGNET: every seat's stale scan clears via Extras.sync (window len change)
            eff = {}
            if it == Item.MAGNET and ev.get("discarded") is not None:
                eff = {"discarded": ev["discarded"].name}             # private reveal (B4, user 2026-07-10)
            self.rec.item_used(self._turn, seat, action.item.name, action.target_id, eff)
            if self.state.chamber is not ch_before and self.state.winner is None:   # Magnet emptied it → reload
                live = sum(1 for s in self.state.chamber.bullets if s == Bullet.LIVE)
                self.rec.reload(self._turn, "empty", len(self.state.chamber.bullets), live)
            self._record_draws(ev)
            self._drain_skips()

    def _record_draws(self, ev):
        """A reload refill (empty/beer/self-death) fans out per-seat draws — record them
        so events_for can hand each seat ONLY its own attempted/received (privacy)."""
        if ev and ev.get("draws"):
            self.rec.draw(self._turn, {pid: {"attempted": [i.name for i in d["attempted"]],
                                             "received": [i.name for i in d["received"]]}
                                       for pid, d in ev["draws"].items()})

    def _drain_ticks(self):
        """Poison ticks fired at a turn advance (or a death) are PUBLIC events —
        flush them; a tick KILL credits the poisoner, not the acting seat."""
        for (v, poisoner, k) in self.state.last_ticks:
            self.rec.tick(self._turn, poisoner, v, k)
            if k:
                self.rec.elimination(self._turn, v, poisoner)
        self.state.last_ticks.clear()
        for batch in self.state.last_draws:              # tick-death deals (RELOAD=REDRAW)
            self._record_draws({"draws": batch})
        self.state.last_draws.clear()

    def _drain_skips(self):
        """A shaken seat skipped at turn-advance is a PUBLIC event — flush the
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

    def _humans_hold_handler(self):
        return any(player_by_id(self.state, h).alive and
                   player_by_id(self.state, h).specials.get("HANDLER", 0) > 0
                   for h in self.human)

    def _run_bots(self):
        while self.state.winner is None and self.is_bot(self.state.current_id):
            pid = self.state.current_id
            self._turn += 1
            hold = self._humans_hold_handler()
            res = take_policy_turn(self.state, pid, random_policy, self.extras,
                                   rec=self.rec, turn_idx=self._turn, stop_before_shot=hold)
            if res.get("pending_shot") is not None and self.state.current_id == pid                     and self.state.winner is None:
                # park the shot; open the aiming window (HANDLER can seize it)
                self.pending_bot_shot = (pid, res["pending_shot"])
                self.gen += 1
                self.phase = "aiming"
                self.phase_ends_at = self.now() + self.AIMING_S
                return

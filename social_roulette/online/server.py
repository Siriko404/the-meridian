"""Async FastAPI bullet around the sync Room core.

One asyncio.Lock per room serializes all mutations of that room's Room object
(no two client messages mutate one GameState concurrently). A human that drops
leaves an empty seat; reconnect with the same token reclaims the seat.
"""
import asyncio
import os
import secrets
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from social_roulette.online import storage
from social_roulette.online.room import Room, IllegalAction

app = FastAPI()
HERE = os.path.dirname(__file__)
STATIC = os.path.join(HERE, "static")
app.mount("/static", StaticFiles(directory=STATIC), name="static")   # logo + shared UI assets

PROFILES = storage.load_profiles()          # papers, hot in memory; storage owns the file


# ---- identity endpoints (spec 2026-07-11 §2) — pure (status, body) helpers, thin routes ----

def papers_create(fi, li, portrait):
    fi, li = str(fi or "").strip().upper(), str(li or "").strip().upper()
    if not (len(fi) == 1 and fi.isalpha() and len(li) == 1 and li.isalpha()):
        return 400, {"msg": "two letters make a monogram"}
    try:
        portrait = int(portrait)
    except (ValueError, TypeError):
        return 400, {"msg": "papers need a face"}
    if not 0 <= portrait <= 11:
        return 400, {"msg": "papers need a face"}
    p = storage.create_profile(fi + "." + li + ".", portrait)
    PROFILES[p["pid"]] = p
    return 200, p


def papers_lookup(fi, li, pid):
    monogram = (str(fi or "").strip().upper() + "." + str(li or "").strip().upper() + ".")
    p = PROFILES.get(str(pid or "").strip().upper())
    if not p or p["initials"] != monogram:
        return 404, {"msg": "no such papers"}
    return 200, p


def journeys(pid):
    return 200, {"journeys": storage.journeys_for(str(pid or "").strip().upper())}


def record_check(code):
    """The session file names every hand and the bullet order — it opens only
    once the line has ended (spec §4: no mid-game access, ever)."""
    code = str(code or "").strip().upper()
    if storage.session_read_meta(code) is None:
        return 404, None
    if not storage.session_is_ended(code):
        return 403, None
    return 200, storage.session_path(code)


class Lobby:
    def __init__(self, code):
        self.code = code
        self.members = []          # list of {"pid","name","portrait","seat","ws","host","ready"}
        self.seats = 5             # the conductor's dial, 5-12 (spec §3); bots fill the gap
        self.room = None           # Room once started
        self.lock = asyncio.Lock()
        self.deadline_task = None   # pending asyncio task that fires the phase deadline
        self.hold_task = None       # pending 5:00 hold-expiry watcher (spec §4)
        self.house_seats = {}       # seat -> {"name","portrait"} after SEAT THE HOUSE:
                                    # the cover keeps playing, identity never flickers
        self.cold = False           # boot-restored car: release needs the READY VOTE
                                    # (user ruling: "present and vote ready"), not mere presence
        self.abandoned = False      # END THE LINE happened: room is gone, record awaits burn

    def by_pid(self, pid):
        return next((m for m in self.members if m.get("pid") == pid), None)


LOBBIES = {}


def _seed_from(code):
    return abs(hash(code)) % 1_000_000


async def _send(ws, msg):
    try:
        await ws.send_json(msg)
    except Exception:
        pass


async def _deadline(lb, gen):
    try:
        await asyncio.sleep(max(0.0, lb.room.phase_ends_at - time.time()))
    except asyncio.CancelledError:
        return
    payloads = None
    async with lb.lock:
        if lb.room is None or lb.room.gen != gen:
            return
        acted = lb.room.on_deadline()
        if acted:
            payloads = _capture_payloads(lb)
            _persist(lb)
    if acted:
        await _broadcast_views(lb, payloads)
        if lb.room.winner is not None:
            for m in lb.members:
                if m["ws"] is not None:
                    await _send(m["ws"], {"type": "end", "winner": lb.room.winner})
    else:
        # Early wake: asyncio.sleep ran on the loop's MONOTONIC clock but the deadline
        # is WALL clock — skew (or a backward step) can land us here a hair before
        # phase_ends_at. on_deadline() no-oped, gen is unchanged, and nothing else will
        # broadcast — re-arm or the phase timer is dead forever (nobody fined/auto-shot).
        _schedule_deadline(lb)


def _schedule_deadline(lb):
    # Never cancel the currently-running _deadline task (it is about to return on its own);
    # cancelling self would surface CancelledError at the winner end-broadcast and truncate it.
    if lb.deadline_task is not None and lb.deadline_task is not asyncio.current_task():
        lb.deadline_task.cancel()
    lb.deadline_task = None
    if lb.room is not None and lb.room.winner is None and lb.room.phase_ends_at is not None:
        lb.deadline_task = asyncio.create_task(_deadline(lb, lb.room.gen))


def _persist(lb):
    # Journal the whole room AFTER a mutation, inside the same lock/critical
    # section as _capture_payloads (spec §4: one line per play; the last line
    # restores the game). A winner closes the record with an `ended` line —
    # only then does /session/<code>/record open (the file names every hand).
    if lb.room is None:
        return
    storage.session_append(lb.code, {"t": time.time(), "gen": lb.room.gen,
                                     "snapshot": lb.room.to_dict()})
    if lb.room.winner is not None:
        storage.session_append(lb.code, {"ended": lb.room.winner, "t": time.time()})


def _appoint_chooser(lb):
    # the conductor if aboard, else the earliest connected human — the 5:00
    # choice must never wait on someone who is gone (spec §4)
    seated = [m for m in lb.members if m["seat"] is not None and m["ws"] is not None]
    host = next((m for m in seated if m["host"]), None)
    pick = host or (seated[0] if seated else None)
    return pick["seat"] if pick else None


async def _hold_watch(lb, since):
    try:
        await asyncio.sleep(max(0.0, since + Room.HOLD_S - time.time()))
    except asyncio.CancelledError:
        return
    async with lb.lock:
        if lb.room is None or lb.room.held_since != since or lb.room.hold_expired:
            return                       # held_since is the gen-guard of holds
        lb.room.hold_expired = True
        lb.room.hold_chooser = _appoint_chooser(lb)
        _persist(lb)
    await _broadcast_views(lb)


async def _sync_hold(lb):
    """Reconcile the hold with who is actually connected (call on every drop and
    rejoin). Enters, refreshes, or releases the hold; broadcasts on change."""
    changed = False
    async with lb.lock:
        r = lb.room
        if r is None or r.winner is not None:
            return
        missing = sorted(m["seat"] for m in lb.members
                         if m["seat"] is not None and m["ws"] is None
                         and m["seat"] in r.human)
        if missing and r.held_since is None:
            r.hold(missing)
            r.hold_chooser = _appoint_chooser(lb)
            if lb.deadline_task is not None:     # the frozen clock must not fire
                lb.deadline_task.cancel()
                lb.deadline_task = None
            if lb.hold_task is not None:
                lb.hold_task.cancel()
            lb.hold_task = asyncio.create_task(_hold_watch(lb, r.held_since))
            _persist(lb)
            changed = True
        elif missing and r.held_since is not None and set(missing) != r.hold_missing:
            r.hold(missing)                      # another agent left / one came back
            r.hold_chooser = _appoint_chooser(lb)
            _persist(lb)
            changed = True
        elif not missing and r.held_since is not None and not lb.cold:
            r.release()                          # all aboard — 3·2·1 rides the new deadline
            if lb.hold_task is not None:         # (cold cars wait for the READY VOTE instead)
                lb.hold_task.cancel()
                lb.hold_task = None
            _persist(lb)
            changed = True
    if changed:
        await _broadcast_views(lb)               # release path re-arms the deadline here


def restore_sessions():
    """Boot restore (spec §4): every unfinished session file becomes a HELD car
    waiting for its humans. Sync + broadcast-free — nobody is connected at boot."""
    storage.sessions_sweep(7)
    for meta in storage.sessions_unfinished():
        last = storage.session_read_last(meta["code"])
        if not last or "snapshot" not in last:
            continue
        lb = Lobby(meta["code"])
        lb.seats = meta.get("seats", 5)
        lb.members = [{"pid": mm["pid"], "name": mm["initials"], "portrait": mm["portrait"],
                       "seat": mm["seat"], "ws": None, "host": i == 0, "ready": False}
                      for i, mm in enumerate(meta.get("members", []))]
        lb.room = Room.from_dict(last["snapshot"])
        lb.room.hold(set(lb.room.human))
        lb.cold = True
        LOBBIES[lb.code] = lb


def _cold_touch(lb):
    # the 5:00 signal clock starts at the FIRST rejoin, not at boot (spec §4)
    if lb.cold and lb.hold_task is None and lb.room is not None:
        lb.room.held_since = time.time()
        lb.room.hold_chooser = _appoint_chooser(lb)
        lb.hold_task = asyncio.create_task(_hold_watch(lb, lb.room.held_since))


async def _try_cold_release(lb):
    """The ready vote: all seated humans aboard AND ready → 3·2·1 → play."""
    changed = False
    async with lb.lock:
        r = lb.room
        if r is None or not lb.cold:
            return
        seated = [m for m in lb.members if m["seat"] is not None and m["seat"] in r.human]
        if seated and all(m["ws"] is not None and m.get("ready") for m in seated):
            lb.cold = False
            r.release()
            if lb.hold_task is not None:
                lb.hold_task.cancel()
                lb.hold_task = None
            _persist(lb)
            changed = True
    if changed:
        await _broadcast_views(lb)


async def _apply_hold_choice(lb, seat, kind):
    """The conductor's 5:00 call (spec §4). Returns (error, payloads, ended)."""
    async with lb.lock:
        r = lb.room
        if r is None or not r.hold_expired or seat != r.hold_chooser:
            return "not your call", None, False
        if kind == "bot":
            # SEAT THE HOUSE: the missing seats' covers play on as bots;
            # their papers can no longer reclaim them
            for s in sorted(r.hold_missing):
                r.human.discard(s)
                mm = next((x for x in lb.members if x["seat"] == s), None)
                if mm:
                    lb.house_seats[s] = {"name": mm["name"], "portrait": mm["portrait"]}
                    lb.members.remove(mm)
            r.release()
            if lb.hold_task is not None:
                lb.hold_task.cancel()
                lb.hold_task = None
            if r.is_bot(r.state.current_id):
                r.last_events = []           # the house plays the frozen turn NOW —
                r._run_bots()                # nobody waits out a dead man's fines
                r._begin_phase_for_current()
            _persist(lb)
            return None, _capture_payloads(lb), False
        if kind == "end":
            # END THE LINE: no verdict; the record closes and opens for download
            storage.session_append(lb.code, {"t": time.time(), "gen": r.gen,
                                             "snapshot": r.to_dict()})
            storage.session_append(lb.code, {"ended": "abandoned", "t": time.time()})
            lb.room = None
            lb.abandoned = True
            if lb.hold_task is not None:
                lb.hold_task.cancel()
                lb.hold_task = None
            if lb.deadline_task is not None:
                lb.deadline_task.cancel()
                lb.deadline_task = None
            return None, None, True
        return "bad payload", None, False


def _capture_payloads(lb):
    # Snapshot each seat's per-seat delta + view WHILE the room lock is held, so a
    # concurrent handler/deadline cannot mutate the room between sends (I1: per-seat
    # events_for/view were formerly recomputed mid-broadcast, outside any lock, with
    # awaits in between — losing or duplicating deltas). Callers pass this to _broadcast_views.
    return {m["seat"]: {"events": lb.room.events_for(m["seat"]), **lb.room.view(m["seat"])}
            for m in lb.members if m["seat"] is not None}


def _portraits(lb):
    # Every seat wears a face: humans their chosen frame, bots the UNUSED frames
    # first (collision-free at any fill — spec §5). Pure + deterministic per
    # broadcast: seating and members' picks are fixed once the car departs.
    out = {m["seat"]: m["portrait"] for m in lb.members if m["seat"] is not None}
    out.update({s: g["portrait"] for s, g in lb.house_seats.items()})   # covers play on
    used = set(out.values())
    pool = [f for f in range(12) if f not in used]
    if lb.room is not None:
        for s in lb.room.seating:
            if s not in out:
                out[s] = pool.pop(0) if pool else s % 12
    return out


async def _broadcast_views(lb, payloads=None):
    roster = {m["seat"]: m["name"] for m in lb.members if m["seat"] is not None}
    roster.update({s: g["name"] for s, g in lb.house_seats.items()})    # identity never flickers
    portraits = _portraits(lb)
    vote = None
    if lb.cold and lb.room is not None:      # the ready-vote tally rides the message —
        vote = {"cold": True,                # it is lobby knowledge, not room knowledge
                "ready": {m["seat"]: bool(m.get("ready") and m["ws"] is not None)
                          for m in lb.members if m["seat"] is not None}}
    for m in lb.members:
        if m["ws"] is not None and m["seat"] is not None:
            # Mutating paths pass a lock-captured snapshot; the no-mutation join rebroadcast
            # (payloads is None) computes fresh — the room is not changing under it.
            p = payloads[m["seat"]] if payloads is not None else {
                "events": lb.room.events_for(m["seat"]), **lb.room.view(m["seat"])}
            out = {"type": "view", "roster": roster, "portraits": portraits, **p}
            if vote:
                out["hold_vote"] = vote
            await _send(m["ws"], out)
    _schedule_deadline(lb)


async def _lobby_state(lb):
    members = [{"name": m["name"], "portrait": m["portrait"], "seat": m["seat"],
                "host": m["host"], "ready": m.get("ready", False)} for m in lb.members]
    all_ready = all(m.get("ready") for m in lb.members)
    for i, m in enumerate(lb.members):
        if m["ws"] is not None:
            # per-recipient "host"/"you": conductor inheritance must reach the heir's DEPART
            # button, and rows carry NO pids (a pid is a credential — never broadcast)
            await _send(m["ws"], {"type": "lobby", "code": lb.code, "seats": lb.seats,
                                  "members": members, "host": m["host"], "you": i,
                                  "all_ready": all_ready})


@app.on_event("startup")
async def _boot_restore():
    restore_sessions()      # held cars survive the server (spec §4)


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC, "game", "index.html"))


@app.get("/v1")
async def index_v1():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/papers")
async def papers_post(body: dict):
    st, out = papers_create(body.get("fi"), body.get("li"), body.get("portrait"))
    return JSONResponse(out, status_code=st)


@app.get("/papers")
async def papers_get(fi: str = "", li: str = "", pid: str = ""):
    st, out = papers_lookup(fi, li, pid)
    return JSONResponse(out, status_code=st)


@app.get("/journeys")
async def journeys_get(pid: str = ""):
    st, out = journeys(pid)
    return JSONResponse(out, status_code=st)


@app.get("/session/{code}/record")
async def record_get(code: str):
    st, path = record_check(code)
    if st != 200:
        return JSONResponse({"msg": "the line is still running" if st == 403
                             else "no such record"}, status_code=st)
    return FileResponse(path, media_type="application/jsonl",
                        filename="meridian-" + code.upper() + ".jsonl")


@app.websocket("/ws")
async def ws(ws: WebSocket):
    await ws.accept()
    lb = None
    me = None
    try:
        while True:
            msg = await ws.receive_json()
            t = msg.get("type")

            if t == "join":
                code = (msg.get("code") or "").strip().upper() or secrets.token_hex(2).upper()
                prof = PROFILES.get(str(msg.get("pid") or "").strip().upper())
                if not prof:                             # papers ARE the identity (spec §2)
                    await _send(ws, {"type": "error", "msg": "papers not in order"})
                    continue
                lb = LOBBIES.setdefault(code, Lobby(code))
                me = lb.by_pid(prof["pid"])
                if me:                                   # reconnect: reclaim seat
                    me["ws"] = ws
                else:
                    if lb.room is not None:              # started cars accept only their own
                        await _send(ws, {"type": "error", "msg": "the car has departed"})
                        continue
                    if len(lb.members) >= lb.seats:      # the dial gates boarding (spec §3)
                        await _send(ws, {"type": "error", "msg": "the car is full"})
                        continue
                    me = {"pid": prof["pid"], "name": prof["initials"], "portrait": prof["portrait"],
                          "seat": None, "ws": ws, "host": len(lb.members) == 0, "ready": False}
                    lb.members.append(me)
                await _send(ws, {"type": "joined", "seat": me["seat"], "pid": me["pid"], "host": me["host"]})
                if lb.room is None:
                    await _lobby_state(lb)
                else:
                    _cold_touch(lb)              # first rejoin starts the 5:00 signal clock
                    await _broadcast_views(lb)
                    await _sync_hold(lb)         # a rejoin may release the held car

            elif t == "ready" and lb and me and (lb.room is None or lb.cold):
                me["ready"] = bool(msg.get("on"))
                if lb.room is None:
                    await _lobby_state(lb)
                else:                            # the cold-car vote (spec §4)
                    await _try_cold_release(lb)
                    if lb.cold:                  # not yet — show the fresh tally
                        await _broadcast_views(lb)

            elif t == "seats" and lb and me and me["host"] and lb.room is None:
                try:
                    n = int(msg.get("n", -1))
                except (ValueError, TypeError):
                    await _send(ws, {"type": "error", "msg": "bad payload"})
                    continue
                if not 5 <= n <= 12 or n < len(lb.members):
                    await _send(ws, {"type": "error", "msg": "5 to 12 seats, never fewer than aboard"})
                    continue
                lb.seats = n
                await _lobby_state(lb)

            elif t == "start" and lb and me and me["host"] and lb.room is None:
                if not all(m["ready"] for m in lb.members):   # DEPART is locked until the
                    await _send(ws, {"type": "error", "msg": "the manifest is not ready"})
                    continue                                  # whole manifest is ready (spec §3)
                async with lb.lock:
                    for seat, m in enumerate(lb.members):
                        m["seat"] = seat
                    human_seats = {m["seat"] for m in lb.members if m["seat"] is not None}
                    lb.room = Room(human_seats=human_seats, seed=_seed_from(lb.code),
                                   num_players=lb.seats)
                    storage.session_write_meta(lb.code, {
                        "code": lb.code, "seats": lb.seats, "created": time.time(),
                        "members": [{"pid": m["pid"], "initials": m["name"],
                                     "portrait": m["portrait"], "seat": m["seat"]}
                                    for m in lb.members]})
                    payloads = _capture_payloads(lb)
                    _persist(lb)
                await _broadcast_views(lb, payloads)     # per-seat events_for carries the opening announce

            elif t == "action" and lb and lb.room and me and me["seat"] is not None:
                try:
                    i = int(msg.get("i", -1))
                except (ValueError, TypeError):
                    await _send(ws, {"type": "error", "msg": "bad payload"})
                    continue
                async with lb.lock:
                    try:
                        lb.room.apply(me["seat"], i)
                    except IllegalAction as e:
                        await _send(ws, {"type": "error", "msg": str(e)})
                        continue
                    payloads = _capture_payloads(lb)
                    _persist(lb)
                await _broadcast_views(lb, payloads)     # per-seat events_for carries the delta
                if lb.room.winner is not None:
                    for m in lb.members:
                        if m["ws"] is not None:
                            await _send(m["ws"], {"type": "end", "winner": lb.room.winner})

            elif t == "proceed" and lb and lb.room and me and me["seat"] is not None:
                async with lb.lock:                      # leave the talk phase → decision (Task 7/9 gate)
                    try:
                        lb.room.proceed(me["seat"])
                    except IllegalAction as e:
                        await _send(ws, {"type": "error", "msg": str(e)})
                        continue
                    payloads = _capture_payloads(lb)
                    _persist(lb)
                await _broadcast_views(lb, payloads)

            elif t == "trade_offer" and lb and lb.room and me and me["seat"] is not None:
                try:
                    to = int(msg.get("to", -1))
                except (ValueError, TypeError):
                    await _send(ws, {"type": "error", "msg": "bad payload"})
                    continue
                async with lb.lock:
                    try:
                        lb.room.trade_offer(me["seat"], to,
                                            msg.get("give") or [], msg.get("want") or [])
                    except IllegalAction as e:
                        await _send(ws, {"type": "error", "msg": str(e)})
                        continue
                    payloads = _capture_payloads(lb)
                    _persist(lb)
                await _broadcast_views(lb, payloads)

            elif t == "trade_respond" and lb and lb.room and me and me["seat"] is not None:
                async with lb.lock:
                    try:
                        lb.room.trade_respond(me["seat"], bool(msg.get("accept")))
                    except IllegalAction as e:
                        await _send(ws, {"type": "error", "msg": str(e)})
                        continue
                    payloads = _capture_payloads(lb)
                    _persist(lb)
                await _broadcast_views(lb, payloads)

            elif t == "trade_withdraw" and lb and lb.room and me and me["seat"] is not None:
                async with lb.lock:
                    try:
                        lb.room.trade_withdraw(me["seat"])
                    except IllegalAction as e:
                        await _send(ws, {"type": "error", "msg": str(e)})
                        continue
                    payloads = _capture_payloads(lb)
                    _persist(lb)
                await _broadcast_views(lb, payloads)

            elif t in ("special", "warrant_take", "handler_seize") \
                    and lb and lb.room and me and me["seat"] is not None:
                async with lb.lock:
                    try:
                        if t == "special":
                            lb.room.use_special(me["seat"], str(msg.get("kind", "")),
                                                msg.get("target"))
                        elif t == "warrant_take":
                            lb.room.warrant_take(me["seat"], msg.get("name"))
                        else:
                            lb.room.handler_seize(me["seat"], int(msg.get("target", -1)),
                                                  msg.get("gen"))
                    except (IllegalAction, ValueError, TypeError) as e:
                        await _send(ws, {"type": "error", "msg": str(e) or "bad payload"})
                        continue
                    payloads = _capture_payloads(lb)
                    _persist(lb)
                await _broadcast_views(lb, payloads)
                if lb.room.winner is not None:
                    for m in lb.members:
                        if m["ws"] is not None:
                            await _send(m["ws"], {"type": "end", "winner": lb.room.winner})

            elif t == "tax" and lb and lb.room and me and me["seat"] is not None:
                try:
                    tier = int(msg.get("tier", -1))
                except (ValueError, TypeError):
                    await _send(ws, {"type": "error", "msg": "bad payload"})
                    continue
                async with lb.lock:
                    try:
                        lb.room.pay_tax(me["seat"], tier, msg.get("items") or [])
                    except IllegalAction as e:
                        await _send(ws, {"type": "error", "msg": str(e)})
                        continue
                    payloads = _capture_payloads(lb)
                    _persist(lb)
                await _broadcast_views(lb, payloads)

            elif t == "flip" and lb and lb.room and me and me["seat"] is not None:
                try:                                     # flip with a CHOSEN payment {target, items:[names]}
                    target = int(msg.get("target", -1))
                except (ValueError, TypeError):
                    await _send(ws, {"type": "error", "msg": "bad payload"})
                    continue
                async with lb.lock:
                    try:
                        lb.room.flip(me["seat"], target, msg.get("items") or [])
                    except IllegalAction as e:
                        await _send(ws, {"type": "error", "msg": str(e)})
                        continue
                    payloads = _capture_payloads(lb)
                    _persist(lb)
                await _broadcast_views(lb, payloads)

            elif t == "hold_choice" and lb and lb.room and me and me["seat"] is not None:
                err, payloads, ended = await _apply_hold_choice(
                    lb, me["seat"], str(msg.get("kind") or ""))
                if err:
                    await _send(ws, {"type": "error", "msg": err})
                    continue
                if ended:
                    for m in lb.members:
                        if m["ws"] is not None:
                            await _send(m["ws"], {"type": "end", "winner": None})
                    continue
                await _broadcast_views(lb, payloads)
                if lb.room.winner is not None:       # the house playthrough may end it
                    for m in lb.members:
                        if m["ws"] is not None:
                            await _send(m["ws"], {"type": "end", "winner": lb.room.winner})

            elif t == "chat" and lb and me:
                if lb.room is not None and lb.room.held_since is not None:
                    await _send(ws, {"type": "error", "msg": "the car is held"})
                    continue
                if lb.room is not None and (me["seat"] is None or not lb.room.can_chat(me["seat"])):
                    await _send(ws, {"type": "error", "msg": "silence"})
                    continue
                text = str(msg.get("text", ""))[:200]
                if lb.room is not None:
                    lb.room.feed.append(f"{me['name']}: {text}")
                for m in lb.members:
                    if m["ws"] is not None:
                        await _send(m["ws"], {"type": "chat", "from": me["name"], "text": text})

            elif t == "ping":
                await _send(ws, {"type": "pong"})

    except WebSocketDisconnect:
        if me and lb:
            if lb.room is None and not lb.abandoned:
                # pre-departure a leaver steps OFF the manifest (a ghost would jam the
                # ready-all gate); the earliest remaining boarder inherits the whistle
                if me in lb.members:
                    lb.members.remove(me)
                    if me["host"] and lb.members:
                        lb.members[0]["host"] = True
                    if lb.members:
                        await _lobby_state(lb)
                    else:
                        LOBBIES.pop(lb.code, None)   # empty car returns to the yard
            elif lb.abandoned or lb.room.winner is not None:
                # journey over (verdict or END THE LINE): leaving is departure, not a
                # drop — the record burns when the LAST agent walks away (spec §4)
                if me in lb.members:
                    lb.members.remove(me)
                if not any(mm["ws"] is not None for mm in lb.members):
                    storage.session_delete(lb.code)
                    LOBBIES.pop(lb.code, None)
            else:
                me["ws"] = None        # seat held; the papers reclaim it
                await _sync_hold(lb)   # a seated human off the car HOLDS the game (spec §4)

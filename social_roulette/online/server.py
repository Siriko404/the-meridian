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
NUM = 5

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
        self.room = None           # Room once started
        self.lock = asyncio.Lock()
        self.deadline_task = None   # pending asyncio task that fires the phase deadline

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
    used = {m["portrait"] for m in lb.members if m["seat"] is not None}
    pool = [f for f in range(12) if f not in used]
    out = {m["seat"]: m["portrait"] for m in lb.members if m["seat"] is not None}
    if lb.room is not None:
        for s in lb.room.seating:
            if s not in out:
                out[s] = pool.pop(0) if pool else s % 12
    return out


async def _broadcast_views(lb, payloads=None):
    roster = {m["seat"]: m["name"] for m in lb.members if m["seat"] is not None}
    portraits = _portraits(lb)
    for m in lb.members:
        if m["ws"] is not None and m["seat"] is not None:
            # Mutating paths pass a lock-captured snapshot; the no-mutation join rebroadcast
            # (payloads is None) computes fresh — the room is not changing under it.
            p = payloads[m["seat"]] if payloads is not None else {
                "events": lb.room.events_for(m["seat"]), **lb.room.view(m["seat"])}
            await _send(m["ws"], {"type": "view", "roster": roster, "portraits": portraits, **p})
    _schedule_deadline(lb)


async def _lobby_state(lb):
    members = [{"name": m["name"], "portrait": m["portrait"], "seat": m["seat"],
                "host": m["host"], "ready": m.get("ready", False)} for m in lb.members]
    for m in lb.members:
        if m["ws"] is not None:
            await _send(m["ws"], {"type": "lobby", "code": lb.code, "members": members})


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
                    if lb.room is not None and len(lb.members) >= NUM:
                        await _send(ws, {"type": "error", "msg": "room full / already started"})
                        continue
                    me = {"pid": prof["pid"], "name": prof["initials"], "portrait": prof["portrait"],
                          "seat": None, "ws": ws, "host": len(lb.members) == 0, "ready": False}
                    lb.members.append(me)
                await _send(ws, {"type": "joined", "seat": me["seat"], "pid": me["pid"], "host": me["host"]})
                if lb.room is None:
                    await _lobby_state(lb)
                else:
                    await _broadcast_views(lb)

            elif t == "start" and lb and me and me["host"] and lb.room is None:
                async with lb.lock:
                    for seat, m in enumerate(lb.members[:NUM]):
                        m["seat"] = seat
                    human_seats = {m["seat"] for m in lb.members if m["seat"] is not None}
                    lb.room = Room(human_seats=human_seats, seed=_seed_from(lb.code))
                    payloads = _capture_payloads(lb)
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
                await _broadcast_views(lb, payloads)

            elif t == "trade_respond" and lb and lb.room and me and me["seat"] is not None:
                async with lb.lock:
                    try:
                        lb.room.trade_respond(me["seat"], bool(msg.get("accept")))
                    except IllegalAction as e:
                        await _send(ws, {"type": "error", "msg": str(e)})
                        continue
                    payloads = _capture_payloads(lb)
                await _broadcast_views(lb, payloads)

            elif t == "trade_withdraw" and lb and lb.room and me and me["seat"] is not None:
                async with lb.lock:
                    try:
                        lb.room.trade_withdraw(me["seat"])
                    except IllegalAction as e:
                        await _send(ws, {"type": "error", "msg": str(e)})
                        continue
                    payloads = _capture_payloads(lb)
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
                await _broadcast_views(lb, payloads)

            elif t == "chat" and lb and me:
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
        if me:
            me["ws"] = None            # seat empty; token can reclaim it

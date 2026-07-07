"""Async FastAPI shell around the sync Room core.

One asyncio.Lock per room serializes all mutations of that room's Room object
(no two client messages mutate one GameState concurrently). A human that drops
leaves an empty seat; reconnect with the same token reclaims the seat.
"""
import asyncio
import os
import secrets
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from social_roulette.online.room import Room, IllegalAction

app = FastAPI()
HERE = os.path.dirname(__file__)
STATIC = os.path.join(HERE, "static")
app.mount("/static", StaticFiles(directory=STATIC), name="static")   # logo + shared UI assets
NUM = 5


class Lobby:
    def __init__(self, code):
        self.code = code
        self.members = []          # list of {"name","token","seat","ws","host"}
        self.room = None           # Room once started
        self.lock = asyncio.Lock()
        self.deadline_task = None   # pending asyncio task that fires the phase deadline

    def by_token(self, token):
        return next((m for m in self.members if m["token"] == token), None)


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


async def _broadcast_views(lb, payloads=None):
    roster = {m["seat"]: m["name"] for m in lb.members if m["seat"] is not None}
    for m in lb.members:
        if m["ws"] is not None and m["seat"] is not None:
            # Mutating paths pass a lock-captured snapshot; the no-mutation join rebroadcast
            # (payloads is None) computes fresh — the room is not changing under it.
            p = payloads[m["seat"]] if payloads is not None else {
                "events": lb.room.events_for(m["seat"]), **lb.room.view(m["seat"])}
            await _send(m["ws"], {"type": "view", "roster": roster, **p})
    _schedule_deadline(lb)


async def _lobby_state(lb):
    members = [{"name": m["name"], "seat": m["seat"], "host": m["host"]} for m in lb.members]
    for m in lb.members:
        if m["ws"] is not None:
            await _send(m["ws"], {"type": "lobby", "code": lb.code, "members": members})


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/health")
async def health():
    return {"ok": True}


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
                lb = LOBBIES.setdefault(code, Lobby(code))
                token = msg.get("token")
                me = lb.by_token(token) if token else None
                if me:                                   # reconnect: reclaim seat
                    me["ws"] = ws
                else:
                    if lb.room is not None and len(lb.members) >= NUM:
                        await _send(ws, {"type": "error", "msg": "room full / already started"})
                        continue
                    me = {"name": msg.get("name") or "Player", "token": secrets.token_hex(8),
                          "seat": None, "ws": ws, "host": len(lb.members) == 0}
                    lb.members.append(me)
                await _send(ws, {"type": "joined", "seat": me["seat"], "token": me["token"], "host": me["host"]})
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

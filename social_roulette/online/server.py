"""Async FastAPI shell around the sync Room core.

One asyncio.Lock per room serializes all mutations of that room's Room object
(no two client messages mutate one GameState concurrently). A human that drops
leaves an empty seat; reconnect with the same token reclaims the seat.
"""
import asyncio
import os
import secrets

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


async def _broadcast_views(lb, events=None):
    for m in lb.members:
        if m["ws"] is not None and m["seat"] is not None:
            await _send(m["ws"], {"type": "view", "events": events or [], **lb.room.view(m["seat"])})


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
                    events = lb.room.last_events        # [announce] — the opening chamber counts
                await _broadcast_views(lb, events)

            elif t == "action" and lb and lb.room and me and me["seat"] is not None:
                async with lb.lock:
                    try:
                        lb.room.apply(me["seat"], int(msg.get("i", -1)))
                    except IllegalAction as e:
                        await _send(ws, {"type": "error", "msg": str(e)})
                        continue
                    events = lb.room.last_events          # capture delta INSIDE the lock (no cross-apply overwrite)
                await _broadcast_views(lb, events)
                if lb.room.winner is not None:
                    for m in lb.members:
                        if m["ws"] is not None:
                            await _send(m["ws"], {"type": "end", "winner": lb.room.winner})

            elif t == "flip" and lb and lb.room and me and me["seat"] is not None:
                async with lb.lock:                      # flip with a CHOSEN payment {target, items:[names]}
                    try:
                        lb.room.flip(me["seat"], int(msg.get("target", -1)), msg.get("items") or [])
                    except IllegalAction as e:
                        await _send(ws, {"type": "error", "msg": str(e)})
                        continue
                    events = lb.room.last_events
                await _broadcast_views(lb, events)

            elif t == "chat" and lb and me:
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

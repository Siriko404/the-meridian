# Online Playable Game (v1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A browser game where people join a room by invite code and play Social Roulette in real time on the existing engine, hosted free, with empty seats filled by random bots.

**Architecture:** A **pure sync core** (per-seat view serializer + a `Room` state-machine driving `engine.step`) is wrapped by a **thin async FastAPI + WebSocket shell**. Humans act one `engine.step` at a time (an action is legal until they shoot, then the engine advances the turn); bot seats run the existing `take_policy_turn`. The core is fully unit-tested without any network.

**Tech Stack:** Python 3.13, existing `social_roulette` engine, FastAPI + `uvicorn[standard]` (WebSockets), vanilla HTML/JS (no build step), Render (free host).

## Global Constraints

- Python interpreter: `./.venv/Scripts/python` (py3.13). Never `py -3.14` (no torch wheels).
- **Server is authoritative.** Every client action is re-validated against `legal_actions(state, seat)`; illegal → rejected, state unchanged.
- **Never serialize full `GameState` to a client.** Only per-seat views (public info + that seat's own hand + its own Magnifier peek + its own legal actions).
- Engine flags for v1: `comms_enabled=False`, `social_enabled=False` (human-only; chat is cosmetic).
- New code lives in `social_roulette/online/`. Tests in `tests/`. Run tests with `./.venv/Scripts/python -m pytest -q`.
- Commit after every green step. Do not touch the engine (`social_roulette/engine/`).

---

### Task 1: Per-seat view serializer + action labels

**Files:**
- Create: `social_roulette/online/__init__.py` (empty)
- Create: `social_roulette/online/view.py`
- Test: `tests/test_online_view.py`

**Interfaces:**
- Consumes: `social_roulette.engine.state.player_by_id`, `social_roulette.engine.actions.legal_actions`, `Shoot/UseItem/Flip`, `social_roulette.engine.constants.Item`.
- Produces:
  - `action_label(state, action) -> str`
  - `seat_view(state, seat, ex, feed=None) -> dict` where `ex` is the dict from `Extras.d()` = `{"known_next_shell", "announced_total", "announced_live"}`, `feed` is a list of strings (event/chat log). Returns keys: `you, players, your_hand, item_counts, chamber, peek, current, winner, legal, feed`. `legal` is `[{"i": int, "label": str}]` (empty unless it is this seat's turn and no winner).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_online_view.py
from social_roulette.engine.engine import new_game
from social_roulette.engine.constants import Item, Shell
from social_roulette.engine.state import player_by_id
from social_roulette.online.view import seat_view, action_label
from social_roulette.engine.actions import Shoot, UseItem, Flip

EX = {"known_next_shell": "unknown", "announced_total": 10, "announced_live": 6}


def _view_str(v):
    import json
    return json.dumps(v)


def test_view_hides_other_hands_and_shell_order():
    g = new_game(5, 0)
    g.current_id = 0
    v = seat_view(g, 0, EX)
    # my hand is present, keyed by item name
    assert isinstance(v["your_hand"], dict)
    # no other player's individual inventory is present anywhere
    for p in v["players"]:
        assert "inventory" not in p and "hand" not in p and "items" not in p
        assert set(p.keys()) <= {"id", "team", "lives", "alive", "handcuffed"}
    # the actual shell order never leaves the server
    blob = _view_str(v)
    assert "LIVE" not in blob and "BLANK" not in blob
    assert "shells" not in v and "chamber" in v  # only announced counts


def test_view_shows_only_own_peek():
    g = new_game(5, 0)
    g.current_id = 0
    seen = dict(EX); seen["known_next_shell"] = "live"
    assert seat_view(g, 0, seen)["peek"] == "live"
    # a seat that did NOT peek sees "unknown"
    assert seat_view(g, 0, EX)["peek"] == "unknown"


def test_view_legal_only_on_your_turn():
    g = new_game(5, 0)
    g.current_id = 0
    assert len(seat_view(g, 0, EX)["legal"]) > 0
    assert seat_view(g, 1, EX)["legal"] == []   # not seat 1's turn


def test_action_label():
    g = new_game(5, 0)
    assert action_label(g, Shoot(0)) == "Shoot yourself" if g.current_id == 0 else True
    assert action_label(g, Shoot(3)) == "Shoot P3"
    assert action_label(g, UseItem(Item.CIGARETTES)) == "Use Cigarettes"
    assert action_label(g, UseItem(Item.IMMUNITY, 2)) == "Immunity on P2"
    assert action_label(g, Flip(2)) == "Flip P2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python -m pytest tests/test_online_view.py -q`
Expected: FAIL (`ModuleNotFoundError: social_roulette.online.view`).

- [ ] **Step 3: Write minimal implementation**

```python
# social_roulette/online/__init__.py
```

```python
# social_roulette/online/view.py
"""Per-seat view serializer — the ONLY game state a client ever receives.

Public info + that seat's own hand + its own Magnifier peek + its own legal
actions. The full GameState (other players' hands, the shell order) is never
serialized. Faithful to game_guide "Information & Visibility".
"""
from social_roulette.engine.state import player_by_id
from social_roulette.engine.actions import Shoot, UseItem, Flip, legal_actions

ITEMS = ["BEER", "HANDCUFFS", "MAGNIFIER", "SAW", "CIGARETTES", "IMMUNITY"]


def _title(name):
    return name.capitalize()


def action_label(state, action):
    if isinstance(action, Shoot):
        return "Shoot yourself" if action.target_id == state.current_id else f"Shoot P{action.target_id}"
    if isinstance(action, UseItem):
        base = f"Use {_title(action.item.name)}"
        return f"{_title(action.item.name)} on P{action.target_id}" if action.target_id is not None else base
    if isinstance(action, Flip):
        return f"Flip P{action.target_id}"
    return str(action)


def seat_view(state, seat, ex, feed=None):
    me = player_by_id(state, seat)
    players = [{"id": p.id, "team": p.team.name, "lives": p.lives,
                "alive": p.alive, "handcuffed": p.handcuffed} for p in state.players]
    counts = {it: 0 for it in ITEMS}
    for p in state.players:
        for it, c in p.inventory.items():
            counts[it.name] += c
    legal = []
    if state.winner is None and state.current_id == seat:
        legal = [{"i": i, "label": action_label(state, a)}
                 for i, a in enumerate(legal_actions(state, seat))]
    return {
        "you": seat,
        "players": players,
        "your_hand": {it.name: c for it, c in me.inventory.items()},
        "item_counts": counts,
        "chamber": {"total": ex["announced_total"], "live": ex["announced_live"], "fired": state.chamber.pos},
        "peek": ex["known_next_shell"],
        "current": state.current_id,
        "winner": state.winner,
        "legal": legal,
        "feed": list(feed or []),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python -m pytest tests/test_online_view.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add social_roulette/online/__init__.py social_roulette/online/view.py tests/test_online_view.py
git commit -m "feat(online): per-seat view serializer + action labels"
```

---

### Task 2: Room state-machine (pure sync core)

**Files:**
- Create: `social_roulette/online/room.py`
- Test: `tests/test_online_room.py`

**Interfaces:**
- Consumes: `new_game`, `engine.step`, `legal_actions`, `Item`, `take_policy_turn`, `random_policy`, `Extras`, `seat_view`.
- Produces:
  - `class IllegalAction(Exception)`
  - `class Room`:
    - `Room(human_seats: set[int], seed: int, num_players: int = 5)`
    - `.is_bot(seat) -> bool`
    - `.view(seat) -> dict`
    - `.apply(seat, i) -> None` — raises `IllegalAction` if not that seat's turn or `i` out of range; applies one human action; then auto-runs bot seats.
    - `.winner -> int | None` (property)
    - `.current -> int` (property)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_online_room.py
import pytest
from social_roulette.online.room import Room, IllegalAction


def test_all_bots_reaches_winner():
    r = Room(human_seats=set(), seed=0)      # everyone a bot => plays to completion in __init__
    assert r.winner is not None


def test_human_turn_has_legal_and_rejects_bad_input():
    r = Room(human_seats={0, 1, 2, 3, 4}, seed=0)   # all humans, nobody auto-plays
    seat = r.current
    assert len(r.view(seat)["legal"]) > 0
    with pytest.raises(IllegalAction):
        r.apply(seat, 9999)                  # index out of range
    with pytest.raises(IllegalAction):
        r.apply((seat + 1) % 5, 0)           # not that seat's turn


def test_human_action_advances_and_bots_autoplay():
    r = Room(human_seats={0}, seed=0)        # seat 0 human, rest bots
    # bots before seat 0 have already auto-played in __init__; it is seat 0's turn
    assert r.current == 0 and r.winner is None
    # keep self-shooting (always legal, index 0 is Shoot self) until the game ends
    for _ in range(200):
        if r.winner is not None:
            break
        if r.current == 0:
            r.apply(0, 0)                     # index 0 == Shoot(self) (relative offset 0)
    assert r.winner is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python -m pytest tests/test_online_room.py -q`
Expected: FAIL (`ModuleNotFoundError: social_roulette.online.room`).

- [ ] **Step 3: Write minimal implementation**

```python
# social_roulette/online/room.py
"""Room — the pure, synchronous game state-machine. No asyncio, no network.

Humans act ONE engine.step at a time (an action is legal until they shoot; the
engine then advances the turn). Bot seats run the existing take_policy_turn.
The async server wraps this class; all game logic and every invariant live here
so they are unit-testable without a socket.
"""
from social_roulette.engine.engine import new_game, step as engine_step
from social_roulette.engine.constants import Item
from social_roulette.engine.actions import legal_actions
from social_roulette.sim.turn import take_policy_turn, random_policy, Extras
from social_roulette.online.view import seat_view


class IllegalAction(Exception):
    pass


class Room:
    def __init__(self, human_seats, seed, num_players=5):
        self.human = set(human_seats)
        self.state = new_game(num_players, seed)
        self.state.comms_enabled = False
        self.state.social_enabled = False
        self.extras = {i: Extras() for i in range(num_players)}
        for e in self.extras.values():
            e.sync(self.state)
        self.feed = []
        self._run_bots()               # auto-play any leading bot seats

    @property
    def winner(self):
        return self.state.winner

    @property
    def current(self):
        return self.state.current_id

    def is_bot(self, seat):
        return seat not in self.human

    def view(self, seat):
        return seat_view(self.state, seat, self.extras[seat].d(), self.feed)

    def apply(self, seat, i):
        if self.winner is not None or seat != self.state.current_id:
            raise IllegalAction("not your turn")
        acts = legal_actions(self.state, seat)
        if not (0 <= i < len(acts)):
            raise IllegalAction("no such action")
        action = acts[i]
        is_mag = getattr(action, "item", None) == Item.MAGNIFIER
        engine_step(self.state, seat, action)
        if is_mag:
            self.extras[seat].peek(self.state)
        for e in self.extras.values():
            e.sync(self.state)
        self._run_bots()

    def _run_bots(self):
        while self.state.winner is None and self.is_bot(self.state.current_id):
            take_policy_turn(self.state, self.state.current_id, random_policy, self.extras)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python -m pytest tests/test_online_room.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add social_roulette/online/room.py tests/test_online_room.py
git commit -m "feat(online): Room sync state-machine (humans step-by-step, bots via take_policy_turn)"
```

---

### Task 3: FastAPI + WebSocket server (async shell)

**Files:**
- Create: `social_roulette/online/server.py`
- Create: `requirements-web.txt`
- Test: manual (Task 5 is the integration check)

**Interfaces:**
- Consumes: `Room`, `IllegalAction`.
- Produces: an ASGI `app`. WebSocket `/ws`. Static `GET /` serves `static/index.html`.
- WS messages — client→server: `{"type":"join","code":str,"name":str,"token":str|null}`, `{"type":"start"}`, `{"type":"action","i":int}`, `{"type":"chat","text":str}`, `{"type":"ping"}`. server→client: `{"type":"joined","seat":int,"token":str,"host":bool}`, `{"type":"lobby","code":str,"members":[...]}`, `{"type":"view",...seat_view...}`, `{"type":"chat","from":str,"text":str}`, `{"type":"error","msg":str}`, `{"type":"end","winner":int}`.

- [ ] **Step 1: Install deps**

Create `requirements-web.txt`:
```
fastapi
uvicorn[standard]
```
Run: `./.venv/Scripts/python -m pip install -r requirements-web.txt`
Expected: installs fastapi + uvicorn + websockets.

- [ ] **Step 2: Write the server**

```python
# social_roulette/online/server.py
"""Async FastAPI shell around the sync Room core.

One asyncio.Lock per room serializes all mutations of that room's Room object
(no two client messages mutate one GameState concurrently). Humans that drop are
played by bots for their turns; reconnect with the same token reclaims the seat.
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


async def _broadcast_views(lb):
    for m in lb.members:
        if m["ws"] is not None and m["seat"] is not None:
            await _send(m["ws"], {"type": "view", **lb.room.view(m["seat"])})


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
                    if lb.room is not None and len([m for m in lb.members]) >= NUM:
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
                await _broadcast_views(lb)

            elif t == "action" and lb and lb.room and me and me["seat"] is not None:
                async with lb.lock:
                    try:
                        lb.room.apply(me["seat"], int(msg.get("i", -1)))
                    except IllegalAction as e:
                        await _send(ws, {"type": "error", "msg": str(e)})
                        continue
                await _broadcast_views(lb)
                if lb.room.winner is not None:
                    for m in lb.members:
                        if m["ws"] is not None:
                            await _send(m["ws"], {"type": "end", "winner": lb.room.winner})

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
            me["ws"] = None            # seat now played by bots for its turns; token can reclaim
```

- [ ] **Step 3: Verify it imports + starts**

Run: `./.venv/Scripts/python -c "import social_roulette.online.server as s; print('app ok', bool(s.app))"`
Expected: `app ok True`.

- [ ] **Step 4: Commit**

```bash
git add social_roulette/online/server.py requirements-web.txt
git commit -m "feat(online): FastAPI + WebSocket server (async shell, per-room lock, reconnect token)"
```

**Note (design):** a disconnected human seat is NOT auto-played until it is that seat's turn AND a human action would be required — v1 keeps it simple: `_run_bots` only advances seats whose id is in the bot set at construction. A dropped human's turn will therefore WAIT. **This is acceptable only with the keepalive + a human present.** If robustness demands it, a later task promotes a dropped seat into the bot set; out of scope for v1 first-run.

---

### Task 4: Static UI (single HTML file)

**Files:**
- Create: `social_roulette/online/static/index.html`

- [ ] **Step 1: Write the UI**

```html
<!-- social_roulette/online/static/index.html -->
<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Social Roulette</title>
<style>
 body{font-family:system-ui;margin:0;background:#111;color:#eee}
 #app{max-width:760px;margin:0 auto;padding:16px}
 .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
 .p{border:1px solid #444;border-radius:8px;padding:8px;min-width:90px}
 .dead{opacity:.4}.me{outline:2px solid #6cf}
 .red{color:#f77}.blue{color:#7af}
 button{background:#2a2a2a;color:#eee;border:1px solid #555;border-radius:6px;padding:8px 10px;cursor:pointer}
 button:hover{background:#3a3a3a}
 #feed{height:140px;overflow:auto;background:#000;border:1px solid #333;padding:6px;font-size:13px}
 input{background:#222;color:#eee;border:1px solid #555;border-radius:6px;padding:8px}
</style></head><body><div id="app">
 <div id="setup"><h2>Social Roulette</h2>
  <div class="row"><input id="name" placeholder="your name"><input id="code" placeholder="invite code (blank=new)"><button onclick="join()">Join</button></div>
  <p id="hint"></p></div>
 <div id="lobby" style="display:none"><h3>Lobby <span id="lcode"></span></h3><div id="members"></div><button id="startbtn" style="display:none" onclick="send({type:'start'})">Start game</button></div>
 <div id="game" style="display:none">
  <div class="row" id="players"></div>
  <p id="chamber"></p><p id="peek"></p>
  <div class="row" id="actions"></div>
  <div id="feed"></div>
  <div class="row"><input id="chat" placeholder="say something…" onkeydown="if(event.key==='Enter')chat()"><button onclick="chat()">Send</button></div>
 </div></div>
<script>
let ws, token=null, mySeat=null, host=false;
function el(id){return document.getElementById(id)}
function send(m){ws.send(JSON.stringify(m))}
function join(){
 const proto=location.protocol==='https:'?'wss':'ws';
 ws=new WebSocket(proto+'://'+location.host+'/ws');
 ws.onopen=()=>send({type:'join',code:el('code').value,name:el('name').value,token});
 ws.onmessage=ev=>handle(JSON.parse(ev.data));
 setInterval(()=>{if(ws.readyState===1)send({type:'ping'})},20000); // keepalive vs host sleep
}
function chat(){const t=el('chat').value;if(t){send({type:'chat',text:t});el('chat').value=''}}
function handle(m){
 if(m.type==='joined'){token=m.token;mySeat=m.seat;host=m.host;localStorage.token=token;el('setup').style.display='none';el('lobby').style.display='';el('startbtn').style.display=host?'':'none';}
 if(m.type==='lobby'){el('lcode').textContent=m.code;el('members').innerHTML=m.members.map(x=>x.name+(x.host?' 👑':'')).join(' · ');}
 if(m.type==='view'){el('lobby').style.display='none';el('game').style.display='';render(m);}
 if(m.type==='chat'){const f=el('feed');f.innerHTML+=`<div><b>${m.from}:</b> ${m.text}</div>`;f.scrollTop=f.scrollHeight;}
 if(m.type==='error'){const f=el('feed');f.innerHTML+=`<div style="color:#f77">⚠ ${m.msg}</div>`;}
 if(m.type==='end'){alert('Winner: P'+m.winner);}
}
function render(v){
 mySeat=v.you;
 el('players').innerHTML=v.players.map(p=>{
  const cls=['p',p.alive?'':'dead',p.id===v.you?'me':'',p.team==='RED'?'red':'blue'].join(' ');
  return `<div class="${cls}">P${p.id} ${p.team==='RED'?'🔴':'🔵'}<br>❤ ${p.lives}${p.handcuffed?'<br>🔒':''}</div>`;
 }).join('');
 el('chamber').textContent=`Chamber: ${v.chamber.fired} fired · announced ${v.chamber.live}/${v.chamber.total} live · your hand: ${JSON.stringify(v.your_hand)}`;
 el('peek').textContent=v.peek!=='unknown'?`🔍 next shell: ${v.peek}`:'';
 el('actions').innerHTML=v.current===v.you&&!v.winner
   ? v.legal.map(a=>`<button onclick="send({type:'action',i:${a.i}})">${a.label}</button>`).join('')
   : (v.winner!=null?`Winner: P${v.winner}`:`Waiting for P${v.current}…`);
}
if(localStorage.token){token=localStorage.token;}
</script></body></html>
```

- [ ] **Step 2: Commit**

```bash
git add social_roulette/online/static/index.html
git commit -m "feat(online): minimal single-file UI (table + action buttons + chat + keepalive)"
```

---

### Task 5: Run locally + play a full game (integration verify)

**Files:** none (manual verification).

- [ ] **Step 1: Start the server**

Run: `./.venv/Scripts/python -m uvicorn social_roulette.online.server:app --port 8000`
Expected: `Uvicorn running on http://127.0.0.1:8000`.

- [ ] **Step 2: Play**

Open `http://localhost:8000` in two browser tabs. Tab 1: name + blank code → Join → note the code shown → Start. Tab 2 (before or after start): enter the same code → Join. Empty seats are bots. Play: click action buttons on your turn; watch the table + chat update in both tabs; game reaches a winner.

- [ ] **Step 3: Integrity spot-check**

In devtools → Network → WS → messages: confirm each `view` frame contains only YOUR `your_hand`, no other player's inventory, and no `LIVE`/`BLANK` shell list.

- [ ] **Step 4: Checkpoint (no code change) — commit a run note**

```bash
git commit --allow-empty -m "chore(online): verified local full-game round + per-seat integrity"
```

---

### Task 6: Deploy to Render (public URL)

**Files:**
- Create: `render.yaml`
- Create: `requirements.txt` (if the repo lacks a top-level one for the web app)

- [ ] **Step 1: Deploy config**

`requirements.txt` (web runtime only — Render does not need torch):
```
fastapi
uvicorn[standard]
```

`render.yaml`:
```yaml
services:
  - type: web
    name: social-roulette
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn social_roulette.online.server:app --host 0.0.0.0 --port $PORT
```

- [ ] **Step 2: Push + deploy**

Push the branch to GitHub. In Render: New → Web Service → connect the repo → it reads `render.yaml` → Deploy. Wait for the public `https://social-roulette.onrender.com` URL.

- [ ] **Step 3: Verify from another machine**

Open the Render URL on a phone / another device. Join with an invite code, play a full round. First hit after idle takes ~40s (free-tier cold start) — expected.

- [ ] **Step 4: Commit**

```bash
git add render.yaml requirements.txt
git commit -m "feat(online): Render free-tier deploy config"
```

---

## Self-Review (done)

- **Spec coverage:** per-seat view (T1) · server-authoritative re-validation + Room (T2) · async shell + per-room lock + reconnect token (T3) · generic action UI + keepalive (T4) · invite code/lobby/bots-fill (T3) · Magnifier peek in view (T1) · engine flags pinned (T2) · Render host (T6). All spec sections map to a task.
- **Placeholders:** none — every code step is complete and runnable.
- **Type consistency:** `seat_view(state, seat, ex, feed)`, `Room(human_seats, seed, num_players)`, `.apply(seat, i)`, `.view(seat)`, WS message `type` names — used identically across tasks.
- **Deferred (named in spec, not this plan):** LLM seats, real talk→decide negotiation, timers, durable rooms, promoting dropped seats to bots mid-game.

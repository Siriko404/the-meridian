# Social Roulette Engine (Stage 0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **The code AND tests in this plan are the spec.** A subagent makes the provided tests pass using the provided code. If code here is wrong, the bug ships — so the tests below are written to pin the dangerous paths (self-kill, Beer-empties-turn, last-shell bonus, killer extra turn, handcuff skip, illegal shots).

**Goal:** Build a deterministic, seedable, ground-truth rule engine for *Social Roulette* (per `game_guide.md`) with a full test suite and a **full-action** random-agent simulation (items + economy + shooting) proving every game terminates with exactly one winner.

**Architecture:** Pure-Python, dependency-light, turn-based state machine. One `GameState` holds full ground truth. Pure functions mutate it. The turn pointer is `current_id` (a player id), not an index — robust to mid-game removals. Determinism comes from one seeded `Random` threaded through `state.rng`.

**Tech Stack:** Python 3.11+, `pytest`, standard library only (`random`, `dataclasses`, `enum`, `hashlib`, `math`).

## Global Constraints

- **No clock.** `game_guide.md` timers (talk/decision/timeout-fines/AFK) are human-play artifacts. Engine rule: each turn is a sequence of optional sub-actions ending in a **mandatory shot**. A per-turn sub-action safety cap forces a shot (stands in for the Stage-1 sub-action budget).
- **Ground truth only.** Engine stores all hidden state (shell order, who holds what). Observation/hiding is **Stage 1** — do NOT build view-filtering here.
- **Engine-level legality.** `take_shot` itself rejects illegal shots (teammate while teams active, or shooting through an immunity placed on the shooter). Agents must not be the only guard — Stage 1 policies emit illegal moves constantly.
- **Determinism is law.** Same seed + same actions ⇒ identical game. ALL randomness via `state.rng`. No module-level `random.*`.
- **Lives:** start 3, max 5, dead at 0. **Inventory caps:** ≤3/type, ≤8 total; over-cap items never received.
- **Consumption cap:** `floor(living * 1.3)` uses per item type per epoch; resets on any death; counted on commit (even if it whiffs); sacrificing-as-currency is exempt.
- **Point values:** Immunity 6, Cigarettes 6, Magnifier 5, Saw 5, Beer 4, Handcuffs 4. **No change on overpay.**
- **Item table (1–6):** 1 Beer, 2 Handcuffs, 3 Magnifier, 4 Saw, 5 Cigarettes, 6 Immunity.
- **Chamber load:** accumulate two dice (higher→total, lower→live) until `live > living`; redo if live fraction outside **30–70%**; shuffle hidden.
- **Min players 5. Teams** RED/BLUE balanced; **coin-flip which color gets the odd seat.** Teams OFF when `< 3` players remain.

## File Structure

```
social_roulette/
  __init__.py
  engine/
    __init__.py
    constants.py   rng.py   state.py
    chamber.py     shooting.py   items.py   economy.py   reload.py
    endgame.py     actions.py    engine.py
  sim/
    __init__.py    random_agent.py   run_sim.py
tests/
  conftest.py  test_rng.py  test_chamber.py  test_shooting.py  test_items.py
  test_economy.py  test_reload.py  test_legal.py  test_turn_driver.py
  test_endgame.py  test_determinism.py  test_sim.py
```

**Deferred to Stage 1 (must not be precluded):** observation/view filtering; Beer-reveal & placed-token visibility; richer sub-action budget/timeout; bilateral Trade in the agent; PettingZoo AEC wrapper; emoji channel; network masking.

---

## Task 0: Scaffold

**Files:** Create `pyproject.toml`, package `__init__.py`s, `tests/conftest.py`, `.gitignore`.

- [ ] **Step 1: `pyproject.toml`**

```toml
[project]
name = "social-roulette"
version = "0.0.0"
requires-python = ">=3.11"
dependencies = []
[project.optional-dependencies]
dev = ["pytest>=8"]
[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2:** Create empty `social_roulette/__init__.py`, `social_roulette/engine/__init__.py`, `social_roulette/sim/__init__.py`, `tests/conftest.py`.
- [ ] **Step 3: `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
.venv/
```

- [ ] **Step 4:** Run `git init && pip install -e ".[dev]" && pytest -q` → collects 0, exits 0.
- [ ] **Step 5:** Commit: `git add -A && git commit -m "chore: scaffold social_roulette package + pytest"`

---

## Task 1: Constants

**Files:** Create `social_roulette/engine/constants.py`; Test `tests/test_rng.py`.

**Interfaces — Produces:** `Item`(BEER,HANDCUFFS,MAGNIFIER,SAW,CIGARETTES,IMMUNITY), `Team`(RED,BLUE), `Shell`(LIVE,BLANK); `POINT_VALUE`, `ITEM_TABLE`, `MAX_PER_TYPE=3`, `MAX_TOTAL=8`, `START_LIVES=3`, `MAX_LIVES=5`, `CONSUMPTION_MULT=1.3`, `MIN_PLAYERS=5`, `LIVE_FRACTION_MIN=0.30`, `LIVE_FRACTION_MAX=0.70`.

- [ ] **Step 1: Failing test**

```python
# tests/test_rng.py
from social_roulette.engine import constants as C

def test_constants_match_spec():
    assert {i.name for i in C.Item} == {"BEER","HANDCUFFS","MAGNIFIER","SAW","CIGARETTES","IMMUNITY"}
    assert C.ITEM_TABLE == {1:C.Item.BEER,2:C.Item.HANDCUFFS,3:C.Item.MAGNIFIER,
                            4:C.Item.SAW,5:C.Item.CIGARETTES,6:C.Item.IMMUNITY}
    assert C.POINT_VALUE[C.Item.IMMUNITY]==6 and C.POINT_VALUE[C.Item.CIGARETTES]==6
    assert C.POINT_VALUE[C.Item.MAGNIFIER]==5 and C.POINT_VALUE[C.Item.SAW]==5
    assert C.POINT_VALUE[C.Item.BEER]==4 and C.POINT_VALUE[C.Item.HANDCUFFS]==4
    assert (C.MAX_PER_TYPE,C.MAX_TOTAL,C.START_LIVES,C.MAX_LIVES,C.MIN_PLAYERS)==(3,8,3,5,5)
```

- [ ] **Step 2:** `pytest tests/test_rng.py::test_constants_match_spec -v` → FAIL.
- [ ] **Step 3: Implement**

```python
# social_roulette/engine/constants.py
from enum import Enum, auto

class Item(Enum):
    BEER=auto(); HANDCUFFS=auto(); MAGNIFIER=auto(); SAW=auto(); CIGARETTES=auto(); IMMUNITY=auto()
class Team(Enum):
    RED=auto(); BLUE=auto()
class Shell(Enum):
    LIVE=auto(); BLANK=auto()

POINT_VALUE={Item.IMMUNITY:6,Item.CIGARETTES:6,Item.MAGNIFIER:5,Item.SAW:5,Item.BEER:4,Item.HANDCUFFS:4}
ITEM_TABLE={1:Item.BEER,2:Item.HANDCUFFS,3:Item.MAGNIFIER,4:Item.SAW,5:Item.CIGARETTES,6:Item.IMMUNITY}
MAX_PER_TYPE=3; MAX_TOTAL=8; START_LIVES=3; MAX_LIVES=5
CONSUMPTION_MULT=1.3; MIN_PLAYERS=5; LIVE_FRACTION_MIN=0.30; LIVE_FRACTION_MAX=0.70
```

- [ ] **Step 4:** `pytest tests/test_rng.py::test_constants_match_spec -v` → PASS.
- [ ] **Step 5:** Commit: `git add social_roulette/engine/constants.py tests/test_rng.py && git commit -m "feat: engine constants"`

---

## Task 2: Seeded RNG

**Files:** Create `social_roulette/engine/rng.py`; Test `tests/test_rng.py`.

**Interfaces — Produces:** `SeededRng(seed)` with `.roll_two_dice()->(int,int)` (1–6 each), `.shuffle(list)`, `.choice(seq)`, `.randint(a,b)`. Same seed ⇒ identical stream.

- [ ] **Step 1: Failing tests (append)**

```python
# tests/test_rng.py (append)
from social_roulette.engine.rng import SeededRng

def test_rng_deterministic():
    a,b=SeededRng(42),SeededRng(42)
    assert [a.roll_two_dice() for _ in range(20)]==[b.roll_two_dice() for _ in range(20)]

def test_rng_dice_range():
    r=SeededRng(1)
    for _ in range(100):
        d1,d2=r.roll_two_dice(); assert 1<=d1<=6 and 1<=d2<=6

def test_rng_shuffle_deterministic():
    a,b=SeededRng(7),SeededRng(7); x,y=list(range(10)),list(range(10))
    a.shuffle(x); b.shuffle(y); assert x==y
```

- [ ] **Step 2:** `pytest tests/test_rng.py -v` → FAIL (ImportError).
- [ ] **Step 3: Implement**

```python
# social_roulette/engine/rng.py
import random
class SeededRng:
    def __init__(self, seed): self._r=random.Random(seed)
    def roll_two_dice(self): return (self._r.randint(1,6), self._r.randint(1,6))
    def shuffle(self, seq): self._r.shuffle(seq)
    def choice(self, seq): return self._r.choice(seq)
    def randint(self, a, b): return self._r.randint(a,b)
```

- [ ] **Step 4:** `pytest tests/test_rng.py -v` → PASS.
- [ ] **Step 5:** Commit: `git add social_roulette/engine/rng.py tests/test_rng.py && git commit -m "feat: seeded RNG"`

---

## Task 3: State model

**Files:** Create `social_roulette/engine/state.py`; Test `tests/test_endgame.py`.

**Interfaces — Produces:**
- `Player`: `id, team, lives, alive, inventory:dict[Item,int], immunity_against:set[int], handcuffed:bool, flipback_discount:bool`.
- `Chamber`: `shells:list[Shell], pos:int`; `.remaining()`, `.current()`, `.is_empty()`.
- `GameState`: `players, order:list[int], current_id:int, chamber, rng, use_counts:dict, saw_active:bool, saw_used_this_turn:bool, bonus_pending:bool, winner:int|None`.
- Helpers: `player_by_id`, `living_players`, `living_ids(state)->set[int]`, `inventory_total`, `can_receive`.

- [ ] **Step 1: Failing test**

```python
# tests/test_endgame.py
from social_roulette.engine.constants import Item, Team, Shell
from social_roulette.engine.state import Player, Chamber, can_receive, inventory_total

def mkp(i=0, **kw):
    d=dict(id=i,team=Team.RED,lives=3,alive=True,inventory={},immunity_against=set(),
           handcuffed=False,flipback_discount=False); d.update(kw); return Player(**d)

def test_can_receive_caps():
    p=mkp(inventory={Item.BEER:3})
    assert can_receive(p,Item.BEER) is False and can_receive(p,Item.SAW) is True
    p.inventory={Item.BEER:3,Item.SAW:3,Item.MAGNIFIER:2}
    assert inventory_total(p)==8 and can_receive(p,Item.HANDCUFFS) is False

def test_chamber_basics():
    c=Chamber(shells=[Shell.LIVE,Shell.BLANK],pos=0)
    assert c.current()==Shell.LIVE and not c.is_empty()
    c.pos=2; assert c.is_empty() and c.current() is None
```

- [ ] **Step 2:** `pytest tests/test_endgame.py -v` → FAIL.
- [ ] **Step 3: Implement**

```python
# social_roulette/engine/state.py
from dataclasses import dataclass, field
from .constants import MAX_PER_TYPE, MAX_TOTAL

@dataclass
class Player:
    id:int; team:object; lives:int; alive:bool; inventory:dict
    immunity_against:set; handcuffed:bool; flipback_discount:bool

@dataclass
class Chamber:
    shells:list; pos:int=0
    def remaining(self): return self.shells[self.pos:]
    def current(self): return self.shells[self.pos] if self.pos<len(self.shells) else None
    def is_empty(self): return self.pos>=len(self.shells)

@dataclass
class GameState:
    players:list; order:list; current_id:int; chamber:object; rng:object
    use_counts:dict=field(default_factory=dict)
    saw_active:bool=False; saw_used_this_turn:bool=False
    bonus_pending:bool=False; winner:int=None

def player_by_id(state,pid): return next(p for p in state.players if p.id==pid)
def living_players(state): return [p for p in state.players if p.alive]
def living_ids(state): return {p.id for p in state.players if p.alive}
def inventory_total(p): return sum(p.inventory.values())
def can_receive(p,item):
    return p.inventory.get(item,0)<MAX_PER_TYPE and inventory_total(p)<MAX_TOTAL
```

- [ ] **Step 4:** `pytest tests/test_endgame.py -v` → PASS.
- [ ] **Step 5:** Commit: `git add social_roulette/engine/state.py tests/test_endgame.py && git commit -m "feat: state model (current_id turn pointer, caps)"`

---

## Task 4: Chamber loading

**Files:** Create `social_roulette/engine/chamber.py`; Test `tests/test_chamber.py`.

**Interfaces — Produces:** `load_chamber(rng, living_count, max_redos=1000) -> Chamber`. Guarantees `live > living_count` and `0.30 <= live/total <= 0.70`; shuffled; `pos=0`. Raises `RuntimeError` if unsatisfiable within `max_redos`.

- [ ] **Step 1: Failing test**

```python
# tests/test_chamber.py
from social_roulette.engine.rng import SeededRng
from social_roulette.engine.constants import Shell, LIVE_FRACTION_MIN, LIVE_FRACTION_MAX
from social_roulette.engine.chamber import load_chamber

def test_load_invariants_across_seeds():
    for seed in range(200):
        for living in (5,6,8,10):
            c=load_chamber(SeededRng(seed),living)
            total=len(c.shells); live=sum(1 for s in c.shells if s==Shell.LIVE)
            assert live>living and LIVE_FRACTION_MIN<=live/total<=LIVE_FRACTION_MAX and c.pos==0

def test_load_deterministic():
    assert load_chamber(SeededRng(123),8).shells==load_chamber(SeededRng(123),8).shells
```

- [ ] **Step 2:** `pytest tests/test_chamber.py -v` → FAIL.
- [ ] **Step 3: Implement**

```python
# social_roulette/engine/chamber.py
from .constants import Shell, LIVE_FRACTION_MIN, LIVE_FRACTION_MAX
from .state import Chamber

def load_chamber(rng, living_count, max_redos=1000):
    for _ in range(max_redos):
        total=0; live=0
        while live<=living_count:
            d1,d2=rng.roll_two_dice(); total+=max(d1,d2); live+=min(d1,d2)
        if LIVE_FRACTION_MIN<=live/total<=LIVE_FRACTION_MAX:
            shells=[Shell.LIVE]*live+[Shell.BLANK]*(total-live); rng.shuffle(shells)
            return Chamber(shells=shells,pos=0)
    raise RuntimeError("load_chamber: could not satisfy invariants")
```

- [ ] **Step 4:** `pytest tests/test_chamber.py -v` → PASS.
- [ ] **Step 5:** Commit: `git add social_roulette/engine/chamber.py tests/test_chamber.py && git commit -m "feat: chamber loading (dice accumulation, 30-70% band)"`

---

## Task 5: Shot resolution (pure)

**Files:** Create `social_roulette/engine/shooting.py`; Test `tests/test_shooting.py`.

**Interfaces — Produces:** `resolve_shot(state, shooter_id, target_id) -> {"shell","damage","killed"}`. Pure mechanical effect only (NO legality/turn logic — that's Task 10). Rules: LIVE damage = 2 if `saw_active` else 1; BLANK = 0 (saw wasted). After: `pos+=1`; `saw_active=False`; `shooter.immunity_against=set()` (expires on firing); `bonus_pending = (shooter==target and shell==BLANK)`. Lives floored at 0; `killed` when target hits 0.

- [ ] **Step 1: Failing tests**

```python
# tests/test_shooting.py
from social_roulette.engine.constants import Team, Shell
from social_roulette.engine.state import Player, Chamber, GameState
from social_roulette.engine.rng import SeededRng
from social_roulette.engine.shooting import resolve_shot

def mkstate(shells, **kw):
    players=[Player(i,Team.RED,3,True,{},set(),False,False) for i in range(2)]
    s=GameState(players=players,order=[0,1],current_id=0,chamber=Chamber(shells,0),rng=SeededRng(0))
    for k,v in kw.items(): setattr(s,k,v)
    return s

def test_live_costs_one(): 
    s=mkstate([Shell.LIVE]); ev=resolve_shot(s,0,1)
    assert ev["damage"]==1 and s.players[1].lives==2 and s.chamber.pos==1
def test_saw_doubles_and_clears():
    s=mkstate([Shell.LIVE],saw_active=True); ev=resolve_shot(s,0,1)
    assert ev["damage"]==2 and s.players[1].lives==1 and s.saw_active is False
def test_saw_wasted_on_blank():
    s=mkstate([Shell.BLANK],saw_active=True); ev=resolve_shot(s,0,1)
    assert ev["damage"]==0 and s.players[1].lives==3 and s.saw_active is False
def test_self_blank_sets_bonus():
    s=mkstate([Shell.BLANK]); resolve_shot(s,0,0); assert s.bonus_pending is True
def test_self_live_no_bonus_immunity_expires():
    s=mkstate([Shell.LIVE]); s.players[0].immunity_against={1}; resolve_shot(s,0,0)
    assert s.bonus_pending is False and s.players[0].immunity_against==set()
def test_kill_floored():
    s=mkstate([Shell.LIVE],saw_active=True); s.players[1].lives=1; ev=resolve_shot(s,0,1)
    assert ev["killed"] is True and s.players[1].lives==0
```

- [ ] **Step 2:** `pytest tests/test_shooting.py -v` → FAIL.
- [ ] **Step 3: Implement**

```python
# social_roulette/engine/shooting.py
from .constants import Shell
from .state import player_by_id

def resolve_shot(state, shooter_id, target_id):
    shooter=player_by_id(state,shooter_id); target=player_by_id(state,target_id)
    shell=state.chamber.current(); damage=0
    if shell==Shell.LIVE:
        damage=2 if state.saw_active else 1
        target.lives=max(0,target.lives-damage)
    state.chamber.pos+=1
    state.saw_active=False
    shooter.immunity_against=set()
    state.bonus_pending=(shooter_id==target_id and shell==Shell.BLANK)
    return {"shell":shell,"damage":damage,"killed":target.lives==0}
```

- [ ] **Step 4:** `pytest tests/test_shooting.py -v` → PASS (6).
- [ ] **Step 5:** Commit: `git add social_roulette/engine/shooting.py tests/test_shooting.py && git commit -m "feat: pure shot resolution (saw, immunity expiry, self-blank bonus)"`

---

## Task 6: Items + consumption cap

**Files:** Create `social_roulette/engine/items.py`; Test `tests/test_items.py`.

**Interfaces — Produces:** `consumption_limit(state)`, `cap_reached(state,item)`, `reset_caps(state)`, `apply_item(state,player_id,item,target_id=None)->dict`. Effects per Global Constraints; Cigarettes at max life **raises** (caller must not offer); Saw **raises** if `saw_used_this_turn`; Beer deletes shell at `pos` (no pos advance), returns `{"discarded","emptied"}`; Immunity/Handcuffs require non-self target (raise otherwise); Handcuffs raises if already cuffed. Consuming decrements inventory + increments `use_counts`. Cap is enforced by the **caller** (Task 9 `legal_actions` + Task 11 `step`).

- [ ] **Step 1: Failing tests**

```python
# tests/test_items.py
import pytest
from social_roulette.engine.constants import Item, Team, Shell
from social_roulette.engine.state import Player, Chamber, GameState
from social_roulette.engine.rng import SeededRng
from social_roulette.engine import items as I

def mkstate(n=5, shells=None):
    players=[Player(i,Team.RED,3,True,{},set(),False,False) for i in range(n)]
    return GameState(players=players,order=list(range(n)),current_id=0,
                     chamber=Chamber(shells or [Shell.LIVE,Shell.BLANK],0),rng=SeededRng(0))

def test_limit_floor_1_3():
    assert I.consumption_limit(mkstate(5))==6 and I.consumption_limit(mkstate(8))==10
def test_cig_heals_and_blocks_at_max():
    s=mkstate(); s.players[0].lives=4; s.players[0].inventory={Item.CIGARETTES:1}
    I.apply_item(s,0,Item.CIGARETTES); assert s.players[0].lives==5
    s.players[0].inventory={Item.CIGARETTES:1}
    with pytest.raises(Exception): I.apply_item(s,0,Item.CIGARETTES)
def test_saw_once_per_turn():
    s=mkstate(); s.players[0].inventory={Item.SAW:2}; I.apply_item(s,0,Item.SAW)
    assert s.saw_active and s.saw_used_this_turn
    with pytest.raises(Exception): I.apply_item(s,0,Item.SAW)
def test_beer_removes_and_shrinks():
    s=mkstate(shells=[Shell.LIVE,Shell.BLANK]); s.players[0].inventory={Item.BEER:1}
    ev=I.apply_item(s,0,Item.BEER)
    assert ev["discarded"]==Shell.LIVE and s.chamber.shells==[Shell.BLANK] and s.chamber.pos==0
def test_beer_last_shell_reports_emptied():
    s=mkstate(shells=[Shell.LIVE]); s.players[0].inventory={Item.BEER:1}
    ev=I.apply_item(s,0,Item.BEER); assert ev["emptied"] is True and s.chamber.is_empty()
def test_place_immunity_handcuffs_and_no_stack():
    s=mkstate(); s.players[0].inventory={Item.IMMUNITY:1,Item.HANDCUFFS:1}
    I.apply_item(s,0,Item.IMMUNITY,target_id=1); I.apply_item(s,0,Item.HANDCUFFS,target_id=2)
    assert 0 in s.players[1].immunity_against and s.players[2].handcuffed is True
    s.players[0].inventory={Item.HANDCUFFS:1}
    with pytest.raises(Exception): I.apply_item(s,0,Item.HANDCUFFS,target_id=2)
def test_no_self_target():
    s=mkstate(); s.players[0].inventory={Item.IMMUNITY:1}
    with pytest.raises(Exception): I.apply_item(s,0,Item.IMMUNITY,target_id=0)
def test_cap_reached_and_reset():
    s=mkstate(5); s.use_counts={Item.BEER:6}
    assert I.cap_reached(s,Item.BEER) is True
    I.reset_caps(s); assert I.cap_reached(s,Item.BEER) is False
```

- [ ] **Step 2:** `pytest tests/test_items.py -v` → FAIL.
- [ ] **Step 3: Implement**

```python
# social_roulette/engine/items.py
import math
from .constants import Item, MAX_LIVES, CONSUMPTION_MULT
from .state import player_by_id, living_players

def consumption_limit(state): return math.floor(len(living_players(state))*CONSUMPTION_MULT)
def cap_reached(state,item): return state.use_counts.get(item,0)>=consumption_limit(state)
def reset_caps(state): state.use_counts={}

def _consume(state,p,item):
    p.inventory[item]-=1
    if p.inventory[item]==0: del p.inventory[item]
    state.use_counts[item]=state.use_counts.get(item,0)+1

def apply_item(state, player_id, item, target_id=None):
    p=player_by_id(state,player_id)
    if item==Item.CIGARETTES:
        if p.lives>=MAX_LIVES: raise ValueError("cigarettes unusable at max life")
        p.lives+=1; _consume(state,p,item); return {"healed":1}
    if item==Item.MAGNIFIER:
        _consume(state,p,item); return {"peek":state.chamber.current()}
    if item==Item.SAW:
        if state.saw_used_this_turn: raise ValueError("saw already used this turn")
        state.saw_active=True; state.saw_used_this_turn=True; _consume(state,p,item); return {"saw":True}
    if item==Item.BEER:
        shell=state.chamber.current()
        if shell is not None: del state.chamber.shells[state.chamber.pos]
        _consume(state,p,item); return {"discarded":shell,"emptied":state.chamber.is_empty()}
    if item==Item.IMMUNITY:
        if target_id is None or target_id==player_id: raise ValueError("immunity needs non-self target")
        player_by_id(state,target_id).immunity_against.add(player_id)
        _consume(state,p,item); return {"immunity_on":target_id}
    if item==Item.HANDCUFFS:
        if target_id is None or target_id==player_id: raise ValueError("handcuffs need non-self target")
        t=player_by_id(state,target_id)
        if t.handcuffed: raise ValueError("already handcuffed (no stacking)")
        t.handcuffed=True; _consume(state,p,item); return {"handcuffed":target_id}
    raise ValueError(f"unknown item {item}")
```

- [ ] **Step 4:** `pytest tests/test_items.py -v` → PASS (8).
- [ ] **Step 5:** Commit: `git add social_roulette/engine/items.py tests/test_items.py && git commit -m "feat: item effects + consumption caps"`

---

## Task 7: Economy

**Files:** Create `social_roulette/engine/economy.py`; Test `tests/test_economy.py`.

**Interfaces — Produces:**
- `pay_cost(state,player_id,cost,sacrifice:list[Item])` — verify ownership + `sum(values)>=cost`; remove items; overpay burned; raise on shortfall/unowned.
- `flip_team(state,payer_id,target_id,sacrifice)` — cost 4 if `payer==target and target.flipback_discount` else 5; pay; toggle team; if discounted → clear target's discount (consumed); elif payer≠target → set target's `flipback_discount=True`. (Window expiry handled in Task 10 turn driver.)

- [ ] **Step 1: Failing tests**

```python
# tests/test_economy.py
import pytest
from social_roulette.engine.constants import Item, Team
from social_roulette.engine.state import Player, Chamber, GameState
from social_roulette.engine.rng import SeededRng
from social_roulette.engine.economy import pay_cost, flip_team

def mkstate():
    players=[Player(i,Team.RED if i%2 else Team.BLUE,3,True,{},set(),False,False) for i in range(5)]
    return GameState(players=players,order=list(range(5)),current_id=0,chamber=Chamber([],0),rng=SeededRng(0))

def test_pay_burns_overpay():
    s=mkstate(); s.players[0].inventory={Item.IMMUNITY:1}
    pay_cost(s,0,5,[Item.IMMUNITY]); assert s.players[0].inventory=={}
def test_pay_rejects_insufficient():
    s=mkstate(); s.players[0].inventory={Item.BEER:1}
    with pytest.raises(Exception): pay_cost(s,0,5,[Item.BEER])
def test_flip_other_costs_5_toggles_grants_discount():
    s=mkstate(); s.players[0].inventory={Item.MAGNIFIER:1}; before=s.players[1].team
    flip_team(s,0,1,[Item.MAGNIFIER])
    assert s.players[1].team!=before and s.players[1].flipback_discount is True
def test_flipback_costs_4_consumes_discount():
    s=mkstate(); s.players[1].flipback_discount=True; s.players[1].inventory={Item.BEER:1}
    flip_team(s,1,1,[Item.BEER]); assert s.players[1].flipback_discount is False
def test_flip_own_no_discount_costs_5():
    s=mkstate(); s.players[1].inventory={Item.MAGNIFIER:1}
    flip_team(s,1,1,[Item.MAGNIFIER]); assert s.players[1].flipback_discount is False
```

- [ ] **Step 2:** `pytest tests/test_economy.py -v` → FAIL.
- [ ] **Step 3: Implement**

```python
# social_roulette/engine/economy.py
from .constants import POINT_VALUE, Team
from .state import player_by_id

def pay_cost(state, player_id, cost, sacrifice):
    p=player_by_id(state,player_id); owned=dict(p.inventory)
    for it in sacrifice:
        if owned.get(it,0)<=0: raise ValueError("cannot sacrifice unowned item")
        owned[it]-=1
    if sum(POINT_VALUE[it] for it in sacrifice)<cost: raise ValueError("insufficient payment")
    for it in sacrifice:
        p.inventory[it]-=1
        if p.inventory[it]==0: del p.inventory[it]

def flip_team(state, payer_id, target_id, sacrifice):
    target=player_by_id(state,target_id)
    discounted=(payer_id==target_id and target.flipback_discount)
    pay_cost(state,payer_id,4 if discounted else 5,sacrifice)
    target.team=Team.RED if target.team==Team.BLUE else Team.BLUE
    if discounted: target.flipback_discount=False
    elif payer_id!=target_id: target.flipback_discount=True
```

- [ ] **Step 4:** `pytest tests/test_economy.py -v` → PASS (5).
- [ ] **Step 5:** Commit: `git add social_roulette/engine/economy.py tests/test_economy.py && git commit -m "feat: economy (sacrifice-to-pay, flip + flip-back discount)"`

---

## Task 8: Reload

**Files:** Create `social_roulette/engine/reload.py`; Test `tests/test_reload.py`.

**Interfaces — Produces:** `draw_items_for_all(state,n=2)` (each living rolls n times, receives if `can_receive`), `reload_on_empty(state)` (fresh chamber sized to living + `draw_items_for_all(2)`), `reload_on_death(state)` (fresh chamber + `reset_caps`). Item draw after a death is the caller's job (only if also emptied).

- [ ] **Step 1: Failing tests**

```python
# tests/test_reload.py
from social_roulette.engine.constants import Item, Team, Shell
from social_roulette.engine.state import Player, Chamber, GameState, living_players
from social_roulette.engine.rng import SeededRng
from social_roulette.engine import reload as R

def mkstate(n=5):
    players=[Player(i,Team.RED,3,True,{},set(),False,False) for i in range(n)]
    return GameState(players=players,order=list(range(n)),current_id=0,
                     chamber=Chamber([],0),rng=SeededRng(3),use_counts={Item.BEER:4})

def test_reload_empty_refills_and_items():
    s=mkstate(5); before=sum(sum(p.inventory.values()) for p in s.players)
    R.reload_on_empty(s)
    assert sum(1 for x in s.chamber.shells if x==Shell.LIVE)>len(living_players(s)) and s.chamber.pos==0
    assert sum(sum(p.inventory.values()) for p in s.players)>=before
def test_reload_death_resets_caps():
    s=mkstate(5); R.reload_on_death(s); assert s.use_counts=={} and s.chamber.pos==0
def test_draw_respects_caps():
    s=mkstate(5)
    for p in s.players: p.inventory={Item.BEER:3,Item.SAW:3,Item.MAGNIFIER:2}
    R.draw_items_for_all(s,2); assert all(sum(p.inventory.values())==8 for p in s.players)
```

- [ ] **Step 2:** `pytest tests/test_reload.py -v` → FAIL.
- [ ] **Step 3: Implement**

```python
# social_roulette/engine/reload.py
from .constants import ITEM_TABLE
from .state import living_players, can_receive
from .chamber import load_chamber
from .items import reset_caps

def draw_items_for_all(state, n=2):
    for p in living_players(state):
        for _ in range(n):
            item=ITEM_TABLE[state.rng.randint(1,6)]
            if can_receive(p,item): p.inventory[item]=p.inventory.get(item,0)+1

def reload_on_empty(state):
    state.chamber=load_chamber(state.rng,len(living_players(state))); draw_items_for_all(state,2)

def reload_on_death(state):
    state.chamber=load_chamber(state.rng,len(living_players(state))); reset_caps(state)
```

- [ ] **Step 4:** `pytest tests/test_reload.py -v` → PASS (3).
- [ ] **Step 5:** Commit: `git add social_roulette/engine/reload.py tests/test_reload.py && git commit -m "feat: reload on empty/death"`

---

## Task 9: Endgame, legality, actions, full legal-action menu

**Files:** Create `social_roulette/engine/endgame.py`, `social_roulette/engine/actions.py`; Test `tests/test_legal.py`.

**Interfaces — Produces:**
- `endgame.py`: `teams_active(state)` (`len(living)>=3`); `legal_targets(state,shooter_id)` (self always; others excluded if in `immunity_against`, or teammate while teams active); `winner(state)`; `next_living_after(order,living:set,pid)` (next id in cyclic `order` that is in `living`); `assert_legal_shot(state,shooter_id,target_id)` (raise if target ∉ legal_targets).
- `actions.py`: dataclasses `UseItem(item,target_id=None)`, `Flip(target_id,sacrifice)`, `Trade(to_id,items)`, `Shoot(target_id)`, `EndSubactions()`; `cheapest_payment(player,cost)->list[Item]|None` (greedy min-items covering cost); `legal_actions(state,player_id)->list` enumerating: Shoot(each legal target); UseItem for each held item that is **not cap-reached** and legal now (Cigarettes only if `lives<MAX_LIVES`; Saw only if not `saw_used_this_turn`; Immunity/Handcuffs as placements on each valid non-self target where legal/no-stack); Flip(target, cheapest_payment) for each player where payment exists. (Trade excluded at Stage 0.)

- [ ] **Step 1: Failing tests**

```python
# tests/test_legal.py
import pytest
from social_roulette.engine.constants import Item, Team, Shell
from social_roulette.engine.state import Player, Chamber, GameState
from social_roulette.engine.rng import SeededRng
from social_roulette.engine.endgame import legal_targets, teams_active, winner, next_living_after, assert_legal_shot
from social_roulette.engine.actions import legal_actions, Shoot, UseItem, Flip, cheapest_payment

def mkstate(teams, **kw):
    players=[Player(i,teams[i],3,True,{},set(),False,False) for i in range(len(teams))]
    s=GameState(players=players,order=list(range(len(teams))),current_id=0,
                chamber=Chamber([Shell.LIVE],0),rng=SeededRng(0))
    for k,v in kw.items(): setattr(s,k,v)
    return s

def test_self_always_legal():
    s=mkstate([Team.RED]*5); assert 0 in legal_targets(s,0)
def test_teammates_excluded_when_teams_active():
    s=mkstate([Team.RED,Team.RED,Team.BLUE,Team.BLUE,Team.BLUE])
    assert 1 not in legal_targets(s,0) and 2 in legal_targets(s,0)
def test_immunity_blocks_target():
    s=mkstate([Team.RED,Team.BLUE,Team.BLUE]); s.players[0].immunity_against={1}
    assert 1 not in legal_targets(s,0)
def test_teams_off_under_three():
    s=mkstate([Team.RED,Team.BLUE])
    assert teams_active(s) is False and 1 in legal_targets(s,0)
def test_assert_legal_shot_raises():
    s=mkstate([Team.RED,Team.RED,Team.BLUE])
    with pytest.raises(Exception): assert_legal_shot(s,0,1)   # teammate
def test_next_living_after_cyclic():
    assert next_living_after([0,1,2,3],{0,2,3},1)==2
    assert next_living_after([0,1,2,3],{0},2)==0
def test_cheapest_payment_minimizes():
    p=Player(0,Team.RED,3,True,{Item.BEER:1,Item.IMMUNITY:1},set(),False,False)
    assert cheapest_payment(p,5)==[Item.IMMUNITY]            # one item beats Beer(4)+something
def test_legal_actions_includes_items_and_shoot():
    s=mkstate([Team.RED,Team.BLUE,Team.BLUE]); s.players[0].inventory={Item.SAW:1,Item.BEER:1}
    acts=legal_actions(s,0)
    assert any(isinstance(a,Shoot) for a in acts)
    assert any(isinstance(a,UseItem) and a.item==Item.SAW for a in acts)
```

- [ ] **Step 2:** `pytest tests/test_legal.py -v` → FAIL.
- [ ] **Step 3: Implement**

```python
# social_roulette/engine/endgame.py
from .state import living_players, living_ids, player_by_id

def teams_active(state): return len(living_players(state))>=3
def winner(state):
    liv=living_players(state); return liv[0].id if len(liv)==1 else None
def legal_targets(state, shooter_id):
    shooter=player_by_id(state,shooter_id); out=[shooter_id]
    for p in living_players(state):
        if p.id==shooter_id or p.id in shooter.immunity_against: continue
        if teams_active(state) and p.team==shooter.team: continue
        out.append(p.id)
    return out
def next_living_after(order, living, pid):
    n=len(order); i=order.index(pid) if pid in order else -1
    for k in range(1,n+1):
        cand=order[(i+k)%n]
        if cand in living: return cand
    return None
def assert_legal_shot(state, shooter_id, target_id):
    if target_id not in legal_targets(state,shooter_id):
        raise ValueError(f"illegal shot {shooter_id}->{target_id}")
```

```python
# social_roulette/engine/actions.py
from dataclasses import dataclass, field
from .constants import Item, POINT_VALUE, MAX_LIVES
from .state import player_by_id, living_players
from .items import cap_reached
from .endgame import legal_targets

@dataclass
class UseItem: item:object; target_id:int=None
@dataclass
class Flip: target_id:int; sacrifice:list=field(default_factory=list)
@dataclass
class Trade: to_id:int; items:list=field(default_factory=list)
@dataclass
class Shoot: target_id:int
@dataclass
class EndSubactions: pass

def cheapest_payment(player, cost):
    # greedy: fewest items whose values cover cost (descending value)
    items=[]
    for it,c in player.inventory.items():
        items+=[it]*c
    items.sort(key=lambda it:POINT_VALUE[it], reverse=True)
    chosen=[]; total=0
    for it in items:
        if total>=cost: break
        chosen.append(it); total+=POINT_VALUE[it]
    return chosen if total>=cost else None

def legal_actions(state, player_id):
    p=player_by_id(state,player_id); acts=[Shoot(t) for t in legal_targets(state,player_id)]
    others=[q.id for q in living_players(state) if q.id!=player_id]
    for it in list(p.inventory):
        if cap_reached(state,it): continue
        if it==Item.CIGARETTES:
            if p.lives<MAX_LIVES: acts.append(UseItem(it))
        elif it==Item.SAW:
            if not state.saw_used_this_turn: acts.append(UseItem(it))
        elif it in (Item.MAGNIFIER, Item.BEER):
            acts.append(UseItem(it))
        elif it==Item.IMMUNITY:
            for o in others: acts.append(UseItem(it,o))
        elif it==Item.HANDCUFFS:
            for o in others:
                if not player_by_id(state,o).handcuffed: acts.append(UseItem(it,o))
    for q in living_players(state):
        pay=cheapest_payment(p,4 if (q.id==player_id and p.flipback_discount) else 5)
        if pay is not None: acts.append(Flip(q.id,pay))
    return acts
```

- [ ] **Step 4:** `pytest tests/test_legal.py -v` → PASS.
- [ ] **Step 5:** Commit: `git add social_roulette/engine/endgame.py social_roulette/engine/actions.py tests/test_legal.py && git commit -m "feat: endgame, legality guard, full legal-action menu"`

---

## Task 10: Turn driver (`take_shot`) — the heart

**Files:** Create `social_roulette/engine/engine.py` (partial: helpers + `take_shot`); Test `tests/test_turn_driver.py`.

**Interfaces — Produces:** `_on_turn_start(state,pid)` (reset `saw_used_this_turn`); `_set_turn_to(state,start_id)` (land on start_id or next living after it, consuming handcuff skips); `_advance_turn(state,from_id)` (clear from_id's `flipback_discount` = window expiry, then `_set_turn_to(next_living_after(from_id))`); `take_shot(state,shooter_id,target_id)->dict`.

**`take_shot` algorithm (precedence — exhaustively tested below):**
1. `assert_legal_shot`; `resolve_shot`; capture `emptied = chamber.is_empty()`.
2. **If killed:** mark dead, remove from `order`, `reload_on_death`, then `draw_items_for_all(2)` **iff emptied**; clear `bonus_pending`/`saw_used_this_turn`; set `winner`. If winner → return.
   - **self-kill** (`shooter==target`): no extra turn → `_set_turn_to(next_living_after(order_before, living, target))`.
   - **else:** killer's **full extra turn** → `_set_turn_to(shooter)`.
3. **Else (no kill):** if `emptied` → `reload_on_empty`. Then if `bonus_pending` → same player continues (reset `saw_used_this_turn`, keep `current_id`). Else → `_advance_turn(shooter)`. Set `winner`.

Co-occurrence truth table the tests must cover: `{blank-other, live-other, self-blank(bonus), self-live, kill-other→extra-turn, self-kill(saw)→no-crash+no-extra, emptied(last shell)→reload, emptied+bonus→reload+same-player, kill+emptied→honor-reload+items, handcuff-skip on advance}`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_turn_driver.py
import pytest
from social_roulette.engine.constants import Team, Shell, Item
from social_roulette.engine.state import Player, Chamber, GameState
from social_roulette.engine.rng import SeededRng
from social_roulette.engine.engine import take_shot

def mk(n, shells, teams=None, **kw):
    teams=teams or [Team.RED]*n
    players=[Player(i,teams[i],3,True,{},set(),False,False) for i in range(n)]
    s=GameState(players=players,order=list(range(n)),current_id=0,chamber=Chamber(shells,0),rng=SeededRng(1))
    for k,v in kw.items(): setattr(s,k,v)
    return s

def test_blank_other_advances():
    s=mk(5,[Shell.BLANK]); take_shot(s,0,2); assert s.current_id==1
def test_self_blank_keeps_turn_bonus():
    s=mk(5,[Shell.BLANK,Shell.LIVE]); take_shot(s,0,0)
    assert s.current_id==0 and s.bonus_pending is True
def test_kill_gives_killer_extra_turn():
    s=mk(5,[Shell.LIVE],teams=[Team.RED,Team.BLUE,Team.RED,Team.RED,Team.RED]); s.players[1].lives=1
    take_shot(s,0,1)
    assert s.players[1].alive is False and s.current_id==0 and 1 not in s.order
def test_self_kill_with_saw_no_crash_no_extra_turn():
    s=mk(5,[Shell.LIVE],saw_active=True); s.players[0].lives=2
    take_shot(s,0,0)   # 2 dmg self -> dies
    assert s.players[0].alive is False and 0 not in s.order and s.current_id==1
def test_emptied_triggers_reload():
    s=mk(5,[Shell.LIVE]); s.players[2].lives=3; take_shot(s,0,2)
    assert len(s.chamber.shells)>0 and s.chamber.pos==0   # reloaded
def test_emptied_plus_bonus_reloads_and_keeps_player():
    s=mk(5,[Shell.BLANK]); take_shot(s,0,0)  # self-blank on last shell
    assert s.current_id==0 and s.bonus_pending is True and len(s.chamber.shells)>0
def test_kill_and_emptied_draws_items():
    s=mk(5,[Shell.LIVE],teams=[Team.RED,Team.BLUE,Team.RED,Team.RED,Team.RED]); s.players[1].lives=1
    before=sum(sum(p.inventory.values()) for p in s.players)
    take_shot(s,0,1)
    assert sum(sum(p.inventory.values()) for p in s.players)>=before and s.chamber.pos==0
def test_handcuff_skipped_on_advance():
    s=mk(5,[Shell.BLANK]); s.players[1].handcuffed=True
    take_shot(s,0,2); assert s.current_id==2 and s.players[1].handcuffed is False
def test_illegal_shot_raises():
    s=mk(3,[Shell.LIVE],teams=[Team.RED,Team.RED,Team.BLUE])
    with pytest.raises(Exception): take_shot(s,0,1)  # teammate
def test_winner_set_on_last_kill():
    s=mk(2,[Shell.LIVE],teams=[Team.RED,Team.BLUE]); s.players[1].lives=1
    take_shot(s,0,1); assert s.winner==0
```

- [ ] **Step 2:** `pytest tests/test_turn_driver.py -v` → FAIL.
- [ ] **Step 3: Implement (partial engine.py)**

```python
# social_roulette/engine/engine.py
from .state import player_by_id, living_ids
from .shooting import resolve_shot
from .reload import reload_on_empty, reload_on_death, draw_items_for_all
from .endgame import assert_legal_shot, winner, next_living_after

def _on_turn_start(state, pid):
    state.saw_used_this_turn=False

def _set_turn_to(state, start_id):
    living=living_ids(state); cur=start_id
    for _ in range(len(state.order)+1):
        p=player_by_id(state,cur)
        if p.handcuffed:
            p.handcuffed=False; cur=next_living_after(state.order,living,cur); continue
        state.current_id=cur; _on_turn_start(state,cur); return
    state.current_id=start_id; _on_turn_start(state,start_id)

def _advance_turn(state, from_id):
    player_by_id(state,from_id).flipback_discount=False
    living=living_ids(state)
    if len(living)<=1: return
    _set_turn_to(state, next_living_after(state.order,living,from_id))

def take_shot(state, shooter_id, target_id):
    assert_legal_shot(state,shooter_id,target_id)
    ev=resolve_shot(state,shooter_id,target_id)
    emptied=state.chamber.is_empty()
    if ev["killed"]:
        order_before=list(state.order)
        player_by_id(state,target_id).alive=False
        state.order=[pid for pid in order_before if pid!=target_id]
        reload_on_death(state)
        if emptied: draw_items_for_all(state,2)
        state.bonus_pending=False; state.saw_used_this_turn=False
        state.winner=winner(state)
        if state.winner is not None: return ev
        if shooter_id==target_id:
            _set_turn_to(state, next_living_after(order_before,living_ids(state),target_id))
        else:
            _set_turn_to(state, shooter_id)   # killer's full extra turn
        return ev
    if emptied: reload_on_empty(state)
    if state.bonus_pending:
        state.saw_used_this_turn=False; return ev   # same player, bonus turn
    _advance_turn(state,shooter_id)
    state.winner=winner(state)
    return ev
```

- [ ] **Step 4:** `pytest tests/test_turn_driver.py -v` → PASS (all). If any fail, fix `take_shot`/helpers until green — this task is the engine's core.
- [ ] **Step 5:** Commit: `git add social_roulette/engine/engine.py tests/test_turn_driver.py && git commit -m "feat: turn driver take_shot with full precedence truth-table"`

---

## Task 11: `new_game` + `step`

**Files:** Modify `social_roulette/engine/engine.py` (append `new_game`, `step`); Test `tests/test_endgame.py` (append).

**Interfaces — Produces:**
- `new_game(num_players,seed)->GameState` — teams balanced with **coin-flipped odd seat**, shuffled onto players; random `order`; `current_id=order[0]`; 3 starting items each (1–6 table); first chamber loaded.
- `step(state,player_id,action)->dict` — `Shoot`→`take_shot`; `UseItem`→ raise if `cap_reached`, else `apply_item`, and if `Item.BEER` emptied the chamber → `reload_on_empty`; `Flip`→`flip_team`; `EndSubactions`→`{}`; `Trade`→`raise NotImplementedError("trade is Stage 1")`.

- [ ] **Step 1: Failing tests (append)**

```python
# tests/test_endgame.py (append)
from social_roulette.engine.engine import new_game, step
from social_roulette.engine.actions import UseItem, Shoot
from social_roulette.engine.constants import Item, Shell

def test_new_game_shape():
    s=new_game(5,seed=1)
    assert len(s.players)==5 and all(p.lives==3 for p in s.players)
    assert all(sum(p.inventory.values())==3 for p in s.players)
    assert sum(1 for x in s.chamber.shells if x==Shell.LIVE)>5 and s.current_id==s.order[0]

def test_team_odd_seat_coinflips_across_seeds():
    reds=set()
    for seed in range(40):
        s=new_game(5,seed=seed); reds.add(sum(1 for p in s.players if p.team.name=="RED"))
    assert reds=={2,3}     # odd seat goes to RED in some seeds, BLUE in others

def test_step_beer_empty_reloads_midturn():
    s=new_game(5,seed=2); s.players[s.current_id].inventory={Item.BEER:1}
    s.chamber.shells=[s.chamber.shells[0]]; s.chamber.pos=0      # force 1-shell chamber
    step(s,s.current_id,UseItem(Item.BEER))
    assert not s.chamber.is_empty()                              # reloaded, ready to shoot
```

- [ ] **Step 2:** `pytest tests/test_endgame.py -v` → FAIL (new tests).
- [ ] **Step 3: Implement (append to engine.py)**

```python
# social_roulette/engine/engine.py (append)
from .constants import Team, ITEM_TABLE, START_LIVES
from .state import Player, Chamber, GameState
from .rng import SeededRng
from .chamber import load_chamber
from .items import apply_item, cap_reached
from .economy import flip_team
from .actions import UseItem, Flip, Trade, Shoot, EndSubactions
from .constants import Item

def new_game(num_players, seed):
    assert num_players>=5
    rng=SeededRng(seed); half=num_players//2; extra=num_players-2*half
    counts={Team.RED:half, Team.BLUE:half}
    if extra: counts[Team.RED if rng.randint(0,1)==0 else Team.BLUE]+=1
    teams=[Team.RED]*counts[Team.RED]+[Team.BLUE]*counts[Team.BLUE]; rng.shuffle(teams)
    players=[]
    for i in range(num_players):
        inv={}
        for _ in range(3):
            it=ITEM_TABLE[rng.randint(1,6)]; inv[it]=inv.get(it,0)+1
        players.append(Player(i,teams[i],START_LIVES,True,inv,set(),False,False))
    order=list(range(num_players)); rng.shuffle(order)
    chamber=load_chamber(rng,num_players)
    return GameState(players=players,order=order,current_id=order[0],chamber=chamber,rng=rng)

def step(state, player_id, action):
    if isinstance(action,Shoot): return take_shot(state,player_id,action.target_id)
    if isinstance(action,UseItem):
        if cap_reached(state,action.item): raise ValueError("consumption cap reached")
        ev=apply_item(state,player_id,action.item,action.target_id)
        if action.item==Item.BEER and state.chamber.is_empty(): reload_on_empty(state)
        return ev
    if isinstance(action,Flip): return flip_team(state,player_id,action.target_id,action.sacrifice)
    if isinstance(action,EndSubactions): return {}
    if isinstance(action,Trade): raise NotImplementedError("trade is Stage 1")
    raise ValueError(f"unknown action {action}")
```

- [ ] **Step 4:** `pytest tests/test_endgame.py -v` → PASS.
- [ ] **Step 5:** Commit: `git add social_roulette/engine/engine.py tests/test_endgame.py && git commit -m "feat: new_game (team coin-flip) + step (Beer-empty reload, cap guard)"`

---

## Task 12: Full-action random agent + simulation

**Files:** Create `social_roulette/sim/random_agent.py`, `social_roulette/sim/run_sim.py`; Test `tests/test_sim.py`.

**Interfaces — Produces:**
- `play_game(num_players,seed,max_turns=20000,max_sub=40)->{"winner","turns","history_hash"}` — outer loop while no winner: for `current_id`, run up to `max_sub` random legal sub-actions; when a `Shoot` is chosen, `take_shot` then end the turn (break); if `max_sub` hit without shooting, force a `Shoot` at a random legal target. Hash each shot's `(shooter,target,shell,damage,killed)`. After each shot the outer loop re-reads `current_id` (so bonus/extra turns recur naturally). Raise if `max_turns` exceeded (non-termination = bug).
- `run_sim.main(games=2000)` — play seeded games across 5–10 players; assert each returns a winner; print mean/median/max turns + winner-by-seat.

**This is the integration proof.** Because the agent uses items/flips/placements, it WILL exercise self-kill, Beer-empty, last-shell bonus, killer extra turn, handcuff skip.

- [ ] **Step 1: Failing test**

```python
# tests/test_sim.py
import pytest
from social_roulette.sim.random_agent import play_game

@pytest.mark.parametrize("seed", range(60))
def test_every_full_action_game_terminates(seed):
    for n in (5,7,10):
        res=play_game(num_players=n,seed=seed)
        assert res["winner"] is not None and res["turns"]<20000
```

- [ ] **Step 2:** `pytest tests/test_sim.py -v` → FAIL (ImportError).
- [ ] **Step 3: Implement**

```python
# social_roulette/sim/random_agent.py
import hashlib
from social_roulette.engine.engine import new_game, step, take_shot
from social_roulette.engine.actions import legal_actions, Shoot
from social_roulette.engine.endgame import legal_targets

def play_game(num_players, seed, max_turns=20000, max_sub=40):
    state=new_game(num_players,seed); h=hashlib.sha256(); turns=0
    while state.winner is None and turns<max_turns:
        pid=state.current_id; shot=False
        for _ in range(max_sub):
            action=state.rng.choice(legal_actions(state,pid))
            if isinstance(action,Shoot):
                ev=take_shot(state,pid,action.target_id)
                h.update(repr((pid,action.target_id,ev["shell"].name,ev["damage"],ev["killed"])).encode())
                shot=True; break
            step(state,pid,action)
        if not shot:
            tgt=state.rng.choice(legal_targets(state,pid))
            ev=take_shot(state,pid,tgt)
            h.update(repr((pid,tgt,ev["shell"].name,ev["damage"],ev["killed"])).encode())
        turns+=1
    if state.winner is None: raise RuntimeError("game did not terminate")
    return {"winner":state.winner,"turns":turns,"history_hash":h.hexdigest()}
```

```python
# social_roulette/sim/run_sim.py
import statistics
from social_roulette.sim.random_agent import play_game

def main(games=2000):
    turns=[]; winners={}
    for seed in range(games):
        n=5+(seed%6); res=play_game(n,seed)
        assert res["winner"] is not None
        turns.append(res["turns"]); winners[res["winner"]]=winners.get(res["winner"],0)+1
    print(f"games={games} mean={statistics.mean(turns):.1f} median={statistics.median(turns)} max={max(turns)}")
    print("winner-by-seat:", dict(sorted(winners.items())))

if __name__=="__main__":
    main()
```

- [ ] **Step 4:** Run `pytest tests/test_sim.py -v && python -m social_roulette.sim.run_sim` → all PASS; sim prints stats, no assertion errors. **If a game raises (self-kill crash, Beer-empty, etc.), that is a real engine bug — go fix the relevant task, don't patch the agent.**
- [ ] **Step 5:** Commit: `git add social_roulette/sim tests/test_sim.py && git commit -m "feat: full-action random agent + sim proving termination over 2000 games"`

---

## Task 13: Determinism + full suite green

**Files:** Test `tests/test_determinism.py`.

- [ ] **Step 1: Failing test**

```python
# tests/test_determinism.py
import pytest
from social_roulette.sim.random_agent import play_game

@pytest.mark.parametrize("seed",[0,1,7,42,99,123,500])
def test_same_seed_same_game(seed):
    a=play_game(8,seed); b=play_game(8,seed)
    assert a["winner"]==b["winner"] and a["history_hash"]==b["history_hash"] and a["turns"]==b["turns"]
```

- [ ] **Step 2:** `pytest tests/test_determinism.py -v` → should PASS immediately (engine already deterministic). If it FAILS, a nondeterminism leak exists (e.g. a `set` iteration affecting an action choice) — hunt and fix before proceeding.
- [ ] **Step 3:** Full suite: `pytest -q` → all green.
- [ ] **Step 4:** Determinism sweep: `python -c "from social_roulette.sim.random_agent import play_game as g; assert all(g(8,s)['history_hash']==g(8,s)['history_hash'] for s in range(300)); print('OK 300 seeds')"`
- [ ] **Step 5:** Commit: `git add -A && git commit -m "test: Stage 0 complete — deterministic, terminating, full-action rule-tested"`

---

## Self-Review

**Spec coverage (game_guide.md → task):** chamber 30–70% → T4; lives/caps → T3,6,8; Immunity → T5,6,9; Cigarettes max-lock → T6; Magnifier → T6; Saw 1/turn+×2+self → T5,6; Beer remove/shrink/last-shell → T6,11; Handcuffs skip/no-stack → T6,10; economy pay/flip/discount+window → T7,10; consumption ×1.3+reset+commit → T6,8,10; reload empty(+2 items)/death(killer extra turn, caps reset, items-iff-also-emptied) → T8,10; teams-off-<3 + win → T9,10; team coin-flip → T11; engine-level legality → T9,10.

**Bug-fix traceability (from the critical self-check + advisor):**
- Self-kill crash → T10 `self-kill` branch + `test_self_kill_with_saw_no_crash_no_extra_turn`.
- Beer-empties-midturn → T11 `step` reload wiring + `test_step_beer_empty_reloads_midturn`.
- emptied+bonus ordering → T10 `test_emptied_plus_bonus_reloads_and_keeps_player`.
- Team coin-flip → T11 `test_team_odd_seat_coinflips_across_seeds`.
- Flip-back window expiry → T10 `_advance_turn` clears `flipback_discount`.
- Cap not enforced / Trade unhandled → T11 `step`.
- `legal_actions` dead code / hollow proof → T9 full menu + T12 agent drives off it.
- No engine legality guard → T9 `assert_legal_shot` + T10 `test_illegal_shot_raises`.

**Deliverable claim (now honest):** the sim is **full-action**, so "every game terminates with one winner" covers items + economy + shooting, not a shoot-only subset.

**Deferred (Stage 1, intentionally absent):** observation filtering; Beer-reveal & token visibility; bilateral Trade; sub-action budget richness; PettingZoo; emoji channel; network masking.

---

## Execution Handoff

Plan complete. Choose execution mode in the next message.

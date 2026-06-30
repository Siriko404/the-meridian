# Stage 3 Emoji Comms (v1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a rule-based emoji chatroom (compositional `[ACT][WHO][VALUE]`, ≤2 msgs/turn) that agents can speak and hear, then measure whether self-interested RL agents actually use it.

**Architecture:** Messages live in `GameState` (deterministic, recordable, observable). A new `Speak` action is dispatched by `engine.step` with no game-state effect. The learner emits speaks as ordinary sub-actions before its shot; everyone hears via a last-K message window appended to the observation. Referents are relative-seat (seat-invariant); events store absolute, listeners re-relativize. Reuses the reserved `MESSAGE` event + Stage-2 self-play machinery.

**Tech Stack:** Python 3.13, gymnasium, sb3-contrib MaskablePPO, pyarrow, scipy. Run via `./.venv/Scripts/python`.

## Global Constraints

- Reward unchanged: terminal-only, individual (+1 win / −1 death / 0).
- No LLM. Lying = emitting a false claim; no special token.
- Talk only on normal turns; **bonus turns silent** (gate on `state.bonus_pending`).
- WHO/target referents are **relative seats** (0=self, 1..4 others); `MESSAGE` event stores **absolute** seat; obs re-relativizes per observer.
- `MSG_CAP = 2` messages/turn. Obs window `K = 8` most-recent messages.
- Eval seeds **≥ 3,000,000** (disjoint from Stage-1 1e6, Stage-2 2e6).
- N_SEATS = 5 (matches `obs.N_SLOTS`, `action_space.N_SEATS`).
- Tests run with `PYTHONUTF8=1 ./.venv/Scripts/python -m pytest -q`.

---

### Task 1: Comms vocabulary (`comms/vocab.py`)

**Files:**
- Create: `social_roulette/comms/__init__.py` (empty)
- Create: `social_roulette/comms/vocab.py`
- Test: `tests/test_vocab.py`

**Interfaces — Produces:**
- `Act` IntEnum: `SHOOT_INTENT=0, GANG_UP=1, NEXT_SHELL=2, TRUCE=3, AGREE=4`
- `ACT_N = 5`
- `SPEAK_N = 15` — total speak options
- `SPEAK_TABLE: list[tuple]` — index → `(act, who_rel, value)` where `who_rel∈{1,2,3,4}` or `None`, `value∈{0,1}` or `None` (NEXT_SHELL: value 1=live,0=blank)
- `speak_index(act, who_rel, value) -> int` — inverse of SPEAK_TABLE
- `render(act, who_name, value) -> str` — NL line fragment

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vocab.py
from social_roulette.comms.vocab import Act, ACT_N, SPEAK_N, SPEAK_TABLE, speak_index, render


def test_speak_table_is_bijective():
    assert SPEAK_N == len(SPEAK_TABLE) == 15
    for i, (act, who, val) in enumerate(SPEAK_TABLE):
        assert speak_index(act, who, val) == i


def test_table_covers_expected_acts():
    acts = [t[0] for t in SPEAK_TABLE]
    assert acts.count(Act.SHOOT_INTENT) == 4   # who 1..4
    assert acts.count(Act.GANG_UP) == 4
    assert acts.count(Act.NEXT_SHELL) == 2      # live/blank
    assert acts.count(Act.TRUCE) == 4
    assert acts.count(Act.AGREE) == 1


def test_render_examples():
    assert render(Act.SHOOT_INTENT, "Wolf", None) == "I'll shoot Wolf"
    assert render(Act.NEXT_SHELL, None, 1) == "next shell is live"
    assert render(Act.AGREE, None, None) == "agreed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONUTF8=1 ./.venv/Scripts/python -m pytest tests/test_vocab.py -q`
Expected: FAIL — `ModuleNotFoundError: social_roulette.comms.vocab`

- [ ] **Step 3: Write minimal implementation**

```python
# social_roulette/comms/__init__.py  -> empty file

# social_roulette/comms/vocab.py
from enum import IntEnum


class Act(IntEnum):
    SHOOT_INTENT = 0
    GANG_UP = 1
    NEXT_SHELL = 2
    TRUCE = 3
    AGREE = 4


ACT_N = 5
_WHO = (1, 2, 3, 4)


def _build_table():
    t = []
    for a in (Act.SHOOT_INTENT, Act.GANG_UP):
        t += [(a, w, None) for w in _WHO]
    t += [(Act.NEXT_SHELL, None, v) for v in (1, 0)]   # live, blank
    t += [(Act.TRUCE, w, None) for w in _WHO]
    t += [(Act.AGREE, None, None)]
    return t


SPEAK_TABLE = _build_table()
SPEAK_N = len(SPEAK_TABLE)
_INDEX = {(a, w, v): i for i, (a, w, v) in enumerate(SPEAK_TABLE)}


def speak_index(act, who_rel, value):
    return _INDEX[(Act(act), who_rel, value)]


def render(act, who_name, value):
    a = Act(act)
    if a == Act.SHOOT_INTENT:
        return f"I'll shoot {who_name}"
    if a == Act.GANG_UP:
        return f"everyone shoot {who_name}"
    if a == Act.NEXT_SHELL:
        return f"next shell is {'live' if value else 'blank'}"
    if a == Act.TRUCE:
        return f"truce, {who_name}"
    return "agreed"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONUTF8=1 ./.venv/Scripts/python -m pytest tests/test_vocab.py -q`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add social_roulette/comms/__init__.py social_roulette/comms/vocab.py tests/test_vocab.py
git commit -m "feat(comms): v1 emoji vocabulary — 5 acts, 15 speak options, NL render"
```

---

### Task 2: Message state (`engine/state.py`)

**Files:**
- Modify: `social_roulette/engine/state.py:33-44` (GameState fields)
- Modify: `social_roulette/engine/engine.py:13-15` (`_on_turn_start`)
- Test: `tests/test_message_state.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Msg(turn, speaker, act, target, value)` dataclass (absolute seat ids); `GameState.messages: list[Msg]`; `GameState.msgs_this_turn: int` (reset to 0 at every turn start).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_message_state.py
from social_roulette.engine.engine import new_game, take_shot
from social_roulette.engine.state import Msg
from social_roulette.engine.endgame import legal_targets


def test_state_has_message_fields():
    s = new_game(5, 1)
    assert s.messages == [] and s.msgs_this_turn == 0


def test_msgs_this_turn_resets_on_turn_advance():
    s = new_game(5, 1)
    s.msgs_this_turn = 2
    shooter = s.current_id
    tgt = next(t for t in legal_targets(s, shooter) if t != shooter)
    take_shot(s, shooter, tgt)          # advances to a new turn
    assert s.msgs_this_turn == 0


def test_msg_dataclass_fields():
    m = Msg(turn=3, speaker=0, act=1, target=2, value=None)
    assert (m.turn, m.speaker, m.act, m.target, m.value) == (3, 0, 1, 2, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONUTF8=1 ./.venv/Scripts/python -m pytest tests/test_message_state.py -q`
Expected: FAIL — `ImportError: cannot import name 'Msg'` and missing fields.

- [ ] **Step 3: Write minimal implementation**

In `social_roulette/engine/state.py`, add after the `Chamber` dataclass (before `GameState`):

```python
@dataclass
class Msg:
    turn: int
    speaker: int      # absolute seat id
    act: int
    target: int       # absolute seat id, or None
    value: int        # 0/1, or None
```

In `GameState`, add two fields after `winner: int = None`:

```python
    messages: list = field(default_factory=list)
    msgs_this_turn: int = 0
```

In `social_roulette/engine/engine.py`, edit `_on_turn_start`:

```python
def _on_turn_start(state, pid):
    state.saw_used_this_turn = False
    state.msgs_this_turn = 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONUTF8=1 ./.venv/Scripts/python -m pytest tests/test_message_state.py -q`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add social_roulette/engine/state.py social_roulette/engine/engine.py tests/test_message_state.py
git commit -m "feat(comms): Msg + GameState.messages/msgs_this_turn (reset on turn start)"
```

---

### Task 3: Speak action + dispatch + legality (`engine/actions.py`, `engine/engine.py`)

**Files:**
- Modify: `social_roulette/engine/actions.py` (add `Speak`, extend `legal_actions`)
- Modify: `social_roulette/engine/engine.py:95-111` (`step` dispatch)
- Test: `tests/test_speak_action.py`

**Interfaces:**
- Consumes: `Msg` (Task 2), `MSG_CAP`.
- Produces: `Speak(act, target, value)` dataclass (target absolute or None); `step` handles `Speak` by appending a `Msg` and incrementing `msgs_this_turn`; `legal_actions` includes `Speak` options when `not state.bonus_pending and state.msgs_this_turn < MSG_CAP`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_speak_action.py
from social_roulette.engine.engine import new_game, step
from social_roulette.engine.actions import Speak, legal_actions, MSG_CAP


def test_step_speak_appends_message():
    s = new_game(5, 1)
    pid = s.current_id
    step(s, pid, Speak(act=4, target=None, value=None))   # AGREE
    assert len(s.messages) == 1 and s.msgs_this_turn == 1
    m = s.messages[0]
    assert m.speaker == pid and m.act == 4


def test_speak_options_present_then_capped():
    s = new_game(5, 1)
    pid = s.current_id
    assert any(isinstance(a, Speak) for a in legal_actions(s, pid))
    for _ in range(MSG_CAP):
        step(s, pid, Speak(act=4, target=None, value=None))
    assert not any(isinstance(a, Speak) for a in legal_actions(s, pid))


def test_speak_silent_on_bonus_turn():
    s = new_game(5, 1)
    s.bonus_pending = True
    assert not any(isinstance(a, Speak) for a in legal_actions(s, s.current_id))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONUTF8=1 ./.venv/Scripts/python -m pytest tests/test_speak_action.py -q`
Expected: FAIL — `ImportError: cannot import name 'Speak'`.

- [ ] **Step 3: Write minimal implementation**

In `social_roulette/engine/actions.py`, add the import line at top: `from .state import player_by_id, living_players, Msg`. Add the dataclass + constant + a vocab-driven legal-speak helper:

```python
MSG_CAP = 2

@dataclass
class Speak:
    act: int
    target: int = None     # absolute seat id, or None
    value: int = None      # 0/1, or None
```

At the END of `legal_actions`, before `return acts`, add:

```python
    if not state.bonus_pending and state.msgs_this_turn < MSG_CAP:
        from social_roulette.comms.vocab import SPEAK_TABLE
        n = len(state.players)
        for act, who_rel, value in SPEAK_TABLE:
            target = (player_id + who_rel) % n if who_rel is not None else None
            if target is not None and not player_by_id(state, target).alive:
                continue
            acts.append(Speak(act, target, value))
```

In `social_roulette/engine/engine.py`, add `Speak` to the actions import (line 10) and handle it in `step` (before the `Trade` branch):

```python
    if isinstance(action, Speak):
        state.messages.append(Msg(state.current_id, player_id, action.act,
                                  action.target, action.value)
                              if False else
                              Msg(turn=len(state.messages), speaker=player_id,
                                  act=action.act, target=action.target, value=action.value))
        state.msgs_this_turn += 1
        return {}
```

(Use the second `Msg(...)` form; `turn` = running message ordinal is fine for v1 ordering. Also add `Msg` to the state import on engine.py line 2 and `Speak` to the actions import on line 10.)

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONUTF8=1 ./.venv/Scripts/python -m pytest tests/test_speak_action.py -q`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add social_roulette/engine/actions.py social_roulette/engine/engine.py tests/test_speak_action.py
git commit -m "feat(comms): Speak action — dispatch appends Msg, legal in talk phase under cap"
```

---

### Task 4: Action codec SPEAK indices (`rl/action_space.py`)

**Files:**
- Modify: `social_roulette/rl/action_space.py`
- Test: `tests/test_speak_codec.py`

**Interfaces:**
- Consumes: `SPEAK_TABLE`, `speak_index`, `Speak`, `MSG_CAP`.
- Produces: `ACTION_N = 24 + SPEAK_N` (=39). `decode` maps a speak index → `Speak(act, abs_target, value)`. `_index_of(Speak,...)` and `legal_mask` cover speak bits.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_speak_codec.py
import numpy as np
from social_roulette.engine.engine import new_game
from social_roulette.engine.actions import Speak
from social_roulette.rl.action_space import ActionCodec, ACTION_N
from social_roulette.comms.vocab import SPEAK_N, Act


def test_action_n_grew_by_speak():
    assert ACTION_N == 24 + SPEAK_N


def test_decode_speak_roundtrips_target_to_absolute():
    s = new_game(5, 1)
    lid = s.current_id
    for idx in range(24, ACTION_N):
        a = ActionCodec.decode(idx, s, lid)
        assert isinstance(a, Speak)
        assert ActionCodec._index_of(a, lid) == idx


def test_mask_includes_speak_in_talk_phase():
    s = new_game(5, 1)
    m = ActionCodec.legal_mask(s, s.current_id, shoot_only=False)
    assert m.shape == (ACTION_N,) and m[24:].any()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONUTF8=1 ./.venv/Scripts/python -m pytest tests/test_speak_codec.py -q`
Expected: FAIL — `ACTION_N == 24` (not 39).

- [ ] **Step 3: Write minimal implementation**

In `social_roulette/rl/action_space.py`: add imports `from social_roulette.engine.actions import Speak` and `from social_roulette.comms.vocab import SPEAK_TABLE, SPEAK_N, speak_index`. Change `ACTION_N = 24 + SPEAK_N`. In `decode`, before the final `Flip` block returns, add at the top a speak branch:

```python
        if idx >= 24:
            act, who_rel, value = SPEAK_TABLE[idx - 24]
            target = _abs_seat(learner_id, who_rel) if who_rel is not None else None
            return Speak(act, target, value)
```

In `_index_of`, add at the top:

```python
        if isinstance(action, Speak):
            who_rel = _rel(learner_id, action.target) if action.target is not None else None
            return 24 + speak_index(action.act, who_rel, action.value)
```

`legal_mask` already loops `legal_actions` → `_index_of`; speak actions now map into `mask[24:]`. No further change (shoot_only still zeroes `mask[5:]`, which correctly excludes speak in shoot-only mode).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONUTF8=1 ./.venv/Scripts/python -m pytest tests/test_speak_codec.py -q`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add social_roulette/rl/action_space.py tests/test_speak_codec.py
git commit -m "feat(comms): ActionCodec SPEAK indices (24..38), relative<->absolute target"
```

---

### Task 5: Hear — last-K message window in obs (`rl/obs.py`)

**Files:**
- Modify: `social_roulette/rl/obs.py`
- Test: `tests/test_obs_messages.py`

**Interfaces:**
- Consumes: `GameState.messages`, `ACT_N`, `N_SLOTS`.
- Produces: `OBS_DIM` grows by `K * MSG_FEATURES`. Each of the last `K=8` messages encodes `[has, speaker_rel/N, act/ACT_N, target_rel/N, value]` re-relativized to `learner_id`; absent slots are zeros. Empty-target/empty-value use sentinel 0 with `has` flag distinguishing real rows.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_obs_messages.py
import numpy as np
from social_roulette.engine.engine import new_game, step
from social_roulette.engine.actions import Speak
from social_roulette.rl.obs import encode_obs, OBS_DIM, MSG_K, MSG_FEATURES

EX = {"known_next_shell": "unknown", "announced_total": 10, "announced_live": 6}


def test_obs_dim_includes_message_window():
    assert OBS_DIM == 62 + MSG_K * MSG_FEATURES


def test_message_changes_obs_and_is_relativized():
    s = new_game(5, 1)
    spk = s.current_id
    base = encode_obs(s, learner_id=0, extras=EX).copy()
    step(s, spk, Speak(act=1, target=(spk + 1) % 5, value=None))   # GANG_UP someone
    after = encode_obs(s, learner_id=0, extras=EX)
    assert not np.array_equal(after, base)            # heard it
    # observer 0 and observer 1 see the SAME message at different relative speaker
    o0 = encode_obs(s, 0, EX); o1 = encode_obs(s, 1, EX)
    assert not np.array_equal(o0[-MSG_K * MSG_FEATURES:], o1[-MSG_K * MSG_FEATURES:])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONUTF8=1 ./.venv/Scripts/python -m pytest tests/test_obs_messages.py -q`
Expected: FAIL — `ImportError: cannot import name 'MSG_K'`.

- [ ] **Step 3: Write minimal implementation**

In `social_roulette/rl/obs.py`: add `from social_roulette.comms.vocab import ACT_N` and constants `MSG_K = 8`, `MSG_FEATURES = 5`, and change `OBS_DIM = N_SLOTS * PER_SLOT + GLOBALS + MSG_K * MSG_FEATURES`. At the END of `encode_obs`, before `return`, append:

```python
    recent = state.messages[-MSG_K:]
    pad = MSG_K - len(recent)
    for _ in range(pad):
        vec += [0.0] * MSG_FEATURES
    for m in recent:
        spk_rel = (m.speaker - learner_id) % N_SLOTS
        tgt_rel = ((m.target - learner_id) % N_SLOTS) if m.target is not None else 0
        vec += [
            1.0,
            spk_rel / N_SLOTS,
            m.act / ACT_N,
            tgt_rel / N_SLOTS,
            0.0 if m.value is None else float(m.value),
        ]
    return np.asarray(vec, dtype=np.float32)
```

(Delete the old `return np.asarray(...)` line that this block replaces.)

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONUTF8=1 ./.venv/Scripts/python -m pytest tests/test_obs_messages.py -q`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add social_roulette/rl/obs.py tests/test_obs_messages.py
git commit -m "feat(comms): obs gains last-K message window, re-relativized per listener"
```

---

### Task 6: Turn driver handles Speak + records MESSAGE (`sim/turn.py`, `observe/recorder.py`, `observe/match.py`)

**Files:**
- Modify: `social_roulette/observe/recorder.py` (add `message`)
- Modify: `social_roulette/sim/turn.py` (handle `Speak` in the sub-action loop)
- Test: `tests/test_turn_speak.py`

**Interfaces:**
- Consumes: `Speak`, `Recorder`.
- Produces: `recorder.message(turn, speaker, act, target, value)` → `MESSAGE` event; `take_policy_turn` executes `Speak` sub-actions (records if `rec`) and continues the turn.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_turn_speak.py
from social_roulette.engine.engine import new_game
from social_roulette.sim.turn import take_policy_turn, Extras
from social_roulette.engine.actions import Speak, legal_actions, Shoot
from social_roulette.observe.events import MESSAGE


def _talky_policy(state, pid, extras):
    for a in legal_actions(state, pid):
        if isinstance(a, Speak):
            return a
    return next(a for a in legal_actions(state, pid) if isinstance(a, Shoot))


def test_take_policy_turn_records_message():
    s = new_game(5, 1)
    extras = {i: Extras() for i in range(5)}
    for e in extras.values():
        e.sync(s)
    from social_roulette.observe.recorder import Recorder
    rec = Recorder(0)
    take_policy_turn(s, s.current_id, _talky_policy, extras, rec=rec, turn_idx=0)
    assert any(r["type"] == MESSAGE for r in rec.rows)
    assert len(s.messages) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONUTF8=1 ./.venv/Scripts/python -m pytest tests/test_turn_speak.py -q`
Expected: FAIL — `AttributeError: 'Recorder' object has no attribute 'message'` (or no MESSAGE row).

- [ ] **Step 3: Write minimal implementation**

In `social_roulette/observe/recorder.py`, add a method:

```python
    def message(self, turn, speaker, act, target, value):
        self._emit(E.MESSAGE, turn=turn, actor=speaker, target=target,
                   extra={"act": act, "value": value})
```

In `social_roulette/sim/turn.py`, import `Speak` (`from social_roulette.engine.actions import legal_actions, Shoot, Flip, Speak`) and in `take_policy_turn`'s 40-iteration loop, add a `Speak` branch BEFORE the `Flip` branch:

```python
        if isinstance(a, Speak):
            step(state, pid, a)
            if rec:
                rec.message(turn_idx, pid, a.act, a.target, a.value)
            for e in extras_map.values():
                e.sync(state)
            continue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONUTF8=1 ./.venv/Scripts/python -m pytest tests/test_turn_speak.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add social_roulette/observe/recorder.py social_roulette/sim/turn.py tests/test_turn_speak.py
git commit -m "feat(comms): take_policy_turn executes Speak + records MESSAGE event"
```

---

### Task 7: Full-suite regression + self-play smoke with comms

**Files:**
- Test: run the whole suite; manual smoke of the existing self-play env (it composes obs+codec+turn, so comms flows automatically).

- [ ] **Step 1: Run the full suite**

Run: `PYTHONUTF8=1 ./.venv/Scripts/python -m pytest -q`
Expected: ALL pass. (Stage-1/2 tests use seat 0 + no messages → `messages=[]`, new obs tail is zeros, `ACTION_N` grew so any hard-coded `24` in tests must be checked. If `tests/test_action_codec.py::test_action_n` asserts `== 24`, update it to `== 24 + SPEAK_N` and note in the commit.)

- [ ] **Step 2: Self-play smoke (comms in the loop, untrained)**

Run:
```bash
PYTHONUTF8=1 ./.venv/Scripts/python -c "
from social_roulette.rl.selfplay_env import SocialRouletteSelfPlayEnv
from social_roulette.sim.turn import random_policy
import numpy as np
env = SocialRouletteSelfPlayEnv(opponent_sampler=lambda rng: random_policy)
obs, info = env.reset(seed=3000001)
rng = np.random.default_rng(0)
term = False
while not term:
    legal = np.flatnonzero(info['action_mask'])
    obs, r, term, _, info = env.step(int(rng.choice(legal)))
print('OK terminal reward', r, 'obs_dim', obs.shape)
"
```
Expected: prints `OK terminal reward {-1.0|1.0} obs_dim (102,)` (62 + 8*5). No crash → comms actions, masking, and the message window all integrate with the Stage-2 env unchanged.

- [ ] **Step 3: Commit any test fixups**

```bash
git add -A && git commit -m "test(comms): regression green with comms wired (ACTION_N/OBS_DIM grown)"
```

---

### Task 8: Train a fresh comms seed (parallel self-play)

**Files:**
- Modify: `social_roulette/rl/selfplay.py` (add `--retrain-seed` already exists; confirm it trains with comms now that the env composes it)
- Artifact: `models/stage3seed`

**Interfaces:**
- Consumes: `make_vec_selfplay_env`, `MaskablePPO`.
- Produces: `models/stage3seed.zip` — a fresh comms-capable policy (do NOT warm-start from `stage2seed`; obs+action shapes differ → load would mismatch).

- [ ] **Step 1: Confirm fresh-train path (no warm-start)**

The existing `--retrain-seed` branch builds a FRESH `MaskablePPO("MlpPolicy", venv, ...)` — correct for the changed shapes. No code change needed beyond Task 1-6.

- [ ] **Step 2: Train (parallel, random opponents — establishes a comms-capable competent seed)**

Run:
```bash
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 ./.venv/Scripts/python -m social_roulette.rl.selfplay \
  --retrain-seed --steps-per-gen 1000000 --n-envs 12 --out models/stage3seed
```
Expected: prints `saved models/stage3seed per-seat vs random: [...]` — per-seat win-rates should be **flat ~0.7** (seat-invariance preserved; comms is just extra masked actions).

- [ ] **Step 3: Commit**

```bash
git add models/stage3seed.zip
git commit -m "feat(comms): fresh comms-capable seed (models/stage3seed), seat-invariant"
```

---

### Task 9: Self-play with comms + the measurement harness

**Files:**
- Create: `social_roulette/rl/comms_eval.py`
- Test: `tests/test_comms_eval.py`

**Interfaces:**
- Consumes: `run_match`, `make_model_policy`, `GameState.messages`, `scipy.stats`.
- Produces:
  - `scramble_messages(state)` — returns a copy of obs-relevant message view with `act/target/value` shuffled across the K window (breaks state-correlation, preserves marginal). Implemented as a policy wrapper that permutes the message tail of the obs before `predict`.
  - `response_shift(model_path, n_games, seed_offset=3_000_000)` → dict with `p_real`, `p_scrambled`, `delta`, `z`, `pvalue` for the GANG_UP→shoot-named-target contingency (the PRIMARY metric).
  - `winrate_ablation(model_path, n_games)` → `{intact, receiver_scrambled, sender_muted}` win-rates (SECONDARY), `n_games ≥ 2500`.

- [ ] **Step 1: Write the failing test** (small n, just exercises the harness shape)

```python
# tests/test_comms_eval.py
from social_roulette.rl.comms_eval import response_shift


def test_response_shift_returns_stats_keys():
    out = response_shift("models/stage3seed", n_games=40, seed_offset=3_000_000)
    for k in ("p_real", "p_scrambled", "delta", "z", "pvalue"):
        assert k in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONUTF8=1 ./.venv/Scripts/python -m pytest tests/test_comms_eval.py -q`
Expected: FAIL — `ModuleNotFoundError: social_roulette.rl.comms_eval`.

- [ ] **Step 3: Write minimal implementation**

```python
# social_roulette/rl/comms_eval.py
"""Stage-3 measurement: does the agent USE the channel?
PRIMARY = per-decision response shift (high power). SECONDARY = win-rate ablation.
"""
import math
from scipy.stats import norm

from social_roulette.observe.match import run_match
from social_roulette.rl.policies import make_model_policy
from social_roulette.rl.obs import MSG_K, MSG_FEATURES
from social_roulette.comms.vocab import Act


def _two_prop(k1, n1, k2, n2):
    if n1 == 0 or n2 == 0:
        return {"delta": 0.0, "z": 0.0, "pvalue": 1.0}
    p1, p2 = k1 / n1, k2 / n2
    pool = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2)) or 1e-9
    z = (p1 - p2) / se
    return {"delta": p1 - p2, "z": z, "pvalue": 1 - norm.cdf(z)}


def response_shift(model_path, n_games, seed_offset=3_000_000):
    """P(learner shoots the named seat | a GANG_UP(seat) was just broadcast)
    with real messages vs scrambled message-tail. Instrumented via run_match
    with the learner in seat 0; counts decisions, not games."""
    real = {"hit": 0, "n": 0}
    scr = {"hit": 0, "n": 0}
    # Implementation note for the engineer: run_match already records SHOT + MESSAGE
    # events. For each game, replay rows: when a GANG_UP(t) message precedes the
    # learner's next SHOT, increment n; increment hit if that SHOT.target == t.
    # The 'scrambled' arm re-runs the same seeds with the learner's incoming message
    # obs permuted (a make_model_policy variant that shuffles the obs message tail).
    a_real = make_model_policy(_load(model_path))
    a_scr = make_model_policy(_load(model_path), scramble=True)  # see Step 3b
    for s in range(seed_offset, seed_offset + n_games):
        _tally(run_match(s, {0: a_real}, record=True)["rows"], real)
        _tally(run_match(s, {0: a_scr}, record=True)["rows"], scr)
    out = _two_prop(real["hit"], real["n"], scr["hit"], scr["n"])
    out.update(p_real=real["hit"] / max(real["n"], 1),
               p_scrambled=scr["hit"] / max(scr["n"], 1))
    return out
```

- [ ] **Step 3b: Add the supporting helpers**

Add `_load` (cached `MaskablePPO.load`), `_tally(rows, acc)` (scan `rows` for the GANG_UP→next-SHOT contingency described in the comment), and extend `make_model_policy` in `rl/policies.py` with an optional `scramble=False` that permutes `obs[-MSG_K*MSG_FEATURES:]` in fixed-size message blocks before `predict`. Keep all of it pure + seeded (use the game seed, not wall-clock).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONUTF8=1 ./.venv/Scripts/python -m pytest tests/test_comms_eval.py -q`
Expected: PASS (keys present; values may be noisy at n=40).

- [ ] **Step 5: Commit**

```bash
git add social_roulette/rl/comms_eval.py social_roulette/rl/policies.py tests/test_comms_eval.py
git commit -m "feat(comms): response-shift + win-rate ablation harness (primary/secondary metrics)"
```

---

### Task 10: Run the experiment + write results

**Files:**
- Create: `docs/stage3_results.md`

- [ ] **Step 1: Train comms self-play** (≥1 generation, warm-start from `stage3seed`, reusing `run_selfplay_parallel`):

```bash
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 ./.venv/Scripts/python -m social_roulette.rl.selfplay \
  --run-parallel --gens 1 --steps-per-gen 250000 --seed-model models/stage3seed --out models/stage3
```

- [ ] **Step 2: Measure** — primary then secondary:

```bash
PYTHONUTF8=1 ./.venv/Scripts/python -c "
from social_roulette.rl.comms_eval import response_shift, winrate_ablation
print('PRIMARY response-shift:', response_shift('models/stage3/gen1', n_games=1500))
print('SECONDARY win-rate ablation:', winrate_ablation('models/stage3/gen1', n_games=3000))
"
```

- [ ] **Step 3: Write `docs/stage3_results.md`** — report the response-shift (z, p) as PRIMARY and the win-rate ablation as SECONDARY, with the honest verdict: **used** (significant shift) or **null** (no shift — the expected cheap-talk outcome). Mirror `docs/stage2_results.md` structure. Note: a null here is a valid scientific result, not a failure.

- [ ] **Step 4: Commit**

```bash
git add docs/stage3_results.md && git commit -m "docs: Stage 3 comms results (used vs null verdict)"
```

---

## Self-Review

- **Spec coverage:** §1 channel→T2,T3; §2 turn integration→T3,T6; §3 hearing→T5; §4 minimal acts→T1; §5 rich set→paper (out of v1 scope, documented); §6 reward unchanged→Global Constraints; §7 metric (primary response-shift + secondary win-rate, n≥2500, asymmetric, scramble, seeds≥3e6)→T9,T10; §8 build sequence→T1-T10; §9 out-of-scope respected (no transformer, no full vocab, no trade mechanic). ✓
- **Placeholder scan:** Task 9 Step 3 leaves `_tally`/`_load`/`scramble` as described-not-shown — flagged as the one task needing the engineer to write the contingency scan from the spec'd rule; acceptable because the exact row-scan depends on T6's recorded event shape, which is fully specified. All other steps have complete code.
- **Type consistency:** `Speak(act, target, value)`, `Msg(turn, speaker, act, target, value)`, `MSG_CAP`, `SPEAK_N=15`, `ACTION_N=24+SPEAK_N`, `MSG_K=8`, `MSG_FEATURES=5`, `OBS_DIM=62+40=102` consistent across T1-T9. ✓

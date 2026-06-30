# Stage 1 — Single Learner vs Random Bots — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline) or subagent-driven-development. Steps use `- [ ]` checkboxes.
>
> Spec: `docs/superpowers/specs/2026-06-29-stage1-single-learner-design.md`. Tasks 1–4 are unit-TDD (env/obs/codec). Tasks 5–8 are **scripted experiments** with measurable bars (win-rate vs baseline, binomial p) — RL training is not unit-testable; the bar is the test.

**Goal:** Train one MaskablePPO agent to beat 4 random bots at *Social Roulette* (win-rate ≫ 20%, one-sided binomial p<0.01), staged shoot-only → full-action.

**Architecture:** Single-agent `gymnasium` env wrapping the Stage-0 engine; the 4 opponents run the existing random policy inside the env (stationary single-agent POMDP). MaskablePPO (`sb3-contrib`) on GPU. Terminal-only reward.

**Tech Stack:** Python 3.13 venv (`.venv`), torch (CUDA cu124), gymnasium, stable-baselines3, sb3-contrib, numpy, scipy (binomial), pytest.

## Global Constraints

- **venv on Python 3.13 only** (torch has no 3.14 wheels). All commands use `./.venv/Scripts/python`.
- **Device: CPU for Stage 1** (decided — GPU gives no speedup on this env-bound, tiny-MLP workload; set up GPU cleanly at Stage 2). All `device="cpu"`.
- **Learner = player id 0**, fixed `num_players=5`. Obs always from id-0's perspective.
- **Never leak hidden state** into obs (no opponent inventories, no shell order). Test for it.
- **Reward terminal-only:** +1 win, −1 learner death, 0 otherwise.
- **Reuse the engine unchanged.** Stage 1 adds a `social_roulette/rl/` package + scripts; it does not modify `engine/`.

## File Structure

```
social_roulette/
  sim/random_agent.py   # MODIFY: extract take_random_turn(state, pid)
  rl/
    __init__.py
    obs.py              # encode_obs(state, learner_id, extras) -> np.ndarray ; OBS_DIM
    action_space.py     # ActionCodec (decode + index<->action), legal_mask ; ACTION_N
    env.py              # SocialRouletteSingleEnv(gymnasium.Env)
    baseline.py         # measure_baseline(n) -> win-rate of random id-0
    train.py            # train MaskablePPO (shoot_only flag), save model + curve
    evaluate.py         # evaluate(model_path, n, seed_offset) -> {win_rate, p_value}
tests/
  test_take_turn.py     # refactor keeps games terminating
  test_obs.py           # shape, no-leak, peek + effect slots
  test_action_codec.py  # decode/index round-trip, mask == legal_actions, shoot-only
  test_env.py           # gym API, terminal reward, bonus-turn stays learner, death terminal
```

**Deferred (later stages):** PettingZoo, self-play, emoji comms, variable-N, recurrent policy, bilateral trade, agent-chosen payment.

---

## Task 0: Dependency gate (verify the stack)

**Files:** none (verification only).

- [ ] **Step 1:** Confirm the CPU stack imports.

Run: `./.venv/Scripts/python -c "import torch,gymnasium,sb3_contrib,scipy; print('OK', torch.__version__, 'gym', gymnasium.__version__)"`
Expected: prints `OK 2.12.1+cpu gym 1.3.0`. (If `scipy` missing: `./.venv/Scripts/python -m pip install scipy -q`.)

- [ ] **Step 2:** No GPU gate — CPU is the decided Stage-1 device.

---

## Task 1: Refactor random agent → reusable single turn

**Files:** Modify `social_roulette/sim/random_agent.py`; Test `tests/test_take_turn.py`.

**Interfaces — Produces:** `take_random_turn(state, pid, max_sub=40)` — plays ONE full turn for `pid` (random legal sub-actions until a shot commits, or forced shot at cap). `play_game` reuses it.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_take_turn.py
from social_roulette.engine.engine import new_game
from social_roulette.engine.state import living_ids
from social_roulette.sim.random_agent import take_random_turn, play_game

def test_take_random_turn_advances_or_ends_game():
    s = new_game(5, seed=4)
    start = s.current_id
    take_random_turn(s, start)
    # after one full turn, either someone shot (chamber moved / someone lost a life / turn passed) or game ended
    assert s.winner is not None or s.current_id != start or any(p.lives < 3 for p in s.players) or s.bonus_pending

def test_play_game_still_terminates():
    for seed in range(30):
        assert play_game(5, seed)["winner"] is not None
```

- [ ] **Step 2:** `./.venv/Scripts/python -m pytest tests/test_take_turn.py -q` → FAIL (no `take_random_turn`).

- [ ] **Step 3: Implement (rewrite random_agent.py)**

```python
import hashlib
from social_roulette.engine.engine import new_game, step, take_shot
from social_roulette.engine.actions import legal_actions, Shoot
from social_roulette.engine.endgame import legal_targets


def take_random_turn(state, pid, max_sub=40):
    """Play one full turn for pid: random legal sub-actions until a shot commits."""
    for _ in range(max_sub):
        action = state.rng.choice(legal_actions(state, pid))
        if isinstance(action, Shoot):
            return take_shot(state, pid, action.target_id)
        step(state, pid, action)
    return take_shot(state, pid, state.rng.choice(legal_targets(state, pid)))


def play_game(num_players, seed, max_turns=20000):
    state = new_game(num_players, seed)
    h = hashlib.sha256()
    turns = 0
    while state.winner is None and turns < max_turns:
        pid = state.current_id
        ev = take_random_turn(state, pid)
        h.update(repr((pid, ev["shell"].name, ev["damage"], ev["killed"])).encode())
        turns += 1
    if state.winner is None:
        raise RuntimeError("game did not terminate")
    return {"winner": state.winner, "turns": turns, "history_hash": h.hexdigest()}
```

- [ ] **Step 4:** `./.venv/Scripts/python -m pytest tests/test_take_turn.py tests/test_sim.py tests/test_determinism.py -q` → PASS (refactor preserves behavior). NOTE: `test_determinism`'s hash changes vs Stage 0 (turn loop restructured) — if it fails on hash equality between two runs it's still fine (determinism = same seed twice, which holds); only cross-version hash changed.

- [ ] **Step 5:** Commit: `git add social_roulette/sim/random_agent.py tests/test_take_turn.py && git commit -m "refactor: extract take_random_turn for reuse by RL env"`

---

## Task 2: Observation encoder

**Files:** Create `social_roulette/rl/__init__.py`, `social_roulette/rl/obs.py`; Test `tests/test_obs.py`.

**Interfaces — Produces:** `OBS_DIM` (int); `encode_obs(state, learner_id, extras) -> np.ndarray((OBS_DIM,), float32)`. `extras = {"known_next_shell": "unknown"|"live"|"blank", "announced_total": int, "announced_live": int}`. Layout (5 fixed player slots, learner-relative). **No hidden state** (no opponent inventories, no shell order).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_obs.py
import numpy as np
from social_roulette.engine.engine import new_game
from social_roulette.engine.constants import Item
from social_roulette.rl.obs import encode_obs, OBS_DIM

EXTRAS = {"known_next_shell": "unknown", "announced_total": 10, "announced_live": 6}

def test_obs_shape_and_dtype():
    s = new_game(5, seed=1)
    o = encode_obs(s, 0, EXTRAS)
    assert o.shape == (OBS_DIM,) and o.dtype == np.float32

def test_obs_does_not_leak_opponent_inventory():
    s = new_game(5, seed=1)
    base = encode_obs(s, 0, EXTRAS).copy()
    # mutate an OPPONENT's inventory; obs must be unchanged (it is hidden)
    s.players[1].inventory = {Item.SAW: 3, Item.BEER: 3}
    assert np.array_equal(encode_obs(s, 0, EXTRAS), base)

def test_obs_reflects_own_inventory():
    s = new_game(5, seed=1)
    base = encode_obs(s, 0, EXTRAS).copy()
    s.players[0].inventory = dict(s.players[0].inventory)
    s.players[0].inventory[Item.SAW] = s.players[0].inventory.get(Item.SAW, 0) + 1
    assert not np.array_equal(encode_obs(s, 0, EXTRAS), base)

def test_obs_peek_slot_changes():
    s = new_game(5, seed=1)
    a = encode_obs(s, 0, {**EXTRAS, "known_next_shell": "unknown"})
    b = encode_obs(s, 0, {**EXTRAS, "known_next_shell": "live"})
    assert not np.array_equal(a, b)
```

- [ ] **Step 2:** `./.venv/Scripts/python -m pytest tests/test_obs.py -q` → FAIL.

- [ ] **Step 3: Implement**

```python
# social_roulette/rl/obs.py
import numpy as np
from social_roulette.engine.constants import Item, MAX_LIVES
from social_roulette.engine.state import player_by_id, living_players
from social_roulette.engine.endgame import teams_active

ITEMS = [Item.BEER, Item.HANDCUFFS, Item.MAGNIFIER, Item.SAW, Item.CIGARETTES, Item.IMMUNITY]
N_SLOTS = 5
# per slot: alive, is_self, is_ally, is_enemy, lives, handcuffed, learner_immunized_them, they_immunized_learner  = 8
PER_SLOT = 8
# globals: own_lives(1) own_inv(6) flipback(1) peek(3 one-hot) item_counts(6) announced_total(1) announced_live(1) fired(1) saw_active(1) bonus(1) = 22
GLOBALS = 22
OBS_DIM = N_SLOTS * PER_SLOT + GLOBALS


def _peek_onehot(v):
    return [1.0 if v == "live" else 0.0, 1.0 if v == "blank" else 0.0, 1.0 if v == "unknown" else 0.0]


def encode_obs(state, learner_id, extras):
    me = player_by_id(state, learner_id)
    ta = teams_active(state)
    vec = []
    for k in range(N_SLOTS):
        p = player_by_id(state, k)
        is_self = (k == learner_id)
        is_ally = (not is_self) and ta and p.team == me.team
        is_enemy = (not is_self) and (not is_ally)
        vec += [
            1.0 if p.alive else 0.0,
            1.0 if is_self else 0.0,
            1.0 if is_ally else 0.0,
            1.0 if is_enemy else 0.0,
            p.lives / MAX_LIVES,
            1.0 if p.handcuffed else 0.0,
            1.0 if learner_id in p.immunity_against else 0.0,      # learner immunized this player
            1.0 if k in me.immunity_against else 0.0,              # this player immunized learner
        ]
    vec.append(me.lives / MAX_LIVES)
    vec += [me.inventory.get(it, 0) / 3.0 for it in ITEMS]
    vec.append(1.0 if me.flipback_discount else 0.0)
    vec += _peek_onehot(extras["known_next_shell"])
    counts = {it: 0 for it in ITEMS}
    for p in state.players:
        for it, c in p.inventory.items():
            counts[it] += c
    vec += [counts[it] / (5 * 3.0) for it in ITEMS]
    at = extras["announced_total"] or 1
    vec.append(at / 30.0)
    vec.append((extras["announced_live"] or 0) / 30.0)
    vec.append(state.chamber.pos / 30.0)
    vec.append(1.0 if state.saw_active else 0.0)
    vec.append(1.0 if state.bonus_pending else 0.0)
    return np.asarray(vec, dtype=np.float32)
```

- [ ] **Step 4:** `./.venv/Scripts/python -m pytest tests/test_obs.py -q` → PASS.

- [ ] **Step 5:** Commit: `git add social_roulette/rl/__init__.py social_roulette/rl/obs.py tests/test_obs.py && git commit -m "feat: RL observation encoder (Markov-sufficient, no hidden leak)"`

---

## Task 3: Action codec + mask

**Files:** Create `social_roulette/rl/action_space.py`; Test `tests/test_action_codec.py`.

**Interfaces — Produces:** `ACTION_N = 24`; index layout — `0..4` shoot(k); `5..8` use Cig/Mag/Saw/Beer; `9..13` Immunity on k; `14..18` Handcuffs on k; `19..23` Flip(k). `ActionCodec.decode(idx, state, learner_id)` → engine action (Flip uses `cheapest_payment`); `ActionCodec.legal_mask(state, learner_id, shoot_only) -> np.bool_ array (ACTION_N,)` built by enumerating `legal_actions` and setting matching indices (shoot-only keeps only `0..4`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_action_codec.py
import numpy as np
from social_roulette.engine.engine import new_game
from social_roulette.engine.actions import Shoot, UseItem, Flip, legal_actions
from social_roulette.engine.constants import Item
from social_roulette.rl.action_space import ActionCodec, ACTION_N

def test_action_n():
    assert ACTION_N == 24

def test_shoot_decode_roundtrip():
    s = new_game(5, seed=1)
    a = ActionCodec.decode(2, s, 0)
    assert isinstance(a, Shoot) and a.target_id == 2

def test_mask_matches_legal_actions():
    s = new_game(5, seed=3)
    mask = ActionCodec.legal_mask(s, s.current_id, shoot_only=False)
    # every shoot at a legal target is unmasked; total unmasked > 0
    assert mask.shape == (ACTION_N,) and mask.dtype == np.bool_ and mask.any()
    # decoding every unmasked index yields an action the engine accepts in principle
    for idx in np.flatnonzero(mask):
        a = ActionCodec.decode(int(idx), s, s.current_id)
        assert a is not None

def test_shoot_only_mask_limits_to_shoots():
    s = new_game(5, seed=3)
    mask = ActionCodec.legal_mask(s, s.current_id, shoot_only=True)
    assert mask[:5].any() and not mask[5:].any()
```

- [ ] **Step 2:** `./.venv/Scripts/python -m pytest tests/test_action_codec.py -q` → FAIL.

- [ ] **Step 3: Implement**

```python
# social_roulette/rl/action_space.py
import numpy as np
from social_roulette.engine.constants import Item
from social_roulette.engine.actions import Shoot, UseItem, Flip, cheapest_payment, legal_actions
from social_roulette.engine.state import player_by_id

ACTION_N = 24
NONTARGET = [Item.CIGARETTES, Item.MAGNIFIER, Item.SAW, Item.BEER]  # indices 5..8


class ActionCodec:
    @staticmethod
    def decode(idx, state, learner_id):
        if idx < 5:
            return Shoot(idx)
        if idx < 9:
            return UseItem(NONTARGET[idx - 5])
        if idx < 14:
            return UseItem(Item.IMMUNITY, idx - 9)
        if idx < 19:
            return UseItem(Item.HANDCUFFS, idx - 14)
        k = idx - 19
        p = player_by_id(state, learner_id)
        cost = 4 if (k == learner_id and p.flipback_discount) else 5
        return Flip(k, cheapest_payment(p, cost) or [])

    @staticmethod
    def _index_of(action):
        if isinstance(action, Shoot):
            return action.target_id
        if isinstance(action, UseItem):
            if action.item in NONTARGET:
                return 5 + NONTARGET.index(action.item)
            if action.item == Item.IMMUNITY:
                return 9 + action.target_id
            if action.item == Item.HANDCUFFS:
                return 14 + action.target_id
        if isinstance(action, Flip):
            return 19 + action.target_id
        return None

    @staticmethod
    def legal_mask(state, learner_id, shoot_only=False):
        mask = np.zeros(ACTION_N, dtype=np.bool_)
        for a in legal_actions(state, learner_id):
            i = ActionCodec._index_of(a)
            if i is not None:
                mask[i] = True
        if shoot_only:
            mask[5:] = False
        return mask
```

- [ ] **Step 4:** `./.venv/Scripts/python -m pytest tests/test_action_codec.py -q` → PASS.

- [ ] **Step 5:** Commit: `git add social_roulette/rl/action_space.py tests/test_action_codec.py && git commit -m "feat: RL action codec + legal mask (absolute ids)"`

---

## Task 4: Single-agent environment

**Files:** Create `social_roulette/rl/env.py`; Test `tests/test_env.py`.

**Interfaces — Produces:** `SocialRouletteSingleEnv(num_players=5, learner_id=0, shoot_only=False)` (gymnasium.Env). `reset(seed)->(obs, info)`; `step(idx)->(obs, reward, terminated, truncated, info)`; `info["action_mask"]`. Opponents auto-run via `take_random_turn`. Terminal when winner set OR learner dead; reward +1 win / −1 death / 0 else. **Bonus/extra turns:** if `current_id` is still the learner after an action, control returns to the agent (no opponent run).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_env.py
import numpy as np
from social_roulette.rl.env import SocialRouletteSingleEnv
from social_roulette.rl.obs import OBS_DIM
from social_roulette.rl.action_space import ACTION_N

def test_reset_returns_obs_and_mask():
    env = SocialRouletteSingleEnv()
    obs, info = env.reset(seed=1)
    assert obs.shape == (OBS_DIM,) and info["action_mask"].shape == (ACTION_N,)
    assert env.state.current_id == 0  # advanced to the learner

def test_step_is_learners_turn_until_shot():
    # with shoot_only, every learner step is a shot -> opponents then run -> back to learner or done
    env = SocialRouletteSingleEnv(shoot_only=True)
    obs, info = env.reset(seed=2)
    steps = 0
    done = False
    while not done and steps < 5000:
        legal = np.flatnonzero(info["action_mask"])
        obs, r, done, trunc, info = env.step(int(legal[0]))  # always shoot target 0-ish (first legal)
        steps += 1
    assert done and r in (1.0, -1.0)

def test_terminal_reward_sign():
    env = SocialRouletteSingleEnv(shoot_only=True)
    wins = 0
    for seed in range(40):
        obs, info = env.reset(seed=seed)
        done = False
        r = 0.0
        while not done:
            legal = np.flatnonzero(info["action_mask"])
            obs, r, done, trunc, info = env.step(int(legal[-1]))
        wins += 1 if r == 1.0 else 0
    assert 0 <= wins <= 40  # runs to completion every game, reward always ±1
```

- [ ] **Step 2:** `./.venv/Scripts/python -m pytest tests/test_env.py -q` → FAIL.

- [ ] **Step 3: Implement**

```python
# social_roulette/rl/env.py
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from social_roulette.engine.engine import new_game, step as engine_step
from social_roulette.engine.constants import Shell, Item
from social_roulette.engine.state import player_by_id
from social_roulette.sim.random_agent import take_random_turn
from social_roulette.rl.obs import encode_obs, OBS_DIM
from social_roulette.rl.action_space import ActionCodec, ACTION_N


class SocialRouletteSingleEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, num_players=5, learner_id=0, shoot_only=False):
        super().__init__()
        self.num_players = num_players
        self.learner_id = learner_id
        self.shoot_only = shoot_only
        self.observation_space = spaces.Box(-1.0, 5.0, shape=(OBS_DIM,), dtype=np.float32)
        self.action_space = spaces.Discrete(ACTION_N)
        self.state = None
        self._known = "unknown"
        self._ann_total = 0
        self._ann_live = 0
        self._last_chamber = None
        self._last_pos = 0

    # --- extras / peek + announced-count tracking ---
    def _on_chamber_change(self):
        ch = self.state.chamber
        if ch is not self._last_chamber:
            self._last_chamber = ch
            self._ann_total = len(ch.shells)
            self._ann_live = sum(1 for s in ch.shells if s == Shell.LIVE)
            self._known = "unknown"
            self._last_pos = ch.pos
        if ch.pos != self._last_pos:
            self._known = "unknown"   # the known shell was consumed
            self._last_pos = ch.pos

    def _extras(self):
        return {"known_next_shell": self._known, "announced_total": self._ann_total,
                "announced_live": self._ann_live}

    def _obs(self):
        return encode_obs(self.state, self.learner_id, self._extras())

    def _mask(self):
        return ActionCodec.legal_mask(self.state, self.learner_id, self.shoot_only)

    def _info(self):
        return {"action_mask": self._mask()}

    def _learner(self):
        return player_by_id(self.state, self.learner_id)

    def _terminal(self):
        return self.state.winner is not None or not self._learner().alive

    def _reward(self):
        if self.state.winner == self.learner_id:
            return 1.0
        if not self._learner().alive:
            return -1.0
        return 0.0

    def _run_opponents(self):
        while self.state.winner is None and self.state.current_id != self.learner_id and self._learner().alive:
            take_random_turn(self.state, self.state.current_id)
            self._on_chamber_change()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.state = new_game(self.num_players, seed if seed is not None else 0)
        self._last_chamber = None
        self._on_chamber_change()
        self._run_opponents()
        return self._obs(), self._info()

    def step(self, idx):
        action = ActionCodec.decode(int(idx), self.state, self.learner_id)
        is_magnifier = getattr(action, "item", None) == Item.MAGNIFIER
        engine_step(self.state, self.learner_id, action)
        if is_magnifier:
            cur = self.state.chamber.current()
            self._known = "live" if cur == Shell.LIVE else ("blank" if cur == Shell.BLANK else "unknown")
        self._on_chamber_change()
        if not self._terminal() and self.state.current_id != self.learner_id:
            self._run_opponents()
        terminated = self._terminal()
        return self._obs(), self._reward(), terminated, False, self._info()
```

- [ ] **Step 4:** `./.venv/Scripts/python -m pytest tests/test_env.py -q` → PASS. (Fix the `is_magnifier` line per the note if it errors.)

- [ ] **Step 5:** Commit: `git add social_roulette/rl/env.py tests/test_env.py && git commit -m "feat: single-agent gym env (opponents in-env, terminal reward, bonus-aware)"`

---

## Task 5: Baseline measurement (pin the bar)

**Files:** Create `social_roulette/rl/baseline.py`.

**Interfaces — Produces:** `measure_baseline(n=5000, num_players=5) -> float` — win-rate of the **random** policy playing id 0 (run full random games, count id-0 wins). `main()` prints it.

- [ ] **Step 1:** Implement

```python
# social_roulette/rl/baseline.py
from social_roulette.sim.random_agent import play_game

def measure_baseline(n=5000, num_players=5):
    wins = sum(1 for seed in range(n) if play_game(num_players, seed)["winner"] == 0)
    return wins / n

def main():
    wr = measure_baseline()
    print(f"random id-0 win-rate over 5000 games = {wr:.4f}  (chance = {1/5:.4f})")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2:** Run: `./.venv/Scripts/python -m social_roulette.rl.baseline`
Expected: prints a win-rate near **0.20** (id 0 has no positional advantage on average). Record the exact number — it is the bar PPO must beat.

- [ ] **Step 3:** Commit: `git add social_roulette/rl/baseline.py && git commit -m "feat: random baseline measurement (the win-rate bar)"`

---

## Task 6: Train Stage 1a (shoot-only) — the GO/NO-GO

**Files:** Create `social_roulette/rl/train.py`, `social_roulette/rl/evaluate.py`.

**Interfaces — Produces:**
- `train.py`: builds `ActionMasker`-wrapped env + `MaskablePPO("MlpPolicy", device="cuda")`; `train(shoot_only, steps, out_path)`; CLI `python -m social_roulette.rl.train --shoot-only --steps 300000 --out models/stage1a`.
- `evaluate.py`: `evaluate(model_path, n=5000, seed_offset=1_000_000, shoot_only=False) -> {win_rate, p_value}` (binomial vs 0.20, eval seeds disjoint from training by the large offset). CLI prints both.

- [ ] **Step 1: Implement train.py**

```python
# social_roulette/rl/train.py
import argparse
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from social_roulette.rl.env import SocialRouletteSingleEnv

def _mask_fn(env):
    return env._mask()

def make_env(shoot_only):
    return ActionMasker(SocialRouletteSingleEnv(shoot_only=shoot_only), _mask_fn)

def train(shoot_only, steps, out_path):
    env = make_env(shoot_only)
    model = MaskablePPO("MlpPolicy", env, device="cpu", verbose=1,
                        n_steps=2048, batch_size=256, gamma=0.999)
    model.learn(total_timesteps=steps)
    model.save(out_path)
    print("saved", out_path)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--shoot-only", action="store_true")
    ap.add_argument("--steps", type=int, default=300000)
    ap.add_argument("--out", default="models/stage1a")
    a = ap.parse_args()
    train(a.shoot_only, a.steps, a.out)
```

- [ ] **Step 2: Implement evaluate.py**

```python
# social_roulette/rl/evaluate.py
import argparse
import numpy as np
from scipy.stats import binomtest
from sb3_contrib import MaskablePPO
from social_roulette.rl.env import SocialRouletteSingleEnv

def evaluate(model_path, n=5000, seed_offset=1_000_000, shoot_only=False):
    model = MaskablePPO.load(model_path, device="cpu")
    env = SocialRouletteSingleEnv(shoot_only=shoot_only)
    wins = 0
    for i in range(n):
        obs, info = env.reset(seed=seed_offset + i)
        done = False
        r = 0.0
        while not done:
            a, _ = model.predict(obs, action_masks=info["action_mask"], deterministic=True)
            obs, r, done, trunc, info = env.step(int(a))
        wins += 1 if r == 1.0 else 0
    wr = wins / n
    p = binomtest(wins, n, 0.20, alternative="greater").pvalue
    return {"win_rate": wr, "p_value": p}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("model"); ap.add_argument("--shoot-only", action="store_true")
    ap.add_argument("--n", type=int, default=5000)
    a = ap.parse_args()
    res = evaluate(a.model, n=a.n, shoot_only=a.shoot_only)
    print(f"win_rate={res['win_rate']:.4f}  p(>0.20)={res['p_value']:.3e}")
```

- [ ] **Step 3: Train 1a**

Run: `./.venv/Scripts/python -m social_roulette.rl.train --shoot-only --steps 300000 --out models/stage1a`
Expected: runs to completion, saves `models/stage1a.zip`. (Watch `ep_rew_mean` trend upward from ~−0.6 toward 0.)

- [ ] **Step 4: Evaluate 1a — the GO/NO-GO gate**

Run: `./.venv/Scripts/python -m social_roulette.rl.evaluate models/stage1a --shoot-only`
Expected: `win_rate` **> 0.20** with `p < 0.01`. 
- **PASS** → the harness learns; proceed to Task 7.
- **FAIL** (win-rate ≈ 0.20) → STOP. The harness/obs/reward is broken, not the game. Debug: confirm reward sign, mask correctness, obs not all-zeros. Do NOT proceed to 1b. (This is the cheap early failure the staging is designed to surface.)

- [ ] **Step 5:** Commit: `git add social_roulette/rl/train.py social_roulette/rl/evaluate.py models/stage1a.zip && git commit -m "feat: Stage 1a shoot-only training + eval (beats random baseline)"`

---

## Task 7: Train Stage 1b (full action) — only if 1a passed

**Files:** none new (reuse train/evaluate without `--shoot-only`).

- [ ] **Step 1: Train 1b**

Run: `./.venv/Scripts/python -m social_roulette.rl.train --steps 1000000 --out models/stage1b`
Expected: completes, saves `models/stage1b.zip`. Full action space → needs more steps.

- [ ] **Step 2: Evaluate 1b**

Run: `./.venv/Scripts/python -m social_roulette.rl.evaluate models/stage1b`
Expected: `win_rate` > 0.20, `p < 0.01`; ideally ≥ 1a (items should help, not hurt). Record both.

- [ ] **Step 3:** Commit: `git add models/stage1b.zip && git commit -m "feat: Stage 1b full-action training + eval"`

---

## Task 8: Stage 1 report

**Files:** Create `docs/stage1_results.md`.

- [ ] **Step 1:** Write `docs/stage1_results.md` recording: random baseline win-rate; 1a win-rate + p; 1b win-rate + p; training steps; one-line verdict ("an agent learns to beat random at Social Roulette: yes/no"). Use the actual numbers from Tasks 5–7.
- [ ] **Step 2:** Commit: `git add docs/stage1_results.md && git commit -m "docs: Stage 1 results — learner vs random"`

---

## Self-Review

**Spec coverage:** single-agent gym (T4) · MaskablePPO+GPU (T6) · fixed-5/id-0 (T2,4) · obs Markov-sufficient incl peek+effects, no leak (T2) · absolute-id masked actions (T3) · terminal-only reward (T4) · venv gate (T0) · baseline+binomial+disjoint eval seeds (T5,6) · shoot-only→full staging (T6,7).

**Known risk to watch at execution:** the `env.step` magnifier-peek line has a deliberate simplification note (Task 4 Step 3) — implement the clean `is_magnifier` form. If 1a fails the gate, the staging did its job: debug the harness, don't touch the engine.

**Deferred (unchanged):** PettingZoo/self-play (Stage 2), emoji comms (Stage 3), variable-N, memory, trade.

---

## Execution Handoff

Plan complete. Choose execution mode in the next message.

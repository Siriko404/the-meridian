# Stage 1 — Single Learner vs Random Bots — Design

**Date:** 2026-06-29
**Goal:** Prove ONE RL agent can learn to play *Social Roulette* well enough to beat 4 random bots — win-rate ≫ the 20% random baseline, statistically significant, with a rising learning curve. This is the cheapest, most debuggable "does it learn at all" test, and it directly attacks the audit's #1 risk (undebuggable slow loop).

**Not in scope:** self-play, emoji comms, variable player count, recurrent/transformer policy, bilateral trade, agent choosing *how* to pay (env auto-pays). All deferred to later stages.

---

## 1. Framing — single-agent, not multi-agent

The 4 opponents run the **fixed Stage-0 random policy**, baked into the environment. That makes the env a **stationary single-agent POMDP** — no self-play, no non-stationarity. So:

- **Stack:** `gymnasium` env + **MaskablePPO** (`sb3-contrib`) + `torch` (CPU). **No PettingZoo** (that is Stage 2 self-play).
- **Fixed 5 players.** Learner is the player with **id 0** (its seat in turn order is still randomized by `new_game`). Obs is always from id-0's perspective.
- **Memoryless (feedforward) policy is sufficient** — provided the observation is Markov-sufficient (see §4). Random opponents need no opponent-modeling, which is *why* memory can be deferred.

---

## 2. Hard gate (do BEFORE any RL code)

- The machine has **both Python 3.13.5 and 3.14.2**. `torch` has **no 3.14 wheels**.
- Create a venv from **3.13**: `py -3.13 -m venv .venv`; activate; `pip install torch gymnasium stable-baselines3 sb3-contrib`.
- Verify `python -c "import torch, gymnasium, sb3_contrib; print('ok')"` **succeeds** before writing the env. If it fails, stop and resolve — the whole approach depends on it.
- Use the venv, never global site-packages (Program Files perms already bit us in Stage 0).

---

## 3. Staging (de-risk the plumbing)

- **Stage 1a — shoot-only action head.** The learner may only `shoot(target)`; it holds items but cannot use them. Opponents still play the **full** game (the engine is untouched — only the learner's action head is restricted). Tiny action space → if PPO can't beat random here, the *harness* is broken and we learn it in minutes.
- **Stage 1b — full action head.** Unlock items/flips (with masking). Only attempt after 1a beats random.

The engine stays full and fully tested; staging restricts only what the *learner* may emit.

---

## 4. Observation (filtered, Markov-sufficient, fixed-length float vector)

Public + own-private only. **Never** include hidden state (shell order, opponents' inventories).

Per the learner (id 0):
- Own **lives** (norm), own **inventory** counts per item type (6 floats).
- **Magnifier peek slot:** the revealed value of the next shell if currently known (set on peek, cleared when that shell is fired/Beer'd), else "unknown". *(Without this, Magnifier is unlearnable.)*
- Own **active effects:** set of players it has cuffed / immunized; who has cuffed / immunized it; its **flip-back-discount** flag.
- Per player slot (5 fixed, padded): **alive, team (relative: ally/enemy/self), lives** (norm).
- **Item-type counts in play** (6 floats) — public.
- **Announced chamber counts** (total + live at last load) and **shells fired since load** — the public "track from memory" signal. `saw_active`, `bonus_pending` flags.

Encoded as one fixed-size `Box`. (Fixed 5 players ⇒ fixed length; variable-N deferred.)

---

## 5. Action space — flat discrete, absolute ids, masked

Fixed index space (absolute player ids 0..4):
- `shoot(k)` for k in 0..4 (includes self).
- `use(item)` non-targeted: Cigarettes, Magnifier, Saw, Beer.
- `use(item, k)` targeted: Immunity / Handcuffs on k in 0..4.
- `flip(k)` for k in 0..4 — **env auto-selects `cheapest_payment`** (agent chooses *whom*, not *how to pay* — a deliberate economic-expressiveness cut for Stage 1).
- `end_turn` is implicit: the turn ends when the agent emits `shoot(...)` (mandatory shot).

Each step the env supplies an **action mask** from the engine's `legal_actions` (mapped to this index space). MaskablePPO consumes it. Illegal indices (dead targets, capped items, unaffordable flips) are masked — dead-player actions retire cleanly because indices are absolute.

**Stage 1a** masks everything except `shoot(k)`.

---

## 6. Env dynamics (`SocialRouletteSingleEnv`)

- `reset(seed)` → `new_game(5, seed)`; then **auto-run** opponents' random turns until it is id-0's decision (or game over). Return obs + mask.
- `step(action_index)` → decode to engine action; apply via engine `step`. If it was a shot (turn ends), **auto-run** opponents' random turns until id-0's next decision or terminal. Return obs, reward, terminated, mask.
- Opponents use the **existing Stage-0 full random agent**.

---

## 7. Reward — terminal-only

- **+1** if id 0 wins, **−1** if id 0 is eliminated, **0** otherwise (per env-step).
- **No per-step shaping** — a per-step survival term gets farmed (agent spams sub-actions) and silently outweighs the win signal over long episodes. Add shaping later only if it won't learn, and key it to **game-turns survived / finishing position**, never env-steps.
- Episodic, γ near 1.

---

## 8. Success metric (pin BEFORE training — it is the deliverable)

- First, **measure the control:** run the Stage-0 random agent as id 0 over **N = 5000** games → confirm ~20% win-rate. That is the bar.
- **Train**, then evaluate on **eval seeds disjoint from training seeds** over N games.
- **Pass = win-rate significantly above 20%** (one-sided binomial test, p < 0.01) AND a rising training curve.
- Report the learning curve (win-rate vs training steps).

---

## 9. Determinism

Stage 0's single-RNG bit-exact replay will **not** survive torch. Seed torch + numpy + env; accept residual nondeterminism. Don't chase bit-exact replay in Stage 1.

---

## 10. Risks (designed-for)

- High variance (random opponents × dice × shuffle) → needs more samples; env is fast (µs/game) so CPU is fine.
- If 1a can't beat random → harness bug, caught early (the point of 1a).
- Obs completeness is the correctness crux — §4 must be Markov-sufficient or items stay unlearnable.

# Stage 1 Results — Single Learner vs Random Bots

**Date:** 2026-06-30
**Question:** Can one RL agent learn to play *Social Roulette* well enough to beat 4 random opponents — and is the result *real play*, not a bug or an exploit?
**Answer:** Yes, decisively, and yes — validated by trajectory inspection.

---

## 1. Headline

5 players · learner = seat id 0 · 4 random opponents · evaluation over **n = 5000** games on **eval seeds disjoint from training** · deterministic policy · one-sided binomial test vs the 0.20 null.

| Policy | Win-rate | Wins/n | vs baseline | p( > 0.20 ) |
|---|---|---|---|---|
| Random (baseline) | **0.1934** | 967/5000* | — (≈ chance 0.20) | — |
| **1a — shoot-only** | **0.4694** | 2347/5000 | **2.4×** | ≈ 0 |
| **1b — full action** | **0.7436** | 3718/5000 | **3.8×** | ≈ 0 |

\* baseline measured separately over its own 5000 games (`baseline.py`).

Full action space (items + flips + placements) lifts the agent from 0.47 → 0.74 — **+27 points (≈1.6×)** over shoot-only. The game's item/economy layer carries large, learnable value.

---

## 2. What was built

- **Framing — single-agent, not multi-agent.** The 4 opponents run the fixed Stage-0 random policy, baked *into* the environment. That makes it a stationary single-agent POMDP (no self-play yet), so a standard `gymnasium` env + PPO suffices.
- **Algorithm:** MaskablePPO (`sb3-contrib`), `MlpPolicy`, CPU.
- **Reward:** terminal-only — **+1 win / −1 death / 0 otherwise** (no per-step shaping, which would be farmable).
- **Observation:** fixed-length, Markov-sufficient, **hides who-holds-what** (only own inventory + public per-type counts are visible). Includes the Magnifier peek slot and own active effects, so a memoryless policy is sufficient.
- **Action space:** flat `Discrete(24)`, indexed by **absolute** player id, with a legal-action **mask** (dead targets / capped items / unaffordable flips are masked). The agent chooses *whom* to flip; the env auto-pays the cheapest items.
- **Staging:** **1a** restricts only the learner's *action head* to `shoot(k)` (the engine stays full and fully tested); **1b** unlocks the full head. This isolates "is the PPO plumbing correct?" from "can it handle the full action space?" — a deliberate de-risking of the audit's #1 "undebuggable loop" concern.

---

## 3. Method & configuration

| Item | Value |
|---|---|
| Players | 5 (learner = id 0) |
| Opponents | fixed Stage-0 random policy (in-env) |
| PPO | n_steps 2048 · batch 256 · gamma 0.999 · seed 0 |
| Training steps | 1a: 300k · 1b: 1,000,000 |
| Eval | deterministic policy · seeds [1,000,000 … 1,005,000) · n 5000 |
| Train seeds | drawn `< 1,000,000` → **guaranteed disjoint** from eval |
| Significance | one-sided binomial vs p₀ = 0.20 |

Repro:
```
python -m social_roulette.rl.baseline
python -m social_roulette.rl.train --shoot-only --steps 300000 --out models/stage1a
python -m social_roulette.rl.evaluate models/stage1a --shoot-only
python -m social_roulette.rl.train --steps 1000000 --out models/stage1b
python -m social_roulette.rl.evaluate models/stage1b
```

---

## 4. Results in detail

- **Baseline 0.1934.** Seat id 0 has no positional advantage — the game is ≈ symmetric across seats, so the bar is chance (0.20). Confirms the eval is honest (the agent must beat 0.20, not a lower number).
- **1a shoot-only 0.4694** (2347/5000), p ≈ 0. Learning is **fast and shallow**: a 3,000-step model already scored ≈ 0.457 (on a noisier n = 300 check), and 300k steps moved it only to 0.469. Shoot-only is a simple control problem — basically "shoot enemies, pick good self-shot odds" — so it saturates quickly.
- **1b full action 0.7436** (3718/5000), p ≈ 0. The jump from 1a shows the agent learns to *use the toolkit* — heal, saw, beer away live shells, handcuff/flip enemies — not just aim.

---

## 5. Behavioral validation — is it *real play*?

A scalar win-rate can hide **reward hacking** (winning via an unintended shortcut) or a **sim bug** (games ending degenerately). We checked by recording full match **trajectories** (the `observe/` engine) and inspecting them.

**Games run at full.** Over 200 random games: length **15–44 turns** (mean 25.7), and **every mechanic fires** across games:

| mechanic | % of games | mechanic | % of games |
|---|---|---|---|
| self-shot | 100% | flip | 100% |
| Saw | 57.5% | elimination | 100% |
| Beer | 80.0% | reload (empty) | 60.5% |
| Immunity | 79.0% | reload (death) | 100% |
| Handcuffs | 91.0% | bonus turn | 98.0% |

No degenerate 2-turn exits; no dead systems. The trained agent's games show the same mechanic richness.

**The agent plays sanely; the bots self-destruct.** Sample (seed 2001, agent = s0, won):
```
T000  s0 (R ♥♥♥)  uses CIGARETTES (heal)  SHOOTS s2: LIVE -1     <- heal, then hit an enemy
...
T007  s0 (R ♥♥♥♥) SHOOTS s2: BLANK click                        <- agent healed up to 4 lives
T009  s3 (B ♥♥♥)  SHOOTS SELF: LIVE -1                           <- random bot self-harms
T010  s1 (R ♥♥♥)  SHOOTS SELF: LIVE -1                           <- random bot self-harms
```
The agent heals when low and fires at enemies; random opponents waste flips every turn and shoot *themselves* with live shells. **No reward-hacking or exploit was observed** — the agent simply behaves sensibly where random play does not.

---

## 6. Threats to validity (honest limits)

- **Opponents are random (weak).** 0.74 *vs random* is not "skilled vs competent." A meaningful fraction of the edge comes from opponents **self-harming** (directly visible in traces), not from agent brilliance alone. Only **Stage 2 (self-play vs competent copies)** tests real skill.
- **Single training run per stage** (seed 0). Win-rates are point estimates of one run; the eval confidence interval is tight (±~0.012 at 0.74, n=5000), but **training-seed variance was not measured**.
- **CPU only.** GPU was deferred — it gives no speedup on this env-bound, small-MLP workload (it will matter at Stage 2).
- **Determinism:** the *engine* is bit-exact reproducible; *PPO training* is not (torch). Eval is deterministic given a model.

---

## 7. What this does and does not prove

- **Does:** the full harness is correct end-to-end — env, observation, action masking, reward, and PPO all wire up, and an agent **learns the game's mechanics and beats random decisively**. The audit's top risk ("undebuggable slow loop") is retired: learning is fast, legible, and trajectory-verified.
- **Does not:** that the agent is a *strong or general* player. That claim requires competent opponents.

---

## 8. Artifacts

- Models: `models/stage1a.zip`, `models/stage1b.zip`
- Code: `social_roulette/rl/` (`env`, `obs`, `action_space`, `train`, `evaluate`, `baseline`); `social_roulette/observe/` (event-sourced records → chunked zstd Parquet → text-replay + health views)
- Tests: 135 passing (engine + RL + observation)

---

## 9. Next — Stage 2

Checkpoint self-play: opponents become **frozen past versions of the learner**, sampled from a pool (mostly recent + some old) to avoid rock-paper-scissors cycling. Adds a competent, co-evolving adversary; success measured by **win-rate vs past checkpoints (an Elo curve)** plus a fixed held-out eval set to detect strategy cycling. This is also where the "opponents self-harm" caveat above gets resolved.

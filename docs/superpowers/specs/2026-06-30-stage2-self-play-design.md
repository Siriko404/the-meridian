# Stage 2 — Checkpoint Self-Play — Design

**Date:** 2026-06-30 · **Status:** building. **Prereq:** Stage 1 done (stage1b = 0.744 vs random).
**Locked in:** prior brainstorm (`…ai-training-design.md` §1, §5) + advisor pressure-test (2026-06-30).

---

## Goal
Replace random opponents with **frozen past versions of the learner**, sampled from a growing pool.
Prove training is **stable** and the agent improves against **competent** (not self-harming) opponents — resolving Stage-1's "opponents self-harm inflates 0.74" caveat.

## Locked design
| Piece | Decision |
|---|---|
| Framing | **Single-agent per generation** (opponents = frozen → env is stationary). NOT PettingZoo — deviation from spec §4 is deliberate & correct (frozen pool ⇒ stationary). |
| Warm-start | Learner inits from **stage1b** weights (continuation, saves compute). |
| Pool seed | `{stage1b}`. Each generation appends its snapshot. |
| Opponent sampling | Per `reset()`, sample N−1 opponents **independently** from pool; bias recent + sprinkle old (RPS guard). |
| Loop | for g in 1..G: train M steps vs pool → snapshot gen_g → append to pool. |
| Reward | Unchanged: terminal-only +1 win / −1 death / 0. |
| Shared turn code | `sim/turn.take_policy_turn` — **same primitive** drives training opponents AND eval. Non-negotiable (else eval measures a different opponent than training used). |
| Per-seat memory | Each opponent gets its own `Extras` (announced counts + magnifier peek) or it predicts on wrong obs and plays weaker than its checkpoint. |

## Advisor hardening (adopted)
1. **Throughput is the landmine.** Model opponents ≈ 100+ NN inferences/game. CPU + env-bound ⇒ could be **20–100× Stage-1 wall-clock, not 4×**. GPU barely helps (tiny MLP).
   → **Throughput pilot FIRST** (~5–10k steps w/ stage1b opponents) → measure steps/sec → size G/M to a wall-clock budget → ask user the budget *with real numbers*.
   → **Cache loaded models in RAM** (`{ckpt_id: model}`); never deserialize a zip per `reset()`.
2. **Gates = numbers, not Elo.** Elo too noisy with ~4–6 policies → **report raw pairwise win-rate matrix** instead (1 copy of A vs 4 copies of B).
3. **Real gen-1 canary** = NOT "beats stage1b" (that's the training *objective*, trivially true). It's: **does gen-1 regress on held-out random?** Overfit-to-one-opponent shows up as a drop from ~0.74 toward ~0.4.

## Gates (every one a number)
- **Gen-1 canary (de-risk stop):** after gen 1, eval lone-vs-4×random. If win-rate **drops below ~0.65** (from 0.744) → STOP, rethink (overfitting to single opponent). Else continue.
- **Hard skill gate:** final gen beats stage1b as **lone-vs-4×stage1b ≥ 0.30** (fair share = 0.20).
- **Compute stop:** G ≤ 4 generations OR wall-clock ≤ [budget TBD post-pilot], whichever first.
- **Report:** full pairwise win-rate matrix across {random, stage1b, gen_1..gen_G}.

## Held-out eval set (fixed, detects cycling)
`{random_policy, stage1b}` + each frozen gen. Pairwise: 1×A vs 4×B, n=2000, eval seeds ≥ 2,000,000 (disjoint from Stage-1's 1e6 eval band and train band).

## 🛑 CRITICAL FINDING (2026-06-30, gen1 run) — seat-specialization invalidates run
The gen1 run completed but is **INVALID**. The eval symmetry ref exposed it:
`stage1b lone vs 4x stage1b = 1.000` (must be ~0.20). Not determinism (stochastic
also gave 0.995). **Per-seat diagnostic (stage1b vs 4x random):**
| seat | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| win-rate | **0.737** | 0.427 | 0.187 | 0.143 | 0.100 |

stage1b only works in **seat 0** (its training seat); in seats 2-4 it's at/below
random. **Root cause:** `obs.encode_obs` loops seats in ABSOLUTE order (`for k in
range(N_SLOTS): player_by_id(state,k)`) and `ActionCodec` targets by ABSOLUTE id.
Trained always as `learner_id=0`, the policy hard-coded "slot 0 = me".
→ In self-play, opponents (stage1b in seats 1-4) were CRIPPLED, not competent.
gen1 "beat" weak play. The whole Stage-2 premise failed silently — caught only by
trajectory/symmetry inspection (the observation philosophy working as intended).

**FIX = ego-centric encoding.** Reorder obs slots so the actor is always slot 0
(others = seats (self+1..self+N-1) mod N); make action targets RELATIVE offsets
(decode r -> seat (self+r)%N; remap immunity/handcuff/flip targets + the r==0
self-cases). Single-agent Stage-1 still trains as seat 0, but the normalized view
now matches ANY seat => policy becomes seat-invariant automatically. Seat-0 obs is
unchanged (identity rotation) so Stage-1 win-rate should reproduce (~0.74). Then
**retrain the seed policy** (stage1b is seat-0-only, unusable) and **re-run Stage 2**.
Stage-2 machinery (env/pool/eval/parallel) stays valid — only obs+action+reseed.

## Build checklist
- [ ] 1. `sim/turn.py`: `Extras`, `random_policy`, `take_policy_turn` (extract from match.py). Verify: full suite green (test_observe = regression guard).
- [ ] 2. `rl/policies.py`: `make_model_policy`. Verify: import + smoke.
- [ ] 3. `rl/pool.py`: `CheckpointPool` (RAM cache, biased sample, seed=stage1b). Verify: test_pool green.
- [ ] 4. `rl/selfplay_env.py`: model opponents via take_policy_turn, per-seat extras. Verify: test_selfplay_env green.
- [ ] 5. Throughput pilot script → steps/sec. **PAUSE → ask user compute budget.**
- [ ] 6. Self-play loop + eval (pairwise matrix) → run within budget → gates → results doc.

## Throughput pilot result (2026-06-30, measured)
| Opponents | steps/sec (CPU) | proj. 1M | proj. 4M |
|---|---|---|---|
| random (Stage-1 env) | 1089 | — | — |
| model (self-play) | **528** | 31 min | **2.1 h** |

Slowdown = **2.1×** (advisor's 20-100× worst case did NOT materialize — MLP predict is cheap, game-logic step dominates). GPU unnecessary. **Budget: G=4 × 1M steps ≈ 2.1 h.** Gen-1 canary gates after the first 31 min.

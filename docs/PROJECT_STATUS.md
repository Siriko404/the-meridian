# Social Roulette — Project Status (resume anchor)

**Updated:** 2026-06-30 · **Branch:** master · **State:** harness complete (Stages 0-3 + a fear probe). Paused; choosing the next lever.
Read this first after any context reset.

---

## One-line
A 5+ player social-deduction game ("Social Roulette") turned into **deterministic code + an RL training harness**. Agents learn to play it. The infra is DONE; the open frontier is making **social behavior** (talk, trust, fear) actually emerge — which keeps coming up null for one reason: no incentive (see THROUGHLINE).

## The stages
| Stage | What | Status |
|---|---|---|
| 0 | Deterministic engine + rule tests + random sim | ✅ DONE |
| 1 | Learn vs RANDOM bots (1a shoot-only → 1b full action) | ✅ DONE (0.74) |
| 2 | Self-play vs POOL of frozen past selves | 🟡 pipeline+eval VALIDATED, seat-bug fixed, no sig gain @ smoke |
| 3 | Emoji COMMS channel | 🟡 BUILT + measured — channel works, agents don't use it (cheap-talk null, both pathways) |
| 4 (probe) | FEAR as a per-agent risk weight | ⚪ INERT vs random — no risky temptation to resolve |

## THE THROUGHLINE (the key synthesis — read this)
Every social behavior reached for (comms, fear; and the proposed trust/revenge/memory/greed) keeps coming up **NULL for the SAME root cause**:
```
individual reward  +  weak/dumb opponents  →  no INCENTIVE for social behavior  →  agents stay "boring" (boring = optimal)
```
It is NOT that the behaviors are coded wrong. Nothing in the game **rewards** them yet. The next lever is therefore the **incentive or the opponent**, not another behavior knob.
- **Comms** got a *shallow* competent-opponent test (Stage-3 gen1 = 1 generation of self-play; its opponents were comms-DEAF, trained vs random) → null. **Deep co-evolution (many generations, all comms-on, speaking+listening bootstrapping together) is UNTESTED** — the most likely place a signal appears, if anywhere.
- **Fear** was only tested vs random → inert (safe play is already win-optimal vs random, so fear has nothing to tip). **Fear-under-self-play is UNTESTED** (a competent opponent makes risk tempting).
- **Risk-attitude correction (don't re-derive):** a +1-win/−1-death win-maximizer is **risk-NEUTRAL** → fear/greed are genuinely ABSENT, not present. "Define fear/greed" = risk-sensitive RL. **Greed must pick ONE mechanism:** impatience (low gamma) · acquisitiveness (intrinsic item/kill reward) · risk-seeking (convex upside). Hidden heterogeneous types = the information-asymmetry comms would need.

## Key results (measured · n=5000 · eval seeds disjoint from train · binomial vs 0.20)
| Policy | Win-rate | p |
|---|---|---|
| random baseline | 0.1934 | — |
| 1a shoot-only (300k steps) | 0.4694 | ≈0 |
| 1b full action (1M steps) | 0.7436 | ≈0 |

Trajectory-validated as **real play** (agent heals + shoots enemies; not a reward-hack). Caveat: random opponents partly **self-harm**, so part of 0.74 is opponent weakness → Stage 2 resolves this.

## Repo map
- `game_guide.md` — the locked game ruleset (source of truth for mechanics).
- `social_roulette/engine/` — pure, seeded, deterministic rule engine (constants, rng, state, chamber, shooting, items, economy, reload, endgame, actions, engine).
- `social_roulette/sim/random_agent.py` — `random_policy`, `take_random_turn`, `play_game`.
- `social_roulette/rl/` — `env` (Stage-1 single-agent gym), `obs` (Markov-sufficient, hides who-holds-what, +last-8 message window), `action_space` (Discrete(39) = 24 game + 15 SPEAK, **ego-centric relative-seat** mask), `train`, `evaluate`, `baseline`, `policies`, `selfplay_env`, `pool`.
- `social_roulette/observe/` — **match observation engine**: `events` (schema + reserved `message` type for Stage-3 comms), `recorder`, `match` (`run_match` = canonical full-table runner, per-seat policies, reused by Stage-2 self-play), `store` (chunked **zstd Parquet**), views: `text_replay`, `health`.
- `social_roulette/rl/selfplay.py` — Stage-2/3 self-play: pool, parallel SubprocVecEnv, eval, per-seat diag, `--comms`/`--retrain-seed`/`--run-parallel`.
- `social_roulette/rl/comms_eval.py` — Stage-3 metrics: `response_shift` (flip-rate=sensitivity), `winrate_ablation` (receiver), `sender_ablation`.
- `social_roulette/comms/vocab.py` — emoji vocabulary (5-act v1, 15 speak options, NL render).
- `social_roulette/rl/fear_env.py` + `fear.py` — Stage-4 fear probe (per-agent fear weight + behavior sweep).
- `tests/` — **171 passing**. `models/` — `stage1a/b`, `stage2seed`, `stage2/gen1`, `stage3seed`, `stage3/gen1`, `fear`.
- `docs/` — `stage1_results.md`, `stage2_results.md`, `stage3_results.md`, `stage4_fear_results.md`. `docs/superpowers/specs|plans/` — per-stage design+plan.
- `mechanics_audit.md` — game-rules audit. `training_design_audit.md` — RL-design adversarial audit (28 findings).

## Environment (Windows)
- **Python 3.13 venv at `.venv`** (py3.14 also installed but UNUSABLE — no torch wheels; always `py -3.13`).
- Stack: torch **2.12.1+cpu**, gymnasium 1.3.0, stable-baselines3 2.9.0, sb3-contrib 2.9.0, pyarrow 24, scipy, pytest.
- `.venv/`, `records/`, `records_demo/` are gitignored.
- **Device = CPU for Stage 1** (GPU gives no speedup on this env-bound, tiny-MLP workload). **GOTCHA:** installing SB3 from PyPI reverts torch to its CPU build → for GPU you must reinstall torch from a **cu126/cu128** index *after* SB3 (cu124 maxes at torch 2.6.0). GPU only matters from Stage 2.

## Commands (from repo root)
```
./.venv/Scripts/python -m pytest -q                                   # 171 tests
# Stage-3 comms run + measure:
PYTHONUTF8=1 ./.venv/Scripts/python -m social_roulette.rl.selfplay --run-parallel --comms --gens 1 --steps-per-gen 250000 --seed-model models/stage3seed --out models/stage3
# Stage-4 fear:  python -m social_roulette.rl.fear --train --measure --out models/fear
./.venv/Scripts/python -m social_roulette.rl.baseline                  # 0.1934
./.venv/Scripts/python -m social_roulette.rl.train [--shoot-only] --steps N --out models/X
./.venv/Scripts/python -m social_roulette.rl.evaluate models/X [--shoot-only]
# observe (UTF-8 for emoji): PYTHONUTF8=1 ./.venv/Scripts/python -c "from social_roulette.observe import store,text_replay,health; print(text_replay.render(store.read_match(DIR, ID)))"
```

## Locked decisions (do NOT re-litigate — detail in specs/audits)
- RL agents, **not** LLMs. Fixed **emoji** comms dictionary for Stage 3 (compositional, length-capped, public broadcast, lying allowed).
- Stage 1 = **single-agent** (opponents = fixed random in-env). Stage 2 = **checkpoint self-play, opponent POOL** of frozen past selves (mostly recent + some old — single-latest cycles RPS).
- **Individual reward** (no shared); teams = a no-shoot constraint + flip economy only.
- **Reward terminal-only** (+1 win / −1 death); shaping behind a flag only if needed.
- Obs Markov-sufficient, **hides who-holds-what**; action = **ego-centric (relative-seat)** masked `Discrete(24 game + 15 speak)`; env auto-pays cheapest for flips. (Stage-2 fix: was absolute-seat → seat-0-only bug.)
- Records = **event-sourced → chunked zstd Parquet**; views pluggable (CLI storyboard / narrator / web = future views, zero rework).

## Stage 2 — status (2026-06-30)
Built + validated. See `docs/stage2_results.md` + `docs/superpowers/specs/2026-06-30-stage2-self-play-design.md`.
- Machinery: `rl/selfplay.py` (pool, parallel SubprocVecEnv self-play, eval, per-seat diag), `rl/selfplay_env.py`, `rl/pool.py`, shared `sim/turn.py`, ego-centric `rl/obs.py`+`rl/action_space.py`.
- **Bug caught + fixed:** obs/actions were absolute-seat-indexed → policy was seat-0-only → self-play opponents were secretly crippled. Fixed with **ego-centric encoding**; seat-invariance proven (flat per-seat win-rate). New seat-invariant seed = `models/stage2seed` (stage1b retired).
- **Result:** eval honest (seed-vs-4×seed = 0.21 ≈ fair share), self-play stable (no collapse), **no significant skill gain at 250k smoke** (gen1 +0.017 over the 0.210 control, p≈0.18). Lever for a real gain = more **training** (not eval).
- Parallelism: SubprocVecEnv = 1.6× only (PPO serial grad phase caps it on a tiny MLP). GPU does NOT help (env-bound); GPU only matters at Stage 3 (transformer).

## Stage 3 — status (2026-06-30)
Built + measured. See `docs/stage3_results.md` + spec/plan `…2026-06-30-stage3-comms*`.
- **Channel works:** emoji `[ACT][WHO][VALUE]`, 5-act v1 set, ≤2 msgs/turn, public, lying allowed, normal-turns-only. Agents **speak** (masked Speak action → `MESSAGE` event) and **perceive** (last-8-message window in obs, re-relativized). Comms gated behind `state.comms_enabled` (opt-in) so Stage-1/2 baselines are untouched. Seat-invariance preserved (seed-vs-seed = 0.193).
- **Verdict = cheap-talk NULL (expected), both pathways:** receiver ablation (intact 0.1996 vs scrambled 0.2132, p=0.12) AND sender ablation (intact 0.1996 vs field-deaf 0.2116, p=0.15) — neither hearing nor broadcasting helps win-rate; n=2500/arm, powered for 0.03. Decisions are *sensitive* to messages (flip-rate 0.55) but identically so in a random-trained seed → incidental, not learned. Under individual reward, agents don't use the channel for gain.
- **Methodological catch:** flip-rate = input-sensitivity, NOT benefit; only the outcome (win-rate) ablation measures use. Rich 28-act vocab remains designed-on-paper (expand only if a regime shows use).
- Artifacts: `models/stage3seed`, `models/stage3/gen1`.

## Stage 4 (probe) — fear (2026-06-30)
Built + measured. See `docs/stage4_fear_results.md`.
- Per-agent fear weight `f~U[0,3]` scales the death penalty (−f), exposed in the agent's own obs (`fear_env.py`, `fear.py`). Trained 1M vs random.
- **INERT:** self-shot rate, heal rate, win-rate all FLAT across `f∈[0,3]`. Pre-registered FAIL branch. Cause: vs random opponents safe play is already win-optimal → no risk-reward tradeoff for fear to tip → policy ignores `f` (flat win-rate confirms).
- Diagnosis → fear needs a TEMPTING risk = competent self-play, not random.

## Open levers / next (PAUSED here — user's call)
Per the THROUGHLINE: change the incentive or the opponent, not the behavior.
| Lever | The bet | Cost |
|---|---|---|
| **Deep comms co-evolution** | many generations, all comms-on → talk may bootstrap (UNTESTED) | medium |
| **Fear under self-play** | competent opponent makes risk tempting → personalities may form (UNTESTED) | low — reuse `selfplay_env` + fear weight |
| **Change incentives** | team reward / cross-game reputation / private-info-worth-sharing → gives social behavior a payoff | larger redesign |
| **Bank** | the harness + the honest "self-interest → no social behavior" finding is itself the result | zero |

## Audit's standing verdict
Stages 0–1 = buildable & **done** (the safe half). Stage 2 = unprecedented method/compute quadrant — a research bet; set a hard compute stop and make every stage gate a number. Stage 3 comms = **near-determined null** under individual reward (agents may ignore the channel) — that null is itself a valid result to design for.

# Social Roulette — Project Status (resume anchor)

**Updated:** 2026-06-30 · **Branch:** master · **State:** end of Stage 1, next = Stage 2.
Read this first after any context reset.

---

## One-line
A 5+ player social-deduction game ("Social Roulette") turned into **deterministic code + an RL training harness**. An agent now learns to play it. We are between Stage 1 (done) and Stage 2 (self-play, not started).

## The 4 stages
| Stage | What | Status |
|---|---|---|
| 0 | Deterministic engine + rule tests + random sim | ✅ DONE |
| 1 | Learn vs RANDOM bots (1a shoot-only → 1b full action) | ✅ DONE |
| 2 | Self-play vs POOL of frozen past selves | 🟡 pipeline+eval VALIDATED, bug fixed, no sig gain @ smoke |
| 3 | Emoji COMMS channel (conversations live here) | ⬜ LATER |

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
- `social_roulette/rl/` — `env` (single-agent gym), `obs` (Markov-sufficient, hides who-holds-what), `action_space` (Discrete(24), absolute-id mask), `train` (MaskablePPO), `evaluate` (binomial), `baseline`.
- `social_roulette/observe/` — **match observation engine**: `events` (schema + reserved `message` type for Stage-3 comms), `recorder`, `match` (`run_match` = canonical full-table runner, per-seat policies, reused by Stage-2 self-play), `store` (chunked **zstd Parquet**), views: `text_replay`, `health`.
- `tests/` — **135 passing**. `models/` — `stage1a.zip`, `stage1b.zip`.
- `docs/superpowers/specs/` — AI-training design + Stage-1 design. `docs/superpowers/plans/` — Stage-0 engine plan + Stage-1 plan. `docs/stage1_results.md` — full Stage-1 report.
- `mechanics_audit.md` — game-rules audit. `training_design_audit.md` — RL-design adversarial audit (28 findings).

## Environment (Windows)
- **Python 3.13 venv at `.venv`** (py3.14 also installed but UNUSABLE — no torch wheels; always `py -3.13`).
- Stack: torch **2.12.1+cpu**, gymnasium 1.3.0, stable-baselines3 2.9.0, sb3-contrib 2.9.0, pyarrow 24, scipy, pytest.
- `.venv/`, `records/`, `records_demo/` are gitignored.
- **Device = CPU for Stage 1** (GPU gives no speedup on this env-bound, tiny-MLP workload). **GOTCHA:** installing SB3 from PyPI reverts torch to its CPU build → for GPU you must reinstall torch from a **cu126/cu128** index *after* SB3 (cu124 maxes at torch 2.6.0). GPU only matters from Stage 2.

## Commands (from repo root)
```
./.venv/Scripts/python -m pytest -q                                   # 135 tests
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
- Obs Markov-sufficient, **hides who-holds-what**; action = absolute-id masked `Discrete(24)`; env auto-pays cheapest for flips.
- Records = **event-sourced → chunked zstd Parquet**; views pluggable (CLI storyboard / narrator / web = future views, zero rework).

## Stage 2 — status (2026-06-30)
Built + validated. See `docs/stage2_results.md` + `docs/superpowers/specs/2026-06-30-stage2-self-play-design.md`.
- Machinery: `rl/selfplay.py` (pool, parallel SubprocVecEnv self-play, eval, per-seat diag), `rl/selfplay_env.py`, `rl/pool.py`, shared `sim/turn.py`, ego-centric `rl/obs.py`+`rl/action_space.py`.
- **Bug caught + fixed:** obs/actions were absolute-seat-indexed → policy was seat-0-only → self-play opponents were secretly crippled. Fixed with **ego-centric encoding**; seat-invariance proven (flat per-seat win-rate). New seat-invariant seed = `models/stage2seed` (stage1b retired).
- **Result:** eval honest (seed-vs-4×seed = 0.21 ≈ fair share), self-play stable (no collapse), **no significant skill gain at 250k smoke** (gen1 +0.017 over the 0.210 control, p≈0.18). Lever for a real gain = more **training** (not eval).
- Parallelism: SubprocVecEnv = 1.6× only (PPO serial grad phase caps it on a tiny MLP). GPU does NOT help (env-bound); GPU only matters at Stage 3 (transformer).

## Next step — choose
(a) **Bank Stage 2** (pipeline validated + bug fixed) and move to **Stage 3** (emoji comms) — or pause. (b) **Invest** a bigger self-play run (more gens × more steps) for a detectable gain.

## Audit's standing verdict
Stages 0–1 = buildable & **done** (the safe half). Stage 2 = unprecedented method/compute quadrant — a research bet; set a hard compute stop and make every stage gate a number. Stage 3 comms = **near-determined null** under individual reward (agents may ignore the channel) — that null is itself a valid result to design for.

# Stage 2 Results — Checkpoint Self-Play (smoke budget)

**Date:** 2026-06-30
**Question:** Can the agent improve against a *competent* opponent (a frozen copy of itself), not just random bots — and is the self-play pipeline correct?
**Answer:** Pipeline + eval validated (after catching & fixing a silent bug). At the 250k smoke budget, gen1 shows a **small but statistically real** skill gain over a competent opponent; general strength is unchanged.

---

## 1. Headline
5 players · learner = lone seat vs a field of 4 copies of opponent B · n=1000 · eval seeds ≥ 2,000,000 (disjoint) · deterministic policy · fair share = 0.20.

| Matchup | Win-rate | Read |
|---|---|---|
| seed vs 4× random | 0.714 | ✓ matches Stage-1 (0.74) — eval sane |
| **seed vs 4× seed** | **0.210** | ✓ **symmetry restored** (was 1.000) — eval honest |
| gen1 vs 4× random | 0.728 | ✓ no collapse (≈ seed) |
| **gen1 vs 4× seed** | **0.227** | real but small: +0.027 over 0.20, ~2.1σ, p≈0.02 |

gen1 = 250k steps warm-started from `stage2seed`, pool = {stage2seed}, parallel self-play.

---

## 2. The bug this stage caught (and fixed)
The first gen1 run looked like a triumph — `gen1 vs 4× stage1b = 0.999`. It was an **artifact**.

**Symptom:** the symmetry reference `stage1b vs 4× stage1b = 1.000` (must be ~0.20 for identical policies).
**Not determinism** (stochastic eval also gave 0.995).
**Diagnosis — per-seat win-rate vs random:**

| seat | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| stage1b (absolute encoding) | 0.737 | 0.427 | 0.187 | 0.143 | 0.100 |
| **stage2seed (ego-centric)** | **0.707** | **0.777** | **0.757** | **0.730** | **0.733** |

**Root cause:** `obs.encode_obs` ordered player slots by **absolute seat** and `ActionCodec` targeted by **absolute id**. Trained always as seat 0, stage1b hard-coded "slot 0 = me" and was near-random in other seats. In self-play it sat in seats 1-4 as an opponent → the opponents were **secretly crippled**, so the "skill gain" was just a strong seat-0 copy beating a weak field.

**Fix:** ego-centric encoding — obs slot 0 is always self (others rotate `(self+j)%N`); action targets are relative offsets (`r=0` = self). A seat-0-trained policy now plays identically from any seat. Verified by the flat per-seat row above.

**This is the observation/validation philosophy working:** a scalar win-rate (0.72 held-out) looked healthy; only trajectory + symmetry inspection exposed that the games were not being "played at full" by competent opponents.

---

## 3. What the validated result says
- **Eval is honest:** identical policies → 0.21 ≈ fair share. The skill metric measures skill, not seat.
- **Self-play training is stable:** no collapse (gen1 holds 0.728 vs random).
- **Skill gain is small:** gen1 best-responded to the seed for +0.027 over fair share (~2σ) — a real but modest edge — while its *general* strength (vs random) is unchanged. Textbook single small self-play step at a tiny budget.

## 4. Honest limits
- **250k steps, 1 generation, single run.** A smoke. A larger/multi-generation run (declined here for time) is needed to see an Elo *trend* or a larger edge.
- **5-player last-one-standing may have a low skill ceiling over a competent opponent** — beating 4 equal copies much above 0.20 is intrinsically hard. The small edge may be partly structural, not just budget.
- Single training seed; CPU; parallelism = 1.6× (PPO's serial grad phase caps env parallelism on a tiny MLP).

## 5. Artifacts
- `models/stage2seed` (seat-invariant seed) · `models/stage2/gen1`
- Code: `rl/selfplay.py` (pool, parallel self-play, eval, per-seat diag), `rl/selfplay_env.py`, `rl/pool.py`, ego-centric `rl/obs.py` + `rl/action_space.py`, shared `sim/turn.py`.
- 150 tests green.

## 6. Next options
1. **Bank it** — pipeline + eval validated, small real gain shown. Move on.
2. **Stronger signal** — more steps/generations (e.g. 4 gens × bigger steps) for an Elo trend; costs more wall-clock.

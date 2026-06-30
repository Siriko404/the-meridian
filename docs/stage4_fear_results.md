# Stage 4 (probe) — Fear as a risk attitude — INERT vs random

**Date:** 2026-06-30
**Question:** If we give each agent a **fear weight** `f` (scales its death penalty, exposed in its own obs), does cautious behavior rise with `f` — i.e., do risk-personalities form?
**Answer (pre-registered one-number test):** **No — the knob is inert** against random opponents. Stop and rethink, as planned.

---

## Setup (minimal, one lever)
- One policy. Each episode draws `f ~ U[0,3]`. Reward = +1 win / **−f** death. `f` appended to the agent's own obs.
- Trained 1M steps, parallel, vs fixed random opponents, comms off (`fear_env.py`, `fear.py`).
- Swept `f`, measured behavior over 400 games each (`behavior_vs_fear`).

## Result — flat in fear
| fear | self-shot rate | heal / game | win-rate |
|---|---|---|---|
| 0.00 | 0.018 | 0.728 | 0.698 |
| 0.75 | 0.023 | 0.720 | 0.680 |
| 1.50 | 0.018 | 0.723 | 0.695 |
| 2.25 | 0.017 | 0.723 | 0.685 |
| 3.00 | 0.020 | 0.725 | 0.688 |

Self-shot rate, heal rate, and win-rate are **all flat** — the policy ignores `f`.

## Diagnosis (the real insight)
A risk attitude only changes behavior where there is a **risk-reward tradeoff**: a +EV-but-deadly action a risk-neutral agent takes and a fearful one declines. **Against random opponents that tradeoff is absent** — safe play is already win-optimal (the agent self-shoots ~2% at *every* `f`, because self-shooting is simply −EV here). With no decision for fear to tip, the gradient on the `f` input is ~0 → the policy correctly learned to ignore it. The **flat win-rate** confirms this: a fear-using agent would sacrifice win-rate for safety at high `f`; it doesn't.

## Implication / next lever
- **Fear needs a tempting risk** to bite. The place that exists is **competent self-play** (a strong opponent makes aggressive/risky plays profitable), not random bots.
- Cheapest next test: re-run the fear sweep with **self-play opponents** (reuse `selfplay_env` + the fear weight). If still flat → risk attitudes are not expressible in this game's action space; if it bends → personalities form and we have a substrate.
- This connects back to the comms null: hidden risk-types would be the information asymmetry signaling needs — but only if the types actually produce distinguishable behavior, which this probe says they do **not** vs random.

## Artifacts
- `models/fear`, `social_roulette/rl/fear_env.py`, `social_roulette/rl/fear.py`, `tests/test_fear_env.py`. 171 tests green.

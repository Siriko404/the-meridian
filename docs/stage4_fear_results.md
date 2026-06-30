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

## Diagnosis (leading explanation — NOT proven; 1 seed)
**Most likely:** a risk attitude only changes behavior where there is a **risk-reward tradeoff** — a +EV-but-deadly action a risk-neutral agent takes and a fearful one declines. Against random opponents that tradeoff is largely absent — safe play is already win-optimal — so there's little for fear to tip and the policy learns to ignore `f`. Flat win-rate is consistent (a fear-using agent would trade win-rate for safety; it doesn't).

**Confounds NOT ruled out (one run can't distinguish these):**
- **Unlearnable input:** one fear scalar appended to a 102-dim obs, signal diluted across random opponents — the net may simply fail to condition on it (the same way Stage-3 agents ignored messages). Predicts the identical flat result.
- **Floor effect:** self-shot rate ~0.02 at *every* `f` — the probed behavior is already pinned near zero, so a decrease can't show. The metric may be saturated, not the agent fearless.

To separate "no tradeoff" from "couldn't learn it": (a) test fear under **self-play** (creates tradeoffs), and (b) probe behaviors with headroom — **aggression rate, defensive-item (immunity/handcuff) use** — not just self-shot/heal.

## Implication / next lever
- **Fear needs a tempting risk** to bite. The place that exists is **competent self-play** (a strong opponent makes aggressive/risky plays profitable), not random bots.
- Cheapest next test: re-run the fear sweep with **self-play opponents** (reuse `selfplay_env` + the fear weight). If still flat → risk attitudes are not expressible in this game's action space; if it bends → personalities form and we have a substrate.
- This connects back to the comms null: hidden risk-types would be the information asymmetry signaling needs — but only if the types actually produce distinguishable behavior, which this probe says they do **not** vs random.

## Artifacts
- `models/fear`, `social_roulette/rl/fear_env.py`, `social_roulette/rl/fear.py`, `tests/test_fear_env.py`. 171 tests green.

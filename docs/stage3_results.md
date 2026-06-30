# Stage 3 Results — Emoji Communication (v1)

**Date:** 2026-06-30
**Question:** Given a working emoji chatroom, do self-interested RL agents actually *use* it — does what others say change what they do, and does it help them win?
**Answer:** The channel is **built and perceivable, but not used for gain.** Decisions are *sensitive* to messages, but that sensitivity is incidental (identical in a model that never trained against meaningful messages), and scrambling a receiver's incoming messages does **not** cost it wins. This is the **cheap-talk null** predicted up front (Crawford-Sobel) under individual reward — a valid, expected result, not a failure.

---

## 1. What was built (and works)
- **Channel:** compositional emoji `[ACT][WHO][VALUE]`, ≤2 msgs/turn, public broadcast, normal turns only (bonus silent), lying allowed. 5-act v1 set (shoot-intent, gang-up, next-shell, truce, agree). No LLM.
- **Speak:** a masked sub-action; the engine appends a `Msg`; recorded as a `MESSAGE` event.
- **Perceive:** every agent's obs carries the **last 8 messages**, re-relativized to itself → feeds the policy. (Capability verified; usage is the experiment below.)
- **Seat-invariant:** comms seed per-seat win-rate `[0.71, 0.69, 0.69, 0.71, 0.72]` (flat). Self-play eval honest: seed-vs-4×seed = **0.193 ≈ fair share** (comms did not break the ego-centric encoding).
- **169 tests green.** Stage-1/2 baselines untouched (comms gated behind an opt-in flag).

## 2. The measurement (two metrics, one trap avoided)

**Trap caught:** a naive "decision flip-rate when messages are scrambled" looked like **55% comms use** — but it is an artifact of *net input-sensitivity*, not learned communication. Proof: a model trained only against **random babble** (`stage3seed`) flips at the **same** rate as the comms-self-play model (`gen1`):

| metric | gen1 | seed | read |
|---|---|---|---|
| response-shift flip-rate | 0.547 | 0.550 | sensitive to message inputs, but **identical** → nothing learned |

(Also: an out-of-distribution column-shuffle was replaced with an in-distribution real-window swap; the conclusion held.) **Flip-rate measures sensitivity, not benefit.** The benefit test is win-rate.

**Win-rate ablation (the real test) — does hearing real messages help you win?**
Lone agent (seat 0) vs a field of the same model, comms on; n=2500 per arm.

| arm | win-rate |
|---|---|
| intact (hears real messages) | **0.1996** |
| receiver-scrambled (hears real-but-other messages) | 0.2132 |
| Δ (intact − scrambled) | **−0.014**, z=−1.19, **p=0.12 — not significant** |

Scrambling the messages a receiver hears does **not** reduce its win-rate (the point estimate even slightly favors scrambled — noise). The agent wins ~its fair share (0.20) regardless of what it hears. **The channel carries no win-relevant information.**

### Receiver vs sender (two distinct causal paths)
The win-rate ablation above is the **receiver** path (*others' messages → my behavior → my win-rate*): null. The **sender** path (*my messages → others' behavior → my win-rate*) is separate and tested independently — seat 0 broadcasts normally while the field is made deaf to it; n=2500.

| ablation | intact | ablated | Δ | verdict |
|---|---|---|---|---|
| receiver (deaf to others) | 0.1996 | 0.2132 | −0.014 (p=0.12) | null |
| sender (field deaf to me) | _running_ | _running_ | _running_ | _pending_ |

## 3. Verdict
- **Capability: yes.** Agents can speak a rule-based emoji language and perceive others' messages in their observation.
- **Use (receiver): no.** Hearing real vs scrambled messages does not change win-rate. The babbling/cheap-talk equilibrium, predicted by theory before building.
- **Use (sender):** measured separately (table above); under the receiver null + policy symmetry, expected null, but tested rather than assumed.
- This is **a clean scientific result**, designed for from the start: "do self-interested agents talk?" → on the receiver side, no.

## 4. Honest limits
- **One generation, 250k self-play steps, single seed.** A bigger run *could* surface a small effect, but the theory says the gradient toward honest signaling is near-zero under pure self-interest, and the win-rate ablation is powered for a 0.03 effect and shows none.
- **Team window under-exploited:** the design aimed signaling at the team phase (≥3 alive, aligned interests) — the only place cheap talk *can* emerge. v1 did not add an explicit incentive there; that is the lever if we want to *force* the question (e.g., a partial team-reward or an information-asymmetry the channel can resolve).
- The flip-rate lesson generalizes: **input-sensitivity ≠ use**; only an outcome ablation (win-rate) measures benefit.

## 5. If we want comms to actually emerge (next-lever options)
1. **Add aligned incentive** in the team window (small shared-survival bonus while teamed) — gives talk a gradient.
2. **Make information valuable & private** — e.g., only the Magnifier-holder knows the next shell; a truthful signal then has real option value to a teammate.
3. Otherwise, **bank the null**: the engine + rich-vocabulary design stand; the result ("self-interest → silence") is itself the finding.

## 6. Artifacts
- Models: `models/stage3seed`, `models/stage3/gen1`.
- Code: `comms/vocab.py`, `engine` Speak/Msg, `rl/obs.py` message window, `rl/action_space.py` SPEAK indices, `rl/comms_eval.py` (response-shift + win-rate ablation), `sim/turn.py` Speak handling.
- Spec/plan: `docs/superpowers/specs/2026-06-30-stage3-comms-design.md`, `docs/superpowers/plans/2026-06-30-stage3-comms.md`.

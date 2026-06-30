# Social Roulette — AI Training Harness — Design

**Date:** 2026-06-29
**Goal:** Train RL agents to play *Social Roulette* (see `game_guide.md`) and observe how they learn, improve, and (maybe) communicate. **Purely programmatic** — no human UI, no LLMs.

---

## 1. Approach (locked in brainstorming)

- **Paradigm:** multi-agent reinforcement learning via **checkpoint self-play**.
- **One trained policy** ("main" = latest weights). Opponents ("team folk") = **frozen past checkpoints**, sampled from a **pool** — mostly recent, some old. (Single-latest opponent cycles rock-paper-scissors; the pool tames it. Same method as AlphaStar / OpenAI Five.)
- **Reward is fully individual.** Every agent plays to win solo. Teams are only a *no-shoot constraint* + the flip economy — **not** a shared reward.
- **Comms:** a **fixed emoji dictionary**. Each emoji = one defined meaning; emojis compose into sentences; **per-message length cap** kills spam. Public broadcast — all agents hear all messages. Agents remember who said what (this game). **Lying allowed** (send a false-by-definition emoji). **Ablatable** — see §5.
- **Reward signal:** outcome-driven — **win / loss + a tiny survival nudge** (reward-c). Shaping bonuses (damage, kills) kept **behind a flag**. NOT locked — expect heavy iteration.

---

## 2. Network architecture (the hard part — this is where it lives or dies)

The game *forces* the architecture:

- **Variable player count** (5 → N, and **shrinks within a game** as players die) → a fixed-size MLP can't represent the state. Use **attention / transformer over per-player entity embeddings**: permutation-invariant over the set of other players, with **action-masking** over the living-target set and legal actions.
- **In-episode memory** ("remember what each seat said/did") → **recurrence or a sequence model** over the episode's message + action history.
- Net shape ≈ a **transformer over (timestep × player)** with masking. One policy head also emits the emoji "sentence."

---

## 3. Turn model — a SEQUENCE of sub-actions, not one action

A turn is autoregressive. The policy is called repeatedly until it ends the turn:

```
[talk phase]  send-emoji* · use-item* · trade*        (normal turn only)
[decision]    use-item* · flip* · peek(Magnifier/Beer reveals info)
              → commit-shot (self | target)
```

Mid-turn reveals (Magnifier peek, Beer discard) must **condition later sub-actions** — peek the shell, *then* choose self vs other. Modeling "turn = one action" cannot express this, so we don't.

---

## 4. Environment & training stack

- **Deterministic rule engine** = single source of truth for `game_guide.md`. Hides chamber, rolls dice, enforces every rule. Backed by a **full rule test suite** (this is where "true determinism" is actually proven — not in the markdown).
- **API:** **PettingZoo AEC** (built for turn-based, sequential-agent games) — don't hand-roll the env loop.
- **Algorithm:** **PPO** (RLlib, or custom).

---

## 5. Progress metric ("watch them improve")

- **Primary:** win-rate of latest vs pool of past checkpoints → an **Elo / skill curve.**
- ⚠️ **Cycling guard:** RPS intransitivity can make the curve *look* like progress while the policy just rotates strategies. Mitigate with a **fixed held-out eval set** (scripted bots + a frozen reference checkpoint) and **round-robin** among checkpoints.
- **Comms instrumentation:** measure whether masking all messages changes win-rate. If not → agents ignore the channel (a real, expected outcome under self-interest, not a failure).

---

## 6. Staged plan (de-risked — each stage delivers standalone value)

| Stage | Build | Proves |
|---|---|---|
| **0** | Deterministic engine + full rule tests + random-agent sim | Rules are airtight & runnable |
| **1** | Single learner vs scripted/random bots, **no comms** | An agent can learn the *mechanics* at all |
| **2** | Checkpoint self-play + pool, no comms | Training is **stable**; eval metric works |
| **3** | Add emoji channel | Test for emergent communication (ablate vs off) |

If Stage 1 won't learn, we find out **before** investing in self-play or comms. A working engine + bots has value even if emergent comms never fully converges.

---

## 7. Open risks (designed-for, not blockers)

- **Comms may stay silent.** Pure self-interest → cheap talk has no honesty incentive; listeners can learn to ignore it. Within-team temporary alignment gives *some* basis. Don't promise a lively chatroom.
- **Reward sparsity is the real danger** (1 winner in 5, one terminal signal, long games, 4 noisy opponents). Bigger risk than over-shaping. Keep shaping behind a flag; iterate.
- **Non-stationarity** of many co-learners — tamed by the frozen-checkpoint pool.

---

## 8. Out of scope (for now)

- Human-playable UI / graphics.
- LLM agents.
- Emergent (un-fixed) emoji semantics — dictionary stays hand-defined.

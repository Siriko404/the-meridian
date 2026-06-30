# Stage 3 — Emoji Communication Engine — Design

**Date:** 2026-06-30 · **Status:** spec (approved v1). **Prereq:** Stage 2 (seat-invariant ego-centric encoding, self-play machinery).

---

## Goal
Give agents a **rule-based emoji language** to talk in a public chatroom, and measure whether self-interested RL agents actually **use** it. No LLM. Lying allowed. Agents speak emoji; a render table shows humans natural-language lines.

## The binding reality (why minimal-first, not rich-first)
Under the **locked individual reward**, pure competition has only a *babbling equilibrium* (Crawford-Sobel): receivers rationally ignore cheap talk → senders go silent → no signaling convention forms. A large vocabulary with no incentive to use it is just unused actions.

**Signaling can emerge only where interests align.** In this game that is the **team window**: while ≥3 players are alive, `legal_targets` forbids shooting teammates and teammates share the goal of eliminating the other team first. Plus ~25-turn intra-episode repetition gives weak reputation/retaliation. **The experiment targets team-coordination while ≥3 alive.**

**Consequence — the sequence:**
1. Design the full rich vocabulary on paper (§5) = the destination.
2. Implement + train a **minimal 5-act subset** (§4) with obvious team-coordination payoff.
3. **Ablation = the success metric** (§7), checked *before* expanding.
4. Expand toward the rich set **only in the regime where ablation shows the channel is used.**

---

## 1. Channel
- Message = compositional emoji string: **`[ACT] [WHO?] [VALUE?]`**, length-capped at ≤4 tokens.
- **Public broadcast** — every living player hears every message.
- **Normal turns only** — the talk phase. Bonus turns are silent (game_guide L189-191).
- **Lying allowed** — emit a false Inform/Commit claim; no special "lie" token.
- **Referents are relative seats** (seat-invariant, consistent with the ego-centric fix): WHO = offset 0=self, 1..4 = others. The `MESSAGE` **event stores the absolute seat**; each listener's obs **re-relativizes** the speaker/target to its own frame. Human render maps absolute seat → public name (🦊🐰🐻🦁🐺).

## 2. Turn integration
- `SPEAK(act, who, value)` becomes an extra **sub-action** in `take_policy_turn`, available only in the talk phase of a normal turn, before the shot.
- Per turn an agent may emit **0-2 messages**, then proceeds to items/flip/shot as today.
- Each SPEAK appends a `MESSAGE` event (already reserved in `events.py`) and is observable by all from the next obs.

## 3. Hearing (interpretation)
- Obs gains a **fixed window of the last K messages** (K≈8-12). Each slot = `[speaker_rel, act_id, target_rel, value]`, re-relativized to the observer.
- **Fixed window, NOT a transformer, for v1** — enough to detect the effect. The spec-§2 player×time transformer is premature; add capacity only if signal appears.

## 4. Minimal act set (v1 — what we train first)
| emoji | act | slots |
|---|---|---|
| 🎯 | I'll shoot | WHO |
| 🗳️ | gang up on | WHO |
| 👁️ | next shell is | VALUE ∈ {live, blank} |
| 🛡️ | truce / won't shoot | WHO |
| ✅ | agree | — |
These form a coordination loop: propose target → agree → share peek → signal non-aggression.

## 5. Rich vocabulary (the expansion target — designed, not yet trained)
Compositional `[ACT][WHO][VALUE]`. ~28 acts grouped by behavior:

| Group | Acts |
|---|---|
| **Inform** (claim; lie-able) | live-count=N · blank-count=N · next-shell=live/blank · I-hold=item · you-hold=item · my-lives=N · your-lives=N · my-team=R/B · your-team=R/B |
| **Commit** | I'll-shoot[s] · won't-shoot[s] · I'll-flip[s] · I'll-heal · I'll-pass · I'll-give[s]=item |
| **Propose** | truce[s] · trade(item↔item) · gang-up[s] · give-me[s]=item |
| **Pressure** | you're-lying[s] · threaten[s] · warn[s about s] · betray[s] |
| **React** | agree/yes · deny/no · doubt[s] · confirm · question[topic] · thanks[s] |
| **Modifiers** | not · ? · swear (truth-stress) |

**WHO:** self · seats 1-4 (relative) · everyone. **VALUE:** 0-6 · live/blank · 6 items · red/blue · shoot/flip/heal.

**Caveat (advisor):** Commit/swear acts have **no teeth** without a cost to breaking them — intra-episode retaliation is the only enforcement. Don't expect honored promises unless retaliation is learnable.

## 6. Reward
**Unchanged** — terminal-only, individual (+1 win / −1 death). Comms adds actions, not reward.

## 7. Success metric — ABLATION (the experiment)
Train a comms policy in self-play (reuse Stage-2 machinery + seat-invariant encoding). Then compare win-rate of a lone comms-agent vs a field:
- **Receiver test:** real incoming messages vs **scrambled** incoming messages (only the test agent's message-obs shuffled). Lower with scrambled ⇒ it *used* what it heard.
- **Sender test:** can broadcast vs **muted** (others don't receive its messages). Lower when muted ⇒ its speech influenced others to its benefit.
- **Gate:** win-rate delta significant (two-proportion test vs the no-comms control, like Stage 2's corrected stats) ⇒ channel is used → expand vocabulary. Delta ≈ 0 ⇒ **channel unused = the honest null** (a valid, expected result under self-interest — not a failure).

## 8. Build sequence (for the plan)
1. `comms.py`: vocabulary (act ids, slot enums), encode/decode, NL render table.
2. `events`/`recorder`: wire the reserved `MESSAGE` event end-to-end (~3 lines).
3. `take_policy_turn`: SPEAK sub-action + per-turn message cap; talk-phase gating.
4. `obs`: append last-K message window (re-relativized).
5. `action_space`: SPEAK action indices (minimal 5-act set) + mask (talk phase only).
6. Self-play train a comms seed (warm-start from `stage2seed`).
7. Ablation harness (receiver + sender) → the number.

## 9. Out of scope (v1)
- The full 28-act set in training (paper only until ablation shows use).
- Transformer/recurrent message encoder (fixed window first).
- Trades as a mechanic (only the *signal* "I'll trade"; actual trade execution is separate).

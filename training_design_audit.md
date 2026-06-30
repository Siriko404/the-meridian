# Social Roulette — AI Training Design — Adversarial Red-Team Audit

**Target under audit:** `docs/superpowers/specs/2026-06-29-social-roulette-ai-training-design.md`
**Rules reference:** `game_guide.md` · **Prior rules audit (context):** `mechanics_audit.md`
**Auditor stance:** hostile examiner. Default verdict on every claim = broken until it survives scrutiny.

---

## Framing note (read first — it changes what this audit attacks)

`mechanics_audit.md` audited an **older** `game_guide.md` and found 33 holes. The **current** `game_guide.md` has since been revised and **resolves the large majority of them** — it now contains an explicit Information & Visibility table (kills old T1-1), a bonus-turn definition (T1-2), a finite Immunity expiry "the moment they fire that shot" (T1-3), "redo the whole roll" loader scope (T2-1), "not received" overflow rule (T2-2), Beer-empties-chamber resolution (T2-3), last-shell-kill precedence via "items drawn only if the chamber also emptied" (T2-4), decision/bonus-phase item rights (T2-5), multi-same-item rule (T2-6), full killer extra-turn + resume-after-killer (T2-7/9), random seating (T2-8), flip-back "actionable turn" window (T2-10), forced self-shoot (T2-11), timeout default (T2-12), dead-player token disposition (T2-13), living-player consumption base (T2-15), and <3-player free-for-all (T2-16).

**Consequence:** this audit does NOT re-litigate those. It attacks (a) the **training design itself**, and (b) the **residual** rule gaps that still block a *deterministic engine* or *leak hidden state into the policy*. Where the design or a rule genuinely survives hard scrutiny, that is stated explicitly with the reason.

Findings are grouped by dimension (A–H) and severity-sorted within each group. Tally, Tier-1 punch-list, and verdict are at the end.

---

## A — Rules → Design coverage (observation / action / turn representability)

### A-00 · Coverage matrix (the exhaustive one-by-one sweep)
Every mechanic in `game_guide.md`, each checked for **Observe** (can the policy see it, without leaking hidden state?), **Act** (does the action space have a slot for it?), **Mask** (is illegal-move masking representable/correct?). `OK` = survives scrutiny; an ID = see that finding.

| Mechanic (`game_guide.md`) | Observe | Act | Mask | Verdict |
|---|---|---|---|---|
| Immunity — place / expiry-on-fire / no self-target | **A-04** (placed-token vis) | OK | OK (A-06) | gap: A-04 |
| Cigarettes — locked & slot-holding at 5 lives | OK (own inv) | OK | OK (A-06) | **OK** |
| Magnifier — peek next 1 / re-peek noop | OK (private; D-01) | OK | OK (A-06) | OK (autoregressive — design's strength) |
| Saw — 1/turn, ×2, self=2, wasted on blank | OK | OK | OK (A-06) | **OK** |
| Beer — remove shell / shrink / last→reload→shoot new | **A-05** (reveal? + mid-turn reload) | OK | OK | gap: A-05 |
| Handcuffs — skip next / one-at-a-time / no self | **A-04** (placed-token vis) | OK | OK (A-06) | gap: A-04 |
| Items-as-currency — sacrifice to pay, no change | OK (own inv + values) | **A-01** (sacrifice-set unmodeled) | OK once modeled | gap: A-01 |
| Team flip — 5 pts, any player, unlimited | OK (colors public) | **A-01** (payment) | OK (afford) | gap: A-01 |
| Flip-back discount — 4 pts, next actionable turn | **A-01** (window field) | OK (variant) | OK | gap: A-01 |
| Trade — teammates / talk-only / gifts / cap-block | OK | **A-02** (bilateral + combinatorial) | OK once modeled | gap: A-02 |
| Public info — colors/flips/lives/item-counts/own-inv | OK | n/a | n/a | **OK (legit obs)** |
| Hidden info — who-holds-what, shell order | must EXCLUDE → **D-01** | n/a | n/a | gap: D-01 (leak) |
| Chamber counts — announced once / track / may lie | OK (load announce + recurrence) | n/a | n/a | OK obs / **C-03** (bluff vacuous) |
| Turn structure — seat order / phases / timeout-fine | OK (turn-type) | OK (sub-actions) | — | **A-03** (timers don't port) |
| Bonus turns — self-blank → silent, items+flips | OK (flag) | OK | OK (no talk/trade) | **OK** |
| Reload (chamber empty) — +2 items each | OK (inv update) | n/a (engine) | n/a | OK (A-05 if Beer-triggered) |
| Reload (kill) — killer extra turn / resume-after-killer / caps reset | OK (turn-type + seat ptr + cap usage) | OK (extra turn) | n/a | **OK** (checked: representable) |
| Chamber sizing — dice accum / 30–70% / shuffled hidden | OK (counts public, order hidden) | n/a | n/a | OK (**F-02** loader cap) |
| Lives 3/5/0 · inventory ≤3/type ≤8 | OK | OK | OK (over-cap not received) | **OK** |
| Consumption cap — living×1.3 floor / reset / commit-counted | OK (cap usage in obs) | n/a | OK lockout (A-06) | **OK** |
| Win — last standing solo | OK (terminal) | n/a | n/a | **OK** |
| Teams ON until <3 / OFF free-for-all | OK (teams flag in obs) | OK | OK (targeting mask flips) | **OK** (checked) |
| Forced self-shoot — no legal target + can't flip | OK | OK | OK (mask → self only) | **OK** |

**Sweep result:** the generic transformer+mask+autoregressive model **can represent the large majority of mechanics** (16 rows `OK`). The failures cluster into a small set of concrete gaps — **A-01** (payment/schema), **A-02** (bilateral trade), **A-03** (timers), **A-04** (placed-token visibility), **A-05** (Beer), **D-01** (hidden-info leak), with **C-03/F-02** as downstream effects — detailed below.

### A-01 · Tier 1 · Dimension A
**Target:** Design §2 ("Network architecture — *this is where it lives or dies*") and §3 (turn model).
**Claim under attack:** The architecture section declares itself make-or-break, then specifies the observation and action **schema** only as "transformer over per-player embeddings + action-masking + one head emits the emoji sentence." The concrete obs vector and action factorization are never enumerated.
**Why it fails / the risk:** §2 is the load-bearing deliverable and it is hand-wave, not a buildable spec. At least three legal-action categories in `game_guide.md` have **no slot in the listed action set** (`send-emoji · use-item · trade · flip · peek · commit-shot`):
1. **Payment / sacrifice choice.** Flipping costs 5 pts paid by *sacrificing items*, and "no change is given" (guide §Economy). So a flip is a compound action: pick target **and** pick *which* items to burn to cover ≥5 (burn a 5-pt Magnifier = exact; burn a 6-pt Immunity = waste 1 pt). The design models "flip*" as atomic — the entire currency-management sub-decision (the heart of the economy) is missing from the action space.
2. **The autoregressive STOP token.** §3's `send-emoji* · use-item* · trade*` are Kleene stars; the policy needs an explicit, maskable "end this phase / proceed to shot" action to terminate the sub-action loop. Not listed.
3. **Per-item target + parameterization.** "use-item" hides six different action shapes (Immunity/Handcuffs need a target; Saw/Beer/Magnifier/Cigarettes are self/chamber; Beer/Cigarettes can be used in multiples). One undifferentiated "use-item" cannot express these.
**Concrete fix:** Before Stage 1, write the explicit schema: the per-player public observation fields (seat, alive, lives, color, flip-state, flip-back-window, placed tokens [pending A-04], handcuff/skip flag), the global fields (per-type item counts in play, chamber announced-counts, consumption-cap usage, turn-type), the **own-only private** fields (inventory, peeked shell), and a factored autoregressive action head: `phase-action ∈ {emit-emoji(token-seq), use-item(type, [target], [count]), propose-trade(...), flip(target, sacrifice-set), end-phase}` then `shot(self|target)`. The schema is the real Stage-0/1 artifact, not the prose in §2.

### A-02 · Tier 2 · Dimension A
**Target:** Design §3 (turn model lists `trade*`) and §4 ("API: PettingZoo AEC").
**Severity note:** Tier 2 (serious **underspecification**), not Tier 1 — it IS expressible in AEC via the propose/accept protocol in the fix below, so it does not break the plan; but it is a non-trivial sub-protocol the design omits entirely, and it must be decided before the engine's trade API is written (Gate 1).
**Claim under attack:** Trades are just another sub-action (`trade*`) inside one agent's turn, and AEC is the right env API.
**Why it fails / the risk:** A trade in `game_guide.md` (§Trade) is **bilateral and consensual** — "any terms you both agree to," teammate-only, cap-checked, possibly a one-way gift. PettingZoo **AEC steps exactly one agent at a time**; the counterparty is not acting during the proposer's turn and cannot "agree" within it. There is no native AEC construct for "Agent A offers, Agent B must consent" mid-A's-turn. Worse, the trade action is **combinatorially large** (choose teammate × any subset of own items to give × any subset of their items to request), and it is **interactive** in a way the design never models. Listing it as `trade*` hides an entire negotiation sub-protocol.
**Concrete fix:** Decide and specify the mechanism: either (a) model trades as a two-step protocol spanning AEC turns — A emits a structured offer as a special action, the offer is queued, and B gets an `accept/reject` action inserted before B's next decision (engine-mediated, with auto-reject on cap breach); or (b) restrict Stage-2/3 trades to **one-way gifts only** (no consent needed — A may push items to a teammate up to caps), which is AEC-expressible, and defer negotiated swaps. Note explicitly that full free-form bilateral negotiation is **out of scope for the RL version** if (b) is chosen — that is a fidelity reduction worth stating.

### A-03 · Tier 2 · Dimension A
**Target:** Design §3 (turn model) vs `game_guide.md` §Turn Structure (1-min talk, 30-s decision, timeout → fine cheapest item → +30 s → broke → auto self-shoot) and §Bonus Turns (30 s, timeout applies).
**Claim under attack:** The turn model is a clean autoregressive sub-action sequence; timing is not mentioned because it is irrelevant programmatically.
**Why it fails / the risk:** The game's **timer mechanics are load-bearing rules, not flavor**, and they have **no analog in a clockless RL env**. An RL policy always emits an action — it never "freezes" — so the entire timeout→fine→auto-self-shoot branch is **dead code** unless the env imposes a synthetic budget. That means one of two unstated things is happening: (i) the rule is silently **dropped**, so the trained agents play a *different game* than the human ruleset (no timeout-fine cost, no clock pressure — a fidelity gap that contaminates any "they learned to play Social Roulette" claim); or (ii) a **sub-action budget** is imposed as a pseudo-timer (which *also* bounds the A-01 STOP loop and D-03), in which case its size and the fine-on-exhaustion mapping must be specified because they change strategy. The design says nothing.
**Concrete fix:** State the mapping explicitly. Recommended: impose a per-phase sub-action budget (the env's clock surrogate); on budget exhaustion apply the guide's fine-cheapest-item-then-auto-self-shoot rule so the *economic consequence* of indecision is preserved; document that wall-clock seconds are replaced by action counts and that this is the one deliberate deviation from the human ruleset.

### A-04 · Tier 2 · Dimension A (also F, D)
**Target:** `game_guide.md` §Information & Visibility (Hidden = "who holds which item"; Public list does **not** include placed tokens) vs Design §2 observation.
**Claim under attack:** Implicit assumption that the observation can be built from the guide's stated public/hidden split.
**Why it fails / the risk:** The visibility table covers **held** items and **shell order**, but is **silent on placed tokens** — i.e., whether the fact that "B has an Immunity token from A on them" or "C is Handcuffed" is **public, private to the holder, or private to the placer**. This is not cosmetic for RL:
- **Legality:** the acting agent must *know* it is immunized/handcuffed to select legal moves (an immunized B literally cannot legally target A; a handcuffed player skips). If placement is hidden from the target, the engine must still mask the target's illegal actions — which silently *reveals* the token through the mask. So the engine's masking choice **forces** a visibility decision.
- **Info-leak (ties to D-01):** in the shared per-player transformer, a placed-token field on another player's embedding is fine **only if** that token is genuinely public; if it is meant to be private, including it leaks hidden state into opponents' observations.
**Concrete fix:** Add placed-token visibility to the guide's table and to the obs schema. Recommended (and self-consistent with masking): **placed Immunity and Handcuffs are public** (everyone sees who is immunized-against-whom and who is cuffed), matching the guide's existing "flips are public, live" philosophy. State it once, globally.

### A-05 · Tier 2 · Dimension A (also F)
**Target:** Design §3 ("Mid-turn reveals (Magnifier peek, **Beer discard**) must condition later sub-actions") vs `game_guide.md` §Items→Beer and §Chamber→A.
**Claim under attack:** Beer is a mid-turn *reveal* analogous to a Magnifier peek, slotting cleanly into the autoregressive loop.
**Why it fails / the risk:** Two problems the design glosses:
1. **Beer may not reveal anything.** The guide says Beer "discard the current shell and draw the next… removed for good" — it never states the discarded shell's live/blank is **shown to the user**. If Beer is a *blind* discard, the design's premise that "Beer discard conditions later sub-actions" via revealed info is **false**; the only thing that changes is the chamber shrank. (Whether Beer reveals is exactly the kind of residual ambiguity Stage 0 must resolve — see F-01.)
2. **Beer can trigger a full-table reload *mid-turn*.** Beer on the last shell empties the chamber → reload → **every player draws 2 items** → fresh chamber → *then* the active player still shoots (guide §Beer + §Chamber-A). That is a large state mutation for **all N agents' observations** in the middle of one agent's turn (everyone's inventory and the chamber change before the shot). The autoregressive `use-item → commit-shot` ordering can sequence it, but the design never acknowledges that a single sub-action can rewrite the whole table's state and hand free items to opponents mid-turn — a real wrinkle for the env's step semantics and for credit assignment.
**Concrete fix:** (i) Resolve whether Beer reveals its discard and put it in the obs spec (recommend: Beer reveals the discarded shell to the beerer only, making it a genuine scout-and-dodge tool and giving the "conditions later sub-actions" claim teeth — see also C-03). (ii) Specify that a mid-turn reload is a full env state transition applied before the pending shot, and that all agents' next observations reflect it.

### A-06 · Tier 3 · Dimension A — (mostly SURVIVES; logged for completeness)
**Target:** `game_guide.md` §Items, §Consumption Limits vs Design §2 "action-masking over legal actions."
**Claim under attack:** Standard action masking can represent the per-item legality rules.
**Why it (mostly) holds:** Walking the mechanics one by one, the **per-item legality is all expressible as a static-plus-dynamic mask**, and this genuinely survives scrutiny:
- Saw "max one per turn" → mask Saw after first use this turn. ✓
- Cigarettes locked at 5 lives → mask Cigarettes-use when lives==max. ✓
- Magnifier re-peek noop → mask (or allow as no-op) when next shell already revealed. ✓
- No self-target for Immunity/Handcuffs; no double-place on same target same turn → target mask. ✓
- Consumption-cap lockout (living×1.3 floor, reset on death, counted on commit) → mask the item type when its cap is hit. ✓
- "Cannot shoot teammate" / immunized-against / handcuffed-skip → target mask + turn-skip. ✓
**Residual risk (why it is logged, not free):** the mask is a **non-trivial table with turn-scoped, episode-scoped, and per-target state**, and a single wrong mask is a silent correctness bug that the agent will exploit (e.g., a missing cap-mask = unlimited Saws). This must be **unit-tested per rule in Stage 0**, not assumed.
**Concrete fix:** Treat the legal-action mask as a first-class, exhaustively rule-tested module; enumerate every (item, turn-type, target, cap-state) legality cell and test each. No design change needed — just don't treat masking as trivial.

---

## B — RL feasibility

### B-01 · Tier 1 · Dimension B
**Target:** Design §1 ("Same method as AlphaStar / OpenAI Five"), §4 ("Algorithm: PPO"), §5 ("Cycling guard… mitigate with a fixed held-out eval set").
**Claim under attack:** Vanilla **PPO** + checkpoint-pool self-play is an appropriate, precedented method for this game, and RPS-cycling is handled by *detecting* it in eval.
**Why it fails / the risk — the empty-quadrant argument:** Social Roulette is an **imperfect-information** game (hidden inventories, hidden shell order, bluffing). Survey the actual landscape of imperfect-info self-play successes — they fall into exactly two quadrants, and this design is in **neither**:
- **(a) Massive-compute policy-gradient + league self-play:** AlphaStar (StarCraft, fog-of-war imperfect info) and OpenAI Five used PG-style RL — *but at thousands of accelerators and months of wall-clock*. Method matches; **budget does not** (see G-01). This is the design's cited precedent, and it is a **compute precedent a solo dev cannot honor**.
- **(b) Explicit equilibrium-convergence methods:** poker (Pluribus, DeepStack, Libratus) uses **Counterfactual Regret Minimization**; "every competitive Texas hold'em AI for ~6 years computed its strategy using some variant of CFR" [1]. Stratego's **DeepNash** uses **model-free RL** but with **R-NaD (Regularized Nash Dynamics)**, which "converges to an approximate Nash equilibrium **instead of 'cycling' around it**, by directly modifying the underlying multi-agent learning dynamics" [2]. The common thread: a **mechanism that drives learning toward non-exploitable play**.
- **The design = vanilla PPO self-play, solo compute, no Nash-convergence mechanism.** Its only "cycling guard" is an **eval-time detector** (held-out set), not a **learning-time force**. Detecting that you are cycling does not stop you cycling. There is **no precedent of success** in this quadrant and **no built-in guarantee** the policy converges to anything non-exploitable rather than rotating strategies forever.
**Concrete fix:** Pick a side of a real quadrant. Either (i) adopt a convergence-driving method for the self-play core — R-NaD-style regularization toward a reference policy, or fictitious-play / PSRO with a best-response oracle — so cycling is fought *in the dynamics*, not just measured; or (ii) explicitly down-scope the ambition to "watch a PPO policy improve against a fixed bot ladder" (Stages 0–1) and **stop claiming AlphaStar-class self-play** is achievable here. At minimum, delete "same method as AlphaStar / OpenAI Five" — it imports their compute, not their results.
**Sources:** [1] https://www.science.org/doi/10.1126/science.aay2400 (Pluribus, MCCFR). [2] https://arxiv.org/abs/2206.15378 (DeepNash, R-NaD).

### B-02 · Tier 1 · Dimension B
**Target:** Design §1 ("Reward… win/loss + a tiny survival nudge. Shaping bonuses behind a flag"), §7 ("Reward sparsity is the real danger").
**Claim under attack:** Sparsity is acknowledged and managed by keeping shaping available behind a flag; the bigger risk is over-shaping.
**Why it fails / the risk:** The design correctly names sparsity but **underweights its interaction with the action space**, which is the actual wall. The terminal signal is **1-of-N** (one winner in 5–8; ~12–20% base rate) at the end of a **long** episode, while a single turn is an **autoregressive product space**: emoji sentences (compositional, length-capped) × item uses (6 types, multiples) × flips (any target × sacrifice-set) × trades × shot target. The number of distinct multi-step turn realizations is enormous, and **PPO explores on-policy** — it perturbs around its current behavior and will essentially **never stumble** onto a coherent multi-step plan (e.g., "flip an enemy onto my color to shield me this round, then shoot the real threat") often enough for a once-per-episode win signal to reinforce it. Sparse reward is survivable with a small action space; a **huge structured action space with a sparse terminal reward is the canonical "won't-learn" regime.** And the design's **default** config (light reward, shaping off) is precisely that worst case — so the default run is the one most likely to flatline, which is the worst possible thing to discover late.
**Concrete fix:** Do not start from the hardest case. For Stage 1, ship **dense diagnostic shaping by default** (per-damage, per-kill, per-survival-step, per-legal-economy-action), prove the agent can climb *with* shaping, then **anneal shaping toward zero** and confirm the policy survives the removal. Treat "learns under the light-reward default" as a *Stage-2 milestone*, not a *Stage-1 assumption*. Also consider action-space curricula (unlock items/flips/comms progressively).

### B-03 · Tier 2 · Dimension B (also G)
**Target:** Design §1 ("One trained policy… Opponents = frozen past checkpoints").
**Claim under attack:** One learner versus frozen-checkpoint opponents is a clean self-play setup.
**Why it fails / the risk:** With exactly **one** main policy per game and the other 4–7 seats frozen, **only one trajectory per episode produces training gradient** for the current policy. That is a **1/N sample-efficiency tax** on a problem (B-02) that is already extremely sample-hungry, and it multiplies the throughput/compute problem (G-01). Frozen opponents also generate **off-policy-ish, stale** experience for modeling, and the lone learner sees each game from a single seat/perspective.
**Concrete fix:** Either seat **multiple copies of the current policy** in each game (shared-parameter self-play; collect gradient from all current-policy seats) and sample only *some* seats from the frozen pool — recovering N× the learning signal per episode — or accept the tax and budget compute accordingly (G-01). State which, because it changes the episode budget by an order of magnitude.

### B-04 · Tier 2 · Dimension B
**Target:** Design §5 ("Cycling guard… RPS intransitivity"), §7 ("Non-stationarity… tamed by the frozen-checkpoint pool").
**Claim under attack:** The checkpoint pool tames non-stationarity and the held-out set catches cycling, so self-play instability is handled.
**Why it fails / the risk:** The pool addresses **one** failure mode (the *latest* policy RPS-chasing the *latest* opponent). It does **not** address **population-wide convergence to a degenerate basin**. In a forced-shoot game with individual reward, plausible low-skill attractors exist that the *whole* pool can settle into — e.g., "always flip the nearest legal target if affordable, else self-shoot," or "ignore items, fire at the lowest-life enemy." Once the pool is saturated with such strategies, win-rate-vs-pool looks *stable and improving* while the population is stuck in a shallow equilibrium. The held-out set catches **cycling** but not a **globally degenerate-but-stable** policy (it will happily beat weak scripted bots too). This is *strategic* collapse, distinct from the *comms* collapse the design does flag in §7.
**Concrete fix:** Add **exploitability / best-response probing** to eval: periodically train a *fresh* best-response learner against the frozen current policy and report how badly it exploits it. A policy that is easy to exploit is in a degenerate basin regardless of its pool win-rate. (This is also the natural bridge to the B-01 fix.)

### B-05 · Tier 2 · Dimension B
**Target:** Design §1 ("a tiny survival nudge (reward-c)").
**Claim under attack:** A small per-step survival reward is a benign, helpful dense signal.
**Why it fails / the risk:** In a last-player-standing game, a **per-step survival reward** pays the agent for *not dying*, which is maximized by **letting others fight while you hide** — the opposite of the aggression required to actually win (you only win by *eliminating* everyone else, and the game *forces* you to shoot every turn). A naive survival nudge therefore biases toward passive, conflict-avoiding policies: prefer self-shooting blanks (when the chamber is blank-heavy) to farm bonus turns + survival reward, shoot to *not-kill*, avoid being the one who finishes opponents (and triggers the killer's extra turn / attention). The guide's ~57% live ratio limits the self-shoot exploit, but the *directional* bias toward passivity is real and it **interacts with episode truncation** (G-03): if a truncated cagey game pays survival reward, passivity is *positively* reinforced.
**Concrete fix:** Make the survival term **potential-based** or fold it into a **win-conditioned** form (reward survival only on trajectories that *win*, or use a potential Φ = f(rank-at-termination) so it cannot be farmed by stalling). Verify empirically that adding reward-c does not *lower* aggression/kill-rate versus reward-c = 0.

---

## C — Comms / emergent communication

### C-01 · Tier 1 · Dimension C
**Target:** Design §0 goal ("…and (maybe) communicate"), §5 ("measure whether masking all messages changes win-rate. If not → agents ignore the channel… a real, expected outcome, not a failure"), §1 (fully individual reward + lying allowed).
**Claim under attack:** Stage 3 is a valid *test* for emergent communication: mask messages; if win-rate is unchanged, that's an informative negative result.
**Why it fails / the risk — the test is unfalsifiable:** The ablation "mask messages → win-rate unchanged ⇒ channel ignored" **cannot distinguish two completely different worlds**: (i) comms is *genuinely useless here*, versus (ii) *your training simply failed to discover a protocol* (sparse reward + huge action space, B-02). Both produce "win-rate unchanged." So a null result teaches you **nothing** about the actual question. Worse, a null is **over-determined** by theory and by the design's own choices:
- **Cheap talk under misaligned incentives is ignored.** The emoji channel is costless, non-binding, and non-verifiable — textbook "cheap talk" (Farrell & Rabin). Under **fully individual reward** in a last-one-wins game, incentives are opposed, and "when agents' incentives are not aligned, meaningful communication is not guaranteed"; senders signal only to help themselves, "consequently disincentiviz[ing] receivers from paying attention" [3][4]. Listeners learning to ignore is the *predicted equilibrium*, not a surprising finding.
- **Even a *useful* signal can't be learned.** Suppose a bluff at turn 12 *would* help you win at turn 80. The PPO credit-assignment path from that one emoji to the terminal win, through 4 noisy opponents and ~70 intervening sub-actions, is **effectively zero gradient** (B-02). So beneficial deception is **undiscoverable**, independent of whether it exists.
**Concrete fix:** (i) **Reframe the Stage-3 deliverable** away from "is there emergent comms?" (unfalsifiable here) to a *capacity* test you can actually run: hand-author a known-useful protocol, **hard-code** one team to use it, and measure whether *that* moves win-rate — establishing the channel's ceiling before asking whether RL finds it. (ii) If genuine *emergence* is the goal, you must create a signaling incentive the current design forbids — e.g., a **partial within-team reward coupling** during the teams-on phase — and accept that this contradicts the "fully individual reward" lock (see H-01). Do not ship "win-rate unchanged" as evidence of anything.
**Sources:** [3] https://arxiv.org/pdf/2006.02419 (Emergent comms survey — incentive alignment). [4] https://arxiv.org/pdf/2303.10733 (Cheap Talk Discovery & Utilization).

### C-02 · Tier 2 · Dimension C (also G — staging)
**Target:** Design §6 staging table (Stage 2 = self-play pool **no comms**; Stage 3 = "Add emoji channel… ablate vs off").
**Claim under attack:** Adding the emoji channel at Stage 3 on top of the Stage-2 self-play pool is the natural place to test for emergent communication.
**Why it fails / the risk:** The Stage-2 pool is **built without comms** — every frozen checkpoint in it is **comms-naive: it never speaks and never listens.** When Stage 3 trains the new policy against that pool, the learner faces opponents who emit nothing (so there is **nothing to learn to listen to**) and who ignore everything (so there is **no reward for learning to speak**). Emergent communication is fundamentally a **co-adaptation** phenomenon — speakers and listeners must evolve *together*. A learner-versus-frozen-mutes structure **structurally suppresses** the very thing Stage 3 is meant to elicit, *independent* of the incentive problem in C-01. So even in the charitable world where comms *could* help, this staging makes its emergence nearly impossible to observe.
**Concrete fix:** If comms is pursued, it cannot be bolted onto a mute pool. Either (i) **co-train a population *with* the channel from the start** of the comms experiment (fresh pool, all members can speak/listen, sampled past checkpoints also comms-capable), or (ii) seed Stage 3 with **at least one co-adapting current-policy opponent** (not only frozen mutes) so speaker and listener move together. Note this raises the non-stationarity the pool was meant to tame — a real tension to budget for.

### C-03 · Tier 2 · Dimension C
**Target:** `game_guide.md` §Information & Visibility ("Players track depletion from memory, and may talk about it publicly, **including lying**") presented as a headline social mechanic; Design §1 ("Lying allowed").
**Claim under attack:** Bluffing about the chamber's shell count is a rich social mechanic for agents to exploit and lie about.
**Why it fails / the risk — the bluff target is nearly empty under RL:** The thing players are supposed to lie *about* — how many live/blank shells remain — is **almost fully publicly inferable** in the RL setting, and **perfect recall is free** for a recurrent/transformer net:
- Every shot's outcome is **public**: lives are public, so a target losing a life ⇒ that shell was **live**; a self-blank grants a publicly-visible **bonus turn** ⇒ that shell was **blank**; an "other, blank" produces no life change after a non-self shot. So the live/blank of essentially every fired shell is **deducible**, and a neural net **remembers all of it perfectly** — there is no human memory limitation to exploit and little hidden count-state to misrepresent.
- The **only** genuinely hidden count-information left is **post-Beer uncertainty** — *if and only if* Beer hides its discarded shell (the unresolved rule in A-05/F-01). If Beer reveals its discard, the residual hidden count collapses toward zero and the "lie about the count" mechanic is **fully dead**. If Beer hides it, there is a *thin* sliver of private state worth bluffing over.
**Net:** a headline social mechanic hinges almost entirely on **one unresolved rule decision** (does Beer reveal its discard?), and even in the favorable case the bluff surface is thin — which compounds C-01 (no incentive *and* almost nothing to lie about).
**Concrete fix:** Decide Beer-reveal (A-05) consciously *as a design lever for the comms layer*: hiding Beer's discard is the cheapest way to keep any private chamber-state alive for bluffing. Separately, recognize that the richer hidden information agents could lie about is **inventory and intent** (who holds Immunity, who will flip whom) — ensure the fixed emoji dictionary can express those speech acts, since shell-count bluffing alone is near-vacuous.

---

## D — Architecture realizability

### D-01 · Tier 2 · Dimension D
**Target:** Design §2 ("transformer over per-player entity embeddings… permutation-invariant over the set of other players").
**Claim under attack:** A shared transformer over per-player embeddings is the obvious encoder; the hidden/public split "just works."
**Why it fails / the risk — silent info-leak is the #1 self-play correctness bug here:** A per-player embedding that includes a player's **inventory** or **peeked shell** is exactly the hidden state the policy must **never** receive about *opponents* (`game_guide.md` Hidden = "who holds which item," shell order; plus a Magnifier peek is private to the peeker). In a shared encoder it is **trivially easy** to build the obs by stuffing every player's full feature vector into the set — leaking opponents' private state into the main policy. The result is the classic disaster: the policy learns to "cheat," training curves look *great*, and the agent is **useless against any fair opponent** (and the leak is invisible unless you test for it). The design's only nod is one line in §4 ("hides chamber") — it never specifies **per-seat observation construction**.
**Concrete fix:** Specify obs as a **per-acting-seat view**: each player-embedding carries only **public** fields (seat, alive, lives, color, flip-state, flip-back window, placed tokens [A-04], skip flag, *aggregate* item-counts-in-play) for *all* players, plus **own-only private** fields (own inventory, own peeked shell) attached solely to the self-embedding. Add an explicit **leak test** to Stage 0: train a probe to predict an opponent's hidden inventory **from the policy's observation tensor**; if it succeeds above chance, the obs is leaking.

### D-02 · Tier 2 · Dimension D
**Target:** Design §2 ("In-episode memory ('remember what each seat said/did') → recurrence or a sequence model… a transformer over (timestep × player)").
**Claim under attack:** "Remember who said what" is handled by a transformer over (timestep × player).
**Why it fails / the risk:** The message + action **history grows unbounded** over an episode, and a transformer over (timestep × player) is **quadratic in timesteps**. Social Roulette episodes are **long** — multiple lives per player, reloads, bonus-turn chains, and *each turn is itself multiple sub-actions/messages* (A-01). A late-game context window of hundreds of (timestep × N-player) tokens is both a **compute blowup per forward pass** (worsening the throughput problem, G-01) and an **unstated architectural commitment**. The design names two different mechanisms ("recurrence **or** a sequence model") without choosing, and never bounds the context.
**Concrete fix:** Choose and bound: either a **recurrent core** (LSTM/GRU/GTrXL) carrying a fixed-size state — O(1) per step, the natural fit for long episodes — or a transformer with an **explicit bounded window** + a learned summary of older history. State the max context length and the per-step cost, because they gate episode throughput and therefore the whole compute budget.

### D-03 · Tier 2 · Dimension D (ties to A-03)
**Target:** Design §3 (`[talk phase] send-emoji* · use-item* · trade*` and `[decision] use-item* · flip* · peek → commit-shot`).
**Claim under attack:** The turn is a clean autoregressive loop that ends at `commit-shot`.
**Why it fails / the risk:** The Kleene stars (`*`) have **no termination bound**. Nothing in the spec stops a policy from emitting `send-emoji` (or `use-item`, if it has stock) **indefinitely**, never reaching `commit-shot`. In human play the **30-second clock** bounds this; the clockless RL env has no such limiter (A-03), so the loop can spin and the episode can hang. A degenerate early policy that just spams the cheapest legal sub-action forever is a *likely* random-init behavior, not a corner case.
**Concrete fix:** Make termination explicit and guaranteed: (i) add the maskable **`end-phase`/STOP** action (A-01) and a **hard per-phase sub-action budget** (the A-03 pseudo-timer); (ii) on budget exhaustion, **force-advance** to `commit-shot` (and apply the guide's timeout fine). The loop must be provably finite per turn before any training runs.

---

## E — Eval validity

### E-01 · Tier 2 · Dimension E
**Target:** Design §5 ("**Primary:** win-rate of latest vs pool… an **Elo / skill curve**").
**Claim under attack:** Elo is a valid primary progress metric.
**Why it fails / the risk:** **Elo assumes transitivity** of skill — and the design *itself* admits the game is RPS-intransitive (§5 "RPS intransitivity"). On cyclic interactions Elo is provably unreliable: the Hodge decomposition separates the transitive component (what Elo captures) from the cyclic component (rock-paper-scissors), and "there is no single dominant strategy" to rank when the cyclic part is large [5]. So a rising Elo curve can reflect **strategy rotation**, not skill gain — exactly the failure the design fears, baked into its **primary** metric. This is further confounded in a **multiplayer (>2)** setting, where pairwise Elo doesn't even cleanly model 5–8-way outcomes.
**Concrete fix:** Demote Elo to a secondary indicator and adopt an intransitivity-aware primary: **Nash averaging / multidimensional Elo (mElo)** over the checkpoint payoff matrix [5], reported alongside the **exploitability probe** (B-04). Track the size of the **cyclic component** explicitly — if it dominates, "improvement" is not well-defined and you should say so rather than show a curve.
**Source:** [5] https://arxiv.org/pdf/1806.02643 (Balduzzi et al., *Re-evaluating Evaluation* — Nash averaging, mElo, Hodge decomposition).

### E-02 · Tier 2 · Dimension E (also G)
**Target:** Design §5 (win-rate as the measured quantity) vs `game_guide.md` setup (dice-rolled chamber + shuffled hidden order + 4–7 opponents).
**Claim under attack:** Win-rate vs checkpoints cleanly measures skill / progress.
**Why it fails / the risk — luck swamps skill at the sample sizes a solo dev will use:** Outcomes are heavily stochastic (random chamber size, random shuffle, who-shoots-whom among 4–7 players). At 5 players the **base win-rate is ~20%**; detecting a *real* improvement of, say, 20%→23% at p<0.05 requires **thousands of games per eval point** (binomial: ~σ≈√(p(1−p)/n); separating 0.20 from 0.23 needs n on the order of 10³–10⁴ *per matchup*). With a pool of K checkpoints and round-robin, eval cost scales ~K² × games — potentially **more compute than training** (compounding G-01). The design budgets **no** eval-game counts, reports **no** confidence intervals, and has **no** variance-reduction plan. A solo dev will be tempted to eval on a few hundred games and read **noise as progress.**
**Concrete fix:** Budget eval explicitly: fix a games-per-matchup count derived from a target detectable effect size with CIs; use **common random numbers** (same seeds/chamber/shuffle across the policies being compared) to cancel luck and slash variance; report every win-rate with a CI and treat overlapping CIs as "no measured change."

### E-03 · Tier 3 · Dimension E
**Target:** Design §5 ("a fixed held-out eval set (**scripted bots** + a frozen reference checkpoint)").
**Claim under attack:** A fixed held-out set of scripted bots + a frozen reference is a sufficient anti-cycling anchor.
**Why it fails / the risk:** Writing a **competent** scripted bot for a hidden-info economy game (when to flip, whom to trade with, when to Beer/Saw, how to read public depletion) is itself a hard, time-consuming subproject — and a **weak** scripted bot makes win-rate-vs-it **saturate near 100% early** and stay there, i.e., it stops being informative precisely when the policy gets good. A single **frozen reference** checkpoint can also be **cycled** (beating it ≠ monotone improvement, per E-01). So the held-out set risks measuring "still beats the easy stuff" rather than "improving."
**Concrete fix:** Use a **ladder** of scripted bots of graded strength (random → greedy → heuristic-economy) so the metric keeps resolving at higher skill, **refresh/extend** the held-out reference set over training (multiple anchors at different eras), and pair it with the exploitability probe (B-04) rather than relying on a single frozen checkpoint.

---

## F — Determinism / engine

### F-01 · Tier 1 · Dimension F (also H)
**Target:** Design §4 ("Deterministic rule engine = single source of truth… **this is where 'true determinism' is actually proven** — not in the markdown") and §6 Stage 0 ("Proves: **Rules are airtight & runnable**").
**Claim under attack:** A full rule **test suite** proves the rules are airtight and the engine is true-to-spec.
**Why it fails / the risk — determinism ≠ correctness; a test cannot resolve an ambiguity:** A test suite can prove **determinism** (same seed → same result) and **conformance to whatever the engine already does**. It **cannot** prove the engine matches the *intended* game, because for any **underspecified** rule the test author must first *pick* an interpretation and then encode it — the test then merely **locks in an arbitrary choice as if it were canonical**. "Airtight" is a property of the **spec**, established by **human design decisions**, not by green tests. The current `game_guide.md` is far better than the version `mechanics_audit.md` saw, but **residual ambiguities remain that still need a decision *before* Stage 0**, each of which the engine cannot resolve on its own:
1. **Placed-token visibility** (Immunity/Handcuffs on a player) — public or private? (A-04) — drives both masking and obs.
2. **Does Beer reveal its discarded shell?** (A-05/C-03) — drives info model and the entire bluff surface.
3. **Loader termination bound** — the "redo the whole roll" reject-resample (guide §Loading) has **no stated iteration cap** and no fallback; a pathological seed could spin (F-02).
4. Minor: confirm a valid in-band integer load **exists** for every living-player count the engine can reach (down to the teams-off 2-player duel).
**Concrete fix:** Convert each residual into an explicit one-line ruling **in `game_guide.md`** *before* writing engine code, then test against the ruling. Rename the Stage-0 success criterion from "rules are airtight" (a spec claim a test can't make) to "**engine is deterministic, seedable, replayable, and conforms to the *resolved* spec**," and keep a short **"resolved ambiguities" changelog** so the locked-in choices are visible, not buried in test code.

### F-02 · Tier 3 · Dimension F — (engine determinism otherwise SURVIVES)
**Target:** `game_guide.md` §Loading the Shotgun / §Chamber & Reloading (accumulate dice until live > living players; redo whole roll if outside 30–70%).
**Claim under attack:** The chamber loader is deterministically implementable from a seed.
**Why it (mostly) holds:** With a single seeded RNG, the dice accumulation, the reject-resample, and the shuffle are all reproducible; given a seed the process terminates almost surely and replays identically. **The core determinism/seedability premise of §4 survives** — this is a genuine strength and the staged "engine first, prove in tests" instinct is right *for the parts that are unambiguous*.
**Residual risk:** "redo the whole roll" is an **unbounded** loop in principle; an adversarial or unlucky seed (e.g., a band that is hard to hit for some N) could iterate many times, which is a (small) reproducibility/throughput wart and an untidy edge for replay logs.
**Concrete fix:** Add a deterministic **iteration cap N_max** with a defined fallback (on the N_max-th failure, clamp live to the nearest in-band integer for the rolled total, or accept the closest-to-band candidate seen). This keeps the loader bounded and fully deterministic without changing the typical-case distribution.

---

## G — Sequencing / scope / runway

### G-01 · Tier 1 · Dimension G
**Target:** Design §4 ("API: PettingZoo **AEC**"), §1 (AlphaStar/OpenAI Five framing), whole-plan compute realism for a **solo, self-funded** dev.
**Claim under attack:** This is a tractable solo project; the method is "the same as AlphaStar / OpenAI Five."
**Why it fails / the risk — the throughput × sample-count × compute product is brutal on a solo budget:**
- **PettingZoo AEC is sequential, single-agent-per-step, pure-Python.** It is **not** vectorizable the way a Parallel/`VectorEnv` is; you cannot trivially batch thousands of envs on a GPU. Episodes are **long** (multi-life, reloads, bonus chains) and **each turn is many sub-actions** (A-01) — so *steps per episode* is large and *episodes per second* on one machine is **low**.
- **Sample demand is huge:** sparse terminal reward + enormous structured action space (B-02) → millions of episodes; **one learner per game** (B-03) multiplies that by N; **eval** can cost as much as training (E-02).
- **The cited precedents ran on thousands of accelerators for months.** Borrowing their *technique* (league/pool self-play) does not borrow their *budget*. A solo dev on 1 GPU faces **weeks of wall-clock per training run × many iteration cycles = months**, plus possible cloud-GPU spend — and that is *if* it learns at all (B-01/B-02).
**Concrete fix:** Re-architect for throughput **before** Stage 2: rewrite the hot path of the engine in a vectorizable form (batched/`numpy`/`jax` or a compiled core; consider a **Parallel** env wrapper rather than AEC for training, keeping AEC only as a reference), profile **steps/sec** early, and set a **hard compute budget** with a go/no-go: if projected episodes-to-signal exceed the budget, **do not start Stage 2**. State target steps/sec and total-episode budget as explicit numbers in the plan.

### G-02 · Tier 2 · Dimension G
**Target:** Design §6 Stage 1 ("Single learner vs scripted/random bots, no comms — Proves: an agent can learn the *mechanics* at all").
**Claim under attack:** Stage 1 is a clean de-risking gate that isolates "can it learn the mechanics."
**Why it fails / the risk:** Stage 1 as written still carries the **full game** — all 6 items, the flip economy, currency sacrifice, 5–8 players, sparse win reward. That is **not** an isolated test of "can it learn mechanics"; it is most of the hard problem (B-02) minus self-play. If Stage 1 stalls, you **cannot tell** whether the blocker is the reward, the action space, the net, or a bug (this is the undebuggability theme — see Verdict). Additionally, the "scripted bots" Stage 1 leans on are a **hidden subproject** (G/E-03): good bots are hard, bad bots teach the learner to beat bad play and then Stage 2 self-play resets that progress.
**Concrete fix:** Insert a **Stage 0.5 / minimal-mechanics** rung *below* Stage 1: e.g., 3 players, **no economy**, 1–2 items, **dense reward**, fixed chamber — the smallest env in which "the net can learn *any* sensible policy" is verifiable in minutes. Climb difficulty one mechanic at a time. Only call it "learns the mechanics" once each mechanic has its own passing rung.

### G-03 · Tier 2 · Dimension G (also B)
**Target:** Design §1 (reward = win/loss + survival nudge) — episode **truncation** policy is unspecified.
**Claim under attack:** (Implicit) episodes terminate cleanly at a winner, so the terminal reward is well-defined.
**Why it fails / the risk:** Cagey or degenerate policies can make a game run **very long** (forced shots are mostly self-blanks farming bonus turns, mutual stalling, broke-stalemate spirals). Real training **must** impose a step/timeout cap — and **how reward is assigned on a truncated episode is undefined and consequential**:
- **Truncate-to-all-loss** poisons the *only* signal you have (B-02): long, hard-fought games — possibly the most informative — get a uniform 0/negative, teaching nothing or teaching "don't get into long games."
- **Truncate-by-survivors / lives** smuggles in **outcome shaping** (rewarding lives/rank) that the design said it would keep **behind a flag** (§1) — so the default reward is secretly shaped.
This interacts directly with the survival-nudge passivity bias (B-05): if truncation pays survivors, passivity is *positively* reinforced.
**Concrete fix:** Define the truncation horizon **and** its reward explicitly. Recommended: bootstrap from the **value function** at truncation (standard PPO time-limit handling) rather than forcing a win/loss, so truncation doesn't inject a spurious terminal signal; and log truncation rate as a health metric (a rising rate = policies learning to stall).

### G-04 · SURVIVES (credit where due) · Dimension G
**Target:** Design §6 (staged plan 0→1→2→3, "each stage delivers standalone value") and §7 (open-risks framed honestly).
**Why it survives — state it plainly:** The **staging is the design's genuine strength** and it is the *correct* de-risking order: build a deterministic, tested engine first; verify single-agent learning *before* paying for self-play; add comms *last*. The explicit "if Stage 1 won't learn, we find out before investing in self-play or comms" is exactly right, and "a working engine + bots has value even if emergent comms never converges" is an honest, motivating fallback. §7's risk register (sparsity is the real danger; comms may stay silent; non-stationarity) shows real self-awareness rather than hype. **Stages 0–1 are achievable and worth building regardless of whether the headline comms goal ever pays off.** The objections above are about the *later* stages' feasibility and the *un-enumerated* schema — not about the sequencing instinct, which is sound.
**Concrete fix:** None to the sequencing. The only addition: make each stage's **go/no-go gate quantitative** (a numeric learning-signal threshold and a compute ceiling per G-01) so "find out before investing" is enforced by a number, not a vibe.

---

## H — Cross-doc contradictions & hidden assumptions

### H-01 · Tier 2 · Dimension H
**Target:** Design §1 ("**Reward is fully individual**… Teams are only a no-shoot constraint… **not** a shared reward") vs §0/§5 goal ("…and (maybe) communicate" / "Test for emergent communication").
**Claim under attack:** The project can hold *both* "reward is fully individual" *and* "study emergent communication" as firm commitments.
**Why it fails / the risk — these two locks are in direct tension:** Emergent, *honest* communication requires some **incentive alignment** between sender and receiver; under fully individual reward in a last-one-wins game that alignment is **absent by construction** (C-01). So the design's **chosen reward** is the **direct cause** of the **near-certain null** for its **stated comms goal**. The design half-acknowledges this (§7 "comms may stay silent") but never names the **self-inflicted** nature of it, and still lists comms as a headline aspiration. You cannot maximize both knobs.
**Concrete fix:** Resolve the contradiction consciously. Either (a) **keep fully-individual reward and demote comms** from "goal" to "instrumented curiosity, expected-null" (and rewrite §0 so the project's success does not depend on it); or (b) **keep comms as a real goal and relax the reward lock** to a *partial within-team coupling during teams-on* (enough to create a signaling incentive) — accepting that this revises §1. Pick one in writing; do not ship both as firm.

### H-02 · Tier 2 · Dimension H
**Target:** Design §1 ("Single-latest opponent cycles rock-paper-scissors; the pool tames it. **Same method as AlphaStar / OpenAI Five**").
**Claim under attack:** Invoking AlphaStar/OpenAI Five validates the approach.
**Why it fails / the risk — the citation justifies one trick, but is leaned on for whole-project feasibility:** The precedent legitimately supports **exactly one** component — sampling **past checkpoints** to stabilize self-play (league/pool play). It does **not** support the implicit inference "therefore this whole plan is feasible." Those projects are **near-perfect-information team games** (or fog-of-war RTS) with **heavy reward shaping** and **industrial compute**; Social Roulette is a **small-N hidden-info social-deduction bluffing** game on a **solo budget** with a **deliberately light reward**. The reference **smuggles in feasibility** it does not actually establish (see B-01 quadrant argument, G-01 compute). A hidden assumption rides along: that techniques validated at OpenAI/DeepMind scale transfer down to a single GPU — they often **do not**, because their results were *partly a function of scale*.
**Concrete fix:** Scope the citation to the pool technique only ("we borrow checkpoint-pool sampling from league play to stabilize self-play"), and **delete the implication** that the overall method/feasibility is precedented. Replace the feasibility argument with the honest one: "unprecedented at this scale/genre; Stages 0–1 are the safe value; Stage 2+ is a research bet."

### H-03 · Tier 3 · Dimension H
**Target:** Design §4 ("Deterministic rule engine = single source of truth for `game_guide.md`") — the assumption that the human ruleset ports 1:1 to RL.
**Claim under attack:** The trained agents are learning to play *Social Roulette* (the human game).
**Why it fails / the risk:** The RL version **necessarily diverges** from the human ruleset in at least the **timer dimension** (A-03): no 30-s/1-min clock, so no clock-pressure, and the timeout-fine rule is replaced by a synthetic sub-action budget (or dropped). The agents therefore learn a **subtly different game** than humans play. This is acceptable, but if left unstated it will be mistaken for "human-game skill," and any future human-vs-agent comparison will be confounded.
**Concrete fix:** Add a short **"RL ruleset deltas"** subsection enumerating every deliberate deviation from `game_guide.md` (timers → action budgets; possibly trade restricted to one-way gifts per A-02; any masking-forced visibility per A-04). Treat that delta list as part of the spec so "plays Social Roulette" is qualified honestly.

---

## Tally

**28 objections + 1 explicit "survives" (G-04); A-06 and F-02 survive with a residual caveat.**

| Tier | Count | IDs |
|---|---|---|
| **Tier 1 — plan/game-breaker** | **6** | A-01, B-01, B-02, C-01, F-01, G-01 |
| **Tier 2 — serious** | **18** | A-02, A-03, A-04, A-05, B-03, B-04, B-05, C-02, C-03, D-01, D-02, D-03, E-01, E-02, G-02, G-03, H-01, H-02 |
| **Tier 3 — minor** | **4** | A-06, E-03, F-02, H-03 |
| **Survives (credit)** | **1 (+2 partial)** | G-04 staging; A-06 masking & F-02 loader survive with caveats |

By dimension: A=6 findings + coverage matrix (A-00), B=5, C=3, D=3, E=3, F=2, G=4, H=3. Dimension A (the most important per the brief) is swept exhaustively in the A-00 matrix: 16 mechanics survive, the rest map to A-01..A-05 / D-01.

---

## Tier-1 PUNCH-LIST — organized by GATE (not all "before any code")

A credible punch-list distinguishes what blocks **Stage 0** from what blocks **Stage 2/3**. Only Gate 1 is "before writing ANY code."

### GATE 1 — Resolve before writing ANY engine code (blocks Stage 0)
1. **Resolve the residual rule ambiguities as written rulings in `game_guide.md`** (F-01): (a) **placed-token visibility** — Immunity/Handcuffs public or private? (A-04); (b) **does Beer reveal its discarded shell?** (A-05/C-03); (c) **loader iteration cap + fallback** (F-02); (d) confirm an in-band load exists for every reachable player count. A test suite *cannot* resolve these — they are design decisions, and "rules are airtight" is a spec claim no green test can make.
2. **Decide how the clock maps to a clockless env** (A-03): replace 30-s/1-min phases + timeout-fine with an explicit **per-phase sub-action budget** and a defined on-exhaustion consequence. This changes the engine's turn API *and* the game being learned — and it is what bounds the autoregressive loop (D-03).
3. **Lock the observation + action schema** (A-01, A-02, D-01) — the §2 "lives-or-dies" deliverable that is currently prose. Must include the four omitted pieces: **flip payment / item-sacrifice choice**, **bilateral trade** mechanism (or an explicit one-way-gift down-scope), the autoregressive **STOP/end-phase token**, and strict **per-seat hidden-info masking** (no opponent inventory/peek in the policy's obs; ship a leak-probe test).

### GATE 2 — Resolve before investing in self-play (blocks Stage 2)
4. **Pick a real method quadrant** (B-01): either adopt a **convergence-driving** self-play core (R-NaD-style regularization / PSRO / fictitious play with a best-response oracle) so RPS-cycling is fought *in the dynamics*, or down-scope ambition and **stop citing AlphaStar/OpenAI Five** (which import compute, not results — H-02).
5. **Do not start from the light-reward default** (B-02): dense diagnostic shaping → anneal to light; add a **Stage 0.5 minimal-mechanics rung** (G-02); consider action-space curricula.
6. **Re-architect for throughput and set a hard compute go/no-go** (G-01): AEC sequential Python won't deliver the episode counts a sparse-reward self-play problem needs on a solo GPU; profile steps/sec, vectorize the engine, and refuse Stage 2 if projected episodes-to-signal exceed budget.
7. **Fix eval validity** (E-01, E-02): intransitivity-aware primary metric (**Nash averaging / mElo**, not Elo) + **exploitability probe** (B-04) + a **statistical-power budget** with CIs and common-random-numbers. Also define **episode-truncation reward** (G-03) and de-bias the **survival nudge** (B-05).

### GATE 3 — Resolve before investing in comms (blocks Stage 3)
8. **Reframe Stage 3 to something falsifiable** (C-01): "mask messages, see if win-rate moves" cannot tell "comms useless" from "training failed." Test the channel's *capacity* with a hard-coded protocol first.
9. **Resolve the individual-reward vs emergent-comms contradiction** (H-01): demote comms to expected-null instrumentation, **or** add partial within-team reward coupling — you cannot maximize both.
10. **Don't train comms against a frozen-mute pool** (C-02): emergence needs co-adapting speakers+listeners. And decide Beer-reveal as a deliberate comms lever (C-03), ensuring the dictionary can express **inventory/intent**, since shell-count bluffing is near-vacuous under perfect-recall nets.

---

## VERDICT

**Is this buildable by a solo dev? Partly — and the honest line is between stages, not across the whole plan.** Stage 0 (a deterministic, seedable, replayable engine for the *now-much-improved* ruleset) and Stage 1 (single-agent learning, ideally with a Stage-0.5 minimal rung and dense shaping) are **genuinely achievable and worth building**, and the **staged, kill-early sequencing is the design's real strength**. The architecture section that the author rightly calls "where it lives or dies," however, is **not yet a spec** — the observation/action schema omits payment, bilateral trade, the STOP token, and per-seat hidden-info masking, and several engine-blocking rule ambiguities still need *decisions* (not tests). Stage 2 sits in an **empty method quadrant**: every imperfect-information self-play success was either massive-compute policy-gradient (AlphaStar — unaffordable solo) or an explicit equilibrium-converging method (CFR / R-NaD — which this design isn't using); vanilla PPO self-play with only an *eval-time* cycling detector has no precedent of success and no force preventing it from rotating strategies forever. Stage 3's emergent-comms headline is, under the project's own fully-individual reward, a **near-determined null that the proposed test can't even interpret.**

**The single thing most likely to kill it is not one wall — it is undebuggability on a slow loop.** Stack sparse 1-in-N terminal reward + an enormous structured action space + hidden information + self-play non-stationarity, and when training won't improve you **cannot attribute the failure** — bug, reward design, undertraining, wrong algorithm class, or info-leak all look identical from the loss curve. Now run each diagnostic cycle through a **sequential Python AEC env on a single GPU**, where one informative experiment is days of wall-clock. **Slow iteration × unattributable failure** is the morale-and-runway killer for a solo, self-funded dev: not that it's provably impossible, but that it can consume months without ever telling you *why* it isn't working. Mitigate by front-loading the cheap, attributable wins (engine + tests + Stage-0.5 dense-reward learning + the leak/exploitability probes), making every stage gate a **number**, and treating Stage 2+ as a research bet with a hard compute stop — not as a promised outcome.


# Social Roulette — Complete Game Guide

## Overview

A social game of deception, alliances, and calculated risk. Players take turns firing a loaded pistol — at themselves or at each other — while managing items, an economy, and shifting team loyalties. **Last player standing wins.** Built for large groups (5+ players). Implemented as a video game (the engine acts as dealer: it hides the chamber, rolls dice, and enforces all rules).

---

## Setup

### 1. Team Assignment
Each player is assigned a team color — **blue** or **red**. You cannot shoot your own teammates. Team color can change mid-game via **flipping** (see Economy).

- **Players: minimum 5**, no hard maximum (8+ recommended for the social layer).
- Teams are split **as balanced as possible.** For odd counts, a coin-flip decides which color gets the extra player (e.g. 5 → 3 vs 2).

### 2. Loading the Pistol
The chamber holds a mix of **live** (bang) and **blank** (click) bullets, sized to the player count:

- Roll two dice repeatedly. Each roll adds its **higher** number to total bullets and its **lower** number to live bullets.
- Keep rolling until **live bullets exceed the (living) player count.**
- The final load must be **30–70% live** (inclusive). If it lands outside the band, redo the whole roll.
- At each load the bullets are shuffled into a **fixed, hidden order.**

> Example (8 players): rolls accumulate to roughly **16–19 total bullets, ~9–11 live**. A fresh chamber always carries more live bullets than living players.

### 3. Item Distribution
Each player rolls a single die **three times** to receive three starting items:

| Roll | Item |
|------|------|
| 1 | Magnet |
| 2 | Shakedown |
| 3 | Geiger |
| 4 | Poison |
| 5 | Passport |
| 6 | Terms |

### 4. Inventory Limits
- Maximum **3 of any single item type.**
- Maximum **8 items total.**
- Any item that would exceed a cap (from a refill or a trade) is **simply not received** — you can never go over.

---

## Cover

- Every player starts with **3 cover**, capped at **5**.
- A live bullet costs the target **1 cover** (2 if Poison is active).
- A player is eliminated at **0 cover**.

---

## The Chamber & Reloading

The chamber reloads whenever it **empties — for any reason.**

### A. The chamber empties (last bullet fired, or Magnet'd away)
- A fresh load is rolled (accumulate until **live > living players**, 30–70% live).
- Every player **draws 2 items**, each rolled on the 1–6 item table, respecting the caps (over-cap items are not received).
- If **Magnet** emptied the chamber, the reload + refill resolve, then the active player **still takes their shot** from the new chamber.

### B. A player is eliminated
- The chamber reloads fresh **"in their honor."**
- The player who landed the killing shot **takes a full extra turn** (talk + trade + items + flip + shoot).
- Play then continues from the **next living seat after the killer**; the dead player leaves the rotation.
- All **item consumption caps reset.**
- **Items are drawn only if the chamber also emptied** (e.g. the kill was the last bullet). A mid-chamber kill just reshuffles — no item draw.
- The dead player's items are **burned.** Of the tokens they had placed on others: their **Terms expires** (it protected them); their **Shakedown stays** (the target still skips).

> `live > players` is guaranteed **only at load.** Magnet can drop live to or below the player count mid-chamber.

---

## Items

Each item is used on your own turn and has both an **effect** and a **point value** (for the economy).

### What Each Item Does

| Item | Effect |
|------|--------|
| **Terms** | Place on one player. They **cannot target you with their next shot.** It expires the **moment they fire that shot** (at anyone, including themselves). If they self-shoot a blank, it expires and they may shoot you on the resulting bonus turn. |
| **Passport** | Restore **1 cover**. **Cannot be used at max cover (5)** — it stays locked in your inventory, taking a slot until you drop below max. (You may instead sacrifice it for points or trade it.) |
| **Geiger** | Peek at the **next 1 bullet**. A second peek at an already-revealed bullet does nothing. |
| **Poison** | Your next shot deals **double damage** (2 cover), including a self-shot (2 self-damage). **If that shot is a blank, the Poison is wasted.** **Max one Poison per turn** (no stacking to 4). |
| **Magnet** | Discard the current bullet and draw the next. **The discarded bullet is removed for good** (the chamber shrinks). Magnet the last bullet → chamber empties → reload → you still take your shot from the new chamber. |
| **Shakedown** | Place on one player — they **skip their next turn.** Only **one Shakedown at a time** per target (a second while one is active does nothing). **Never on a teammate** while teams are active (2026-07-10). |

### Item-Use Rules
- Items are used **only on your own turn** (talk or decision phase, and bonus turns). **No reactive use.**
- **No self-targeting** of placed items (Terms / Shakedown).
- You **may use multiple of the same item in one turn** — e.g. 2 Passports heal 2, 2 Magnets remove 2 bullets — **except Poison (one per turn)**, and you may never place two of the same item on the same target.

### Consumption Limits
- **Limit = the number of living players** (e.g. 8 alive → 8 uses). *(Was ×1.3 — tightened 2026-07-10.)*
- When a cap is hit, **no one** can use that item until a player is eliminated. **A death resets all caps.**
- A "use" is counted the **moment you commit the item** (Poison activated, Terms placed) — even if it later whiffs (Poison on a blank, an untriggered Terms).
- **Sacrificing an item as currency does NOT count** toward its cap.

---

## Economy — Items Are the Currency

Items double as currency. To pay for an action, you **sacrifice items** whose combined point value covers the cost.

| Item | Point Value |
|------|-------------|
| Passport | 6 pts |
| Shakedown | 6 pts |
| Geiger | 5 pts |
| Poison | 5 pts |
| Magnet | 4 pts |
| Terms | 4 pts |

- **No change is given.** If you overpay, the surplus value is **burned.**
- A 5-point action is paid most cleanly with a **Geiger or Poison** (both worth 5).

### Team Flipping

| Action | Cost |
|--------|------|
| Flip any one player's color (blue ↔ red) | **5 pts** |

- You may flip **anyone** — yourself or another player. **Unlimited** flips, as long as you can pay.
- Flips happen **on your own turn.**
- A flip is **not permanent** — the new color holds until someone flips that player again.
- **Flip-back discount:** if your color was flipped by someone else, you may flip back for **4 pts** — but only on your **next turn that you can actually act** (a Shakedown-skipped turn does not consume the window). Pass an actionable turn without using it and the discount is gone.

**Why flip?** It removes the "no shooting teammates" wall. Flip a teammate to enemy color to shoot them; or flip an opponent onto your color to protect them temporarily.

---

## Trade

- Trade items **only with teammates** (same color).
- **No fairness threshold** — any terms you both agree to, including **one-way gifts.** A trade that would exceed a cap is blocked.
- Trades happen **during the talk phase only** (not the decision phase, not bonus turns).

---

## Alliances

- **Cross-team alliances** allowed at any time — informal, verbal, unenforced. Betrayal is always possible.
- Team color is the only **hard** restriction on shooting.

---

## Information & Visibility

| Public — all players see | Hidden |
|---|---|
| Every player's **team color**, and every **flip** (live) | **Who holds which item** |
| Every player's **current cover** | The **order** of bullets in the chamber |
| The **count of each item type in play** (e.g. "5 Passports exist") | |
| Your own cover and full inventory | |

- **Chamber counts (total bullets + live bullets) are announced once, at load — and never updated officially after.** Players track depletion from memory, and may **talk about it publicly, including lying.**
- The bullet **order** is always hidden — Geiger is the only legal peek.

---

## Turn Structure

### Step 1 — First Player & Order
The engine assigns a **random seating order** at match start; the first seat goes first; play proceeds by seat, wrapping. Eliminated players leave the rotation.

### Step 2 — Talking Phase (1 minute)
Talk openly: negotiate, ally, deal, bluff. **Item use AND trades are allowed.**

### Step 3 — Decision Phase (30 seconds)
Silence. Decide your target: **yourself** or **another player**. **Item use and flips are allowed; trades stop.**

> **Timer runs out** with no action taken → you're **fined one item** (your cheapest, random among ties) and given **30 more seconds.** Time out again → fined again. With **no item left to lose, the gun auto self-shoots.**

### Step 4 — Shoot

| Outcome | Result |
|---------|--------|
| Self, **blank** | Survive. Earn a **bonus turn**. |
| Self, **live** | Lose 1 cover (2 if Poison). Turn ends. |
| Other, **blank** | Nothing happens. Turn ends. |
| Other, **live** | Target loses 1 cover (2 if Poison). Turn ends. |

> If you have **no legal target** and **cannot afford a flip**, you **must shoot yourself** — passing is never allowed.

### Bonus Turns
- A **self-blank** earns a bonus turn: **30 seconds, silent.** You **may use items and flip**, but **no talking and no trades.** (A bonus turn = a normal turn minus talk + trade.)
- This holds for **every** bonus turn, including chained ones (keep self-shooting blanks → keep earning 30s silent turns).
- Talking and trading happen **only on a normal turn.**
- **Timeout applies here too:** freeze on a bonus turn → fined your cheapest item + 30s more (no item to lose → auto self-shoot), same as a normal turn.

---

## Win Condition & Endgame

- **Last player standing wins** — a solo win, not a team win.
- **Teams stay ON until fewer than 3 players remain.** At **4+ players**, even if everyone left is one color, the rule holds: a player with no legal enemy can only shoot **themselves** — which pressures them to spend **5 pts to flip** a target and shoot them. Flipping is the endgame's elimination engine.
- **At fewer than 3 players (final 2): teams turn OFF** — free-for-all. Play continues in the same rotation; everyone is a legal target, so flipping becomes moot.

---

## Quick Reference

- **Players:** min 5, no hard max; teams balanced (coin-flip the odd one)
- **Cover:** start 3, max 5, dead at 0
- **Inventory:** ≤ 3 per type, ≤ 8 total; over-cap items not received
- **Chamber load:** accumulate two dice until **live > living players**; 30–70% live; shuffled, hidden order
- **Reload triggers:** chamber empties (→ +2 items each, rolled on the 1–6 table) OR any elimination (→ killer's full extra turn, caps reset; items only if the chamber also emptied)
- **Item caps:** = living players; resets on any elimination; counted on commit; sacrificing is cap-free
- **Multi-use:** same item multiple times/turn OK — except Poison (1/turn) and no double-placing on one target
- **Currency:** items themselves; no change on overpay
- **Flip:** 5 pts, any player, unlimited, your turn; not permanent; 4 pts to flip back (next actionable turn only)
- **Bonus turn:** self-blank → 30s silent (items + flips, no talk/trade); applies to all, incl. chains
- **Timeout:** fined cheapest item + 30s; broke → auto self-shoot
- **Teams off:** < 3 players remain
- **Win:** last player standing

---

## Design Notes (playtest-tuning, not open holes)

- **Scarcity:** at ×1.0 (tightened 2026-07-10 from ×1.3) the use-cap binds sooner — the "items lock → someone must die" loop is meant to bite.
- **Tuning dials:** reload refill amount (2), inventory total cap (8), and the cap multiplier — all adjustable after playtest.
- **Self-shoot viability:** ~57% live makes self-shooting (for a bonus turn) a risky bet; watch whether it goes unused.
- **Two engine defaults I set (change freely):** after a kill, play resumes from the seat *after the killer*; and there is *no hard maximum* player count.

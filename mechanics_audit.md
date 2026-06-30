# Social Roulette — Adversarial Mechanics Audit

**Summary:** An adversarial rules-lawyer pass over `game_guide.md` (the complete ruleset) hunting only for genuinely **unspecified**, internally **contradictory**, or **unhandled-interaction** situations a developer or two players could not resolve from the text. Locked design choices are not re-litigated.

**Total: 33 holes + 6 confirmations.**
- **Tier 1 — Blocks implementation / game-breaking: 3**
- **Tier 2 — Major ambiguity: 16**
- **Tier 3 — Minor / edge case: 14**
- **Confirmations (likely already-answered, list to verify): 6**

Each finding carries: *Title · Rule touched · Concrete scenario · Why it matters · Suggested fix(es).*

---

## Tier 1 — Blocks implementation / game-breaking

These have **no safe default** — the engine cannot render/decide, or the only literal reading is game-breaking.

### T1-1. Information model is completely undefined — especially whether team colors / flips are public
- **Rule:** Overview ("the engine … hides the chamber"); Setup → Team Assignment; Economy → Team Flipping; Lives; Inventory.
- **Scenario:** Player A pays 5 pts to flip Player B from blue to red on A's turn. On C's later turn, C wants to shoot B. **Does C see that B is now red (a legal target)?** Nothing in the doc says whether team color, *or a flip*, is public, private to the flipper, or revealed only to the flipped player. Likewise: can players see each other's **current lives**, each other's **inventories**, or the **count of live/blank shells remaining** in the chamber?
- **Why it matters:** Legal targeting is the single hardest constraint in the game ("you cannot shoot your own teammates"). If color/flip visibility is undefined, a player literally cannot know whom they may shoot, and the engine cannot draw the targeting UI. The whole bluff/economy layer (when to flip, whom to trade with, whom to heal) depends on what is observable. This is the largest single implementation blocker.
- **Fix:** Specify a visibility table. Minimum viable: **team colors and all flips are public** (everyone sees current color); **own lives + own inventory always visible; others' lives visible, others' inventories hidden** (or visible — pick one); **remaining live/blank counts are announced at each load** (Buckshot-style) **or** fully hidden — choose and state it.

### T1-2. "Turn" is never defined relative to **bonus turns** — and a dozen rules hinge on it
- **Rule:** Bonus Turns; Items → "used only on your own turn"; Immunity ("on their turn" / "on that bonus turn"); Handcuffs ("skip their next turn"); Economy → Flipping ("on your own turn") + flip-back ("your very next turn"); Reloading → killer "extra turn."
- **Scenario:** A flips B (B owes a flip-back, discount valid "your very next turn"). On B's next turn B self-shoots a blank and earns a **bonus turn**. (a) Is the bonus turn B's "very next turn" for the 4-pt discount, or must B flip-back during the *normal* turn? (b) A had placed **Handcuffs** on B ("skip next turn") — does the bonus turn count as a "turn" that gets skipped? (c) C placed **Immunity** on B — Immunity is stated to expire when B self-blanks into a bonus turn, so this case is partly covered, but the general "their turn" duration is not.
- **Why it matters:** Different rules want **different** answers, so there is no single safe default. "Items only on your own turn" + "Flips on your own turn" imply bonus turns *do* permit items/flips; but "just decide and shoot" (Bonus Turns) implies they do *not*. Handcuffs and flip-back windows break either way depending on the choice. A developer cannot write the turn loop without one global ruling on whether a bonus turn is a "turn."
- **Fix:** Add a one-line definition: e.g., *"A bonus turn IS a 'turn' for Immunity-expiry, Handcuffs-skip, and flip-back timing, but ONLY the shoot action + listed items are available (no flips, no trades)."* — or the opposite — and state it once, globally. (See also T2-5, T2-7, T2-10.)

### T1-3. Immunity duration — the only stated expiry makes it **permanent one-way immunity**
- **Rule:** Items → Immunity: *"Place on one player. They cannot shoot you on their turn. If they shoot themselves with a blank and earn a bonus turn, the immunity expires."*
- **Scenario:** A places Immunity on B. On B's next turn B shoots **C** (not self) — no self-blank, so the stated expiry does not trigger. B's following turn: B still cannot shoot A. And the turn after. Under the literal text, **B can never shoot A again until B happens to self-blank into a bonus turn** — possibly never.
- **Why it matters:** The text gives exactly one expiry condition (self-blank → bonus). Read literally, Immunity is a permanent, one-directional "you may never shoot me" lock for 6 pts — clearly game-breaking and almost certainly unintended, yet it is the only reading the rules support. The competing intuition ("they cannot shoot you on their turn," singular = one turn) directly contradicts the single-expiry clause.
- **Fix:** State a finite duration explicitly. Most likely intent: Immunity blocks the target from shooting the placer **for the target's next one turn only** (and additionally expires early on a self-blank-bonus). Pick "one turn" vs "until placer's next turn" vs "until consumed by an attempted shot" and write it down.

---

## Tier 2 — Major ambiguity

A reasonable default exists and play can continue, but two players would disagree, or it materially shifts strategy.

### T2-1. Chamber-load algorithm: reroll scope, band-check timing, and termination
- **Rule:** Setup → Loading the Shotgun (and Chamber & Reloading, "same rule").
- **Scenario:** For 8 players the engine rolls (1,6),(1,6),… — each roll adds 1 live / 6 total. After 9 such rolls live=9 (>8, stop condition met) but total=54 → 16.7% live, **below the 30% band**. Doc says "reroll if it falls outside the band." **Reroll what?** Restart the entire accumulation from zero, or re-roll only the last pair? And is the band checked **after every roll** or **only once at the stop**? A streak of doubles can also stop with live just over players at >70%.
- **Why it matters:** The natural min/max ratio averages ~0.57 (matching the doc's "~57% live"), so it usually lands in band — but the tails fall out, and the loader is non-deterministic. Without defined reroll scope + check timing the engine cannot be implemented deterministically, and a naïve "restart on fail" loop has an unbounded (though finite-expectation) worst case.
- **Fix:** Specify: *"Accumulate until live > players; THEN check the 30–70% band; if outside, discard and restart the whole accumulation; cap at N restarts, then clamp to the nearest in-band integer load."* Define `players` as **current living players** at load time.

### T2-2. Inventory-cap overflow on item GAIN (empty-reload refill and trades)
- **Rule:** Setup → Inventory Limits (≤3/type, ≤8 total); Chamber → A ("draws 2 new items … respecting the caps"); Trade.
- **Scenario (refill):** On an empty-chamber reload, B already holds 8 items (incl. a locked Cigarette). B is owed "+2 items." **What happens** — B draws 0? The draws are lost? Re-rolled until they fit? **Scenario (per-type):** B holds 3 Beer; B's refill roll is a 4th Beer — skipped, re-rolled, or converted to points? **Scenario (trade):** A trades B a Beer but B already has 3 Beer — is the trade blocked or does the 4th vanish?
- **Why it matters:** "Respecting the caps" names the constraint but not the resolution. Three different implementations (drop / reroll-into-a-legal-item / block) yield materially different item economies, which feeds directly into the acknowledged scarcity question.
- **Fix:** State one rule for *all* item gains: e.g., *"Any item that would exceed a cap is not received (silently dropped); refills do not reroll. Trades that would breach a cap are illegal and rejected before confirmation."*

### T2-3. Beer on the last shell empties the chamber — does the player still shoot?
- **Rule:** Items → Beer ("Beering the last shell empties the chamber → reload"); Turn Structure → Step 4 (a turn always ends in Shoot); Chamber → A (empty reload refills +2 items each).
- **Scenario:** Decision phase, one shell left. A uses Beer → that shell is discarded → chamber empty → reload triggers. Step 4 says A must Shoot. **Does A now (a) shoot the freshly-reloaded chamber, (b) skip the shot and pass the turn, or (c) something else?** And does the **+2-item refill to every player** resolve **before** A's (possible) shot — so A shoots into a brand-new live-heavy chamber and everyone just got items mid-turn?
- **Why it matters:** Step 4 implies a shot always happens, but Beer can remove the only shell, leaving nothing to fire. The three resolutions differ sharply in danger and in refill timing. Also interacts with T2-1 (the reloaded chamber re-guarantees live > players).
- **Fix:** State: e.g., *"If Beer empties the chamber, the reload (and +2 refill) resolves immediately, then the active player still takes their Step-4 shot from the new chamber"* — or *"…the turn ends with no shot."* Pick one.

### T2-4. Last-shell KILL triggers BOTH reload types at once — refill or not? (contradiction)
- **Rule:** Chamber → A (empty → reload **+ everyone draws 2 items**) vs B (elimination → reload, killer extra turn, caps reset, **explicitly NO item refill**).
- **Scenario:** The chamber's final shell is a live round; A fires it at B; B drops to 0 and is eliminated. Now the chamber is **empty** (trigger A) **and** a player died (trigger B) **simultaneously**. Trigger A says "+2 items to everyone"; trigger B says "no item refill on a death-reload." **Which wins?**
- **Why it matters:** Direct contradiction with real economic stakes (a free +2 items for the whole table or not). It is reachable whenever the killing shot is the last shell — not rare in a small late-game chamber.
- **Fix:** Add a precedence rule: e.g., *"If a shot both empties the chamber and eliminates a player, treat it as a death-reload only (no +2 refill); the single fresh load is rolled in the victim's honor."* (Or the inverse — but state it.)

### T2-5. Which items (and flips) are usable during the silent 30s phases?
- **Rule:** Turn Structure → Step 3 ("Item use is allowed; trades stop") and Bonus Turns ("silent — no talking, no trades. Just decide and shoot"); Item-Use Rules ("talk or decision phase").
- **Scenario:** B is on a **bonus turn**. May B place Handcuffs on C, peek with Magnifier, activate Saw, pay 5 to flip someone, or use Cigarettes? "Decision phase" allows items; the bonus turn is a decision-like silent phase but is described as "just decide and shoot," which reads as *shoot-only*.
- **Why it matters:** Whether the full item/flip suite is live on bonus turns massively changes their power (a chain of self-blanks could become a chain of free flips/handcuffs). Two players will read "just decide and shoot" oppositely.
- **Fix:** Enumerate explicitly which of the 6 items + flipping are permitted on (a) the 30s decision phase and (b) bonus turns. (Resolves jointly with T1-2.)

### T2-6. Self-targeted items vs the "no two of the same item on the same player in one turn" rule
- **Rule:** Item-Use Rules ("cannot use two of the same item on the same player in one turn (applies to every item)"); Beer/Saw/Magnifier/Cigarettes (all self/chamber-directed).
- **Scenario:** A holds 2 Saw — may A use both this turn for **4 damage** (and if allowed, do they even stack, or stay at 2)? A holds 3 Beer — may A Beer away 3 shells in one turn? A at 3 lives holds 2 Cigarettes — may A heal **2** in one turn, or does the rule forbid "two of the same item on the same player (yourself)"? A holds 2 Magnifiers — peek two shells, or is the second blocked / redundant?
- **Why it matters:** The "same player" rule clearly targets *placed* items (Immunity/Handcuffs). For self/chamber items it is undefined whether "the same player" means "yourself," which determines whether double-Saw, multi-Beer, and double-heal are legal — all strong plays.
- **Fix:** Clarify scope: e.g., *"The same-item-same-target limit applies only to items placed on another player (Immunity, Handcuffs). Self/chamber items (Beer, Saw, Magnifier, Cigarettes) may be used multiple times per turn,"* and state whether multiple Saws stack damage.

### T2-7. The killer's "extra turn" — full turn or 30s-silent, and what is the turn order afterward?
- **Rule:** Chamber → B ("The player who landed the killing shot takes an extra turn"); Bonus Turns (defines the *self-blank* bonus as 30s silent — different wording).
- **Scenario:** A kills B and "takes an extra turn." Is that a **full turn** (1-min talk + 30s decision, with trades) or a **30s silent** turn like a self-blank bonus? After A's extra turn ends, does play resume from **the player after A**, or from **the player after the eliminated B**?
- **Edge:** If the kill drops the field from 3 to 2, **teams switch off mid-resolution** (T2-16) — does the killer's extra turn run under teams-on or teams-off rules? Resolve jointly with T2-16.
- **Why it matters:** A full talk-enabled extra turn as a kill reward is a much bigger prize than a silent 30s. And the resume point changes who acts next around the table — core turn-loop behavior.
- **Fix:** State the extra turn's format (recommend: same 30s-silent structure as a bonus turn, or an explicit full turn) and define resumption (recommend: continue from the player after the killer; the dead player is removed from the order).

### T2-8. First-player selection and base turn order
- **Rule:** Turn Structure → Step 1 ("Decide who goes first; play proceeds in order").
- **Scenario:** The video-game engine starts an 8-player match. There is no physical table. **Who goes first, and what is "in order"?** Random? Join order? Seat index? Tie-breaks?
- **Why it matters:** "Decide who goes first" is a tabletop instruction with no analog the engine can execute. Turn order is foundational.
- **Fix:** Define: e.g., *"Engine assigns a random seating order at match start; first player is seat 0; play proceeds by increasing seat index, wrapping."*

### T2-9. Turn order after eliminations
- **Rule:** Turn Structure; Chamber → B (extra turn); Win Condition (eliminations shrink the field).
- **Scenario:** Order is A→B→C→D. C is eliminated on B's turn. Whose turn is next, and is C removed from the rotation cleanly? Combined with the killer's extra turn (T2-7), the resume point is doubly unclear.
- **Why it matters:** Without a stated rule the engine cannot advance turns after any death — and deaths are frequent.
- **Fix:** *"Eliminated players are removed from the rotation; after a normal turn, play passes to the next living seat; after a kill, the killer's extra turn resolves, then play passes to the next living seat after the killer."*

### T2-10. Flip-back 4-pt discount window — which exact turn, and what cancels it?
- **Rule:** Economy → Team Flipping ("flip back for 4 pts … only on your very next turn. Pass the turn without using it and the discount is gone").
- **Scenario:** A flips B on A's turn. (a) B's "very next turn" — does it include a **bonus turn** B earns by self-blanking (see T1-2)? (b) B is **Handcuffed** and *skips* their next turn — does the discount expire (a turn "passed") or carry to B's next *actual* turn? (c) B is flipped by **two** players across two turns — does each grant a fresh 4-pt window, and does flipping back clear both?
- **Why it matters:** The discount is a tight, single-turn economic incentive; whether it survives a skipped turn or a bonus turn changes whether B can ever afford to undo a flip. "Pass the turn" is ambiguous between "a turn elapsed" and "B chose not to act."
- **Fix:** Define "very next turn" precisely (recommend: B's next turn on which B is *able to act*; a Handcuff-skipped turn does **not** consume the window; a bonus turn **does** count). State whether multiple flips stack discounts.

### T2-11. No legal target AND cannot afford a flip — is self-shooting mandatory? Is the broke-stalemate guaranteed to end?
- **Rule:** Win Condition & Endgame ("an active player with no legal enemy can only shoot themselves … pressures them to spend 5 pts to flip"); Turn Structure → Step 4 (always Shoot); Economy (min item value 4 < 5).
- **Scenario:** 4 players, all the same color (teams still on at 4+). Player A's only items total **4 pts** (one Beer) — A **cannot** pay 5 to flip and has no enemy. The rules say A "can only shoot themselves." Is the self-shot **forced**? A self-blanks → bonus turn → still no target → must self-shoot again → … until a live shell costs a life. Across the broke table this repeats until someone dies (caps reset, but no heals if broke), dropping the count toward <3.
- **Why it matters:** The doc asserts "flipping is the endgame's elimination engine" but never states the **forced-self-shoot fallback** for a player who *cannot* flip, nor confirms the spiral provably terminates (it does — lives are finite and unhealed — but it is not stated). Players will dispute whether passing is allowed.
- **Fix:** Add: *"A player with no legal target who cannot or chooses not to flip MUST shoot themselves; passing is never allowed. Because live shells reduce lives and a broke player cannot heal, the all-one-color stalemate is guaranteed to reduce the field until teams switch off (<3)."*

### T2-12. Decision-timer / bonus-timer expiry — the engine's default action is undefined
- **Rule:** Turn Structure → Step 3 (30s decision); Bonus Turns (30s).
- **Scenario:** The 30-second decision timer hits 0 and the player has selected **no** target / taken no action. What does the engine do — **auto self-shoot**, auto-shoot a random legal target, forfeit the shot (turn ends), or something else?
- **Why it matters:** The engine *must* do something deterministic on timeout, and the choices differ wildly in fairness (auto self-shoot at ~57% live is brutal; random-target is hostile; skip breaks the always-shoot structure). This blocks the core turn loop.
- **Fix:** Pick and state a default — recommend *"timeout = automatic self-shot"* (consistent with "can only shoot themselves" and Step 4 always firing), or *"timeout = turn forfeited, no shot."*

### T2-13. An eliminated player's inventory and their *placed* tokens
- **Rule:** Lives (eliminated at 0); Chamber → B; Items → Immunity/Handcuffs; Open Questions (fixed item supply).
- **Scenario:** (a) B is eliminated holding 5 items — are they **discarded**, **redistributed**, or **dropped to a pool**? (b) Earlier A placed **Handcuffs** on C (C will skip C's next turn), then **A is eliminated** before C's skipped turn — does C still skip? (c) A had placed **Immunity** on D; A dies — does D's restriction vanish?
- **Why it matters:** Dead players' items directly affect the "fixed item supply" that the acknowledged scarcity analysis depends on. And whether a placer's death cancels their placed effects is a concrete, reachable dispute the rules don't answer.
- **Fix:** State: e.g., *"An eliminated player's items are removed from the game (burned). Effects they placed on others persist independently of the placer's death."* (Or "expire when the placer dies" — choose.)

### T2-14. Persistence of placed Immunity / Handcuffs across reloads, deaths, and flips (acknowledged-open — enumerate the interactions)
- **Rule:** Open Questions ("Placed Immunity / Handcuffs — exact persistence window not yet pinned"); Chamber → A & B; Economy → Flipping.
- **Scenario:** A Handcuff is on B (skip next turn). Then an **unrelated** player is eliminated → death-reload + **caps reset**. Do the Handcuffs survive (they are not a "cap"), or get wiped by the reset? Separately: Immunity on B, then **B is flipped** to the other color — Immunity is color-independent, so does it persist (likely yes, but unstated)?
- **Why it matters:** The doc flags the window as open; the concrete failure is that "caps reset on death" might be misread as clearing all placed tokens, and flips/reloads have no stated effect on tokens. Reachable every death.
- **Fix:** State that placed tokens are **independent of chamber reloads, cap resets, and flips**, and persist until their own condition resolves (turn skipped / shot attempted / self-blank-bonus per T1-3).

### T2-15. Consumption cap: is "Players" current-alive or starting, and what counts as a "use"?
- **Rule:** Items → Consumption Limits ("Limit = Number of Players × 1.3 … resets on elimination … only actually *using its effect* counts").
- **Scenario:** (a) Game starts at 8 (cap ~10–11). Three players die. Is the cap now `8×1.3` or `5×1.3`? It "resets on elimination," but reset **to what base**? (b) A activates **Saw** and then fires a **blank** — the Saw is wasted with no effect. Does that wasted Saw **count toward Saw's cap**? (c) A places **Immunity** but the target never tries to shoot A — was the "effect" ever "used"?
- **Why it matters:** Whether the base shrinks with the field changes how often the cap binds (the acknowledged scarcity concern). "Only using its effect counts" is fuzzy for items whose effect can whiff (Saw-on-blank) or never trigger (unused Immunity/Handcuffs on a skipped target).
- **Fix:** Define `Players` = **current living players** at the moment of use; and define "use" crisply — recommend *"a use is counted when the item is committed (Saw activated, Immunity placed), regardless of whether it later whiffs."*

### T2-16. The <3-player free-for-all — turn order, bonus turns, and whether flipping/currency still function
- **Rule:** Win Condition & Endgame ("at fewer than 3 players … teams turn OFF — free-for-all").
- **Scenario:** Down to the final 2 (teams off). (a) Whose turn is it and how does order alternate? (b) Do **bonus turns** still apply (nothing turns them off, so presumably yes)? (c) **Flipping** changes team color, but colors no longer matter — can a player still pay 5 to flip (pointlessly), or is flipping disabled? Can items (Immunity/Handcuffs) still be placed?
- **Why it matters:** The endgame is where the winner is decided; "free-for-all" is named but its turn mechanics are not specified. Whether flipping is a no-op or disabled affects what a player can spend points on in the final duel.
- **Fix:** State: *"At <3 players, teams are off; turn order continues in the existing rotation among survivors; bonus turns and all items remain active; flipping has no effect on legality (everyone is a legal target) and may be treated as disabled."*

---

## Tier 3 — Minor / edge case

### T3-1. Chamber must be confirmed an **ordered queue fixed at load**
- **Rule:** Items → Magnifier ("peek the next 1 shell"), Beer ("discard the current shell and draw the next").
- **Scenario:** Magnifier reveals "the next shell" and Beer discards "the current" and advances to "the next" — both presuppose a **determined sequence**. The load rules fix only *counts* (live/blank), never that the sequence is shuffled and locked.
- **Why it matters:** Magnifier and Beer are only coherent if there is a fixed next shell; if the engine resolves live/blank lazily at fire time, "peek" and "discard the current" are meaningless.
- **Fix:** State: *"At each load the engine shuffles the shells into a fixed ordered queue; Magnifier reveals queue position 1; Beer removes position 1 and advances."*

### T3-2. Magnifier peek voided by Beer (scout-then-dodge) — legal, and what does the new shell show?
- **Rule:** Magnifier; Beer.
- **Scenario:** A peeks the current shell = **live**, then uses Beer to discard it. The peeked info is now void and the new current shell is unknown. Is this "scout, then dodge a live round" combo intended/legal, and does it reveal nothing about the replacement?
- **Why it matters:** It's a strong, probably-intended combo, but the rules never confirm Beer can remove the very shell Magnifier peeked, nor that the new shell stays hidden.
- **Fix:** Confirm: *"Magnifier and Beer reference the same 'current/next' shell; Beering a peeked shell is legal and the replacement is unrevealed."*

### T3-3. Self-targeting Immunity / Handcuffs
- **Rule:** Immunity / Handcuffs ("Place on one player").
- **Scenario:** A places **Immunity on A** — literal text "they cannot shoot you" ⇒ A cannot shoot A ⇒ A can't self-shoot. A places **Handcuffs on A** — A skips their own next turn. Are self-placements legal?
- **Why it matters:** Self-Immunity producing a self-shoot ban is an absurd but literal outcome; "one player" doesn't exclude oneself.
- **Fix:** State whether placed items may target the placer (recommend: **no** for Immunity/Handcuffs).

### T3-4. Cross-turn stacking of placed tokens
- **Rule:** Item-Use Rules (only *same-turn* same-target double-use is banned).
- **Scenario:** A Handcuffs B on turn 1; C Handcuffs B on turn 2 — does B skip **two** turns? A re-places Immunity on B on consecutive turns — does it refresh or stack a duration (which is itself undefined, T1-3)?
- **Why it matters:** The same-turn ban doesn't address cross-turn accumulation; double-skip is a real possibility.
- **Fix:** State whether placed effects stack across turns (recommend: Handcuffs queue/stack into consecutive skips; Immunity does not stack).

### T3-5. Minimum and maximum player count
- **Rule:** Overview ("Built for large groups (8+)"); Win Condition ("teams off at <3").
- **Scenario:** Can a match **start** with fewer than 8 (is 8 a hard floor or a recommendation)? Is there an **upper** bound? The engine min to keep running is 2 (then 1 wins).
- **Why it matters:** Setup needs a hard min/max to size lobbies; "8+" is ambiguous between requirement and guidance.
- **Fix:** State a hard minimum to start and a maximum (or "no max").

### T3-6. Team-assignment method and odd-count split *(acknowledged open)*
- **Rule:** Setup → Team Assignment; Open Questions ("team split for odd player counts — undecided").
- **Scenario:** 8 players → 4/4? Random or balanced? 7 or 9 players → 4/3, 5/4? Undecided.
- **Why it matters:** Engine must assign colors at setup deterministically.
- **Fix:** Define the split rule (recommend balanced, random tie-break for odd counts).

### T3-7. Consumption-cap rounding *(acknowledged open)*
- **Rule:** Open Questions ("Players × 1.3 is non-integer — floor/round/ceil?").
- **Scenario:** 8 players → 10.4 uses → cap 10 (floor/round) or 11 (ceil)?
- **Why it matters:** Determines the exact cap integer per item.
- **Fix:** Pick floor, round, or ceil and state it.

### T3-8. Saw on a self-shot — double self-damage? *(acknowledged open)*
- **Rule:** Items → Saw; Open Questions ("Saw on a self-shot … undecided").
- **Scenario:** A activates Saw, self-shoots a live round — lose **2** lives, or does Saw not apply to self-shots?
- **Why it matters:** Determines a (niche) self-damage value and whether the engine even allows the combo.
- **Fix:** Decide (recommend: Saw applies to any shot, including self ⇒ 2 self-damage).

### T3-9. Simultaneous mutual last-two death / no draw rule
- **Rule:** Win Condition ("Last player standing wins — a solo win").
- **Scenario:** Can the final two die "at the same time"? Turn-based play fires one shot at one target, so deaths are strictly sequential — a true simultaneous mutual kill appears **structurally unreachable**. But the rules define **no draw/tie** outcome if one ever arose.
- **Why it matters:** Likely a non-issue, but the win logic has no tie branch; worth confirming none can occur.
- **Fix:** Add a one-liner: *"Deaths resolve one at a time; if any simultaneous-elimination edge ever arises, [tie-break rule]."*

### T3-10. Band inclusivity and "live > players" strictness on each reload
- **Rule:** Loading the Shotgun; Chamber & Reloading.
- **Scenario:** Is 70.0% live in-band (inclusive)? Is the stop strictly `live > players` (so 2 players ⇒ ≥3 live, total ≥5)? Is `players` re-evaluated to the living count on each mid-game reload?
- **Why it matters:** Minor boundary cases in the loader; small chambers late game carry many shells per player.
- **Fix:** State inclusivity (recommend inclusive 30–70%) and that `players` = current living count.

### T3-11. Empty-reload refill — which items, and by what mechanism?
- **Rule:** Chamber → A ("draws 2 new items").
- **Scenario:** Are the +2 items rolled on the **same 1–6 table** as setup, or drawn from some pool? The doc never says how refill item *types* are determined.
- **Why it matters:** Affects item distribution and the fixed-supply scarcity question; engine needs a concrete draw method.
- **Fix:** State: *"Refill items are rolled on the 1–6 item table, subject to caps (see T2-2)."*

### T3-12. No stated upper bound on items/flips per turn
- **Rule:** Turn Structure; Economy → Flipping ("Unlimited flips, as long as you can pay").
- **Scenario:** In one turn A could Magnify + Saw + Beer + place Immunity on B + place Handcuffs on C + flip three players (if A can pay) + shoot. Is such a turn intended, or is there an action budget?
- **Why it matters:** Flips are explicitly unlimited; combined with no per-turn item ceiling, a single turn can be very swingy. Probably intended, but unbounded.
- **Fix:** Confirm "no per-turn action cap beyond payment and the same-item-same-target rule," or add one.

### T3-13. Beer can drop live ≤ players mid-chamber (invariant holds only at load)
- **Rule:** Loading ("live > players"); Beer ("the discarded shell is removed for good").
- **Scenario:** A Beers away several live shells; the live count falls **at or below** the player count mid-chamber. The "live > players" guarantee is a *load-time* property only.
- **Why it matters:** Players may wrongly assume the chamber always has live > players. Likely intended (Beer is a risk-reducer), but worth stating.
- **Fix:** Note explicitly that `live > players` is guaranteed **only at load**; Beer may reduce live below that mid-chamber.

### T3-14. Trade "any terms" — gifts and non-item terms
- **Rule:** Trade ("any terms you both agree to").
- **Scenario:** May a teammate **gift** an item for nothing (one-sided trade)? May terms include **non-item promises** (e.g., "I'll flip X next turn")? The engine can only enforce item-for-item.
- **Why it matters:** Minor, but the engine's trade UI must decide whether a 0-for-1 transfer is allowed; verbal promises are unenforceable anyway.
- **Fix:** State: *"Trades may include one-sided item gifts; only item transfers are engine-enforced; verbal side-deals are unenforced (per Alliances)."*

---

## Confirmations — likely already answered, verify and make explicit

These read as resolved in the text; listed so they're consciously confirmed rather than assumed.

- **C-1 — No trades on bonus turns.** Bonus Turns state "no trades," Trade states "talk phase only." Consistent ⇒ confirm: trades are impossible on bonus turns and in the decision phase.
- **C-2 — Same item on *different* targets, same turn, is allowed.** Item-Use Rules ban only *same-target* same-turn double-use ⇒ confirm A may place Immunity on B *and* Immunity on C in one turn.
- **C-3 — Flips don't touch inventory.** Flipping changes only color, adds no items ⇒ confirm a flip can never push a target over inventory caps (non-issue).
- **C-4 — `live > players` is re-guaranteed on every reload.** Both reload paths use the load rule ⇒ confirm each fresh chamber restarts with live > current players (always more live than living players at load).
- **C-5 — Self-elimination grants no extra turn.** A self-shoots live at 1 life and dies; "the player who landed the killing shot takes an extra turn" — but that player is dead ⇒ confirm no extra turn on self-elimination; reload proceeds, next living player acts.
- **C-6 — Sacrificing for currency never counts toward the use-cap.** Consumption Limits state only "using its effect" counts ⇒ confirm sacrificing items to pay (flips, actions) is cap-free.

---

## Open-Question Checklist (walk through one by one)

**Tier 1**
1. **Visibility model:** Are team colors and flips **public**? Are others' lives / inventories / remaining shell counts visible? (T1-1)
2. **Does a "turn" include a bonus turn** for Immunity, Handcuffs, flip-back, item-use, and flip rights? (T1-2)
3. **Immunity duration:** how long does "they cannot shoot you" last beyond the self-blank-bonus expiry? (T1-3)

**Tier 2**
4. Chamber loader: reroll scope (restart vs last roll), band-check timing, `players`=living, iteration cap. (T2-1)
5. Item-gain overflow (refill + trade): drop / reroll / block on exceeding caps? (T2-2)
6. Beer empties chamber: does the player still shoot, and when does the +2 refill resolve? (T2-3)
7. Last-shell **kill**: empty-reload (+2 items) vs death-reload (no items) — which wins? (T2-4)
8. Which items/flips are usable in the 30s decision phase and on bonus turns? (T2-5)
9. Self/chamber items vs "no two same-item same-target": legal to use 2 Saw / 2 Beer / 2 Cigarettes / 2 Magnifier per turn? Do Saws stack? (T2-6)
10. Killer's "extra turn": full turn or 30s-silent? Turn order resumes from where? (T2-7)
11. First-player selection and base turn order. (T2-8)
12. Turn order after an elimination. (T2-9)
13. Flip-back 4-pt window: counts a bonus turn? survives a Handcuff-skip? multiple flippers? (T2-10)
14. No legal target + can't afford flip: is self-shoot mandatory and is the broke stalemate's termination stated? (T2-11)
15. Decision-/bonus-timer expiry: engine's default action? (T2-12)
16. Dead player's inventory disposition; do a dead placer's placed tokens persist? (T2-13)
17. Placed-token persistence across reloads / cap-resets / flips. (T2-14)
18. Consumption cap: `Players`=living or starting; what counts as a "use" (wasted Saw, untriggered Immunity)? (T2-15)
19. <3-player free-for-all: turn order, bonus turns, is flipping disabled? (T2-16)

**Tier 3**
20. Confirm chamber is a fixed ordered queue shuffled at load. (T3-1)
21. Magnifier→Beer scout-then-dodge: legal; replacement unrevealed? (T3-2)
22. May placed items target the placer (self-Immunity / self-Handcuffs)? (T3-3)
23. Cross-turn stacking of Handcuffs / Immunity? (T3-4)
24. Hard min/max player count to start. (T3-5)
25. Team-assignment method + odd-count split. (T3-6)
26. Consumption-cap rounding: floor/round/ceil. (T3-7)
27. Saw on a self-shot: 2 self-damage or disallowed? (T3-8)
28. Draw/tie outcome — confirm structurally unreachable. (T3-9)
29. Band inclusivity; strict `live > players`; per-reload `players`=living. (T3-10)
30. Refill item types rolled on the 1–6 table? (T3-11)
31. Any per-turn action/item budget beyond payment + same-target rule? (T3-12)
32. Note `live > players` is a load-time-only invariant (Beer can break it). (T3-13)
33. Trade gifts / non-item terms: allowed and enforceable? (T3-14)

**Confirmations**
- C-1 No trades on bonus turns · C-2 Same item, different targets, allowed · C-3 Flips don't touch inventory · C-4 `live>players` re-guaranteed each reload · C-5 No extra turn on self-elimination · C-6 Sacrificing is cap-free.

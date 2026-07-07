# Rules Fidelity Audit — `game_guide.md` vs engine vs online product

**Date:** 2026-07-06 · **Trigger:** user verdict: UI not good, "you keep missing details about the rules that are critical", promised process animations (dice rolls etc.) never shipped. This audit is Phase 1 of the full UI redesign (Phase 2 = motion/look mockup, Phase 3 = build to ratified contract).

**Method:** full line-by-line read of `game_guide.md` (228 lines) + ALL engine files (564 LOC) + online `room/view/server` + `static/` UI. Every rule row cites guide line + code location.

**Legend:** ✅ correct · ⚠ partial/edge-case/cosmetic · ❌ missing or wrong · — not applicable to that layer

---

## 1 · Setup

| # | Rule (guide) | Engine | UI shows it? |
|---|---|---|---|
| S1 | Teams balanced, coin-flip decides odd extra (:15) | ✅ `engine.py:79-84` | ❌ no coin-flip moment; teams just appear |
| S2 | Min 5 players (:14) | ✅ `engine.py:77` | ✅ bots fill to 5 |
| S3 | Load = two dice; higher→total, lower→live; until live > living (:20-21) | ✅ `chamber.py:9-12` | ❌ **no dice animation — the "dealer ceremony" (guide:5) is invisible; text-only "LOADING CHAMBER"** |
| S4 | Load must be 30–70% live inclusive, else redo whole roll (:22) | ✅ `chamber.py:13` (20k-load test: 0 violations) | — (hidden by design) |
| S5 | Shells shuffled into fixed hidden order (:23) | ✅ `chamber.py:14-15` | ✅ never serialized |
| S6 | Each player rolls 1d6 ×3 for starting items (:28-37) | ✅ `engine.py:88-91` | ❌ no deal/roll moment; cards just appear |
| S7 | Inventory caps: ≤3/type, ≤8 total; over-cap simply not received (:40-42) | ✅ `state.py:79-80`, `reload.py:11`, trade `engine.py:123` | ❌ caps never shown; a swallowed over-cap draw is silent |

## 2 · Lives & Shooting

| # | Rule | Engine | UI |
|---|---|---|---|
| L1 | Start 3, cap 5, dead at 0 (:46-50) | ✅ `constants.py:41-42`, `engine.py:50-51` | ✅ pips |
| L2 | Live = 1 damage, 2 with Saw, incl. self (:49, :86) | ✅ `shooting.py:10-12` | ⚠ damage shown only as pip-drop; no "-1"/"-2" moment |
| L3 | Self-blank → bonus turn (:181, :189) | ✅ `shooting.py:16`, `engine.py:68-70` | ❌ **bonus turn invisible** — no "BONUS" indicator; looks like a stuck turn |
| L4 | No legal target + can't afford flip → must self-shoot; pass never allowed (:186) | ✅ self always in `legal_targets` (`endgame.py:15`), no pass action exists | ⚠ the "why can I only shoot myself" moment is unexplained |

## 3 · Chamber & Reload

| # | Rule | Engine | UI |
|---|---|---|---|
| C1 | Reload whenever chamber empties, any reason (:56) | ✅ `engine.py:66-67`, `engine.py:106-107` | ⚠ toast only; no cylinder-refill motion |
| C2 | Empty-reload → everyone draws 2 (caps respected) (:58-60) | ✅ `reload.py:15-17` | ❌ **hand updates silently — no "you drew X, Y" moment** (spec promised "cards fly out") |
| C3 | Beer empties chamber → reload resolves, active player still shoots (:61) | ✅ Beer never advances turn | ✅ (R3 fix: re-announce after beer-empty) |
| C4 | Kill → chamber reloads "in their honor" (:63-64) | ✅ `engine.py:53` | ⚠ indistinct from any other reload |
| C5 | Killer takes a full extra turn (:65) | ✅ `engine.py:61-64` | ❌ **extra turn unexplained** — dot stays on killer, reads as a bug |
| C6 | After killer's turn, play continues from next living after killer (:66) | ✅ `_advance_turn` from shooter | ✅ dot |
| C7 | Death resets all consumption caps (:67) | ✅ `reload.py:20-22` | ❌ caps invisible anyway |
| C8 | Items drawn on kill ONLY if chamber also emptied (:68) | ✅ `engine.py:54-55` | ❌ same silent-draw problem |
| C9 | Dead player's items burned; their placed Immunity expires; their placed Handcuffs stays (:69) | ⚠ inventory kept on corpse (harmless engine-side) · handcuff stays ✅ · stale `immunity_against` entries naming a dead caster persist | ❌ **two real bugs: (a) `view.py:48-51` counts DEAD players' burned items into public `item_counts`; (b) stale "P✝M" immunity tag persists on the wearer until they next shoot** |

## 4 · Items

| # | Rule | Engine | UI |
|---|---|---|---|
| I1 | Immunity: target can't shoot caster; expires the moment target fires at anyone; self-blank → may shoot caster on bonus (:83) | ✅ `items.py:50-55`, `endgame.py:17`, `shooting.py:15` | ✅ "P3M" tag (R2) — minus the stale-tag bug (C9) |
| I2 | Cigarettes: +1 life, locked at max 5 (:84) | ✅ `items.py:28-33`, gated `actions.py:68-70` | ⚠ lock never explained (item just missing from menu) |
| I3 | Magnifier: peek next 1 shell; re-peek adds nothing (:85) | ✅ `items.py:34-36` | ✅ own-only "NEXT SHELL: …" |
| I4 | Saw: next shot ×2 incl self; wasted on blank; max ONE per turn (:86) | ✅ `items.py:37-43`, `shooting.py:11,14`, reset `engine.py:14` | ❌ **saw-armed state invisible** — nothing shows the next shot is ×2 |
| I5 | Beer: shell removed for good, chamber shrinks (:87) | ✅ `items.py:44-49` | ✅ "SHELL OUT" toast (R3) |
| I6 | Handcuffs: skip next turn; one at a time per target (:88) | ✅ `items.py:56-64`, skip `engine.py:22-26` | ⚠ "HELD" shows; the actual SKIP moment isn't shown (turn silently passes over) |
| I7 | Items only on own turn, no reactive use (:91) | ✅ Room gates `seat == current_id` | ✅ |
| I8 | No self-targeting placed items (:92) | ✅ `items.py:51,57` | ✅ (self-seat not targetable) |
| I9 | Multiple same item per turn OK, EXCEPT Saw; never two of the same item on the same target (:93) | ⚠ **gap: a 2nd Immunity by the same caster on the same target is offered + consumed as a wasted no-op (`actions.py:76-78` doesn't check `immunity_against`); guide says it must not be placeable** (Handcuffs correctly blocked) | ❌ nothing warns |
| I10 | Consumption cap floor(living×1.3); nobody can use that item until a death; commit-counted incl whiffs; sacrifice cap-free (:96-99) | ✅ `items.py:7-23`, `engine.py:103-104`, `economy.py` never touches counts | ❌ **caps completely invisible** (public info — "no one can use X now" is a game-state everyone should see) |

## 5 · Economy, Flip, Trade

| # | Rule | Engine | UI |
|---|---|---|---|
| E1 | Point values 6/6/5/5/4/4 (:108-115) | ✅ `constants.py:23-30` | ✅ payment picker shows them |
| E2 | No change; overpay burned (:117) | ✅ `economy.py:5-17` | ✅ picker total ≥ cost |
| E3 | Flip: 5 pts, anyone incl self, unlimited, own turn, not permanent (:122-128) | ✅ `economy.py:20-28`, `actions.py:83-86` | ✅ picker (R3) |
| E4 | Flip-back discount: 4 pts, only your next ACTIONABLE turn; handcuff-skip doesn't consume window (:129) | ✅ `economy.py:27-28`, cleared in `_advance_turn` (`engine.py:35`), skip path doesn't touch it (`engine.py:22-26`) · ⚠ edge: discount survives being flipped BACK by a third party | ⚠ cost 4 appears in picker but the discount/window is never announced or explained |
| E5 | Trade: teammates only, any terms incl gifts, cap-blocked, TALK PHASE only (:136-139) | ⚠ Trade action EXISTS (`actions.py:95-100`, `engine.py:118-132`) but **`social_enabled=False` in Room (`room.py:46`) → absent from the product** | ❌ **no trade UI at all** |

## 6 · Information & Visibility

| # | Rule | Engine/server | UI |
|---|---|---|---|
| V1 | Public: team colors + every flip, live (:154) | ✅ view + flip events | ✅ |
| V2 | Public: lives (:155) | ✅ | ✅ pips |
| V3 | **Public: count of each item type in play** (:156) | ⚠ computed + SENT (`view.py:48-51`) but counts dead players' burned items (bug, see C9) | ❌ **NEVER RENDERED — public information the guide grants is withheld from players** |
| V4 | Own lives + full inventory (:157) | ✅ | ✅ hand cards |
| V5 | Hidden: who holds which item (:154) | ✅ only own hand serialized | ✅ |
| V6 | Chamber counts announced ONCE at load, never updated (:159) | ✅ announce/reload events only (R2) | ✅ 5s toast |
| V7 | Shell order always hidden; Magnifier the only peek (:160) | ✅ | ✅ |

## 7 · Turn Structure — **the biggest block: the SOCIAL layer is absent**

| # | Rule | Engine | UI/product |
|---|---|---|---|
| T1 | Random seating; first seat starts; wrap; dead leave rotation (:166-167) | ✅ `engine.py:93-96`, `engine.py:52` | ⚠ intentional divergence: order rotated so the human starts (`room.py:47-55`) — keep? |
| T2 | **Talking phase, 1 min: talk + items + trades (:169-170)** | ❌ no phases anywhere | ❌ chat exists but ungated, untimed, phase-less |
| T3 | **Decision phase, 30 s: silent; items + flips; trades stop (:172-173)** | ❌ | ❌ |
| T4 | **Timeout → fined cheapest item (random among ties) + 30 s more; no items left → auto self-shoot (:175, :192)** | ❌ no timers, no fines, no auto-shoot | ❌ a human can stall the game forever |
| T5 | Bonus turn = 30 s, SILENT, items + flips, no talk/trade, chains too (:189-192) | ⚠ bonus exists + trade/speak correctly blocked (`actions.py:87,95`); no timer/silence | ❌ invisible (L3) |
| T6 | Killer's extra turn is FULL (talk + trade + items + flip + shoot) (:65) | ⚠ turn granted; "full" meaningless until phases exist | ❌ |

## 8 · Endgame

| # | Rule | Engine | UI |
|---|---|---|---|
| G1 | Last standing wins, solo (:198) | ✅ `endgame.py:8-10` | ✅ winner banner |
| G2 | Teams ON until <3 alive; all-one-color at 4+ still binds (flip = elimination engine) (:199) | ✅ `endgame.py:4-5,19-20` | ⚠ the "flip someone to shoot them" pressure is never surfaced |
| G3 | Final 2: teams OFF, free-for-all (:200) | ✅ `teams_active` False | ❌ **teams-off moment invisible** — forms still show ●/○ as if teams matter |

---

## TOP GAPS (ranked by product impact)

1. **T2-T4 — the social core is missing.** Talk phase, decision phase, timers, timeout-fines, auto self-shoot: the entire Turn Structure section. Chat is a free-floating text box. For a SOCIAL deduction game this is the game.
2. **Dealer ceremony has no body (S1, S3, S6, C1-C2).** Guide:5: *"the engine acts as dealer: it hides the chamber, rolls dice, enforces rules."* Every dealer moment (dice accumulation, coin-flip, shuffle, card deal/draw) is a text label today. This is the repeatedly-requested animation gap.
3. **E5 — Trade disabled.** Engine supports it; product hides it. Teammate gifting is a core social lever.
4. **V3 — public item counts withheld** (+ counts corpse items: `view.py:48-51` bug).
5. **State moments invisible:** bonus turn (L3), killer extra turn (C5), saw armed (I4), teams-off (G3), handcuff skip (I6), item-draw results (C2), flip-back window (E4), consumption caps (I10).
6. **C9 — stale immunity tag** from a dead caster persists on the wearer (UI bug).
7. **I9 — engine gap:** 2nd Immunity same-caster→same-target must be illegal, currently a consumed no-op.

## Design decisions Phase 2 must answer (user calls)

| # | Question | Options sketch |
|---|---|---|
| D1 | Real timers online? | full guide timers (1min/30s/fines) · shortened · host-configurable · none-for-bots-only |
| D2 | Trade UI in v2? | yes (talk-phase only, needs phases) · defer |
| D3 | Keep human-always-first divergence (T1)? | keep · true random first seat |
| D4 | Aesthetic reset | stays pure-B&W? richer motion within B&W? new direction entirely? |
| D5 | #3b remaining-shell visibility | A hidden (guide-faithful, current) · B remaining count · C next-shell-exists |

**Next:** Phase 2 — motion + look mockup playing EVERY moment above on fake data; each moment ratified visually before build. Phase 3 — build to that contract (fix engine gap I9 + view bugs C9/V3 along the way).

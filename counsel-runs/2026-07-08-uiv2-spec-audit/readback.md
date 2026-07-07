# COUNSEL JOURNAL — aspect: UI v2 design-spec fidelity: rules coverage, code-reality feasibility, audit closure, internal consistency
counts: steps 10 · records 31 · sources 0 · gaps 3

## GROUNDED — 31
- [a1] (finding, high, step 6) M17's over-cap bounce is unbuildable as specified: the engine silently discards an over-cap draw without recording the attempted item, no draw event type exists anywhere, and the spec's only new event types are fine and trade — no engine/room change to expose attempted draws is listed in section 5 or 4.6.
    evidence C2 @ section 7, M17 row (line 249): "Your 2 draws: die tumble → icon slides into KIT with name; **over-cap: the icon bounces off the KIT with "FULL"** (the silently-swallowed draw becomes visible)"
    evidence C12 @ reload.py:10-12 draw_items_for_all: "item = ITEM_TABLE[state.rng.randint(1, 6)]
            if can_receive(p, item):
                p.inventory[item] = p.inventory.get(item, 0) + 1"
    evidence C2 @ section 4.6 (line 159): "New event types: `fine`, `trade`."
    evidence C20 @ events.py:10-20 full event-type list: "MATCH_START = "match_start"
TURN_START = "turn_start"
ITEM_USED = "item_used"
FLIP = "flip"
SHOT = "shot"
BONUS = "bonus"
ELIMINATION = "elimination"
RELOAD = "reload""
    caveat: Same failure class as the user-caught inventory-cap miss: a promised cap-visibility moment with no producer
- [a2] (finding, medium, step 9) M17's successful-draw reveal ('icon slides into KIT with name') also lacks a per-seat data source: the client receives only the event delta plus the FINAL view, so the drawn items must be recovered by diffing your_hand across the whole delta — a diff that cannot attribute items when the same delta contains the human's own item uses or more than one reload; no per-seat draw enrichment is listed as new work.
    evidence C15 @ room.py:97-98 apply(): "self._run_bots()
        self.last_events = [_anim(r) for r in self.rec.rows[n0:]]"
    evidence C15 @ room.py:25 _ANIM_KEYS: "_ANIM_KEYS = ("type", "actor", "target", "shell", "damage", "killed", "item")"
    evidence C2 @ section 11 build step 3: "Protocol: view fields, `proceed`/`trade` messages, per-seat event enrichment, roster + tests."
    caveat: In the common single-reload case a hand diff works; the failure is in multi-reload or use+reload deltas
- [a3] (finding, high, step 9) The setup ceremony's named data source does not exist online: section 7 sources M1-M5 'from match_start', but Room never emits match_start into last_events (its opening delta is a single announce event), the _anim filter strips the extra payload (which is where match_start carries players/teams/inventories) for every type except reload, and no work item adds match_start to the online stream.
    evidence C2 @ section 7, setup ceremony header (line 224): "**Setup ceremony** (from `match_start`, cosmetic replay):"
    evidence C15 @ room.py:64-66 __init__: "self._run_bots()               # no-op when a human leads; else auto-plays leading bots
        # the first view carries only the public opening announce (game_guide:159 "announced at load").
        self.last_events = [self._announce()]"
    evidence C15 @ room.py:31-34 _anim: "if row["type"] == "reload":
        ex = json.loads(row["extra"]) if row.get("extra") else {}
        return {"type": "reload", "total": ex.get("new_total"), "live": ex.get("new_live")}
    return {k: row[k] for k in _ANIM_KEYS if k in ("type", "actor") or row.get(k) is not None}"
    caveat: M1/M3/M4 data is DERIVABLE from the first view (players/teams, your_hand) + the announce event, so the ceremony is salvageable — but the spec's stated mechanism is wrong and the required client derivation or new emission is unstated
- [a4] (risk, high, step 8) Clock-fairness defect: server-side phase deadlines (phase_ends_at, wall epoch) start when the Room transition runs, but the client replays the preceding event cascade sequentially (dice ceremony M2, reloads M16, multi-bot turn chains) before the human can even see their phase — the spec never specifies when phase_ends_at is anchored relative to cascade replay, so long cascades silently consume the human's 60s/30s windows and can push a slow-to-watch player into fines.
    evidence C2 @ section 4.3, bullet 3: "Client renders the countdown from `phase_ends_at` + `server_now` (clock-offset corrected);
  it never enforces anything."
    evidence C2 @ section 4.1, bullet 3: "**Bot turns have no phases or timers** — they resolve at the animation cascade's pace. Timers
  exist to bound *human* stalling; bots never stall."
    evidence C15 @ room.py:156-160 _run_bots: "def _run_bots(self):
        while self.state.winner is None and self.is_bot(self.state.current_id):
            self._turn += 1
            take_policy_turn(self.state, self.state.current_id, random_policy, self.extras,
                             rec=self.rec, turn_idx=self._turn)"
    caveat: Tap-to-skip mitigates but does not bound the loss; a fix needs an explicit rule (e.g. schedule the deadline with a cascade-duration grace, or start the phase on client ack)
- [a5] (finding, high, step 5) Trade settlement is not atomic as specified: the engine's Trade step silently skips any item the receiver cannot receive instead of failing, so applying a SWAP as 'two engine gift steps (engine unchanged)' is order-dependent and can partially transfer even when the post-swap inventories clear every cap (e.g. both parties at the 3-per-type cap swapping that same type, or an 8/8 inventory swapping equal counts) — and the validation clause 'the swap clears both inventories' caps' never defines whether caps are checked against pre-state per step or the post-swap net.
    evidence C2 @ section 4.5, Settlement bullet: "Success → the swap applies
  **atomically** under the room lock as two engine gift steps (engine unchanged)."
    evidence C7 @ engine.py:122-127 step() Trade branch: "for it in action.items:
            if giver.inventory.get(it, 0) > 0 and can_receive(receiver, it):
                giver.inventory[it] -= 1"
    evidence C6 @ state.py:79-80: "def can_receive(p, item):
    return p.inventory.get(item, 0) < MAX_PER_TYPE and inventory_total(p) < MAX_TOTAL"
    caveat: Concrete break: A holds 3 POISON, B holds 3 POISON, they agree to swap 1 POISON each (legal under guide 'any terms'); post-swap state equals pre-swap so caps clear, yet each gift step sees the receiver at cap and silently drops the item while the public 'made an exchange' event still fires
- [a6] (risk, medium, step 2) The trade protocol has no cancel/withdraw: with 'one pending offer at a time' and expiry only at talk-phase end, a counterparty who simply never responds (AFK human) locks the actor out of ALL trading for the remainder of their talk phase — the actor cannot retract, re-target, or replace the offer.
    evidence C2 @ section 4.5, bullet 4: "One-way gift = an offer with an empty WANT side. One pending offer at a time; pending offers
  expire when the talk phase ends. Decline is silent to the rest of the table."
    caveat: Bounded by the 60s talk window, so starvation is per-phase, not permanent
- [a7] (finding, high, step 3) Audit row L4 is left unaddressed: the guide's forced-self-shoot rule (no legal target + can't afford a flip → must shoot yourself) gets no spec treatment — M11 only brackets the legal seats; no moment, band text, or tray explains WHY only the self-seat is targetable, which is the exact ⚠ the audit recorded.
    evidence C3 @ section 2, row L4: "| L4 | No legal target + can't afford flip → must self-shoot; pass never allowed (:186) | ✅ self always in `legal_targets` (`endgame.py:15`), no pass action exists | ⚠ the "why can I only shoot myself" moment is unexplained |"
    evidence C1 @ game_guide.md:186: "> If you have **no legal target** and **cannot afford a flip**, you **must shoot yourself** — passing is never allowed."
    evidence C2 @ section 7, M11 row: "| M11 | Target pick | Legal seats get red corner brackets; tap → "\<VERB\> \<NAME\> — CONFIRM" strip |"
- [a8] (finding, high, step 3) Audit row G2 is left unaddressed: the endgame 'flip someone to shoot them' pressure (all-one-color at 4+ players, flipping as the elimination engine) has no spec treatment — M27 covers only the teams-OFF moment at 2 alive; nothing surfaces the G2 state or nudges the flip, and the spec does not defer it.
    evidence C3 @ section 8, row G2: "| G2 | Teams ON until <3 alive; all-one-color at 4+ still binds (flip = elimination engine) (:199) | ✅ `endgame.py:4-5,19-20` | ⚠ the "flip someone to shoot them" pressure is never surfaced |"
    evidence C1 @ game_guide.md:199: "- **Teams stay ON until fewer than 3 players remain.** At **4+ players**, even if everyone left is one color, the rule holds: a player with no legal enemy can only shoot **themselves** — which pressures them to spend **5 pts to flip** a target and shoot them. Flipping is the endgame's elimination engine."
    evidence C2 @ section 7, M27 row: "| M27 | Teams off (G3) | At 2 alive: "AGENCIES DISSOLVED · FREE FOR ALL" band; both plates equalize (black, white text, equal 3px frames) — team semantics visibly end |"
    caveat: Overlaps R7/L4: the same all-one-color state is where the forced-self-shoot confusion bites
- [a9] (finding, high, step 3) Audit row I2 is left unaddressed: PASSPORT (Cigarettes) locked at max life has no spec treatment — the KIT's greyed 'SEALED UNTIL A DEATH' state covers only the CONSUMPTION cap, while the max-life lock is a different condition (guide: the item stays locked in inventory until you drop below max); legal_actions simply omits the action at 5 lives, so in v2 the verb silently vanishes exactly as the audit complained.
    evidence C3 @ section 4, row I2: "| I2 | Cigarettes: +1 life, locked at max 5 (:84) | ✅ `items.py:28-33`, gated `actions.py:68-70` | ⚠ lock never explained (item just missing from menu) |"
    evidence C1 @ game_guide.md:84: "Restore **1 life**. **Cannot be used at max life (5)** — it stays locked in your inventory, taking a slot until you drop below max. (You may instead sacrifice it for points or trade it.)"
    evidence C2 @ section 6.2, KIT tray description: "**KIT** (briefcase — your items,
at-cap items greyed "SEALED UNTIL A DEATH";"
    evidence C8 @ actions.py:68-70: "if it == Item.CIGARETTES:
            if p.lives < MAX_LIVES:
                acts.append(UseItem(it))"
    caveat: Guide also notes the locked item may still be sacrificed or traded — the KIT/TRADE/FLIP trays must keep it selectable for those uses, which the spec never states
- [a10] (finding, medium, step 6) Audit row E4's engine edge is neither fixed nor deferred: the audit flags that the flip-back discount survives being flipped BACK by a third party (economy.flip_team unconditionally grants the discount to any target flipped by another payer, even one restoring your original color), and the spec's section 5 engine-fix list (I9, C9, V3, fine_cheapest) does not touch it, nor is it stated as accepted behavior.
    evidence C3 @ section 5, row E4 engine cell: "⚠ edge: discount survives being flipped BACK by a third party"
    evidence C11 @ economy.py:25-28 flip_team: "if discounted:
        target.flipback_discount = False
    elif payer_id != target_id:
        target.flipback_discount = True"
    evidence C2 @ section 5 header: "## 5 · Engine fixes (audit I9, C9, V3 — at the source)"
    caveat: Guide:129 is arguably ambiguous on this edge, but the audit called it out and the spec is silent either way
- [a11] (finding, medium, step 2) Internal tension around the cylinder dial vs #3b=A: M2 fills the dial's bores with shells at load and M22 pops a shell out of the cylinder, yet the ratified rule says chamber counts are shown once and never again — the spec never states whether the persistent center dial visually tracks shells after the announce; if bores remain visible and deplete per shot/eject, the remaining count becomes permanently readable, contradicting #3b=A. The dial is also double-cast as a SEAT pointer (bore points at current seat) and a SHELL container (M2/M22) with no reconciliation.
    evidence C2 @ section 1, Scope row: "**#3b = A**: chamber counts shown once at load/reload, never again"
    evidence C2 @ section 7, M2 row: ""30–70% · SEALED" stamp; bores fill black one-by-one (order hidden); cylinder spin-shuffles with decelerating click-ticks"
    evidence C2 @ section 7, M22 row: "| M22 | MAGNET (beer) | Shell pops out of the cylinder top, flies off-screen; "SHELL OUT"; empty → M16 |"
    evidence C2 @ section 1, Turn indicator row: "Fluted revolver-cylinder dial at table center; chambered bore points at current seat; click-step rotation (`Back.easeOut`, 420ms)"
    caveat: Also note the bore COUNT itself: a dial with one bore per shell would need variable bore counts (dice loads vary), while a seat dial needs one bore per seat — physically incompatible readings a builder must resolve
- [a12] (finding, medium, step 2) M14's death-dissolve rule is ambiguous in a way that can violate guide:69: it dissolves 'their chips (COVER placed by them) ... table-wide', but the chip vocabulary is inconsistent — 6.2 lists chips as COVER/SKIP/BURNED while the item moments name them BLACKMAIL (M21) and SEDATED (M23); if a builder reads 'their chips' as ALL chips the dead player placed, the SEDATED (Handcuffs) chip wrongly dissolves, while the guide requires the dead player's Handcuffs to STAY and the target to still skip.
    evidence C2 @ section 7, M14 row: "pips clear; their chips (COVER placed by them) dissolve table-wide"
    evidence C2 @ section 6.2, seat arc line: "+ status chips (COVER/SKIP/BURNED)"
    evidence C2 @ section 7, M21 row: "Envelope chip flies caster→target; target plate gains "BLACKMAIL · \<caster\>" chip"
    evidence C1 @ game_guide.md:69: "- The dead player's items are **burned.** Of the tokens they had placed on others: their **Immunity expires** (it protected them); their **Handcuffs stays** (the target still skips)."
    caveat: Not a naming-taste issue: the ambiguity decides whether a rules-mandated persistent token survives; one clarifying sentence fixes it
- [a13] (finding, medium, step 9) Bot gifts have no defined presentation or privacy rule: enabling social_enabled=True makes random bots emit engine Trade actions recorded as the EXISTING event type 'gift' (take_policy_turn → rec.gift), but the spec's new-event list names only 'fine' and 'trade', section 7 assigns no moment to a bare gift event (M26 choreographs only the offer/accept flow), and the 4.5 privacy stripping is defined only for the settled 'trade' event.
    evidence C2 @ section 4.4: "`social_enabled=True` turns Trade on
(engine already supports it; random bots will occasionally gift — acceptable flavor)."
    evidence C18 @ turn.py:89-93 take_policy_turn: "elif isinstance(a, Trade):
            to = a.to_id
            step(state, pid, a)
            if rec:
                rec.gift(turn_idx, pid, to, [it.name for it in a.items])"
    evidence C20 @ events.py:19: "GIFT = "gift"              # Stage 5: an item handed to a teammate (costly signal)"
    caveat: Today's _anim already strips gift's extra (item identities) so no leak occurs by default; the miss is the undefined client handling of an event type the spec's own decision makes live
- [a14] (finding, medium, step 8) The guide's 'no hard maximum' player count has no spec treatment: the guide sets minimum 5 with no maximum (8+ recommended), the server hard-codes NUM = 5, and the spec bakes a fixed '5 seats on the arc' into the TableScene layout without either parameterizing seat count or explicitly deferring >5-player rooms — an unstated omission (the non-goals and section 12 deferral lists do not mention room size).
    evidence C1 @ game_guide.md:14: "- **Players: minimum 5**, no hard maximum (8+ recommended for the social layer)."
    evidence C17 @ server.py:20-21: "app.mount("/static", StaticFiles(directory=STATIC), name="static")   # logo + shared UI assets
NUM = 5"
    evidence C2 @ section 6.2 layout diagram: "│      5 seats on the arc      │ portrait tile + plate + heart pips"
    caveat: v1 has the same 5-seat reality (audit S2 only checked the minimum), so this is inherited — but a full-redesign layout contract that silently freezes seat count forecloses the guide's 8+ recommendation without a ratified decision
- [a15] (finding, medium, step 2) The KIT cap display still omits the per-type cap: guide:40 sets 'Maximum 3 of any single item type', but 6.2's cap readout shows the total cap explicitly ('N/8') while the two per-item numbers are your COUNT and the table's remaining CONSUMPTION uses — neither marks 3 as the per-type ceiling, so a per-type bounce (a 4th SAW draw or trade blocked at 3) remains as unexplained in v2 as the total-cap bounce the user personally caught.
    evidence C1 @ game_guide.md:40-41: "- Maximum **3 of any single item type.**
- Maximum **8 items total.**"
    evidence C2 @ section 6.2, KIT tray description: "as numbers: header tally "N/8" (total load), and beside each item card two numbers —
**your count** of that item and **how many uses the table has left to consume**"
    caveat: Cheap fix: render the per-item count as "n/3"; the spec's parenthetical cites guide:40-42 so the intent to cover BOTH caps is there — the concrete readout it specifies covers only one
- [a16] (risk, low, step 2) M26's public settle animation can leak trade magnitude: 4.5 promises the table sees only 'made an exchange', no contents, but M26 flies 'card-backs ... BOTH ways publicly' — if one card-back renders per item, the public reads each direction's item COUNT (and a one-way gift becomes distinguishable from a swap); the spec never states the public card-back count is masked/fixed.
    evidence C2 @ section 4.5, Privacy bullet: "The table
  publicly sees only a **settled** trade ("VESPER and WREN made an exchange", no contents) —
  Room strips items from the public event and enriches the two parties' copies."
    evidence C2 @ section 7, M26 row: "**settle:** card-backs fly BOTH ways publicly, real items render only for the two parties"
    caveat: Counts are arguably not 'contents' (identities stay hidden); still, D4's rationale is guide:154 hidden-holdings, and per-direction counts materially narrow inventory inference
- [a17] (risk, low, step 2) M9 publicly reveals the fined item's identity ('FINED · <ITEM>' stamped on the plate, the item icon falls from the tile) — 'who holds which item' is the guide's canonical hidden info, and unlike the trade event (D4 deliberately strips identities) the spec never specifies the fine event's public payload nor justifies the reveal as an intended public burn.
    evidence C2 @ section 7, M9 row: ""FINED · \<ITEM\>" stamp on actor's plate; the item icon falls from their tile and crumbles; timer resets 0:30"
    evidence C1 @ game_guide.md:154 visibility table: "| Every player's **team color**, and every **flip** (live) | **Who holds which item** |"
    caveat: Defensible as an intended public penalty (a physical-table fine would be seen; the public LEDGER count drops either way) — but it is a DECISION the spec makes silently, unlike D4/D8 which document their visibility calls
- [a18] (finding, medium, step 9) M23's skip beat has no event: the engine clears handcuffed and skips the seat silently inside turn advancement, no 'skip' event type exists, and the spec adds none — inside a bot cascade the client must reconstruct the skip by joining the turn_start sequence gap against the PREVIOUS view's handcuffed flags (intermediate views are never sent), a fragile inference the spec neither names as client work nor replaces with an event.
    evidence C2 @ section 7, M23 row: "**at the skip itself:** rotation pauses at their seat, "SKIPPED" stamp, chip clears, rotation continues — the invisible skip becomes a beat"
    evidence C7 @ engine.py:22-26 _set_turn_to: "p = player_by_id(state, cur)
        if p.handcuffed:
            p.handcuffed = False
            cur = next_living_after(state.order, living, cur)
            continue"
    evidence C2 @ section 4.6 (line 159): "New event types: `fine`, `trade`."
    caveat: Derivable in principle (turn_start events + seating order + prior handcuffed flags), so buildable without server change — but the mechanism is unstated and the human-being-skipped case surfaces only as a turn that never arrives
- [a19] (finding, medium, step 8) Reconnect mid-phase drops a pending trade offer irrecoverably: the server's reconnect path re-sends only views, the 4.6 view field list carries no pending-offer state, and 4.5 delivers the offer as a one-shot private message — so a counterparty who refreshes during TALK loses the ACCEPT/DECLINE tray with no redelivery mechanism specified, silently killing the trade.
    evidence C17 @ server.py:87-88 join/reconnect: "if me:                                   # reconnect: reclaim seat
                    me["ws"] = ws"
    evidence C2 @ section 4.6, view additions: "View gains: `phase` (`"talk"|"decision"|null` — null while bots cascade), `phase_ends_at`,
`server_now`, `bonus` (bool), `extra_turn` (bool — killer's earned turn, Room-derived),"
    evidence C2 @ section 4.5, Flow bullet: "The offer goes privately to that teammate,
  who gets an ACCEPT / DECLINE tray."
    caveat: Low frequency (refresh inside a 60s window with an open offer) but the spec's own reconnect story (v1 token-reclaim kept) makes state-on-view the recovery contract — the offer is the one new private state left out of it
- [a20] (finding, medium, step 5) Section 4.4's phase-filtered action list and section 4.5's message-based trade flow define two overlapping trade mechanisms without reconciliation: the talk-phase view will contain engine Trade entries (single-item gifts generated by legal_actions once social_enabled=True) alongside the new trade_offer/trade_respond channel — the spec never states whether the human client renders, hides, or maps those indexed Trade actions, and 6.3's TRADE grammar uses only the offer flow.
    evidence C2 @ section 4.4: "Room computes the engine list, then the view includes
only entries legal in the current phase (talk: UseItem+Trade; decision: UseItem+Flip+Shoot)."
    evidence C8 @ actions.py:95-100 legal_actions: "if state.social_enabled and not state.bonus_pending:
        for it in list(p.inventory):
            for q in others:
                mate = player_by_id(state, q)
                if mate.team == p.team and can_receive(mate, it):
                    acts.append(Trade(q, [it]))"
    evidence C2 @ section 4.5, New WS messages bullet: "New WS messages: `{type:"trade_offer", to:<seat>, give:[names], want:[names]}` ·
  `{type:"trade_respond", accept:<bool>}`."
    caveat: Also note the indexed Trade path settles INSTANTLY with no accept step — if the client exposes it, it bypasses 4.5's offer/accept and privacy design entirely
- [a21] (finding, high, step 2) Grounded negative — phase legality is faithful: 4.1's TALK (items+trade), DECISION (items+flips+shoot), and BONUS (=silent decision, no talk/trade) map exactly onto the guide's enumerations, and the 60s/30s durations match the guide's 1 minute / 30 seconds; no phase-legality mismatch found between 4.1, 4.4, 6.2's action strip, and section 10's tests.
    evidence C1 @ game_guide.md:169-173: "Talk openly: negotiate, ally, deal, bluff. **Item use AND trades are allowed.**

### Step 3 — Decision Phase (30 seconds)
Silence. Decide your target: **yourself** or **another player**. **Item use and flips are allowed; trades stop.**"
    evidence C2 @ section 4.1 phase table: "| **BONUS** (self-blank) | 30s | locked | = one DECISION phase (items + flips + shoot; no talk/trade) — guide:189 |"
    evidence C1 @ game_guide.md:189: "- A **self-blank** earns a bonus turn: **30 seconds, silent.** You **may use items and flip**, but **no talking and no trades.** (A bonus turn = a normal turn minus talk + trade.)"
- [a22] (finding, high, step 8) Grounded negative — the spec's code-reality citations check out: view.py:48-51 does count dead players' inventories into public item_counts (V3 claim exact), actions.py:76-78 does offer a same-caster repeat Immunity with no immunity_against check (I9 claim exact), items.py Immunity is a silent set.add (consumed no-op confirmed), and fine_cheapest is feasible as described (state.rng exists on GameState; inventory mutation helpers engine-side).
    evidence C16 @ view.py:48-51: "counts = {it: 0 for it in ITEMS}
    for p in state.players:
        for it, c in p.inventory.items():
            counts[it.name] += c"
    evidence C8 @ actions.py:76-78: "elif it == Item.IMMUNITY:
            for o in others:
                acts.append(UseItem(it, o))"
    evidence C9 @ items.py:50-55 apply_item: "if item == Item.IMMUNITY:
        if target_id is None or target_id == player_id:
            raise ValueError("immunity needs non-self target")
        player_by_id(state, target_id).immunity_against.add(player_id)"
- [a23] (finding, high, step 9) Grounded negative — M19's peek-persistence claim is verified in code: Extras.sync clears the known shell whenever the chamber object is swapped (reload) or its position moves (any fire/eject), and every Room path re-syncs all seats after every sub-action, so 'persists until that shell moves (server Extras logic, unchanged)' is accurate including a bot's Beer ejecting a human's peeked shell.
    evidence C18 @ turn.py:28-38 Extras.sync: "def sync(self, state):
        ch = state.chamber
        if ch is not self._lc:
            self._lc = ch
            self.total = len(ch.shells)
            self.live = sum(1 for s in ch.shells if s == Shell.LIVE)
            self.known = "unknown"
            self._lp = ch.pos
        elif ch.pos != self._lp:
            self.known = "unknown"
            self._lp = ch.pos"
    evidence C2 @ section 7, M19 row: "peek chip fills "NEXT: LIVE" (red) / "NEXT: BLANK" (white), persists until that shell moves (server Extras logic, unchanged)"
- [a24] (finding, high, step 3) Grounded negative — audit closure is otherwise solid: of the 49 RULES_AUDIT rows, every ❌/⚠ row EXCEPT L4, G2, I2, and the E4 engine edge has a concrete spec treatment (S1→M1, S3→M2, S6→M4, S7→6.2 KIT, L2→M12 floats, L3→M13, C1/C4→M16, C2→M17, C5→M15, C7→M24 reset, C8→M16/M17+engine, C9→section 5, I4→M20, I6→M23, I9→section 5, I10→M24+view fields, E5→4.5, V3→section 5+LEDGER, T1→section 1 ratified keep, T2-T4→section 4, T5→4.1 BONUS, T6→4.1+M15, G3→M27, V6→M3), and the audit's five open design questions D1-D5 are all answered in section 1.
    evidence C2 @ section 1, Scope row: "Full guide timers (60s talk / 30s decision / fines / auto self-shoot) · trade UI in · human plays first (v1 rotation kept) · **#3b = A**: chamber counts shown once at load/reload, never again"
    evidence C3 @ TOP GAPS list, item 1: "1. **T2-T4 — the social core is missing.** Talk phase, decision phase, timers, timeout-fines, auto self-shoot: the entire Turn Structure section. Chat is a free-floating text box. For a SOCIAL deduction game this is the game."
    caveat: Treatments named at spec level; separate records a1/a2 show two of those treatments (M17) lack a working data source — closure at the promise level, not necessarily the mechanism level
- [a25] (finding, medium, step 8) Grounded negative — the gen-counter deadline scheme is sound as specified: capture-gen-at-schedule + no-op-if-moved + take-lock-before-transition + reschedule-on-every-broadcast closes the stale-deadline race (a stale task fires, sees gen moved, no-ops; the action's own broadcast has already rescheduled), and duplicate tasks with the same gen are benign (first applies and bumps gen, second no-ops); no starvation or double-fine path found inside the described protocol itself.
    evidence C2 @ section 4.3, bullet 2: "The **server** owns one asyncio deadline task per room: capture `gen` when scheduling; on fire,
  take the room lock, no-op if `room.gen` moved (action already resolved the phase), else call the
  Room transition and broadcast. Every broadcast reschedules the next deadline."
    evidence C17 @ server.py:111-114 action handler: "elif t == "action" and lb and lb.room and me and me["seat"] is not None:
                async with lb.lock:
                    try:
                        lb.room.apply(me["seat"], int(msg.get("i", -1)))"
    caveat: Sound ONLY if non-state broadcasts (chat) either bump gen or reschedule without cancelling the live task — the spec says gen increments on state mutation and chat is arguably not one; implementers must not let a chat reschedule silently replace a still-valid deadline with a same-gen duplicate that then double-applies (mitigated because the first application bumps gen)
    caveat: The clock-fairness defect recorded separately (a4) is about WHEN deadlines anchor, not the scheduling race
- [a26] (finding, medium, step 8) Grounded negative — visibility sweep is otherwise clean: no hidden-info leak found in the 4.6 view additions (saw_active is committed publicly, use_counts/use_limit and teams_active are guide-public, flipback_discount is own-view only, roster is public names) and no public info withheld (LEDGER delivers guide:156's item counts, M3/M16 deliver the once-only chamber announce, lives/teams/flips all rendered); the only visibility questions found are the three recorded separately (cylinder depletion a11, trade card-back counts a16, fined-item identity a17).
    evidence C2 @ section 4.6, view additions: "`saw_active` (public: the commit event was public), `use_counts` + `use_limit` (public, audit I10),
`teams_active` (bool, audit G3), `flipback_discount` (own view only, audit E4),"
    evidence C1 @ game_guide.md:156 visibility table: "| The **count of each item type in play** (e.g. "5 Cigarettes exist") | |"
    evidence C2 @ section 6.2, LEDGER description: "**LEDGER**
(small icon by the band — the public counts panel: per-item total in play + uses left, audit V3/I10),"
    caveat: Checked both directions across 4.6 fields, M1-M28, and the trays against the guide's visibility table
- [a27] (finding, medium, step 2) Grounded negative — moment completeness against engine transitions is otherwise full: every remaining engine-producible transition has a moment (4 shot outcomes M12, self-blank chain M13, mid-chamber vs emptying kill M14/M16/M17, beer-empty still-your-shot M22→M16, skip M23, cap hit M24, flip incl. flip-back cost M25/6.3, teams-off M27, winner M28, fines M9, auto self-shoot M10, killer extra turn M15, item effects M18-M23) and section 8's red list matches the catalog's red usages exactly (M8, M11, M12, M14, M19, M20 — nothing else in sections 6-7 uses red); the only presentation gaps found are the bot 'gift' event (a13) and the data-source defects recorded separately.
    evidence C2 @ section 8: "Target brackets (M11) · final-5s countdown digits (M8) · pip-shatter particles (M12) ·
"×2 ARMED" glow/chip (M20) · "NEXT: LIVE" peek (M19) · "BURNED" stamp (M14). Nothing else is red."
    evidence C2 @ section 7, M16 row: "| M16 | Reload (C1/C4) | Compressed M2 (~2× speed); death-reload prefixed "IN THEIR HONOR"; announce 5s (M3). After MAGNET-emptied reload: band "STILL YOUR SHOT" (C3) |"
    caveat: Saw-wasted-on-blank has no dedicated beat but the M20 chip clears on shot resolve, which presents the outcome implicitly — judged not material
    caveat: A Saw-armed ×2 chip carried into an M10 auto self-shoot resolves via M12's −2 float — covered
- [a28] (recommendation, high, step 6) Add a per-seat 'draw' event to the contract: have draw_items_for_all return (or the Room record) each seat's ATTEMPTED and RECEIVED items, emit it as a new event type enriched per-seat like the trade event — this is the single change that makes both M17 promises (name reveal + FULL bounce) buildable and should be added to section 4.6's new-event list and section 5's engine touch-list before build step 1.
    evidence C12 @ reload.py:7-12: "def draw_items_for_all(state, n=2):
    for p in living_players(state):
        for _ in range(n):
            item = ITEM_TABLE[state.rng.randint(1, 6)]
            if can_receive(p, item):
                p.inventory[item] = p.inventory.get(item, 0) + 1"
    based_on: a1, a2 — Both M17 defects share one root: the draw outcome is never recorded anywhere
- [a29] (recommendation, high, step 5) Pin trade settlement semantics before build step 2: define cap validation against the POST-SWAP inventories (remove promised gives, then add wants, check ≤3/type and ≤8 total) and apply the transfer with a primitive that does not re-check can_receive mid-flight (either a new engine swap step or direct inventory moves under the room lock with a test asserting all-or-nothing) — the current 'two engine gift steps (engine unchanged)' wording cannot deliver the promised atomicity.
    evidence C2 @ section 4.5, Settlement bullet: "Success → the swap applies
  **atomically** under the room lock as two engine gift steps (engine unchanged)."
    based_on: a5 — Engine gift steps silently drop unreceivable items; only a post-swap-net check plus an unchecked-move primitive is order-independent
- [a30] (recommendation, medium, step 8) State a phase-anchor rule in 4.3: either add a bounded grace proportional to the cascade being delivered (server knows the event count it just broadcast) before phase_ends_at starts, or start the phase deadline on the first client ack, with a hard server-side ceiling so the anti-stall guarantee survives — and specify that a mid-decision MAGNET reload does or does not extend the 30s window.
    evidence C2 @ section 4.3, bullet 3: "Client renders the countdown from `phase_ends_at` + `server_now` (clock-offset corrected);
  it never enforces anything."
    based_on: a4 — Closes the cascade clock-burn without giving clients timer authority
- [a31] (finding, high, step 2) Grounded negative — the remaining guide sections sweep clean: the section 2 theme table's effects and point values match constants.py and items.py exactly (6/6/5/5/4/4, all six effects), 4.5 carries all four guide trade rules (teammates-only, any terms incl. one-way gifts, cap-blocked, talk-phase only), alliances (guide:145) need no mechanism beyond the gated chat (informal/verbal/unenforced by design), and the timeout chain (fine cheapest, rng ties, 30s more, auto self-shoot when broke, applies to bonus turns) is fully and faithfully specified in 4.2; the unaddressed guide rules found in the whole sweep are exactly the ones recorded separately (guide:186 explanation, guide:199 pressure, guide:84 lock, guide:40 per-type cap display, guide:14 no-max, guide:69 chip ambiguity).
    evidence C5 @ constants.py:23-30 POINT_VALUE: "POINT_VALUE = {
    Item.IMMUNITY: 6,
    Item.CIGARETTES: 6,
    Item.MAGNIFIER: 5,
    Item.SAW: 5,
    Item.BEER: 4,
    Item.HANDCUFFS: 4,
}"
    evidence C2 @ section 4.5, first bullet: "- **Only the active player trades**, TALK phase only, living **teammates** only."
    evidence C1 @ game_guide.md:175: "> **Timer runs out** with no action taken → you're **fined one item** (your cheapest, random among ties) and given **30 more seconds.** Time out again → fined again. With **no item left to lose, the gun auto self-shoots.**"
    caveat: 4.5's active-player-only initiation narrows the guide (which is silent on who initiates) but is a user-designed, dated decision (D3 basis line) — a stated call, not a miss

## DERIVED — 0

## ASSERTION — 0

## CONTEXT LEDGER — 23
- C1: read — game_guide.md full 228 lines
- C2: read — ui-v2-phaser-design.md full 333 lines
- C3: read — RULES_AUDIT.md full 125 lines
- C5: read
- C6: read
- C7: read
- C8: read
- C9: read
- C10: read
- C11: read
- C12: read
- C13: read
- C14: read
- C15: read
- C16: read
- C17: read
- C18: read
- C19: read
- C20: read
- C4: partial — Read Track B / NEXT section (lines 40-108) for ratified decisions; no contradiction with spec found (status doc carries OLDER draft item names PAPERS/COVER/MANIFEST/INTERCEPT/BURN; spec's table is marked RATIFIED 2026-07-08 and supersedes)
- C21: skipped — Spike scene is the ratified visual baseline (aesthetics out of scope); not needed for rules/feasibility findings
- C22: skipped — v1 client glue not read; spec claims about it recorded as a gap instead
- C23: skipped — v1 visual layer not read; decoder/queue-port claims recorded as a gap instead

## SOURCES REGISTERED — 0

## GAPS — 3
- Did not verify the spec's v1-port claims against the v1 client code (C22/C23 unread): 'v1's proven queue/drain/skip loop, ported' (section 3), 'v1's terminal decoder, ported to Phaser' (section 7 header), and '(kind, item, target) uniquely keys a legal action (v1 invariant, kept)' (6.3) are taken on the spec's word; if the v1 loop has undocumented assumptions (e.g. single-events-array-per-message), the port estimate could slip
- M2's per-roll dice values have no server source (announce/reload carry only totals); 'cosmetic replay' implies the client synthesizes a hi/lo roll sequence consistent with (total, live) — I judged this a stated deferral rather than a finding, but did not prove a consistent decomposition generator exists for every reachable (total, live) pair; worth a one-line build note
- Outside my facet (Phaser/client engineering): canvas performance of the moment catalog on real phones, Scale.FIT behavior, and the KIT-tray/seat-arc collision (the spec itself flags 'verify at build') were not assessed; also bot-intelligence effects of social_enabled=True (random bots gifting altering game balance) are out of scope per the brief

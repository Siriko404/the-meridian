# Social Roulette — Project Status (resume anchor)

**Updated:** 2026-07-03 · **Branch:** master · Read this first after any context reset.

---

## ═══ CURRENT STATE — 2026-07-03 (READ THIS FIRST) ═══
The project now runs on **two tracks**. The rest of this doc (below) is the older RL-only history.

### TRACK A — RL research (PAUSED)
- **Stage 5 — emergent alliances:** BUILT + trained + measured → **cooperation NULL.**
  Added a real gift/Trade action + per-opponent **harm/help memory** in obs, a co-evolution
  self-play driver, and emergence metrics. Fresh social seed = 0.748; 5 self-play gens (gen4/5 ≈ 0.78).
  **Outcome ablation:** memory-off & gift-off Δ≈−0.005, p≈0.7 → gifts happen (~2/game) but do NOT
  raise win-rate. Same THROUGHLINE (no incentive under individual reward). Files: `social_roulette/rl/social_*.py`,
  `models/stage5seed`+`models/stage5/gen1..5`. Commits d00df0c, f77c54d, 816f4d4.
- **LLM-play pivot — INVESTIGATED, not built.** Idea: let LLMs play (they carry human social priors) instead of RL.
  **FREELLMAPI gateway is LIVE** (localhost:3001, OpenAI-compatible, ~64 free models, unified key stored in its
  `server/data/freeapi.db` `settings` row; repo at `~/OneDrive/Desktop/Projects/OpensourceProjects/freellmapi`).
  Findings (probed 8 models): **refusals are NOT a problem** (0/8 refused the shotgun game); **rate-limits are THE wall**
  (3/8 HTTP 429 on the first burst; a real benchmark = ~26 turns/game → 100k–700k calls); **reproducibility fights the
  gateway** (pinning `gpt-oss-120b` still hopped cerebras↔groq). Seam = `engine.step`; the talk-phase + an LLM NL
  state/action interface are the hard unbuilt parts. PAUSED here.

### TRACK B — the game as a playable product (ACTIVE)
- **ONLINE GAME — BUILT + browser-verified.** FastAPI + WebSocket, **invite-code rooms**, humans + random-bot fill to 5,
  real-time, on the real engine. Anti-cheat **per-seat views** (never full state; includes own Magnifier peek),
  async `Room` state-machine + per-room lock, server-authoritative action re-validation, reconnect token. **181 tests green in this env** (+8 RL modules uncollectable — missing `gymnasium`/`sb3_contrib`).
  I drove a **full game to a winner in the actual browser** — every mechanic verified (items/heal, shoot advances turn,
  bot autoplay, team-flips → legal-target recompute, reload item-draw, handcuff exclusion, Magnifier peek, self-blank→bonus,
  death, winner). Fixed one bug (winner used a blocking `alert()` → inline banner). Files: **`social_roulette/online/`**
  (`view.py`, `room.py`, `server.py`, `static/index.html`). Spec+plan: `docs/superpowers/specs|plans/2026-07-03-online-game*`.
  Run: `./.venv/Scripts/python -m uvicorn social_roulette.online.server:app --port 8000`.
  **Deploy target = Render free** (pending: your GitHub repo + Render signup; server is host-agnostic — a ~5-min step).
- **UI — BUILT + refined (mobile-locked, playable).** Full pure-B&W mobile UI on the real engine, locked to ONE
  phone screen (no scroll/zoom): circular table (teams ●/○, **you seated FIRST**, ring in **TURN ORDER**), center
  **dial + gliding turn-dot**, **tap-to-target** (verb → item picker → tap a seat), Terminal decoder, slower
  **labelled** bot cascade, **flip PAYMENT PICKER** (choose which items pay), chamber counts CONFIDENTIAL
  (announce-only), immunity markers "P3M", beer "SHELL OUT". Files: `social_roulette/online/{room,view,server}.py`
  + `static/{index.html,sr_ui.js,sr_ui.css}`. Verified live in Chrome across 3 refinement rounds.
  **Full refinement log + exact mechanics:** `docs/superpowers/specs/2026-07-03-ui-redesign-design.md`.
  - **⛔ AWAITING USER — decision #3b "see 2 bullets":** whether the REMAINING shell count is visible (this
    CONTRADICTS the R2 confidential-count rule you set, `game_guide:159`). Pick **A** (hidden, current) /
    **B** (show remaining count, never nature) / **C** (only whether a next shell exists). Do NOT build until answered.
  - #1 "ratio deviation" = **NOT a bug** — 20000 loads, 0 outside 30–70% (`chamber.py:13`); likely the *remaining* ratio.
  Run: `python -m uvicorn social_roulette.online.server:app --port 8015` → http://127.0.0.1:8015.

### Dev servers this session (restartable; NOT compaction-critical — they may be dead on resume)
```
game    ./.venv/Scripts/python -m uvicorn social_roulette.online.server:app --port 8000
demos   ./.venv/Scripts/python -m http.server 8010 --directory social_roulette/online/static   (mockup.html, decoders_binary.html)
freellm supervisor at ~/.freellmapi-supervisor, or: cd freellmapi/server && ../node_modules/.bin/tsx src/index.ts  (:3001)
```

### NEXT (Track B, the active work) — ⟲ FULL REDESIGN v2, in PHASER 4 (updated 2026-07-07)
v1 web UI rejected (look/feel/flow/process + missed rules + missing dealer animations). All decisions below
are RATIFIED by the user — do not re-litigate:
- **Stack: Phaser 4 (4.2.0 vendored at `static/vendor/phaser.min.js`) + existing Python server/engine/WS.**
  Godot REJECTED twice on evidence (iOS-browser crash history, 40MB wasm vs 27KB, native needs a Mac).
  User directive: **"proceed ONLY in the engine"** — no HTML/SVG mockups; visuals are judged in running
  Phaser scenes only.
- **Scope locked:** full guide timers (talk 1min / decision 30s / fines / auto self-shoot) · Trade UI in ·
  human plays first · #3b = A (counts stay hidden after the one announce) · chamber floor already >100% of
  living at every load (verified 40k loads) — no change.
- **Copyright (ratified): full re-theme.** Buckshot's 1:1 item cluster was the smoking gun (mechanics stay,
  every fiction/name changes; `docs/RULES_AUDIT.md` still governs rules). **THEME LOCKED: fictional world
  at war → wartime SPY / sealed night train** (picked from generals/spies/nations trio after several
  rejected rounds — broadcast/theater/boardgame and armistice/tin/paper all killed). Working title
  "SLEEPER CAR" — user hates it, name TBD ("DEAD DROP" taken twice; "Orient Express" is trademarked —
  the train's invented name: "THE MERIDIAN"). Lives = cover identities · teams = two agencies · flip =
  a turned double agent · dealer = the Handler · item DRAFT names: PAPERS heal·6, COVER immunity·6,
  MANIFEST peek·5, POISON ×2·5, INTERCEPT eject·4, BURN skip·4.
- **ART POLICY (standing, 4 rejections deep): Claude NEVER hand-draws figurative art in code.** Community
  CC assets FIRST; image-gen ONLY when absolutely necessary; **faces are SACRED** (never tint/invert).
  Vendored packs (`static/game/assets/ATTRIBUTION.md`): JJ99 Noir 1-bit Portraits (12× 36px, commercial
  OK) + Darkmoonfire 1-Bit Mystery Icons (45× 16px, CC-BY-SA, credit due). Icon indices: revolver=0
  heart=20 ledger=37 briefcase=40 envelope=14 poison=11 phone=38 cigarette=25 pocket-watch=45.
  Style: **1-bit noir pixel + single red accent (red = danger ONLY)** — Obra Dinn / Downwell pedigree.
- **SPIKE BUILT + user-refined** (`static/game/spike.html|js`; serve `python -m http.server 8010
  --directory social_roulette/online/static` → /game/spike.html): fluted revolver-CYLINDER turn dial
  (shallow flutes ratified; the chambered bore points at the current seat, click-step rotation) · KIT
  tray behind a briefcase icon (**STANDING PRINCIPLE: every screen-occupying menu opens from a tapped
  icon**) · teams = **nameplate polarity + thick/thin frames on avatar AND plate** (user-picked from
  in-engine samples `game/teams_samples.html`) · no window band · text ≥13 design-px bold with
  setResolution(2) (desktop preview ≈0.78×; phones render bigger). Phaser 4.2 gotchas: setTintFill =
  silent no-op (use setTint) · camera vignette filter works · rAF throttles in backgrounded tabs.
- **SPEC RATIFIED + AUDITED (2026-07-08):** `docs/superpowers/specs/2026-07-07-ui-v2-phaser-design.md`
  — walked with user; trade redesigned to bluffable offer/accept swap; items RATIFIED
  (PASSPORT/BLACKMAIL/SPYCAM/POISON/MAGNET/SEDATIVE); counsel-audited (1 Fable expert, 31 grounded
  records, gate PASS, `counsel-runs/2026-07-08-uiv2-spec-audit/`), all 14 findings absorbed; user
  decisions D14 (fine publicly anonymous) + D15 (parametric seats, ship at 5).
- **PLAN A (SERVER) — ✅ MERGED TO MASTER 2026-07-08 (merge `0cdea26`, 236 tests green).**
  Plan `docs/superpowers/plans/2026-07-08-uiv2-server.md`, executed subagent-driven (opus
  implementers + reviewers, every task review-gated; audit trail `.superpowers/sdd/progress.md`,
  committed). Landed: engine I9/C9/V3 fixes · `economy.fine_cheapest` + atomic `swap` ·
  `ev["draws"]` + `state.last_skipped` · fine/skip/draw/trade events · Room phase machine
  (talk 60s / decision 30s, injectable clock, `proceed`, `on_deadline` fines→auto-self-shoot,
  gen counter) · phase-gated actions (incl. `flip()` decision-gate) · bluffable trade lifecycle +
  privacy-enriched `events_for(seat)` · full v2 view contract incl. `gen` (clients replay events
  only when gen increases — spec §4.6 note) · server deadline tasks + `proceed`/`trade_*` WS
  messages + chat gate + roster + lock-captured per-seat broadcast payloads + payload-crash
  hardening. **Fable whole-branch review found 2 Criticals (both PLAN-authored: T7's "re-begin
  phase after every action" reset decision→talk on item use; `flip()` ungated) + 3 Importants —
  all fixed (`5936ed1`, `6f027da`), merge-gate re-review PASS. LESSON for Plan B's plan review:
  check phase/state-transition CONDITIONS, not just call sites.**
  v1 web UI now DEGRADED by phases (expected; retired in Plan B).
- **Accepted debt (final-review triage, non-blocking):** gift-event receiver enrichment missing
  (Plan B: diff `your_hand`, or add later) · bot-cascade draw rows may precede the reload row
  (Plan B choreographer must NOT assume reload→draw order in bot cascades; human path IS
  reload→draw) · deadline-task liveness if wall clock steps backward · non-int WS field coercions
  (join `code`, trade `give/want` lists) can still kill a socket · offer-lifecycle broadcasts leak
  traffic-level "something private happened" · `trade_offer` accepts bot targets (withdraw
  recovers) · post-winner chat muted (undecided) · `last_skipped` drain-contract comment.
- **PLAN B NEAR-DONE — branch `uiv2-client` (now @ `b8bb840`), INLINE execution** (user: "no delegation";
  "remove me from the loop, YOU handle 100%"). Plan doc `docs/superpowers/plans/2026-07-09-uiv2-client.md`
  — **Tasks 1-8 DONE** (T6 live wiring, T7 interaction, T8 `/`=v2 `/v1`=old; 238 pytest + 8 node
  green). LIVE-PLAY VERIFIED by in-page autopilot bots: multiple FULL games to the winner incl. a
  **2-human game (two tabs, same team)** proving the offer→respond→settle round-trip on the wire;
  0 JS errors across all runs. REMAINS: **Task 9 = USER GATE** (user plays on his phone, then merge
  --no-ff to master) · icon picks (SPYCAM 8/MAGNET 5/SEDATIVE 2 drafts) · winner-face spritesheet
  edge-bleed at scale 6 (asset nit).
- **⟲ ACTIVE NOW (2026-07-09 eve): THREAD-MENU OVERHAUL — the dial idiom is SUPERSEDED.** User
  played Task-9 style and killed the dial chains ("quite long and unpleasant"). New ratified system,
  built SAMPLE-FIRST in dev labs (NOT yet wired into main.js — dials still run the live game):
  `scene.openThread(opts)` in scene.js — Skyrim-style vertical list threads. **Ratified stack:**
  fade layout (locked lists ghost-compress in place) + decode rows (in-loop swaps decode FAST
  130ms) + **B design = whisper captions** under verbs (fs8, ITEM "OPEN YOUR KIT" / TRADE "PRIVATE
  OFFER TO A TEAMMATE" / PROCEED "GO SILENT — DECIDE" / SHOOT "PICK A TARGET — OR YOURSELF" / FLIP
  "BUY A CHANGE OF LOYALTY") + **always-centered active list** (trail slides up 240ms, fades before
  y<134; per-object settled targets `_ty` stop drift; `_oy` restores on home) + **menu BURN-CIRCLE**
  (24 chord segments R20 under the title at (W/2,100), digits = fmt(left) SAME as the big bar, white
  talk / red decision, fed by setBand; band zone sleeps behind opaque topCover while a thread is
  open; seat-pick ducks reveal the real bar). **Standing rules (user law):** dot divider row
  `{dot:true}` (38px slot) before EVERY button row (CONTINUE/SEND/PAY/EXECUTE/ACCEPT) · ✕ STAND
  DOWN collapses to the thread's MAIN menu everywhere (engine `th.home()`, driver `homeTo`) ·
  ◂ BACK rewinds ONE step (engine `th.back()`, `th._pop` for swap sub-lists) · item confirms carry
  the THEME blurb as an info row · seat-picks DUCK the thread and tap the real avatar (shoot/flip =
  RED brackets `setTargets`, trade = marching ANTS, items = WHITE PULSE `setItemTargets`; ✕ CANCEL
  = back to the open list, ribbon y116) · row types: dim/info/still/split(two stat columns)/dot/
  sub/frame · hits named "trow", arm only after entrance, double-tap guard `th._act`.
  **Menu ratification status:** YOUR MOVE(talk) ✅B · DECIDE ✅ (user waived) · TRADE builder ✅ +
  count picker ✅ + OFFER-IN ✅ (user played tradelab post-fixes: "looks perfect") · LEDGER ✅
  one-screen "n LIVE · k TO USE" split columns · WITHDRAW OFFER ✅ · burn-circle ✅ synced ·
  **KIT-use ✅ · PAY ✅ · KIT-info ✅ (ratified 2026-07-09 night via AskUserQuestion; user caught
  the fake demo flip cost — REAL cost 5, self flip-back 4, actions.py:85; POINT_VALUE ==
  theme.js pts). ALL MENUS NOW RATIFIED.** Designs: KIT rows wear blurb whispers (sub = theme
  blurb, "· SEALED" suffix; bright = usable per main.js:166 rule) header "YOUR KIT · 3/8" · PAY =
  real pts (4/4/5/5/6/6), "PAY n/5 PTS" arms at ≥cost, whisper "OVERPAY IS SPENT — NO CHANGE"
  (trays.pay truth), ✕ STAND DOWN row · KIT-info = ONE screen (same rows, still, no taps,
  "✕ CLOSE"). threadlab kitUse/pay/kitInfo match (tap-inspect infoThread deleted).
  **⟲ THE WIRING — DONE 2026-07-09 late (awaiting user check → Task-9 phone gate → merge):**
  scene.js: openRadial/closeRadial DELETED; pick hits named tgt/tcxl/tabort/tback (for the bot).
  main.js [ACT] rewritten to threads: openTh driver (show/_hist/onBack/homeTo + `alive()` guard —
  EVERY await is followed by t.alive() before building more UI, else dead-thread leak),
  moveThread (talk+decision roots, legality dims, M11 forced-self note), kitStep (kitUseThread =
  briefcase on-turn, thread rooted at KIT; off-turn = kitInfoThread one-screen), offerStep
  (GIVE⇄count→WANT→SEND), payStep (server a.cost), ledgerThread, respondThread (auto-opens on
  po.to===you; the hub re-opens it if aborted), confirmStep; drain() closes any thread BEFORE
  beats; onKit/onLedger/onAction gated on !busy (menus never open OVER beats — thread scrim is
  .88, beats bleed; found on live film). trays.js DELETED (+ script lists, offer_in/dial_*
  scenarios; runner catalog rebuilt = 59 scenarios). **devbot.js** (loaded ONLY with ?bot=1):
  auto-join (?code&tag&start), rAF-dead loop pump (g.loop.step when loop.now stale — headless
  tabs), semantic monkey (trow/tgt/tcxl/tabort/tback + hubs), 3×2 contact sheets + console-error
  trap → sink; `?canvas=1` forces CANVAS renderer (headless WebGL toDataURL = black);
  window.__scene/__game dev handles. **VERIFIED:** 59-scenario rig sweep (non-V0 = the known ×1
  transients, unchanged) · 8 node + 238 pytest · TWO live monkey games (2 headless humans + 3
  server bots), 60 frames each, ZERO console errors — films show live kit w/ blurbs,
  BLACKMAIL→C.D. confirm, one-screen ledger, DECIDE root, SHOOT-YOURSELF confirm, slash clock +
  burn-circle in-game. NOT live-verified: winner overlay after threads (games outlast the film
  cap; path is untouched choreo) · human↔human trade on the NEW builder (wire protocol identical
  to the pre-compaction verified round-trip). NOTE: threadlab `?auto=` headless smoke is broken for ALL flows
  (pre-existing — Phaser clock dead under --screenshot; differential-tested vs untouched ledger);
  interactive play + rig films are the verification. **Labs (dev pages, cache-busted):** `threadlab.html` (MOVE/MOVE·R/DECIDE/
  TRADE/KIT/LEDGER/OFFER·IN buttons, live band ticker) · `tradelab.html` (beat-exact trade
  lifecycle vs scripted bot: SEND→accept/decline, WITHDRAW/PROCEED void silently, RECEIVE arrives
  like pending_offer; real center-hub entry). **Rig:** ~18 thread scenarios in capture.html
  (thread_talk/talkr/decide/flip/item/trade/kitinfo/ledger2/respond/shoot/sedate/ants/back +
  move_r1-3) all V0 (×1 mid-tween transients benign); bandLoop feeds the mini clock; decision
  scenarios pass ("decision"). **Engine truths honored in samples:** sedative = any living
  non-self non-sedated; shoot = SELF + living enemies; flip = any living affordable; legacy
  MOVE_ROWS hybrid (SHOOT+TRADE) was fake and is dead. **TRADE-STEP SWEEP DONE (2026-07-09 night,
  user: "a bunch of errors"):** 7 tr_* scenarios render the WHOLE lifecycle in capture.html
  (tr_build/hang/settle/declined/recv/recv_d/race). 6 defects found+fixed: ① setBand re-showed the
  burn-circle during the seat-pick duck (now `th._picking`; circle returns w/ fresh digits on done)
  ② `_arrowTo` re-showed ▼ over an open thread (now `setVisible(!this._thread)`) ③ menu opened
  clockless ≤1s (setBand caches `_bandO`; openThread re-applies) ④ lock "▸ " doubled arrows on
  ▸-suffixed buttons ⑤ **id2=J.L., id4=W.N.** (CODENAMES theme.js:20) — tradelab band hardcoded
  "C.W."; rig headers lied ("GIVE → C.W." etc.) — all copy fixed ⑥ bot answer while a menu is up
  painted beats UNDER the scrim + leaked pick chrome — policy: closeThread FIRST (tradelab settle/
  declined; closeThread now resolves a live pick null + own-registers ribbon/cancel). **WIRING
  LAW:** main.js trade/choreo event handler must closeThread() before beats. offer_in (legacy
  trays sheet) audits ×15 overlaps = dead UI, ignore. **OPEN:** ① TRADE builder verdict (also:
  ghost trail after GIVE lock reads only "CONTINUE ▸" — no give-summary on the WANT screen;
  surface w/ verdict) ② server gap: bots can't answer/send offers (room.py has no bot respond
  path; offer to a bot hangs until withdraw/phase-end) — user decision pending ③ after all menus
  ratified: wire threads into main.js (replace actionRadial/kitRadial/ledgerRadial/offerRadial/
  countRadial/confirmAct/pickTarget/pickItemTargets/pickTrade + TRAYS.respond/pay), delete
  openRadial+trays.js, update monkey bot to "trow" hits, full bot-play verify, THEN Task-9 user gate.
  PowerShell gotcha: NEVER pipe file content through PS regex replaces (mojibake — use Edit tool or
  [System.IO.File]::ReadAllLines/WriteAllLines).
- **RULES FIXED IN PLAY:** bots may NOT pass items unilaterally — `room.py social_enabled=False`
  (every transfer = turn-holder offers → counterparty ACCEPT/DECLINE; engine Trade backdoor was
  RL legacy; user caught the gift toast) · self flip-back copy = "X SWITCHED SIDES" · every
  item/flip/fine/trade beat dials the ARROW to its actor first (replay never looks off-turn) ·
  token read at CONNECT not page-load (second same-browser tab used to hijack the seat).
- **THE DIAL (SUPERSEDED by the thread system above — still wired in main.js until the swap):**
  `scene.openRadial(cx,cy,items,opts)` —
  GTA-style ring on an OPAQUE black stage; full circle mid-screen (195,430), auto half-arc at the
  dock hub (195,776); slots = circle+icon/label+top-right ×badge, bright ring/dim states; hub =
  wrapped title + confirm trigger; caption BELOW the ring; entrance stagger. Dashboard = 3 circular
  hubs: ≣ LEDGER · center ACTION face ("YOUR MOVE"/"· · ·", opens verb dial, becomes armed confirm
  [SHOOT C.W.]+✕) · briefcase KIT — NO text labels; phone icon dead, the ticker row IS the chat
  button. OFFER dial: all items offerable (bluff free), owned counts = badge+bright ring, tap item
  → count dial 0-3 with YOUR holding lit, GIVE→WANT→SEND on hub. Trade targets = MARCHING-ANTS
  dotted frames. Bots + humans all wear MONOGRAM initials (join asks 2 letters "F.L."; bot
  codenames V.K./C.W./J.L./N.D./W.N.). Pre-game = boarding-pass ticket (double-rule frame, serif
  masthead, two big initial boxes auto-advance, dashed code field, manifest lobby).
- **TEXT SYSTEM:** serif FS=1.5, **INVERSE outlines** (white text/black rim, black text/white rim,
  NO gray, thickness 6; trays 4); every setColor site must ALSO setStroke (South-plate blob bug).
  **THE CLOCK (RATIFIED 2026-07-09 "its perfect" + WIRED — the only band renderer):** ///// slash
  field (2px, α.45) drains L→R between TWO single ticket rules (±20, no box, no frame); digits
  fs20 white + black stroke 8, FIXED center, riding ON the field (no parted window — the burn edge
  visibly crosses behind them); everything red at ≤30s; 5s loading shimmer = 3-slash comet
  (`_drawPulse` 33ms loop reads `_hatchInfo`). Old solid-burn + masked twin-digit layers
  (barFill/barSecsD/_mFillG/_mEmptyG/barFrame) DELETED; `_bandStyle` gone. Rig `clock_final`
  films full→red→0:00; clocklab.html = live viewer (real 60→30 countdown). Game page index.html CACHE-BUSTS its scripts (?v=Date.now()) —
  stale JS twice faked dead masks for the user.
- **CAPTURE RIG v3 (Claude's eyes):** `capture.html?run=<scenario>[&canvas=1]` — virtual clock
  (rAF+performance.now+Date.now via MessageChannel pump), FULL-RES 390x844 thumbs 3x2/sheet,
  **DEFECT DETECTOR** (Text/Image overlap+offscreen+copy inventory /100ms; exemptions: fx, stamp,
  masked twin layers, dim-aware cut ≥0.8 fillAlpha) → `<run>_audit.txt`. `runner.html` sweeps all
  **~43 scenarios** incl. 11 dial states + ants + seam (title `ALLDONE runs bad viol`); ×1-count
  hits at slide/stagger moments = benign transients. **LIVE-PLAY rig:** inject pump (steps
  `game.loop.step()` when rAF dead) + 3fps recorder + random monkey (taps rslot/rhub circles,
  brackets, ants, trays, ACTION hub when face says YOUR) — plays full games unattended; two-tab
  variant for 2-human tests (clear meridian_token in BOTH tabs first or the seat is reclaimed).
  Automated-tab facts: rAF 0x, window 0x0 (no real clicks; Phaser-layer emit only), CDP screenshots
  STALE — `canvas.toDataURL` is truth; cache-bust everything.
  Servers: game `./.venv/Scripts/python -m uvicorn social_roulette.online.server:app --port 8016`
  (bg) · sink `./.venv/Scripts/python _devcap.py` (bg, threaded; beware SO_REUSEADDR double-bind).
  Node tests: `node --test social_roulette/online/static/game/test/*.test.mjs`.

---

## One-line
A 5+ player social-deduction game ("Social Roulette") turned into **deterministic code + an RL training harness**. Agents learn to play it. The infra is DONE; the open frontier is making **social behavior** (talk, trust, fear) actually emerge — which keeps coming up null for one reason: no incentive (see THROUGHLINE).

## The stages
| Stage | What | Status |
|---|---|---|
| 0 | Deterministic engine + rule tests + random sim | ✅ DONE |
| 1 | Learn vs RANDOM bots (1a shoot-only → 1b full action) | ✅ DONE (0.74) |
| 2 | Self-play vs POOL of frozen past selves | 🟡 pipeline+eval VALIDATED, seat-bug fixed, no sig gain @ smoke |
| 3 | Emoji COMMS channel | 🟡 BUILT + measured — channel works, agents don't use it (cheap-talk null, both pathways) |
| 4 (probe) | FEAR as a per-agent risk weight | ⚪ INERT vs random — no risky temptation to resolve |

## THE THROUGHLINE (the key synthesis — read this)
Every social behavior reached for (comms, fear; and the proposed trust/revenge/memory/greed) keeps coming up **NULL for the SAME root cause**:
```
individual reward  +  weak/dumb opponents  →  no INCENTIVE for social behavior  →  agents stay "boring" (boring = optimal)
```
It is NOT that the behaviors are coded wrong. Nothing in the game **rewards** them yet. The next lever is therefore the **incentive or the opponent**, not another behavior knob.
- **Comms** got a *shallow* competent-opponent test (Stage-3 gen1 = 1 generation of self-play; its opponents were comms-DEAF, trained vs random) → null. **Deep co-evolution (many generations, all comms-on) is UNTESTED.** ⚠️ CONJECTURE, not finding: it's the plausible place a signal *could* appear, but theory (Crawford-Sobel under pure conflict) predicts it likely STILL null — treat a deep-run as a chosen bet, not a promised payoff.
- **Fear** tested vs random (1 seed, 1M) → flat. ⚠️ Diagnosis "no risk tradeoff" is CONSISTENT WITH the data but NOT proven — two confounds unruled-out: (i) one scalar in a 102-dim obs may be **unlearnable** (same way messages were ignored), (ii) **floor effect** — self-shot ~0.02 at every `f` leaves no headroom to drop. **Fear-under-self-play is UNTESTED** (a competent opponent makes risk tempting).
- **Risk-attitude correction (don't re-derive):** a +1-win/−1-death win-maximizer is **risk-NEUTRAL** → fear/greed are genuinely ABSENT, not present. "Define fear/greed" = risk-sensitive RL. **Greed must pick ONE mechanism:** impatience (low gamma) · acquisitiveness (intrinsic item/kill reward) · risk-seeking (convex upside). Hidden heterogeneous types = the information-asymmetry comms would need.

## Key results (measured · n=5000 · eval seeds disjoint from train · binomial vs 0.20)
| Policy | Win-rate | p |
|---|---|---|
| random baseline | 0.1934 | — |
| 1a shoot-only (300k steps) | 0.4694 | ≈0 |
| 1b full action (1M steps) | 0.7436 | ≈0 |

Trajectory-validated as **real play** (agent heals + shoots enemies; not a reward-hack). Caveat: random opponents partly **self-harm**, so part of 0.74 is opponent weakness → Stage 2 resolves this.

## Repo map
- `game_guide.md` — the locked game ruleset (source of truth for mechanics).
- `social_roulette/engine/` — pure, seeded, deterministic rule engine (constants, rng, state, chamber, shooting, items, economy, reload, endgame, actions, engine).
- `social_roulette/sim/random_agent.py` — `random_policy`, `take_random_turn`, `play_game`.
- `social_roulette/rl/` — `env` (Stage-1 single-agent gym), `obs` (Markov-sufficient, hides who-holds-what, +last-8 message window), `action_space` (Discrete(39) = 24 game + 15 SPEAK, **ego-centric relative-seat** mask), `train`, `evaluate`, `baseline`, `policies`, `selfplay_env`, `pool`.
- `social_roulette/observe/` — **match observation engine**: `events` (schema + reserved `message` type for Stage-3 comms), `recorder`, `match` (`run_match` = canonical full-table runner, per-seat policies, reused by Stage-2 self-play), `store` (chunked **zstd Parquet**), views: `text_replay`, `health`.
- `social_roulette/rl/selfplay.py` — Stage-2/3 self-play: pool, parallel SubprocVecEnv, eval, per-seat diag, `--comms`/`--retrain-seed`/`--run-parallel`.
- `social_roulette/rl/comms_eval.py` — Stage-3 metrics: `response_shift` (flip-rate=sensitivity), `winrate_ablation` (receiver), `sender_ablation`.
- `social_roulette/comms/vocab.py` — emoji vocabulary (5-act v1, 15 speak options, NL render).
- `social_roulette/rl/fear_env.py` + `fear.py` — Stage-4 fear probe (per-agent fear weight + behavior sweep).
- `tests/` — **171 passing**. `models/` — `stage1a/b`, `stage2seed`, `stage2/gen1`, `stage3seed`, `stage3/gen1`, `fear`.
- `docs/` — `stage1_results.md`, `stage2_results.md`, `stage3_results.md`, `stage4_fear_results.md`. `docs/superpowers/specs|plans/` — per-stage design+plan.
- `mechanics_audit.md` — game-rules audit. `training_design_audit.md` — RL-design adversarial audit (28 findings).

## Environment (Windows)
- **Python 3.13 venv at `.venv`** (py3.14 also installed but UNUSABLE — no torch wheels; always `py -3.13`).
- Stack: torch **2.12.1+cpu**, gymnasium 1.3.0, stable-baselines3 2.9.0, sb3-contrib 2.9.0, pyarrow 24, scipy, pytest.
- `.venv/`, `records/`, `records_demo/` are gitignored.
- **Device = CPU for Stage 1** (GPU gives no speedup on this env-bound, tiny-MLP workload). **GOTCHA:** installing SB3 from PyPI reverts torch to its CPU build → for GPU you must reinstall torch from a **cu126/cu128** index *after* SB3 (cu124 maxes at torch 2.6.0). GPU only matters from Stage 2.

## Commands (from repo root)
```
./.venv/Scripts/python -m pytest -q                                   # 171 tests
# Stage-3 comms run + measure:
PYTHONUTF8=1 ./.venv/Scripts/python -m social_roulette.rl.selfplay --run-parallel --comms --gens 1 --steps-per-gen 250000 --seed-model models/stage3seed --out models/stage3
# Stage-4 fear:  python -m social_roulette.rl.fear --train --measure --out models/fear
./.venv/Scripts/python -m social_roulette.rl.baseline                  # 0.1934
./.venv/Scripts/python -m social_roulette.rl.train [--shoot-only] --steps N --out models/X
./.venv/Scripts/python -m social_roulette.rl.evaluate models/X [--shoot-only]
# observe (UTF-8 for emoji): PYTHONUTF8=1 ./.venv/Scripts/python -c "from social_roulette.observe import store,text_replay,health; print(text_replay.render(store.read_match(DIR, ID)))"
```

## Locked decisions (do NOT re-litigate — detail in specs/audits)
- RL agents, **not** LLMs. Fixed **emoji** comms dictionary for Stage 3 (compositional, length-capped, public broadcast, lying allowed).
- Stage 1 = **single-agent** (opponents = fixed random in-env). Stage 2 = **checkpoint self-play, opponent POOL** of frozen past selves (mostly recent + some old — single-latest cycles RPS).
- **Individual reward** (no shared); teams = a no-shoot constraint + flip economy only.
- **Reward terminal-only** (+1 win / −1 death); shaping behind a flag only if needed.
- Obs Markov-sufficient, **hides who-holds-what**; action = **ego-centric (relative-seat)** masked `Discrete(24 game + 15 speak)`; env auto-pays cheapest for flips. (Stage-2 fix: was absolute-seat → seat-0-only bug.)
- Records = **event-sourced → chunked zstd Parquet**; views pluggable (CLI storyboard / narrator / web = future views, zero rework).

## Stage 2 — status (2026-06-30)
Built + validated. See `docs/stage2_results.md` + `docs/superpowers/specs/2026-06-30-stage2-self-play-design.md`.
- Machinery: `rl/selfplay.py` (pool, parallel SubprocVecEnv self-play, eval, per-seat diag), `rl/selfplay_env.py`, `rl/pool.py`, shared `sim/turn.py`, ego-centric `rl/obs.py`+`rl/action_space.py`.
- **Bug caught + fixed:** obs/actions were absolute-seat-indexed → policy was seat-0-only → self-play opponents were secretly crippled. Fixed with **ego-centric encoding**; seat-invariance proven (flat per-seat win-rate). New seat-invariant seed = `models/stage2seed` (stage1b retired).
- **Result:** eval honest (seed-vs-4×seed = 0.21 ≈ fair share), self-play stable (no collapse), **no significant skill gain at 250k smoke** (gen1 +0.017 over the 0.210 control, p≈0.18). Lever for a real gain = more **training** (not eval).
- Parallelism: SubprocVecEnv = 1.6× only (PPO serial grad phase caps it on a tiny MLP). GPU does NOT help (env-bound); GPU only matters at Stage 3 (transformer).

## Stage 3 — status (2026-06-30)
Built + measured. See `docs/stage3_results.md` + spec/plan `…2026-06-30-stage3-comms*`.
- **Channel works:** emoji `[ACT][WHO][VALUE]`, 5-act v1 set, ≤2 msgs/turn, public, lying allowed, normal-turns-only. Agents **speak** (masked Speak action → `MESSAGE` event) and **perceive** (last-8-message window in obs, re-relativized). Comms gated behind `state.comms_enabled` (opt-in) so Stage-1/2 baselines are untouched. Seat-invariance preserved (seed-vs-seed = 0.193).
- **Verdict = cheap-talk NULL (expected), both pathways:** receiver ablation (intact 0.1996 vs scrambled 0.2132, p=0.12) AND sender ablation (intact 0.1996 vs field-deaf 0.2116, p=0.15) — neither hearing nor broadcasting helps win-rate; n=2500/arm, powered for 0.03. Decisions are *sensitive* to messages (flip-rate 0.55) but identically so in a random-trained seed → incidental, not learned. Under individual reward, agents don't use the channel for gain.
- **Methodological catch:** flip-rate = input-sensitivity, NOT benefit; only the outcome (win-rate) ablation measures use. Rich 28-act vocab remains designed-on-paper (expand only if a regime shows use).
- Artifacts: `models/stage3seed`, `models/stage3/gen1`.

## Stage 4 (probe) — fear (2026-06-30)
Built + measured. See `docs/stage4_fear_results.md`.
- Per-agent fear weight `f~U[0,3]` scales the death penalty (−f), exposed in the agent's own obs (`fear_env.py`, `fear.py`). Trained 1M vs random.
- **INERT:** self-shot rate, heal rate, win-rate all FLAT across `f∈[0,3]`. Pre-registered FAIL branch.
- Leading explanation (NOT proven, 1 seed): vs random, safe play is already win-optimal → no risk tradeoff for fear to tip. **Confounds not ruled out:** the `f` scalar may be unlearnable in a 102-dim obs; self-shot ~0.02 floor leaves no room to fall. To distinguish: test fear under self-play AND probe behaviors with headroom (aggression, defensive-item use), not just self-shot/heal.

## Open levers / next (PAUSED here — user's call)
Per the THROUGHLINE: change the incentive or the opponent, not the behavior.
| Lever | The bet | Cost |
|---|---|---|
| **Deep comms co-evolution** | many generations, all comms-on → talk may bootstrap (UNTESTED) | medium |
| **Fear under self-play** | competent opponent makes risk tempting → personalities may form (UNTESTED) | low — reuse `selfplay_env` + fear weight |
| **Change incentives** | team reward / cross-game reputation / private-info-worth-sharing → gives social behavior a payoff | larger redesign |
| **Bank** | the harness + the honest "self-interest → no social behavior" finding is itself the result | zero |

## Audit's standing verdict
Stages 0–1 = buildable & **done** (the safe half). Stage 2 = unprecedented method/compute quadrant — a research bet; set a hard compute stop and make every stage gate a number. Stage 3 comms = **near-determined null** under individual reward (agents may ignore the channel) — that null is itself a valid result to design for.

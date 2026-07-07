# Sealed expectations — pre-registered BEFORE firing (2026-07-08)

Kept OUT of every manifest. The expert never sees this file. At read-back, recovery of
these planted known-weak spots calibrates whether the sweep was real. (Claude-authored;
these are suspicions, not verified findings.)

| # | Expected finding | Where it hides |
|---|---|---|
| X1 | Flip-back discount edge: discount survives being flipped back by a THIRD party — audit E4 flagged "⚠ edge", spec has no treatment | RULES_AUDIT E4 vs spec §9 D-table / §4 |
| X2 | Reload item draws emit NO events today (`reload.draw_items_for_all` is silent, recorder has no draw method) — spec M17 promises animated per-player draws but §4.6/§5 never lists the new event emission the server must add | reload.py:7-17, recorder.py, spec M17 vs §4.6 |
| X3 | Timer vs cascade skew: the 30s decision clock starts server-side while the client is still replaying the previous event cascade — effective thinking time can be far under 30s; spec silent | spec §4.3 + §7 cascade durations |
| X4 | Bonus-turn timeout fines: guide:192 explicitly extends fines to bonus turns; spec §4.2 names only "DECISION deadline" — implicit at best | guide:192 vs spec §4.2 |
| X5 | `fine` event type added (§4.6) but the Recorder has no fine method and §5's engine-change table omits recorder work | recorder.py vs spec §4.6/§5 |
| X6 | Setup-ceremony data source: M1 coin flip (odd-split) and per-seat opening draws are not in any event or view today (`new_game` buries them); spec never says where M1/M4 data comes from | engine.py:76-96 vs spec M1/M4 |

Recovery bar: ≥4 of 6 independently found → sweep credible. <4 → re-fire with sharpened duties.

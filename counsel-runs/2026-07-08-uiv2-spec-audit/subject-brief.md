# Subject Brief — UI v2 Design-Spec Audit

**Run:** 2026-07-08-uiv2-spec-audit · **Kind:** audit · **Panel:** ONE Fable expert (user-set)

## The exact question

Is `docs/superpowers/specs/2026-07-07-ui-v2-phaser-design.md` a SAFE contract to build
from — or does it miss, contradict, or under-specify anything material in
(a) the game rules (`game_guide.md`, every line),
(b) the codebase it claims to extend (engine + online server as they actually are),
(c) the known gap list it claims to close (`docs/RULES_AUDIT.md`),
(d) itself (internal contradictions between its own sections)?

Trigger: the user personally caught a miss (inventory-cap display, guide:40-42) that the
spec had dropped despite two prior passes. Assume more misses exist. Hunt them.

## What a useful answer looks like

Atomic records, each ONE claim, each with verbatim locatable quotes:
- **missed rule** — a guide rule with no spec treatment (UI, server, or engine) where one is needed;
- **contradiction** — spec vs guide, spec vs code reality, or spec section vs spec section;
- **under-specified mechanism** — a spec promise the named code seam cannot deliver as written
  (e.g. an event the server never emits, a state the view never carries);
- **unaddressed audit row** — a RULES_AUDIT gap (49 rows) the spec neither fixes nor
  explicitly defers;
- **well-evidenced "nothing found"** for any duty that comes up clean.

## Out of scope

Aesthetic taste (art style, theme, layout are user-ratified) · naming quality (names are
user-picked; missing/TBD names are user-owned deferrals, not findings) · Track A / RL
code · deploy/hosting · bot intelligence · sound. Deliberate, stated deferrals inside
the spec ("build-time pick", "naming pass later") are not findings — but an UNSTATED
omission is.

## Pass bar (defined before firing)

The run passes if: the journal seals with every must_read context item read; the
read-back gate (`verify-readback.js`) exits clean; and at read-back the sealed
pre-registered expectations list (`expectations-sealed.md`, kept out of the manifest)
is substantially recovered — the expert independently finding the planted known-weak
spots is the calibration that the sweep was real. Misses against the sealed list =
audit judged shallow → re-fire with sharpened duties.

**Ratified by Sina:** 2026-07-08 (AskUserQuestion: "Ratify as written")

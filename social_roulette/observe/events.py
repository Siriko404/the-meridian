"""Canonical match-event schema — the contract every view reads.

One row per event. Common columns are queryable; type-specific fields live in
the `extra` JSON column so NEW event types never break the schema.
"""

SCHEMA_VERSION = 2   # v2 (2026-07-10): column `shell` -> `bullet`; item enums renamed to final names

# event types
MATCH_START = "match_start"
TURN_START = "turn_start"
ITEM_USED = "item_used"
FLIP = "flip"
SHOT = "shot"
BONUS = "bonus"
ELIMINATION = "elimination"
RELOAD = "reload"
MESSAGE = "message"        # future: emoji comms (schema ready, unused in Stage 1)
GIFT = "gift"              # Stage 5: an item handed to a teammate (costly signal)
FINE = "fine"              # v2: timeout fine (public copy names no item)
SKIP = "skip"              # v2: a handcuffed seat was skipped at turn advance
DRAW = "draw"              # v2: reload refill draws (per-seat enrichment)
TRADE = "trade"            # v2: settled offer/accept swap
TICK = "tick"              # v3: poison tick fired at the poisoner's turn start (or their death)
MATCH_END = "match_end"

COLUMNS = ["match_id", "seq", "turn", "actor", "type", "target",
           "item", "bullet", "damage", "killed", "extra"]

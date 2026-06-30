"""Canonical match-event schema — the contract every view reads.

One row per event. Common columns are queryable; type-specific fields live in
the `extra` JSON column so NEW event types never break the schema.
"""

SCHEMA_VERSION = 1

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
MATCH_END = "match_end"

COLUMNS = ["match_id", "seq", "turn", "actor", "type", "target",
           "item", "shell", "damage", "killed", "extra"]

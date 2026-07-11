from dataclasses import dataclass, field

from .constants import MAX_PER_TYPE, MAX_TOTAL


@dataclass
class Player:
    id: int
    team: object
    cover: int
    alive: bool
    inventory: dict
    immunity_against: set
    handcuffed: bool
    flipback_discount: bool
    poison_tick: int = None    # poisoner pid whose next turn-start costs me 1 cover; max ONE (no stacking)


@dataclass
class Chamber:
    bullets: list
    pos: int = 0

    def remaining(self):
        return self.bullets[self.pos:]

    def current(self):
        return self.bullets[self.pos] if self.pos < len(self.bullets) else None

    def is_empty(self):
        return self.pos >= len(self.bullets)


@dataclass
class Msg:
    turn: int
    speaker: int      # absolute seat id
    act: int
    target: int       # absolute seat id, or None
    value: int        # 0/1, or None


@dataclass
class GameState:
    players: list
    order: list
    current_id: int
    chamber: object
    rng: object
    use_counts: dict = field(default_factory=dict)
    poison_armed: bool = False
    poison_used_this_turn: bool = False
    bonus_pending: bool = False
    winner: int = None
    messages: list = field(default_factory=list)
    msgs_this_turn: int = 0
    comms_enabled: bool = False   # Stage 3 opt-in; off => no Speak in legal_actions
    social_enabled: bool = False  # Stage 5 opt-in; off => no Trade/gift in legal_actions
    # Stage 5 interaction memory (objective public record; each seat reads its own row):
    harm: dict = field(default_factory=dict)   # (victim_id, actor_id) -> cumulative damage taken from actor
    help: dict = field(default_factory=dict)   # (receiver_id, giver_id) -> cumulative gift point-value received
    last_skipped: list = field(default_factory=list)  # pids skipped by handcuff at turn advance
    last_ticks: list = field(default_factory=list)    # (victim, poisoner, killed) fired at turn advance / a death


def player_by_id(state, pid):
    return next(p for p in state.players if p.id == pid)


def living_players(state):
    return [p for p in state.players if p.alive]


def living_ids(state):
    return {p.id for p in state.players if p.alive}


def inventory_total(p):
    return sum(p.inventory.values())


def can_receive(p, item):
    return p.inventory.get(item, 0) < MAX_PER_TYPE and inventory_total(p) < MAX_TOTAL

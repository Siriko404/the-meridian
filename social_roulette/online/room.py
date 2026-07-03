"""Room — the pure, synchronous game state-machine. No asyncio, no network.

Humans act ONE engine.step at a time (an action is legal until they shoot; the
engine then advances the turn). Bot seats run the existing take_policy_turn.
The async server wraps this class; all game logic and every invariant live here
so they are unit-testable without a socket.
"""
from social_roulette.engine.engine import new_game, step as engine_step
from social_roulette.engine.constants import Item
from social_roulette.engine.actions import legal_actions
from social_roulette.sim.turn import take_policy_turn, random_policy, Extras
from social_roulette.online.view import seat_view


class IllegalAction(Exception):
    pass


class Room:
    def __init__(self, human_seats, seed, num_players=5):
        self.human = set(human_seats)
        self.state = new_game(num_players, seed)
        self.state.comms_enabled = False
        self.state.social_enabled = False
        self.extras = {i: Extras() for i in range(num_players)}
        for e in self.extras.values():
            e.sync(self.state)
        self.feed = []
        self._run_bots()               # auto-play any leading bot seats

    @property
    def winner(self):
        return self.state.winner

    @property
    def current(self):
        return self.state.current_id

    def is_bot(self, seat):
        return seat not in self.human

    def view(self, seat):
        return seat_view(self.state, seat, self.extras[seat].d(), self.feed)

    def apply(self, seat, i):
        if self.winner is not None or seat != self.state.current_id:
            raise IllegalAction("not your turn")
        acts = legal_actions(self.state, seat)
        if not (0 <= i < len(acts)):
            raise IllegalAction("no such action")
        action = acts[i]
        is_mag = getattr(action, "item", None) == Item.MAGNIFIER
        engine_step(self.state, seat, action)
        if is_mag:
            self.extras[seat].peek(self.state)
        for e in self.extras.values():
            e.sync(self.state)
        self._run_bots()

    def _run_bots(self):
        while self.state.winner is None and self.is_bot(self.state.current_id):
            take_policy_turn(self.state, self.state.current_id, random_policy, self.extras)

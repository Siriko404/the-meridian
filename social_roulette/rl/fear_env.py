"""Stage-4 risk personalities: a per-agent FEAR weight.

Each episode draws a fear weight f ~ U[0, FEAR_MAX]. Death costs -f (instead of -1);
winning still pays +1. f is appended to the agent's own observation, so ONE policy
can condition its risk attitude on f. A pure win-maximizer is risk-neutral; f departs
from that — higher f => death hurts more => the agent should play safer.

Opponents = fixed random policy (Stage-1 framing); comms off. This isolates ONE
lever (fear) to test ONE thing: does cautious behavior rise with f?
"""
import numpy as np
import gymnasium as gym
from gymnasium import spaces

from social_roulette.engine.engine import new_game, step as engine_step
from social_roulette.engine.constants import Bullet, Item
from social_roulette.engine.state import player_by_id
from social_roulette.sim.turn import take_policy_turn, Extras, random_policy
from social_roulette.rl.obs import encode_obs, OBS_DIM
from social_roulette.rl.action_space import ActionCodec, ACTION_N

FEAR_MAX = 3.0


class SocialRouletteFearEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, num_players=5, learner_id=0, fear_max=FEAR_MAX):
        super().__init__()
        self.num_players = num_players
        self.learner_id = learner_id
        self.fear_max = fear_max
        self.observation_space = spaces.Box(-1.0, 5.0, shape=(OBS_DIM + 1,), dtype=np.float32)
        self.action_space = spaces.Discrete(ACTION_N)
        self.state = None
        self.fear = 0.0
        self._extras = {}

    def _pre_obs(self):
        for _ in range(100):
            if self.state.winner is not None or not self._learner().alive:
                return
            if self.state.current_id != self.learner_id:
                self._run_opponents()
                continue
            if self.state.tax_pending:
                _auto_resolve_tax(self.state, self.learner_id)
                continue
            return

    def _obs(self):
        base = encode_obs(self.state, self.learner_id, self._extras[self.learner_id].d())
        return np.concatenate([base, [np.float32(self.fear / self.fear_max)]]).astype(np.float32)

    def _mask(self):
        return ActionCodec.legal_mask(self.state, self.learner_id, shoot_only=False)

    def _info(self):
        return {"action_mask": self._mask()}

    def _learner(self):
        return player_by_id(self.state, self.learner_id)

    def _terminal(self):
        return self.state.winner is not None or not self._learner().alive

    def _reward(self):
        if self.state.winner == self.learner_id:
            return 1.0
        if not self._learner().alive:
            return -self.fear
        return 0.0

    def _run_opponents(self):
        while (self.state.winner is None and self.state.current_id != self.learner_id
               and self._learner().alive):
            take_policy_turn(self.state, self.state.current_id, random_policy, self._extras)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        game_seed = seed if seed is not None else int(self.np_random.integers(0, 1_000_000))
        self.fear = float(self.np_random.uniform(0.0, self.fear_max))
        self.state = new_game(self.num_players, game_seed)
        self._extras = {i: Extras() for i in range(self.num_players)}
        for e in self._extras.values():
            e.sync(self.state)
        self._run_opponents()
        self._pre_obs()
        return self._obs(), self._info()

    def step(self, idx):
        action = ActionCodec.decode(int(idx), self.state, self.learner_id)
        is_scan = getattr(action, "item", None) == Item.GEIGER
        res = engine_step(self.state, self.learner_id, action)
        if is_scan:
            self._extras[self.learner_id].scan(res)
        for e in self._extras.values():
            e.sync(self.state)
        if not self._terminal() and self.state.current_id != self.learner_id:
            self._run_opponents()
        self._pre_obs()
        return self._obs(), self._reward(), self._terminal(), False, self._info()

def _auto_resolve_tax(state, learner_id):
    """RL codec carries no PayTax action (ledger ruling: auto-rule). Greedy: keep
    the turn silently for 4 if affordable, else skip."""
    from social_roulette.engine.actions import PayTax, cheapest_payment, legal_actions as _la
    from social_roulette.engine.engine import step as _step
    from social_roulette.engine.state import player_by_id as _pbi
    while (state.winner is None and state.tax_pending
           and state.current_id == learner_id and _pbi(state, learner_id).alive):
        pay = cheapest_payment(_pbi(state, learner_id), 4)
        _step(state, learner_id, PayTax(4, pay) if pay is not None else PayTax(0))

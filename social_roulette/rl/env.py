import numpy as np
import gymnasium as gym
from gymnasium import spaces

from social_roulette.engine.engine import new_game, step as engine_step
from social_roulette.engine.constants import Bullet, Item
from social_roulette.engine.state import player_by_id
from social_roulette.sim.random_agent import take_random_turn
from social_roulette.rl.obs import encode_obs, OBS_DIM
from social_roulette.rl.action_space import ActionCodec, ACTION_N


class SocialRouletteSingleEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, num_players=5, learner_id=0, shoot_only=False):
        super().__init__()
        self.num_players = num_players
        self.learner_id = learner_id
        self.shoot_only = shoot_only
        self.observation_space = spaces.Box(-1.0, 5.0, shape=(OBS_DIM,), dtype=np.float32)
        self.action_space = spaces.Discrete(ACTION_N)
        self.state = None
        self._scan = (None, 0)     # (scan_live, scan_of) — own GEIGER result
        self._ann_total = 0
        self._ann_live = 0
        self._last_chamber = None
        self._last_pos = 0
        self._last_len = 0

    def _on_chamber_change(self):
        ch = self.state.chamber
        if ch is not self._last_chamber:
            self._last_chamber = ch
            self._ann_total = len(ch.bullets)
            self._ann_live = sum(1 for s in ch.bullets if s == Bullet.LIVE)
            self._scan = (None, 0)
            self._last_pos = ch.pos
            self._last_len = len(ch.bullets)
        elif ch.pos != self._last_pos or len(ch.bullets) != self._last_len:
            self._scan = (None, 0)   # window moved or a MAGNET ejected from it
            self._last_pos = ch.pos
            self._last_len = len(ch.bullets)

    def _extras(self):
        return {"scan_live": self._scan[0], "scan_of": self._scan[1],
                "announced_total": self._ann_total, "announced_live": self._ann_live}

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
        return encode_obs(self.state, self.learner_id, self._extras())

    def _mask(self):
        return ActionCodec.legal_mask(self.state, self.learner_id, self.shoot_only)

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
            return -1.0
        return 0.0

    def _run_opponents(self):
        while (self.state.winner is None and self.state.current_id != self.learner_id
               and self._learner().alive):
            take_random_turn(self.state, self.state.current_id)
            self._on_chamber_change()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        game_seed = seed if seed is not None else int(self.np_random.integers(0, 1_000_000))
        self.state = new_game(self.num_players, game_seed)
        self._last_chamber = None
        self._on_chamber_change()
        self._run_opponents()
        self._pre_obs()
        return self._obs(), self._info()

    def step(self, idx):
        action = ActionCodec.decode(int(idx), self.state, self.learner_id)
        is_scan = getattr(action, "item", None) == Item.GEIGER
        res = engine_step(self.state, self.learner_id, action)
        if is_scan:
            self._scan = (res.get("scan_live"), res.get("scan_of", 0))
        self._on_chamber_change()
        if not self._terminal() and self.state.current_id != self.learner_id:
            self._run_opponents()
        terminated = self._terminal()
        self._pre_obs()
        return self._obs(), self._reward(), terminated, False, self._info()

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

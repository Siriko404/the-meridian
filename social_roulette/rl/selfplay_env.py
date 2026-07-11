"""Stage-2 self-play env: opponents are frozen checkpoints sampled from a pool.

Same gym contract as the Stage-1 SocialRouletteSingleEnv, but the 4 opponents are
model-backed policies drawn fresh each reset() from `opponent_sampler(rng)`.
Because the pool is frozen during a generation, the env is a stationary
single-agent POMDP — no PettingZoo needed (deliberate deviation from spec §4).

Opponent turns run through `sim.turn.take_policy_turn` — the SAME primitive eval
uses — so eval never measures a different opponent than training saw. Every seat
keeps its own Extras (announced counts + magnifier peek), or model opponents would
predict on the wrong observation and play weaker than their checkpoint.
"""
import numpy as np
import gymnasium as gym
from gymnasium import spaces

from social_roulette.engine.engine import new_game, step as engine_step
from social_roulette.engine.constants import Item
from social_roulette.engine.state import player_by_id
from social_roulette.sim.turn import take_policy_turn, Extras
from social_roulette.rl.obs import encode_obs, OBS_DIM
from social_roulette.rl.action_space import ActionCodec, ACTION_N


class SocialRouletteSelfPlayEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, opponent_sampler, num_players=5, learner_id=0, shoot_only=False, comms=False):
        super().__init__()
        if opponent_sampler is None:
            raise ValueError("opponent_sampler is required")
        self.opponent_sampler = opponent_sampler
        self.num_players = num_players
        self.learner_id = learner_id
        self.shoot_only = shoot_only
        self.comms = comms
        self.observation_space = spaces.Box(-1.0, 5.0, shape=(OBS_DIM,), dtype=np.float32)
        self.action_space = spaces.Discrete(ACTION_N)
        self.state = None
        self._extras = {}
        self._opp_pol = {}

    def _obs(self):
        return encode_obs(self.state, self.learner_id, self._extras[self.learner_id].d())

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
            pid = self.state.current_id
            take_policy_turn(self.state, pid, self._opp_pol[pid], self._extras)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        game_seed = seed if seed is not None else int(self.np_random.integers(0, 1_000_000))
        self.state = new_game(self.num_players, game_seed)
        self.state.comms_enabled = self.comms
        self._extras = {i: Extras() for i in range(self.num_players)}
        for e in self._extras.values():
            e.sync(self.state)
        self._opp_pol = {seat: self.opponent_sampler(self.np_random)
                         for seat in range(self.num_players) if seat != self.learner_id}
        self._run_opponents()
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
        terminated = self._terminal()
        return self._obs(), self._reward(), terminated, False, self._info()

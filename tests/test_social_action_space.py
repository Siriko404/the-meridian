from social_roulette.engine.engine import new_game
from social_roulette.engine.actions import Trade
from social_roulette.engine.constants import Item
from social_roulette.engine.state import player_by_id
from social_roulette.rl.action_space import ActionCodec, ACTION_N as BASE_N
from social_roulette.rl.social_action_space import (
    SocialActionCodec, ACTION_N_SOCIAL, GIFT_ITEMS, GIFT_N)


def test_action_n():
    assert GIFT_N == 24
    assert ACTION_N_SOCIAL == BASE_N + GIFT_N == 63


def test_gift_decode_encode_roundtrip():
    g = new_game(5, 0)
    for learner in range(5):
        for r in range(1, 5):
            for item in GIFT_ITEMS:
                target = (learner + r) % 5
                idx = SocialActionCodec._index_of(Trade(target, [item]), learner)
                assert BASE_N <= idx < ACTION_N_SOCIAL
                a = SocialActionCodec.decode(idx, g, learner)
                assert isinstance(a, Trade) and a.to_id == target and a.items == [item]


def test_base_actions_pass_through():
    g = new_game(5, 0)
    for idx in range(BASE_N):
        assert type(SocialActionCodec.decode(idx, g, 0)) is type(ActionCodec.decode(idx, g, 0))


def test_mask_includes_legal_gift_and_shoot_only_excludes():
    g = new_game(5, 0)
    g.social_enabled = True
    g.current_id = 0
    mate = next(p.id for p in g.players if p.id != 0 and p.team == g.players[0].team)
    player_by_id(g, 0).inventory = {Item.MAGNET: 1}
    player_by_id(g, mate).inventory = {}
    mask = SocialActionCodec.legal_mask(g, 0, shoot_only=False)
    assert mask.shape == (ACTION_N_SOCIAL,)
    assert mask[SocialActionCodec._index_of(Trade(mate, [Item.MAGNET]), 0)]
    assert not SocialActionCodec.legal_mask(g, 0, shoot_only=True)[BASE_N:].any()

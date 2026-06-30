from social_roulette.comms.vocab import Act, ACT_N, SPEAK_N, SPEAK_TABLE, speak_index, render


def test_speak_table_is_bijective():
    assert SPEAK_N == len(SPEAK_TABLE) == 15
    for i, (act, who, val) in enumerate(SPEAK_TABLE):
        assert speak_index(act, who, val) == i


def test_table_covers_expected_acts():
    acts = [t[0] for t in SPEAK_TABLE]
    assert acts.count(Act.SHOOT_INTENT) == 4
    assert acts.count(Act.GANG_UP) == 4
    assert acts.count(Act.NEXT_SHELL) == 2
    assert acts.count(Act.TRUCE) == 4
    assert acts.count(Act.AGREE) == 1


def test_render_examples():
    assert render(Act.SHOOT_INTENT, "Wolf", None) == "I'll shoot Wolf"
    assert render(Act.NEXT_SHELL, None, 1) == "next shell is live"
    assert render(Act.AGREE, None, None) == "agreed"

import json
from social_roulette.online.room import Room
from social_roulette.engine.state import player_by_id
from social_roulette.engine.constants import Item


def clockroom():
    t = [1000.0]
    return Room(human_seats={0, 1, 2, 3, 4}, seed=0, now_fn=lambda: t[0]), t


def test_view_carries_v2_fields():
    r, t = clockroom()
    v = r.view(r.current)
    for k in ("phase", "phase_ends_at", "server_now", "bonus", "extra_turn",
              "poison_armed", "use_counts", "use_limit", "teams_active"):
        assert k in v, k
    assert v["phase"] == "talk" and v["teams_active"] is True
    assert v["use_limit"] == 5                       # cap = living players (×1.0, 2026-07-10)
    me = r.view(r.current)
    assert "flipback_discount" in me


def test_trade_event_public_strips_and_parties_enriched():
    r, t = clockroom()
    seat = r.current
    me = player_by_id(r.state, seat)
    mate = next(p.id for p in r.state.players
                if p.id != seat and p.alive and p.team == me.team)
    bystander = next(p.id for p in r.state.players if p.id not in (seat, mate))
    player_by_id(r.state, seat).inventory = {Item.MAGNET: 1}
    player_by_id(r.state, mate).inventory = {Item.POISON: 1}
    r.trade_offer(seat, mate, ["MAGNET"], ["POISON"])
    r.trade_respond(mate, True)
    pub = [e for e in r.events_for(bystander) if e["type"] == "trade"][0]
    assert "items" not in pub and "give" not in json.dumps(pub)
    mine = [e for e in r.events_for(seat) if e["type"] == "trade"][0]
    assert mine["items"] == {"give": ["MAGNET"], "want": ["POISON"]}


def test_no_foreign_hand_or_bullet_order_in_any_view_or_events():
    r, t = clockroom()

    def sweep():
        for seat in range(5):
            blob = json.dumps({"v": r.view(seat), "e": r.events_for(seat)})
            assert "bullets" not in blob
            assert "Bullet.LIVE" not in blob and "Bullet.BLANK" not in blob
            # a draw event may only ever carry THIS seat's own refill, never another's
            for e in r.events_for(seat):
                if e.get("type") == "draw":
                    assert set(e.keys()) <= {"type", "you"}

    sweep()
    # Drive the match to completion via deadline auto-shoots: this exercises real
    # reloads (-> draw events), eliminations and phase churn, so the sweep is genuine.
    for _ in range(60):
        if r.winner is not None:
            break
        t[0] = (r.phase_ends_at or t[0]) + 0.1
        r.on_deadline()
        sweep()


def test_magnet_eject_value_only_for_the_ejector():
    r, t = clockroom()
    seat = r.current
    player_by_id(r.state, seat).inventory = {Item.MAGNET: 1}
    i = next(a["i"] for a in r.view(seat)["legal"] if a["kind"] == "item" and a["item"] == "MAGNET")
    r.apply(seat, i)
    mine = [e for e in r.events_for(seat) if e.get("item") == "MAGNET"][0]
    assert mine["you"]["ejected"] in ("LIVE", "BLANK")
    other = next(p for p in range(5) if p != seat)
    theirs = [e for e in r.events_for(other) if e.get("item") == "MAGNET"][0]
    assert "you" not in theirs and "seq" not in theirs and "ejected" not in json.dumps(theirs)

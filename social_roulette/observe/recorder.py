"""Recorder — collects ordered event rows for a single match.

Pure data: produces a list of flat dicts (one per event) matching events.COLUMNS.
A view or a Parquet writer consumes `recorder.rows`. The engine never imports this.
"""
import json

from . import events as E


class Recorder:
    def __init__(self, match_id):
        self.match_id = str(match_id)
        self.rows = []
        self._seq = 0

    def _emit(self, type, turn=None, actor=None, target=None, item=None,
              bullet=None, damage=None, killed=None, extra=None):
        self.rows.append({
            "match_id": self.match_id, "seq": self._seq, "turn": turn, "actor": actor,
            "type": type, "target": target, "item": item, "bullet": bullet,
            "damage": damage, "killed": killed,
            "extra": json.dumps(extra, separators=(",", ":")) if extra is not None else None,
        })
        self._seq += 1

    def match_start(self, players, num_players, seed, ann_total, ann_live):
        self._emit(E.MATCH_START, turn=0, extra={
            "schema_version": E.SCHEMA_VERSION, "num_players": num_players, "seed": seed,
            "announced_total": ann_total, "announced_live": ann_live,
            "players": [{"id": p.id, "team": p.team.name, "lives": p.cover,
                         "inv": {it.name: c for it, c in p.inventory.items()}} for p in players],
        })

    def turn_start(self, turn, actor, team, lives):
        self._emit(E.TURN_START, turn=turn, actor=actor, extra={"team": team, "lives": lives})

    def item_used(self, turn, actor, item, target, effect):
        self._emit(E.ITEM_USED, turn=turn, actor=actor, item=item, target=target, extra=effect or {})

    def flip(self, turn, actor, target, paid, new_team):
        self._emit(E.FLIP, turn=turn, actor=actor, target=target,
                   extra={"paid": paid, "new_team": new_team})

    def shot(self, turn, actor, target, bullet, damage, killed, poison):
        self._emit(E.SHOT, turn=turn, actor=actor, target=target, bullet=bullet,
                   damage=damage, killed=killed, extra={"poison": poison, "self": actor == target})

    def bonus(self, turn, actor):
        self._emit(E.BONUS, turn=turn, actor=actor)

    def elimination(self, turn, victim, killer):
        self._emit(E.ELIMINATION, turn=turn, actor=killer, target=victim)

    def reload(self, turn, reason, new_total, new_live):
        self._emit(E.RELOAD, turn=turn, extra={"reason": reason, "new_total": new_total, "new_live": new_live})

    def message(self, turn, speaker, act, target, value):
        self._emit(E.MESSAGE, turn=turn, actor=speaker, target=target,
                   extra={"act": act, "value": value})

    def gift(self, turn, giver, receiver, items):
        self._emit(E.GIFT, turn=turn, actor=giver, target=receiver, extra={"items": items})

    def fine(self, turn, actor, item):
        self._emit(E.FINE, turn=turn, actor=actor, extra={"item": item})

    def skip(self, turn, seat):
        self._emit(E.SKIP, turn=turn, target=seat)

    def draw(self, turn, draws):
        self._emit(E.DRAW, turn=turn, extra={"draws": draws})

    def tick(self, turn, poisoner, victim, killed):
        self._emit(E.TICK, turn=turn, actor=poisoner, target=victim, damage=1, killed=killed)

    def tax(self, turn, actor, tier):
        self._emit(E.TAX, turn=turn, actor=actor, extra={"tier": tier})

    def special(self, turn, actor, kind, target=None):
        self._emit(E.SPECIAL, turn=turn, actor=actor, target=target, extra={"kind": kind})

    def trade(self, turn, actor, target, give, want):
        self._emit(E.TRADE, turn=turn, actor=actor, target=target,
                   extra={"give": give, "want": want})

    def match_end(self, turn, winner):
        self._emit(E.MATCH_END, turn=turn, extra={"winner": winner, "turns": turn})

"""Health view — behavioral stats over a Parquet record set.

Catches degenerate play: games too short, items never firing, trivial wins.
Streams row-group batches and keeps only tiny per-match summaries in memory.
"""
import json
import statistics

from . import store

_MECHANICS = ["self_shot", "SAW", "BEER", "IMMUNITY", "HANDCUFFS", "flip",
              "elimination", "reload_empty", "reload_death", "bonus"]


def health(out_dir, learner_id=None):
    summ = {}   # match_id -> small summary
    for batch in store.iter_batches(out_dir, columns=["match_id", "type", "item", "extra"]):
        d = batch.to_pydict()
        for mid, ty, item, extra in zip(d["match_id"], d["type"], d["item"], d["extra"]):
            m = summ.setdefault(mid, {"mech": set(), "turns": None, "winner": None})
            if ty == "shot":
                e = json.loads(extra) if extra else {}
                if e.get("self"):
                    m["mech"].add("self_shot")
            elif ty == "item_used" and item:
                m["mech"].add(item)
            elif ty == "flip":
                m["mech"].add("flip")
            elif ty == "elimination":
                m["mech"].add("elimination")
            elif ty == "bonus":
                m["mech"].add("bonus")
            elif ty == "reload":
                e = json.loads(extra) if extra else {}
                m["mech"].add("reload_" + e.get("reason", "?"))
            elif ty == "match_end":
                e = json.loads(extra) if extra else {}
                m["turns"], m["winner"] = e["turns"], e["winner"]

    n = len(summ)
    turns = [m["turns"] for m in summ.values() if m["turns"] is not None]
    lines = [f"matches={n}   turns: mean={statistics.mean(turns):.1f} "
             f"median={statistics.median(turns)} min={min(turns)} max={max(turns)}"]
    if learner_id is not None:
        wins = sum(1 for m in summ.values() if m["winner"] == learner_id)
        lines.append(f"learner s{learner_id} win-rate = {wins / n:.3f}")
    lines.append("mechanic firing (% of matches):")
    for mech in _MECHANICS:
        pct = 100 * sum(1 for m in summ.values() if mech in m["mech"]) / n
        lines.append(f"   {mech:14s} {pct:5.1f}%")
    return "\n".join(lines)

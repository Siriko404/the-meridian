"""Text replay view — renders an ordered event list as a human-readable match.

A pure function of the event rows; reads nothing else. Every future view
(CLI storyboard, narrator, web timeline) is a sibling of this file.
"""
import json

HEART = "♥"


def render(rows):
    rows = sorted(rows, key=lambda r: r["seq"])
    out = []
    for r in rows:
        ex = json.loads(r["extra"]) if r["extra"] else {}
        ty = r["type"]
        if ty == "match_start":
            out.append(f"=== match {r['match_id']}  {ex['num_players']}p  seed={ex['seed']}  "
                       f"chamber {ex['announced_total']}sh/{ex['announced_live']}live ===")
            for p in ex["players"]:
                inv = " ".join(f"{k}:{v}" for k, v in p["inv"].items()) or "-"
                out.append(f"   s{p['id']} {p['team'][0]} {HEART * p['lives']}  [{inv}]")
        elif ty == "turn_start":
            out.append(f"T{r['turn']:03d}  s{r['actor']} ({ex['team'][0]} {HEART * ex['lives']})")
        elif ty == "item_used":
            tgt = f" -> s{r['target']}" if r["target"] is not None else ""
            detail = " ".join(f"{k}={v}" for k, v in ex.items())
            out.append(f"        uses {r['item']}{tgt}" + (f"  ({detail})" if detail else ""))
        elif ty == "flip":
            out.append(f"        FLIPS s{r['target']} -> {ex['new_team']}  (paid {ex['paid']})")
        elif ty == "shot":
            who = "SELF" if ex.get("self") else f"s{r['target']}"
            res = (f"LIVE \U0001f4a5 -{r['damage']}" if r["damage"] else f"{r['bullet']} click")
            saw = " [POISON x2]" if ex.get("saw") else ""
            out.append(f"        SHOOTS {who}: {res}{saw}")
        elif ty == "bonus":
            out.append(f"        ↺ earns bonus turn (self-blank)")
        elif ty == "elimination":
            out.append(f"        ☠ s{r['target']} ELIMINATED by s{r['actor']}")
        elif ty == "reload":
            out.append(f"        ↻ reload ({ex['reason']}) -> {ex['new_total']}sh/{ex['new_live']}live")
        elif ty == "match_end":
            w = ex["winner"]
            out.append(f"=== WINNER s{w}  in {ex['turns']} turns ===" if w is not None
                       else f"=== no winner ({ex['turns']} turns) ===")
    return "\n".join(out)

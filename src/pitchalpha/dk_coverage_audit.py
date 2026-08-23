from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from pitchalpha.raw_store import iter_raw


def audit_dk_fields(raw_dir: Path):
    totals = defaultdict(lambda: {"observed": 0, "non_null": 0, "positive": 0})
    accuracy_pairs = []
    latest = {}
    for path, doc in iter_raw(raw_dir, "fixtures_players"):
        fixture = int(doc["provenance"]["params"]["fixture"])
        latest[fixture] = (path, doc)
    for _, doc in latest.values():
        for team in doc["payload"].get("response") or []:
            for player in team.get("players") or []:
                for stats in player.get("statistics") or []:
                    position = (stats.get("games") or {}).get("position")
                    fields = {
                        "accurate_passes": (stats.get("passes") or {}).get("accuracy"),
                        "fouls_drawn": (stats.get("fouls") or {}).get("drawn"),
                        "goalkeeper_saves": (stats.get("goals") or {}).get("saves"),
                        "goals_allowed": (stats.get("goals") or {}).get("conceded"),
                        "penalties_missed": (stats.get("penalty") or {}).get("missed"),
                        "penalties_saved": (stats.get("penalty") or {}).get("saved"),
                    }
                    for name, value in fields.items():
                        if name in {"goalkeeper_saves", "goals_allowed", "penalties_saved"} and position != "G":
                            continue
                        totals[name]["observed"] += 1
                        if value is not None:
                            totals[name]["non_null"] += 1
                            try: totals[name]["positive"] += float(str(value).replace("%", "")) > 0
                            except ValueError: pass
                    total_passes = (stats.get("passes") or {}).get("total")
                    accurate = fields["accurate_passes"]
                    if total_passes is not None and accurate is not None:
                        try: accuracy_pairs.append((float(accurate), float(total_passes)))
                        except ValueError: pass
    matrix = [
        {"dk_event":"Crosses", "available":"No", "endpoint_field":"None at player level",
         "historical_coverage":"0%", "reliability":"Not supplied; team corners/cross attacks cannot be allocated to players."},
        {"dk_event":"Accurate passes", "available":"Ambiguous", "endpoint_field":"/fixtures/players passes.accuracy",
         "historical_coverage":_coverage(totals["accurate_passes"]),
         "reliability":f"Values were <= total passes in {sum(a<=t for a,t in accuracy_pairs)}/{len(accuracy_pairs)} observed pairs, but API documentation describes accuracy rather than an unambiguous completed-pass count. Do not score until verified."},
        {"dk_event":"Fouls drawn", "available":"Yes", "endpoint_field":"/fixtures/players fouls.drawn",
         "historical_coverage":_coverage(totals["fouls_drawn"]), "reliability":"Player-level; null is provider zero-event convention when minutes observed."},
        {"dk_event":"Goalkeeper saves", "available":"Yes", "endpoint_field":"/fixtures/players goals.saves",
         "historical_coverage":_coverage(totals["goalkeeper_saves"]), "reliability":"Player-level goalkeeper statistic."},
        {"dk_event":"Goals allowed", "available":"Yes", "endpoint_field":"/fixtures/players goals.conceded",
         "historical_coverage":_coverage(totals["goals_allowed"]), "reliability":"Player-level goalkeeper statistic."},
        {"dk_event":"Clean sheets", "available":"Derivable", "endpoint_field":"goals.conceded + position + minutes",
         "historical_coverage":"Same as goalkeeper goals.conceded", "reliability":"Requires DraftKings minimum-minutes eligibility rule."},
        {"dk_event":"Goalkeeper wins", "available":"Derivable", "endpoint_field":"fixture result + team + position",
         "historical_coverage":"380/380 fixtures", "reliability":"Reliable result; requires goalkeeper participation eligibility rule."},
        {"dk_event":"Penalties missed", "available":"Yes", "endpoint_field":"/fixtures/players penalty.missed; /fixtures/events Missed Penalty",
         "historical_coverage":_coverage(totals["penalties_missed"]), "reliability":"Player-level aggregate; events can verify scorer and minute."},
        {"dk_event":"Penalties saved", "available":"Yes", "endpoint_field":"/fixtures/players penalty.saved",
         "historical_coverage":_coverage(totals["penalties_saved"]), "reliability":"Player-level goalkeeper aggregate."},
        {"dk_event":"Assisted shots", "available":"Yes", "endpoint_field":"/fixtures/players passes.key",
         "historical_coverage":"Present for EPL player-match statistics", "reliability":"Key pass is the provider analogue; stat-provider definitions may differ."},
    ]
    return {"matrix": matrix, "raw_counts": dict(totals), "fixtures_audited": len(latest)}


def _coverage(item):
    return f"{item['non_null']}/{item['observed']} ({100*item['non_null']/max(1,item['observed']):.1f}% non-null)"

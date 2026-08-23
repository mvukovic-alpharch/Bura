"""Leakage-safe pre-match feature construction.

Every aggregate is computed before the current row is appended to history.  Rows
sharing a kickoff are processed as a batch, so even simultaneous matches cannot
inform one another.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Iterable, Mapping

WINDOWS = (3, 5, 10)
COUNT_STATS = ("minutes", "goals", "assists", "shots", "shots_on_target", "key_passes",
               "fouls_drawn", "tackles", "interceptions", "yellow_cards", "red_cards",
               "saves", "goals_conceded")


def _dt(value):
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _num(value) -> float:
    return float(value or 0.0)


def build_lagged_features(rows: Iterable[Mapping], target="actual_dk_points") -> list[dict]:
    """Return one feature row per input row using strictly earlier kickoffs."""
    ordered = sorted((dict(r) for r in rows), key=lambda r: (_dt(r["date"]), r.get("match_id", 0), r.get("player_id", 0)))
    player_hist, team_hist = defaultdict(list), defaultdict(list)
    out, i = [], 0
    while i < len(ordered):
        kickoff = _dt(ordered[i]["date"])
        j = i
        while j < len(ordered) and _dt(ordered[j]["date"]) == kickoff:
            j += 1
        batch = ordered[i:j]
        for row in batch:
            hist = player_hist[row["player_id"]]
            feat = dict(row)
            feat["sample_size"] = len(hist)
            feat["season_sample_size"] = sum(h.get("season") == row.get("season") for h in hist)
            for window in WINDOWS:
                previous = hist[-window:]
                mins = sum(_num(h.get("minutes")) for h in previous)
                feat[f"fp_per_min_{window}"] = sum(_num(h.get(target)) for h in previous) / mins if mins else 0.0
                feat[f"minutes_{window}"] = sum(_num(h.get("minutes")) for h in previous) / len(previous) if previous else 0.0
                feat[f"start_rate_{window}"] = sum(bool(h.get("started")) for h in previous) / len(previous) if previous else 0.0
                for stat in COUNT_STATS[1:]:
                    feat[f"{stat}_{window}"] = sum(_num(h.get(stat)) for h in previous) / len(previous) if previous else 0.0
            season = [h for h in hist if h.get("season") == row.get("season")]
            sm = sum(_num(h.get("minutes")) for h in season)
            feat["fp_per_min_season"] = sum(_num(h.get(target)) for h in season) / sm if sm else 0.0
            feat["expected_minutes"] = feat["minutes_5"]
            previous_date = _dt(hist[-1]["date"]) if hist else None
            feat["rest_days"] = max(0.0, (kickoff - previous_date).total_seconds() / 86400) if previous_date else 7.0
            team = team_hist[row.get("team_id")]
            opp = team_hist[row.get("opponent_id")]
            feat["team_recent_goals"] = sum(_num(x.get("goals")) for x in team[-5:]) / max(1, len(team[-5:]))
            feat["opponent_recent_goals_allowed"] = sum(_num(x.get("goals_allowed")) for x in opp[-5:]) / max(1, len(opp[-5:]))
            out.append(feat)
        # Only completed earlier-kickoff rows become available here.
        team_match = defaultdict(lambda: {"goals": 0.0, "goals_allowed": 0.0})
        for row in batch:
            player_hist[row["player_id"]].append(row)
            team_match[row.get("team_id")]["goals"] += _num(row.get("goals"))
        for row in batch:
            team_match[row.get("team_id")]["goals_allowed"] = team_match[row.get("opponent_id")]["goals"]
        for team_id, values in team_match.items():
            team_hist[team_id].append(values)
        i = j
    return out

"""Strictly pre-kickoff opportunity features and realized targets."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime


def _dt(value):
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _minutes(row):
    return float(row["minutes"]) if row.get("minutes") is not None else 0.0


def build_opportunity_features(rows):
    ordered = sorted((dict(r) for r in rows), key=lambda r: (_dt(r["date"]), r["match_id"], r["player_id"]))
    player_history, team_dates = defaultdict(list), defaultdict(list)
    output, index = [], 0
    while index < len(ordered):
        kickoff = _dt(ordered[index]["date"])
        end = index
        while end < len(ordered) and _dt(ordered[end]["date"]) == kickoff:
            end += 1
        batch = ordered[index:end]
        for row in batch:
            history = player_history[row["player_id"]]
            season = [item for item in history if item.get("season") == row.get("season")]
            appearances = [item for item in history if item.get("minutes") is not None]
            feat = dict(row)
            feat["target_start"] = int(row.get("started") is True)
            mins = _minutes(row)
            feat["target_minutes"] = mins
            feat["target_60"] = int(mins >= 60)
            feat["target_75"] = int(mins >= 75)
            feat["target_90"] = int(mins >= 90)
            feat["history_size"] = len(history)
            feat["appearance_history"] = len(appearances)
            for window in (3, 5, 10):
                prior = history[-window:]
                feat[f"starts_{window}"] = sum(item.get("started") is True for item in prior) / max(1, len(prior))
                feat[f"minutes_{window}"] = sum(_minutes(item) for item in prior) / max(1, len(prior))
                feat[f"involvement_{window}"] = sum(item.get("minutes") is not None for item in prior) / max(1, len(prior))
                started = [item for item in prior if item.get("started") is True]
                feat[f"minutes_if_start_{window}"] = sum(_minutes(item) for item in started) / max(1, len(started))
            feat["previous_minutes"] = _minutes(history[-1]) if history else 0.0
            previous_appearance = _dt(appearances[-1]["date"]) if appearances else None
            feat["days_since_appearance"] = min(30.0, (kickoff-previous_appearance).total_seconds()/86400) if previous_appearance else 30.0
            feat["season_start_rate"] = sum(item.get("started") is True for item in season) / max(1, len(season))
            feat["season_minutes"] = sum(_minutes(item) for item in season)
            season_starts = [item for item in season if item.get("started") is True]
            feat["season_minutes_if_start"] = sum(_minutes(item) for item in season_starts) / max(1, len(season_starts))
            nonstarts = [item for item in history[-10:] if item.get("started") is not True]
            sub_appearances = [item for item in nonstarts if item.get("minutes") is not None]
            feat["nonstart_appearance_rate_10"] = len(sub_appearances) / max(1, len(nonstarts))
            feat["nonstart_minutes_10"] = sum(_minutes(item) for item in sub_appearances) / max(1, len(sub_appearances))
            start_minutes = [_minutes(item) for item in history[-10:] if item.get("started") is True]
            start_mean = sum(start_minutes) / max(1, len(start_minutes))
            feat["start_minutes_std_10"] = (sum((x-start_mean)**2 for x in start_minutes)/max(1,len(start_minutes)))**.5
            sub_mean = feat["nonstart_minutes_10"]
            feat["nonstart_minutes_std_10"] = (sum((_minutes(x)-sub_mean)**2 for x in sub_appearances)/max(1,len(sub_appearances)))**.5
            prior_team_dates = team_dates[row.get("team_id")]
            feat["team_rest_days"] = min(14.0, (kickoff-prior_team_dates[-1]).total_seconds()/86400) if prior_team_dates else 7.0
            reasons = []
            if len(appearances) < 3: reasons.append("fewer_than_3_appearances")
            historical_teams = [item.get("team_id") for item in history if item.get("team_id") is not None]
            if historical_teams and historical_teams[-1] != row.get("team_id"): reasons.append("new_team")
            if len(history) >= 10:
                recent_start = sum(item.get("started") is True for item in history[-3:]) / 3
                prior_start = sum(item.get("started") is True for item in history[-10:-3]) / 7
                if abs(recent_start-prior_start) >= .5: reasons.append("material_role_change")
            feat["cold_start"] = bool(reasons)
            feat["cold_start_reason"] = ",".join(reasons) if reasons else None
            output.append(feat)
        for row in batch:
            player_history[row["player_id"]].append(row)
        for team_id in {row.get("team_id") for row in batch}:
            team_dates[team_id].append(kickoff)
        index = end
    return output


NUMERIC_FEATURES = tuple(
    [f"{name}_{window}" for window in (3, 5, 10)
     for name in ("starts", "minutes", "involvement", "minutes_if_start")]
    + ["previous_minutes", "days_since_appearance", "season_start_rate", "season_minutes",
       "season_minutes_if_start", "team_rest_days", "history_size", "appearance_history"]
)


def model_features(row):
    values = {name: float(row.get(name) or 0) for name in NUMERIC_FEATURES}
    values[f"position={row.get('position') or 'UNK'}"] = 1.0
    values[f"team={row.get('team_id') or 'UNK'}"] = 1.0
    return values

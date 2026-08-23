from __future__ import annotations

from typing import Any


def _stat(stats: dict[str, Any], group: str, field: str, default=None):
    value = (stats.get(group) or {}).get(field, default)
    if value in (None, "null", ""):
        return None
    return value


def transform_player_fixture(
    payload: dict[str, Any], match: dict[str, Any], observed_at, source_file: str = ""
) -> list[dict[str, Any]]:
    fixture = match["fixture"]
    league = match["league"]
    home, away = match["teams"]["home"], match["teams"]["away"]
    rows = []
    for team_block in payload.get("response") or []:
        team = team_block.get("team") or {}
        is_home = team.get("id") == home.get("id")
        opponent = away if is_home else home
        for item in team_block.get("players") or []:
            player = item.get("player") or {}
            for stats in item.get("statistics") or []:
                games = stats.get("games") or {}
                rating = games.get("rating")
                minutes = games.get("minutes")
                position = games.get("position")
                goals_block = stats.get("goals") or {}
                penalty = stats.get("penalty") or {}
                opponent_goals = (match.get("goals") or {}).get("away" if is_home else "home")
                team_goals = (match.get("goals") or {}).get("home" if is_home else "away")
                clean_sheet = (minutes >= 60 and opponent_goals == 0) if minutes is not None and position in {"D", "G"} and opponent_goals is not None else None
                goalkeeper_win = (minutes >= 90 and team_goals > opponent_goals) if minutes is not None and position == "G" and team_goals is not None and opponent_goals is not None else None
                rows.append({
                    "match_id": fixture.get("id"), "date": fixture.get("date"),
                    "season": league.get("season"), "player_id": player.get("id"),
                    "player_name": player.get("name"), "team_id": team.get("id"),
                    "team": team.get("name"), "opponent_id": opponent.get("id"),
                    "opponent": opponent.get("name"), "home_away": "home" if is_home else "away",
                    "position": position, "started": games.get("substitute") is False,
                    "minutes": minutes, "goals": _stat(stats, "goals", "total"),
                    "assists": _stat(stats, "goals", "assists"), "shots": _stat(stats, "shots", "total"),
                    "shots_on_target": _stat(stats, "shots", "on"), "passes": _stat(stats, "passes", "total"),
                    "key_passes": _stat(stats, "passes", "key"), "tackles": _stat(stats, "tackles", "total"),
                    "interceptions": _stat(stats, "tackles", "interceptions"),
                    "fouls": _stat(stats, "fouls", "committed"),
                    "assisted_shots": _stat(stats, "passes", "key"),
                    "fouls_drawn": _stat(stats, "fouls", "drawn"),
                    "saves": goals_block.get("saves"), "goals_conceded": goals_block.get("conceded"),
                    "clean_sheet": clean_sheet, "goalkeeper_win": goalkeeper_win,
                    "penalties_missed": penalty.get("missed"), "penalties_saved": penalty.get("saved"),
                    "yellow_cards": _stat(stats, "cards", "yellow"),
                    "red_cards": _stat(stats, "cards", "red"),
                    "rating": float(rating) if rating not in (None, "") else None,
                    "observed_at": observed_at, "source_file": source_file,
                })
    return rows


def transform_matches(payload: dict[str, Any], observed_at, source_file: str = ""):
    rows = []
    for item in payload.get("response") or []:
        f, league, teams = item.get("fixture") or {}, item.get("league") or {}, item.get("teams") or {}
        venue, goals = f.get("venue") or {}, item.get("goals") or {}
        rows.append({
            "match_id": f.get("id"), "date": f.get("date"), "season": league.get("season"),
            "league_id": league.get("id"), "round": league.get("round"),
            "status": (f.get("status") or {}).get("short"),
            "home_team_id": (teams.get("home") or {}).get("id"),
            "away_team_id": (teams.get("away") or {}).get("id"),
            "home_goals": goals.get("home"), "away_goals": goals.get("away"),
            "venue": venue.get("name"), "observed_at": observed_at, "source_file": source_file,
        })
    return rows

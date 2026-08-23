from __future__ import annotations

CHECKS = {
    "duplicate_match_ids": "SELECT count(*) FROM (SELECT match_id FROM matches GROUP BY match_id HAVING count(*) > 1)",
    "duplicate_team_ids": "SELECT count(*) FROM (SELECT team_id FROM teams GROUP BY team_id HAVING count(*) > 1)",
    "duplicate_player_ids": "SELECT count(*) FROM (SELECT player_id FROM players GROUP BY player_id HAVING count(*) > 1)",
    "impossible_minutes": "SELECT count(*) FROM player_match WHERE minutes < 0 OR minutes > 130",
    "missing_player_ids": "SELECT count(*) FROM player_match WHERE player_id IS NULL",
    "missing_team_ids": "SELECT count(*) FROM player_match WHERE team_id IS NULL",
    "duplicate_player_match": "SELECT count(*) FROM (SELECT match_id, player_id FROM player_match GROUP BY ALL HAVING count(*) > 1)",
    "invalid_match_dates": "SELECT count(*) FROM matches WHERE date IS NULL OR year(date) < 1992 OR year(date) > year(current_date) + 1",
}


def validate(con) -> dict[str, int]:
    return {name: con.execute(query).fetchone()[0] for name, query in CHECKS.items()}


def raw_response_quality(raw_dir) -> dict[str, int]:
    from pitchalpha.raw_store import iter_raw
    empty = errors = 0
    for _, doc in iter_raw(raw_dir):
        payload = doc.get("payload") or {}
        if payload.get("errors"):
            errors += 1
        elif not (payload.get("response") or []):
            empty += 1
    return {"empty_api_responses": empty, "archived_api_errors": errors}

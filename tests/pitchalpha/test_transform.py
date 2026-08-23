from datetime import datetime, timezone

from pitchalpha.transform import transform_matches, transform_player_fixture

OBSERVED = datetime(2025, 8, 16, 20, tzinfo=timezone.utc)
MATCH = {
    "fixture": {"id": 100, "date": "2025-08-16T14:00:00+00:00", "status": {"short": "FT"}, "venue": {"name": "Ground"}},
    "league": {"id": 39, "season": 2025, "round": "Regular Season - 1"},
    "teams": {"home": {"id": 1, "name": "Home"}, "away": {"id": 2, "name": "Away"}},
    "goals": {"home": 2, "away": 1},
}


def test_transform_matches():
    row = transform_matches({"response": [MATCH]}, OBSERVED, "raw.json")[0]
    assert row["match_id"] == 100
    assert row["home_team_id"] == 1
    assert row["observed_at"] == OBSERVED


def test_player_match_mapping_and_null_preservation():
    payload = {"response": [{"team": {"id": 1, "name": "Home"}, "players": [{
        "player": {"id": 9, "name": "Forward"}, "statistics": [{
            "games": {"minutes": 90, "position": "F", "rating": "7.4", "substitute": False},
            "shots": {"total": 3, "on": 2}, "goals": {"total": 1, "assists": None},
            "passes": {"total": 22, "key": 1}, "tackles": {"total": None, "interceptions": 1},
            "fouls": {"committed": 2}, "cards": {"yellow": 0, "red": 0},
        }]
    }]}]}
    row = transform_player_fixture(payload, MATCH, OBSERVED)[0]
    assert (row["match_id"], row["player_id"], row["opponent_id"]) == (100, 9, 2)
    assert row["started"] is True
    assert row["tackles"] is None
    assert row["rating"] == 7.4


def test_empty_response_is_empty_not_invented():
    assert transform_player_fixture({"response": []}, MATCH, OBSERVED) == []


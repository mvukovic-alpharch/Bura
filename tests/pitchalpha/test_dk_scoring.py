import json

import pytest

from pitchalpha.dk_scoring import add_dk_score, load_scoring_config, score_player_match


CORE_ROW = {
    "minutes": 90,
    "goals": 1, "assists": 1, "shots": 3, "shots_on_target": 2,
    "key_passes": 1, "assisted_shots": 1, "fouls_drawn": 0, "fouls": 2,
    "tackles": 2, "interceptions": 1, "yellow_cards": 1, "red_cards": 0,
}


def test_known_events_are_scored_and_unsupported_events_are_explicit():
    result = score_player_match(CORE_ROW)
    assert result.actual_dk_points == pytest.approx(22.0)
    assert result.scoring_completeness == "partial"
    assert result.scoring_complete is False
    assert "crosses" in result.unreconstructable_components
    assert "accurate_passes" in result.unreconstructable_components


def test_null_core_event_makes_actual_score_unusable_not_zero():
    result = score_player_match({**CORE_ROW, "minutes": None})
    assert result.actual_dk_points is None
    assert result.scoring_completeness == "unusable"
    assert "minutes" in result.missing_components


def test_provider_null_event_is_explicit_zero_only_for_participant():
    result = score_player_match({**CORE_ROW, "tackles": None})
    assert result.actual_dk_points == pytest.approx(20.0)
    assert result.scoring_completeness == "partial"


def test_verified_goalkeeper_components_are_scored():
    row={**CORE_ROW,"position":"G","interceptions":None,"saves":4,"goals_conceded":1,
         "penalties_saved":1,"clean_sheet":False,"goalkeeper_win":True}
    result=score_player_match(row)
    assert result.actual_dk_points == pytest.approx(35.5)


def test_add_score_uses_canonical_field_names_without_mutating_input():
    row = {"match_id": 1, "player_id": 2, **CORE_ROW}
    enriched = add_dk_score(row)
    assert "actual_dk_points" not in row
    assert enriched["actual_dk_points"] == pytest.approx(22.0)
    assert enriched["scoring_completeness"] == "partial"


def test_weights_are_loaded_from_replaceable_config(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({
        "weights": {"goals": 2},
        "reconstructable_core": ["goals"],
        "unreconstructable": [],
    }), encoding="utf-8")
    config = load_scoring_config(path)
    result = score_player_match({"goals": 3, "minutes": 90}, config)
    assert result.actual_dk_points == 6
    assert result.scoring_complete is True
    assert result.scoring_completeness == "complete"


def test_invalid_config_fails_loudly(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"weights": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="missing keys"):
        load_scoring_config(path)

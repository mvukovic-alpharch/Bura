from pitchalpha.schema import connect
from pitchalpha.raw_store import RawStore
from pitchalpha.validate import raw_response_quality, validate


def test_empty_database_passes_validation(tmp_path):
    with connect(tmp_path / "test.duckdb") as con:
        assert all(value == 0 for value in validate(con).values())


def test_empty_api_response_is_reported(tmp_path):
    from datetime import datetime, timezone
    RawStore(tmp_path).save("/fixtures", {"league": 39}, {"response": []}, datetime.now(timezone.utc))
    assert raw_response_quality(tmp_path) == {"empty_api_responses": 1, "archived_api_errors": 0}


def test_api_error_is_not_classified_as_empty(tmp_path):
    from datetime import datetime, timezone
    RawStore(tmp_path).save("/injuries", {}, {"errors": {"page": "invalid"}}, datetime.now(timezone.utc))
    assert raw_response_quality(tmp_path) == {"empty_api_responses": 0, "archived_api_errors": 1}

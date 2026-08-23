from datetime import datetime, timezone

import duckdb
import pytest

from pitchalpha.raw_store import RawStore
from pitchalpha.snapshot import create_snapshot, parse_as_of


def _fixture(goals: int):
    return {
        "fixture": {
            "id": 10,
            "date": "2025-01-01T15:00:00+00:00",
            "status": {"short": "FT"},
            "venue": {"name": "Ground"},
        },
        "league": {"id": 39, "season": 2025, "round": "Round 1"},
        "teams": {"home": {"id": 1}, "away": {"id": 2}},
        "goals": {"home": goals, "away": 0},
    }


def test_snapshot_excludes_observations_after_cutoff(tmp_path):
    raw = tmp_path / "raw"
    store = RawStore(raw)
    early = datetime(2025, 1, 1, 16, tzinfo=timezone.utc)
    late = datetime(2025, 1, 2, 16, tzinfo=timezone.utc)
    store.save("/fixtures", {"league": 39}, {"response": [_fixture(1)]}, early)
    store.save("/fixtures", {"league": 39}, {"response": [_fixture(9)]}, late)

    output = tmp_path / "early.duckdb"
    result = create_snapshot(raw, output, early)

    with duckdb.connect(str(output), read_only=True) as con:
        assert con.execute("SELECT home_goals, observed_at FROM matches").fetchone() == (1, early)
        assert con.execute("SELECT as_of, included_raw_files, excluded_raw_files FROM snapshot_metadata").fetchone() == (early, 1, 1)
    assert result["excluded_raw_files"] == 1
    assert len(list(raw.rglob("*.json"))) == 2


def test_snapshot_refuses_overwrite_and_naive_cutoff(tmp_path):
    output = tmp_path / "existing.duckdb"
    output.touch()
    with pytest.raises(FileExistsError):
        create_snapshot(tmp_path / "raw", output, datetime.now(timezone.utc))
    with pytest.raises(ValueError, match="timezone"):
        parse_as_of("2025-01-01T12:00:00")

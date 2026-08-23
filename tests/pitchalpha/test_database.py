from pitchalpha.database import replace_rows
from pitchalpha.schema import connect


def test_replace_rows_bulk_deduplicates_by_key(tmp_path):
    with connect(tmp_path / "test.duckdb") as con:
        rows = [
            {"team_id": 1, "team": "Old", "country": None, "founded": None, "national": None,
             "logo": None, "venue_id": None, "venue_name": None, "observed_at": None, "source_file": "a"},
            {"team_id": 1, "team": "New", "country": None, "founded": None, "national": None,
             "logo": None, "venue_id": None, "venue_name": None, "observed_at": None, "source_file": "b"},
        ]
        assert replace_rows(con, "teams", rows, ["team_id"]) == 1
        assert con.execute("SELECT team, source_file FROM teams").fetchone() == ("New", "b")

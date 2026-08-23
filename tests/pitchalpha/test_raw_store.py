import json
from datetime import datetime, timezone

from pitchalpha.raw_store import RawStore


def test_raw_store_is_timestamped_and_append_only(tmp_path):
    store = RawStore(tmp_path)
    at = datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    first = store.save("/fixtures/players", {"fixture": 1}, {"response": []}, at)
    second = store.save("/fixtures/players", {"fixture": 1}, {"response": []}, at)
    assert first != second
    doc = json.loads(first.read_text())
    assert doc["provenance"]["requested_at"] == "2025-01-02T03:04:05+00:00"
    assert doc["provenance"]["params"] == {"fixture": 1}
    assert store.has_success("/fixtures/players", {"fixture": 1}) is True
    assert store.has_success("/fixtures/players", {"fixture": 2}) is False

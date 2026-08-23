from datetime import datetime, timezone

from pitchalpha.dk_coverage_audit import audit_dk_fields
from pitchalpha.raw_store import RawStore


def test_audit_detects_unused_player_fields(tmp_path):
    payload={"response":[{"team":{"id":1},"players":[{"player":{"id":2},"statistics":[{
        "games":{"minutes":90},"passes":{"total":30,"accuracy":"24","key":1},
        "fouls":{"drawn":2},"goals":{"saves":3,"conceded":1},
        "penalty":{"missed":0,"saved":1}}]}]}]}
    RawStore(tmp_path).save("/fixtures/players",{"fixture":10},payload,datetime.now(timezone.utc))
    result=audit_dk_fields(tmp_path)
    assert result["fixtures_audited"] == 1
    matrix={row["dk_event"]:row for row in result["matrix"]}
    assert matrix["Goalkeeper saves"]["available"] == "Yes"
    assert matrix["Crosses"]["available"] == "No"
    assert "1/1" in matrix["Fouls drawn"]["historical_coverage"]

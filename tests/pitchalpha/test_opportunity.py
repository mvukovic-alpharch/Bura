from datetime import datetime, timedelta, timezone

from pitchalpha.opportunity import build_opportunity_features
from pitchalpha.opportunity_eval import opportunity_summary, walk_forward_opportunity
from pitchalpha.opportunity_models import OpportunityBaseline, OpportunityEconometric, OpportunityGradientBoosting


def sample_rows(n=80):
    start=datetime(2025,1,1,tzinfo=timezone.utc)
    return [{"match_id":i,"date":start+timedelta(days=i),"season":2025,"player_id":1,
             "player_name":"P","team_id":10,"position":"M","started":i%3!=0,
             "minutes":None if i%5==0 else (90 if i%3!=0 else 25)} for i in range(n)]


def test_opportunity_features_never_use_current_match():
    rows=sample_rows(6); features=build_opportunity_features(rows)
    assert features[0]["history_size"] == 0
    assert features[0]["cold_start"] is True
    assert "fewer_than_3_appearances" in features[0]["cold_start_reason"]
    changed=sample_rows(6); changed[3]["minutes"]=1; changed[3]["started"]=False
    assert build_opportunity_features(changed)[3]["minutes_3"] == features[3]["minutes_3"]


def test_same_kickoff_is_isolated():
    rows=sample_rows(2); rows[1]["date"]=rows[0]["date"]
    assert [r["history_size"] for r in build_opportunity_features(rows)] == [0,0]


def test_interface_and_walk_forward_models():
    features=build_opportunity_features(sample_rows())
    required={"p_start","expected_minutes","expected_minutes_if_start","p_60","p_75","p_90"}
    for factory in (OpportunityBaseline,OpportunityEconometric,OpportunityGradientBoosting):
        predictions=walk_forward_opportunity(features,factory,min_train=40,step=20)
        assert predictions and required <= predictions[0].keys()
        assert all(0 <= row["p_start"] <= 1 for row in predictions)
        summary=opportunity_summary(predictions)
        assert "brier" in summary["metrics"]["p_start"]
        assert "rmse" in summary["metrics"]["minutes"]

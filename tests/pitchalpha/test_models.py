from datetime import datetime, timedelta, timezone

from pitchalpha.evaluation import evaluation_summary, metrics, walk_forward
from pitchalpha.features import build_lagged_features
from pitchalpha.models import BaselineB000, EconometricE001


def rows(n=12):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [{"match_id": i, "date": start + timedelta(days=i), "season": 2025, "player_id": 1,
             "team_id": 10, "opponent_id": 20, "position": "F", "home_away": "home",
             "started": True, "minutes": 90, "goals": i % 2, "assists": 0, "shots": 2,
             "shots_on_target": 1, "key_passes": 1, "tackles": 0, "interceptions": 0,
             "actual_dk_points": float(i)} for i in range(n)]


def test_features_are_strictly_lagged():
    featured = build_lagged_features(rows())
    assert featured[0]["sample_size"] == 0
    assert featured[3]["fp_per_min_3"] == sum((0, 1, 2)) / 270
    changed = rows(); changed[4]["actual_dk_points"] = 9999
    assert build_lagged_features(changed)[4]["fp_per_min_3"] == featured[4]["fp_per_min_3"]


def test_same_kickoff_cannot_leak():
    source = rows(2); source[1]["date"] = source[0]["date"]; source[1]["player_id"] = 1
    assert [x["sample_size"] for x in build_lagged_features(source)] == [0, 0]


def test_models_and_walk_forward_are_deterministic():
    featured = build_lagged_features(rows(30))
    a = walk_forward(featured, EconometricE001, min_train=10, step=5)
    b = walk_forward(featured, EconometricE001, min_train=10, step=5)
    assert [x["prediction"] for x in a] == [x["prediction"] for x in b]
    assert metrics(a)["n"] == 20
    assert len(walk_forward(featured, BaselineB000, min_train=10, step=5)) == 20


def test_baseline_uses_all_trailing_windows():
    model = BaselineB000(shrinkage=0)
    model.prior = {"ALL": 0.0, "F": 0.0}
    row = {"position": "F", "sample_size": 10, "season_sample_size": 10,
           "expected_minutes": 90, "fp_per_min_3": 1.0, "fp_per_min_5": 0.0,
           "fp_per_min_10": 0.0, "fp_per_min_season": 0.0}
    assert model.predict_one(row) > 0


def test_walk_forward_never_trains_on_test(monkeypatch):
    seen = []
    class Spy(BaselineB000):
        def fit(self, values, target="actual_dk_points"):
            seen.append(max(v["date"] for v in values)); return super().fit(values, target)
    featured = build_lagged_features(rows(20))
    predicted = walk_forward(featured, Spy, min_train=10, step=5)
    assert seen[0] < predicted[0]["date"]


def test_evaluation_includes_required_slices_and_top_k():
    predicted = walk_forward(build_lagged_features(rows(30)), BaselineB000, min_train=10, step=5)
    report = evaluation_summary(predicted)
    assert {"by_position", "by_expected_minutes", "by_sample_size", "top_k_average_actual"} <= report.keys()
    assert len(report["largest_positive_errors"]) == 10

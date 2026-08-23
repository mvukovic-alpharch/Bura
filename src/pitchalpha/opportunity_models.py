"""PA-003 opportunity baseline, interpretable model, and boosting challenger."""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.preprocessing import StandardScaler

from pitchalpha.opportunity import model_features


PROBABILITY_TARGETS = {"p_start": "target_start", "p_60": "target_60", "p_75": "target_75", "p_90": "target_90"}


class OpportunityBaseline:
    version = "PA-MIN-B000"

    def fit(self, rows):
        self.rows = list(rows)
        self.priors = {}
        for output, target in PROBABILITY_TARGETS.items():
            self.priors[output] = sum(r[target] for r in self.rows) / max(1, len(self.rows))
        self.minute_prior = sum(r["target_minutes"] for r in self.rows) / max(1, len(self.rows))
        starters = [r["target_minutes"] for r in self.rows if r["target_start"]]
        self.start_minute_prior = sum(starters) / max(1, len(starters))
        return self

    def predict(self, rows):
        predictions = []
        for row in rows:
            n = min(int(row.get("history_size") or 0), 10)
            shrink = 5.0
            def shrunk(observed, prior): return (n*observed + shrink*prior)/(n+shrink)
            p_start = shrunk(row.get("starts_10", 0), self.priors["p_start"])
            p60 = shrunk(min(row.get("starts_10", 0), row.get("minutes_10", 0)/60), self.priors["p_60"])
            p75 = shrunk(min(row.get("starts_10", 0), row.get("minutes_10", 0)/75), self.priors["p_75"])
            p90 = shrunk(min(row.get("starts_10", 0), row.get("minutes_10", 0)/90), self.priors["p_90"])
            expected = shrunk(row.get("minutes_10", 0), self.minute_prior)
            if_start = shrunk(row.get("minutes_if_start_10", 0), self.start_minute_prior)
            predictions.append({"p_start": p_start, "expected_minutes": expected,
                "expected_minutes_if_start": if_start, "p_60": p60, "p_75": p75, "p_90": p90})
        return predictions


class _SklearnOpportunity:
    classifier_type = LogisticRegression
    regressor_type = Ridge

    def _classifier(self): return self.classifier_type(max_iter=500, random_state=42)
    def _regressor(self): return self.regressor_type(alpha=10.0) if self.regressor_type is Ridge else self.regressor_type(random_state=42)

    def fit(self, rows):
        self.vectorizer = DictVectorizer(sparse=False)
        x = self.vectorizer.fit_transform([model_features(r) for r in rows])
        self.scaler = StandardScaler().fit(x)
        x = self.scaler.transform(x)
        self.classifiers = {}
        for output, target in PROBABILITY_TARGETS.items():
            y = np.array([r[target] for r in rows])
            self.classifiers[output] = float(y[0]) if len(set(y)) == 1 else self._classifier().fit(x, y)
        self.minutes = self._regressor().fit(x, [r["target_minutes"] for r in rows])
        sx = [i for i, r in enumerate(rows) if r["target_start"]]
        self.minutes_if_start = self._regressor().fit(x[sx], [rows[i]["target_minutes"] for i in sx])
        return self

    def predict(self, rows):
        x = self.scaler.transform(self.vectorizer.transform([model_features(r) for r in rows]))
        values = []
        minute = np.clip(self.minutes.predict(x), 0, 100)
        minute_start = np.clip(self.minutes_if_start.predict(x), 0, 100)
        for i in range(len(rows)):
            item = {key: (model if isinstance(model, float) else float(model.predict_proba(x[i:i+1])[0, 1]))
                    for key, model in self.classifiers.items()}
            item.update(expected_minutes=float(minute[i]), expected_minutes_if_start=float(minute_start[i]))
            values.append(item)
        return values


class OpportunityEconometric(_SklearnOpportunity):
    version = "PA-MIN-E001"


class OpportunityGradientBoosting(_SklearnOpportunity):
    version = "PA-MIN-ML001"
    classifier_type = HistGradientBoostingClassifier
    regressor_type = HistGradientBoostingRegressor

    def _classifier(self): return HistGradientBoostingClassifier(max_iter=80, max_depth=4, learning_rate=.06, random_state=42)
    def _regressor(self): return HistGradientBoostingRegressor(max_iter=80, max_depth=4, learning_rate=.06, l2_regularization=5, random_state=42)


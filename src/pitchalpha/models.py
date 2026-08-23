"""Transparent PA-B000 and PA-E001 models."""
from __future__ import annotations

import math
from collections import defaultdict


class BaselineB000:
    version = "PA-B000"

    def __init__(self, shrinkage=5.0):
        self.shrinkage = shrinkage
        self.prior = {"ALL": 0.0}

    def fit(self, rows, target="actual_dk_points"):
        values = defaultdict(list)
        for r in rows:
            if r.get(target) is not None and float(r.get("minutes") or 0) > 0:
                values[r.get("position") or "UNK"].append(float(r[target]) / float(r["minutes"]))
        all_values = [v for vs in values.values() for v in vs]
        self.prior = {k: sum(v) / len(v) for k, v in values.items() if v}
        self.prior["ALL"] = sum(all_values) / len(all_values) if all_values else 0.0
        return self

    def predict_one(self, r):
        sample = int(r.get("sample_size") or 0)
        season_sample = int(r.get("season_sample_size") or 0)
        rates = []
        for window in (3, 5, 10):
            weight = min(sample, window)
            if weight:
                rates.append((float(r.get(f"fp_per_min_{window}") or 0), weight))
        if season_sample:
            rates.append((float(r.get("fp_per_min_season") or 0), min(season_sample, 10)))
        n = sum(weight for _, weight in rates)
        observed = sum(rate * weight for rate, weight in rates) / n if n else 0.0
        prior = self.prior.get(r.get("position") or "UNK", self.prior["ALL"])
        rate = (n * observed + self.shrinkage * prior) / (n + self.shrinkage)
        return max(0.0, float(r.get("expected_minutes") or 0) * rate)

    def predict(self, rows):
        return [self.predict_one(r) for r in rows]


DEFAULT_FEATURES = ("expected_minutes", "fp_per_min_3", "fp_per_min_5", "fp_per_min_10",
                    "start_rate_5", "goals_5", "assists_5", "shots_5", "shots_on_target_5",
                    "key_passes_5", "tackles_5", "interceptions_5", "team_recent_goals",
                    "opponent_recent_goals_allowed", "rest_days")


def _solve(a, b):
    n = len(b)
    aug = [list(a[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        aug[col], aug[pivot] = aug[pivot], aug[col]
        scale = aug[col][col]
        if abs(scale) < 1e-12:
            continue
        aug[col] = [x / scale for x in aug[col]]
        for row in range(n):
            if row != col:
                factor = aug[row][col]
                aug[row] = [x - factor * y for x, y in zip(aug[row], aug[col])]
    return [aug[i][-1] for i in range(n)]


class EconometricE001:
    """Standardized ridge regression with explicit numeric and categorical features."""
    version = "PA-E001"

    def __init__(self, alpha=10.0, features=DEFAULT_FEATURES):
        self.alpha, self.features = alpha, tuple(features)

    def _raw(self, r):
        numeric = [float(r.get(k) or 0) for k in self.features]
        cats = [f"pos={r.get('position') or 'UNK'}", f"ha={r.get('home_away') or 'UNK'}"]
        return numeric, cats

    def fit(self, rows, target="actual_dk_points"):
        rows = [r for r in rows if r.get(target) is not None]
        self.categories = sorted({c for r in rows for c in self._raw(r)[1]})
        raw = [self._raw(r)[0] for r in rows]
        p = len(self.features)
        self.means = [sum(x[j] for x in raw) / len(raw) for j in range(p)] if raw else [0] * p
        self.scales = [math.sqrt(sum((x[j]-self.means[j])**2 for x in raw)/max(1, len(raw))) or 1 for j in range(p)] if raw else [1] * p
        x = [self._vector(r) for r in rows]
        y = [float(r[target]) for r in rows]
        q = 1 + p + len(self.categories)
        xtx = [[sum(row[i]*row[j] for row in x) for j in range(q)] for i in range(q)]
        for i in range(1, q):
            xtx[i][i] += self.alpha
        xty = [sum(row[i]*value for row, value in zip(x, y)) for i in range(q)]
        self.coef_ = _solve(xtx, xty) if rows else [0.0] * q
        return self

    def _vector(self, r):
        nums, cats = self._raw(r)
        return [1.0] + [(v-m)/s for v, m, s in zip(nums, self.means, self.scales)] + [float(c in cats) for c in self.categories]

    def predict(self, rows):
        return [max(0.0, sum(a*b for a, b in zip(self.coef_, self._vector(r)))) for r in rows]

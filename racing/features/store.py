"""Feature store — raw past-performance data -> model feature vector.

This is the domain heart. Good features ARE the edge. Each function turns
messy racing history into one standardized number the conditional-logit
win model consumes. Standardization is WITHIN-RACE (z-score across the
field) because what matters is a horse's edge over today's rivals, not
absolute figures.
"""
from __future__ import annotations

import numpy as np

from ..models import Race, Entry
from ..pace import classify_style, project_pace, pace_fit_scores
from ..win_model import FEATURES


def _recency_weighted(values: list[float], dates, half_life_days: float = 120):
    """Exponentially weight recent races heavier. Racing form decays."""
    if not values:
        return 0.0
    import datetime as dt
    today = max(dates)
    w = np.array([0.5 ** ((today - d).days / half_life_days) for d in dates])
    v = np.array(values)
    return float((v * w).sum() / w.sum()) if w.sum() > 0 else float(v.mean())


def _horse_raw_features(entry: Entry) -> dict:
    """Pre-standardization raw numbers for one horse."""
    pp = entry.horse.past
    if not pp:
        # first-time starter: neutral priors
        return {"speed_last": 0.0, "speed_best": 0.0, "class_rating": 0.0,
                "freshness": 0.0, "early": 0.0, "late": 0.0,
                "jockey_sr": entry.jockey_sr, "trainer_sr": entry.trainer_sr,
                "post": entry.post_position, "weight": entry.weight}
    dates = [p.date for p in pp]
    speeds = [p.speed_fig for p in pp]
    return {
        "speed_last": pp[0].speed_fig,                       # most recent
        "speed_best": max(speeds[:6]) if speeds else 0.0,    # recent ceiling
        "class_rating": _recency_weighted([p.class_level for p in pp], dates),
        "freshness": (min((max(dates).toordinal() - max(dates).toordinal()), 0)),
        "early": _recency_weighted([p.early_pace for p in pp], dates),
        "late": _recency_weighted([p.late_pace for p in pp], dates),
        "jockey_sr": entry.jockey_sr,
        "trainer_sr": entry.trainer_sr,
        "post": entry.post_position,
        "weight": entry.weight,
    }


def _zscore(x: np.ndarray) -> np.ndarray:
    sd = x.std()
    return (x - x.mean()) / sd if sd > 1e-9 else np.zeros_like(x)


def build_feature_matrix(race: Race) -> np.ndarray:
    """Returns (n_horses, len(FEATURES)) standardized matrix in FEATURES order,
    and populates each entry's run_style + pace_fit as a side effect."""
    raws = [_horse_raw_features(e) for e in race.entries]

    early = np.array([r["early"] for r in raws])
    late = np.array([r["late"] for r in raws])
    early_z, late_z = _zscore(early), _zscore(late)

    # pace classification + projection across the field
    styles = [classify_style(early_z[i], late_z[i]) for i in range(len(raws))]
    pace = project_pace(styles)
    fits = pace_fit_scores(styles, pace)
    for i, e in enumerate(race.entries):
        e.run_style = styles[i]
        e.pace_fit = float(fits[i])

    # standardize each feature within the race
    cols = {
        "speed_last": _zscore(np.array([r["speed_last"] for r in raws])),
        "speed_best": _zscore(np.array([r["speed_best"] for r in raws])),
        "class_rating": _zscore(np.array([r["class_rating"] for r in raws])),
        "pace_fit": fits,                                    # already in [-1,1]
        "freshness": _zscore(np.array([r["freshness"] for r in raws])),
        "jockey_sr": _zscore(np.array([r["jockey_sr"] for r in raws])),
        "trainer_sr": _zscore(np.array([r["trainer_sr"] for r in raws])),
        "post_bias": _zscore(np.array([r["post"] for r in raws])),
        "weight": _zscore(np.array([r["weight"] for r in raws])),
    }
    return np.column_stack([cols[f] for f in FEATURES])

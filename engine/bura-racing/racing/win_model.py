"""Win-probability model — conditional logit over a race field.

The right structure for racing: a race is a discrete-choice problem. Each
horse has a 'strength' score that's a linear combo of features; win prob is
the softmax over the field. This is the conditional logit (a.k.a.
multinomial logit / Plackett-Luce top-1), the workhorse of racing models.

  strength_i = beta . features_i
  P(i wins)  = exp(strength_i) / sum_j exp(strength_j)

Features that actually carry signal in DIRT ROUTE races (the periphery of
racing — mid-tier weekday cards where the crowd is soft):
  - speed figure (Beyer-style), last & best-recent
  - class rating (purse level of recent races)
  - pace fit: early-speed vs the race's projected pace scenario
  - days since last race (freshness / layoff)
  - jockey & trainer strike rate
  - post position (matters more on routes around two turns)
  - weight carried

beta is fit by maximum likelihood on historical results (each race
contributes the log-prob of the actual winner). v0 ships hand-set,
literature-reasonable weights so the pipeline runs TODAY; fit_mle replaces
them once you have a results table.
"""
from __future__ import annotations

import numpy as np

__all__ = ["FEATURES", "DEFAULT_BETA", "strength", "win_probs", "fit_mle"]

FEATURES = [
    "speed_last", "speed_best", "class_rating", "pace_fit",
    "freshness", "jockey_sr", "trainer_sr", "post_bias", "weight",
]

# Hand-set, literature-reasonable priors (standardized features assumed).
# Positive = helps win prob. These are STARTING POINTS, replaced by fit_mle.
DEFAULT_BETA = np.array([
    0.55,   # speed_last   — recent form, biggest single signal
    0.35,   # speed_best   — class ceiling
    0.40,   # class_rating — dropping in class is a known edge
    0.45,   # pace_fit     — lone speed on routes is gold
    0.15,   # freshness    — mild; too much layoff hurts
    0.25,   # jockey_sr
    0.30,   # trainer_sr   — sharp barns win
    0.10,   # post_bias    — small on routes, larger sprints
   -0.20,   # weight       — more weight, slower (negative)
])


def strength(feat: np.ndarray, beta: np.ndarray = DEFAULT_BETA) -> np.ndarray:
    """feat: (n_horses, n_features) standardized. Returns strength score."""
    return feat @ beta


def win_probs(feat: np.ndarray, beta: np.ndarray = DEFAULT_BETA) -> np.ndarray:
    """Softmax over the field -> win probabilities summing to 1."""
    s = strength(feat, beta)
    s = s - s.max()                  # numerical stability
    e = np.exp(s)
    return e / e.sum()


def fit_mle(races: list[tuple[np.ndarray, int]], l2: float = 1.0,
            iters: int = 200, lr: float = 0.1) -> np.ndarray:
    """Maximum-likelihood fit of beta via conditional logit.

    races: list of (feature_matrix (n_i, F), winner_index). Each race
    contributes log P(actual winner). Simple full-batch gradient ascent
    with L2 shrinkage — racing data is noisy, regularize hard.

    This is the upgrade path: feed it a season of results and it learns the
    weights instead of using the hand-set priors."""
    F = len(FEATURES)
    beta = np.zeros(F)
    for _ in range(iters):
        grad = np.zeros(F)
        for feat, win in races:
            p = win_probs(feat, beta)
            # gradient of log-softmax: x_winner - sum_i p_i x_i
            grad += feat[win] - p @ feat
        grad -= l2 * beta
        beta += lr * grad / max(1, len(races))
    return beta

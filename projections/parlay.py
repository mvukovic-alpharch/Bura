"""Parlay scoring — turn individual prop projections into an honest parlay
probability. The key insight the books exploit and casual bettors miss:
parlay legs are often CORRELATED, and naive multiplication misprices them.

If you parlay 'QB over passing yards' AND 'his WR over receiving yards',
those aren't independent — same game script drives both. Positive
correlation makes the TRUE parlay prob HIGHER than the naive product
(good for you); negative correlation makes it lower. This module lets you
flag correlated legs so your educated parlay reflects reality.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ParlayLeg:
    label: str
    p_hit: float                # P(this leg hits) from the projection engine
    group: str | None = None    # legs sharing a group are correlated


def naive_parlay_prob(legs: list[ParlayLeg]) -> float:
    """Assumes independence — what a parlay calculator does. Often wrong."""
    p = 1.0
    for leg in legs:
        p *= leg.p_hit
    return p


def correlated_parlay_prob(legs: list[ParlayLeg], rho: float = 0.3) -> float:
    """Gaussian-copula approximation of a correlated parlay. Legs sharing a
    `group` get positive correlation rho (same game script). Same-game
    parlays of QB+WR yards are the classic case. Returns the joint P(all hit).

    This is an approximation, not exact — but it's directionally honest,
    which beats the naive product that ignores correlation entirely."""
    n = len(legs)
    if n == 0:
        return 1.0
    # convert each p_hit to a Gaussian threshold
    from scipy.stats import norm
    thresholds = np.array([norm.ppf(np.clip(l.p_hit, 1e-6, 1 - 1e-6)) for l in legs])

    # build correlation matrix from groups
    R = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            if legs[i].group and legs[i].group == legs[j].group:
                R[i, j] = R[j, i] = rho

    # Monte Carlo the joint upper-orthant probability
    rng = np.random.default_rng(0)
    try:
        L = np.linalg.cholesky(R)
    except np.linalg.LinAlgError:
        return naive_parlay_prob(legs)
    N = 40_000
    z = rng.standard_normal((N, n)) @ L.T
    all_hit = np.all(z > thresholds, axis=1)   # leg hits when latent > threshold
    return float(all_hit.mean())


def score_parlay(legs: list[ParlayLeg], payout_odds: float | None = None,
                 rho: float = 0.3) -> dict:
    naive = naive_parlay_prob(legs)
    corr = correlated_parlay_prob(legs, rho)
    out = {
        "n_legs": len(legs),
        "naive_prob": round(naive, 4),
        "correlated_prob": round(corr, 4),
        "fair_odds": round(1.0 / corr, 2) if corr > 0 else None,
        "correlation_effect": round((corr - naive) / naive * 100, 1) if naive > 0 else 0,
    }
    if payout_odds is not None:
        out["ev"] = round(corr * payout_odds - 1.0, 4)
    return out

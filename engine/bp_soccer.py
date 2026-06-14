"""Bivariate Poisson fair-value engine — the periphery soccer sleeve's model.

Why this model, in one paragraph: X = X1 + X3, Y = X2 + X3 with
X_k ~ Poisson(lambda_k) independent. lambda_1/lambda_2 are net team
scoring strengths; lambda_3 is shared game state (tempo, weather,
mutual fatigue). The decisive property for trading: the difference
Z = X - Y (match winner) follows a Skellam distribution that does NOT
depend on lambda_3 — but draws and totals DO. A book lazily copying a
sharp 1X2 line can therefore be exactly right on the moneyline and
structurally wrong on the draw and the totals surface. In thin leagues
that's where the edge lives.

v0 fitting is method-of-moments (lambda_3 = cov, lambda_i = mean - cov);
EM with covariates is the upgrade path once snapshots accumulate.
"""
from __future__ import annotations

import numpy as np
from scipy.special import gammaln, ive
from scipy.stats import poisson

__all__ = [
    "bp_pmf_matrix", "inflate_diagonal", "price_1x2", "price_total",
    "skellam_win_prob", "fit_moments",
]


def _log_bp_pmf(x: int, y: int, l1: float, l2: float, l3: float) -> float:
    """Log PMF of BP(l1,l2,l3) at (x,y), summation in log-space."""
    base = -(l1 + l2 + l3) + x * np.log(l1) - gammaln(x + 1) \
           + y * np.log(l2) - gammaln(y + 1)
    kmax = min(x, y)
    if l3 == 0 or kmax < 0:
        return base
    r = np.log(l3) - np.log(l1) - np.log(l2)
    terms = []
    for k in range(kmax + 1):
        t = (gammaln(x + 1) - gammaln(k + 1) - gammaln(x - k + 1)
             + gammaln(y + 1) - gammaln(k + 1) - gammaln(y - k + 1)
             + gammaln(k + 1) + k * r)
        terms.append(t)
    m = max(terms)
    return base + m + np.log(sum(np.exp(t - m) for t in terms))


def bp_pmf_matrix(l1: float, l2: float, l3: float, max_goals: int = 12) -> np.ndarray:
    """Joint score matrix P[x, y] for x, y in 0..max_goals."""
    if min(l1, l2) <= 0 or l3 < 0:
        raise ValueError("need l1, l2 > 0 and l3 >= 0")
    M = np.zeros((max_goals + 1, max_goals + 1))
    for x in range(max_goals + 1):
        for y in range(max_goals + 1):
            M[x, y] = np.exp(_log_bp_pmf(x, y, l1, l2, l3))
    return M


def inflate_diagonal(M: np.ndarray, p: float, dist: str = "geometric",
                     theta: float = 0.5) -> np.ndarray:
    """Diagonal-inflated BP: mass p moved onto x == y with weights from
    a Bernoulli(0-0 only), geometric, or poisson inflation distribution.
    Corrects the classic under-prediction of 1-1 in low-scoring soccer."""
    n = M.shape[0]
    if dist == "bernoulli":
        w = np.zeros(n); w[0] = 1.0
    elif dist == "geometric":
        w = (1 - theta) ** np.arange(n) * theta
    elif dist == "poisson":
        w = poisson.pmf(np.arange(n), theta)
    else:
        raise ValueError(f"unknown inflation dist '{dist}'")
    w = w / w.sum()
    out = (1.0 - p) * M.copy()
    out[np.arange(n), np.arange(n)] += p * w
    return out


def price_1x2(M: np.ndarray) -> dict[str, float]:
    home = float(np.tril(M, -1).sum())   # x > y
    draw = float(np.trace(M))
    away = float(np.triu(M, 1).sum())    # y > x
    s = home + draw + away
    return {"home": home / s, "draw": draw / s, "away": away / s}


def price_total(M: np.ndarray, line: float) -> dict[str, float]:
    """P(X + Y over/under line). Note X+Y = X1 + X2 + 2*X3 — NOT Poisson;
    lambda_3 fattens/reshapes the totals distribution. This is exactly
    the surface a double-Poisson copier gets wrong."""
    n = M.shape[0]
    totals = np.add.outer(np.arange(n), np.arange(n))
    over = float(M[totals > line].sum())
    under = float(M[totals < line].sum())
    s = over + under  # pushes excluded for .0 lines
    return {"over": over / s, "under": under / s}


def skellam_win_prob(l1: float, l2: float) -> dict[str, float]:
    """Win/draw/loss from Z = X - Y ~ Skellam(l1, l2). Independent of l3.
    Used as a cross-check: matrix 1X2 must match this when p_inflate=0."""
    zs = np.arange(-60, 61)
    # ive = exponentially scaled Bessel I_v; rescale in log space
    logp = (-(l1 + l2) + zs / 2.0 * np.log(l1 / l2)
            + np.log(ive(np.abs(zs), 2.0 * np.sqrt(l1 * l2)))
            + 2.0 * np.sqrt(l1 * l2))
    p = np.exp(logp)
    p = p / p.sum()
    return {"home": float(p[zs > 0].sum()),
            "draw": float(p[zs == 0].sum()),
            "away": float(p[zs < 0].sum())}


def fit_moments(home_goals: np.ndarray, away_goals: np.ndarray) -> tuple[float, float, float]:
    """Method-of-moments v0: l3 = cov(X,Y) (floored at 0),
    l1 = mean(X) - l3, l2 = mean(Y) - l3. EM upgrade comes later."""
    x = np.asarray(home_goals, float)
    y = np.asarray(away_goals, float)
    l3 = max(0.0, float(np.cov(x, y, ddof=1)[0, 1]))
    l1 = float(x.mean()) - l3
    l2 = float(y.mean()) - l3
    if min(l1, l2) <= 0:
        l3 = 0.0
        l1, l2 = float(x.mean()), float(y.mean())
    return l1, l2, l3

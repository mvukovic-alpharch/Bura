"""Player prop projection engine — distribution-first.

The whole philosophy: do NOT predict a single number. Predict the full
probability DISTRIBUTION of a player's stat, then you can price ANY line
the book posts and get a calibrated P(over) / P(under). That calibrated
probability is what makes a parlay leg an educated bet instead of a vibe.

This is NOT an edge-finder against efficient books — it's an honest
projection so YOUR picks are informed. Stat types map to distributions:

  counting, low-mean   (TDs, goals, made-3s)  -> Poisson
  counting, overdispersed (rush yds in chunks, receptions) -> NegBinom
  continuous (passing yds, points)            -> Normal / truncated Normal

Each projection = base rate (player's recent form, usage) adjusted for
opponent strength and game pace, then wrapped in the right distribution.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

__all__ = ["StatProjection", "project_stat", "price_line"]


# ---- distribution wrappers ---------------------------------------------------

def _poisson_dist(mean: float):
    return stats.poisson(mu=max(0.01, mean))


def _negbinom_dist(mean: float, dispersion: float = 0.25):
    """Overdispersed counts. dispersion>0 adds variance beyond Poisson.
    Parameterize NB by mean and a dispersion k: var = mean + dispersion*mean^2."""
    mean = max(0.01, mean)
    var = mean + dispersion * mean * mean
    p = mean / var
    n = mean * p / (1 - p) if p < 1 else mean
    return stats.nbinom(n=max(0.1, n), p=min(0.999, max(0.001, p)))


def _normal_dist(mean: float, sd: float):
    return stats.norm(loc=mean, scale=max(0.1, sd))


# ---- the projection ----------------------------------------------------------

@dataclass
class StatProjection:
    player: str
    stat: str
    sport: str
    mean: float                 # adjusted expected value
    dist_family: str            # poisson | negbinom | normal
    _dist: object               # frozen scipy distribution

    def p_over(self, line: float) -> float:
        """P(stat > line). For half-point lines (e.g. 1.5) this is exact;
        for whole-number lines the push mass is split out separately."""
        if self.dist_family == "normal":
            return float(self._dist.sf(line))
        # discrete: P(X >= ceil(line+epsilon))
        import math
        threshold = math.floor(line) + 1
        return float(1.0 - self._dist.cdf(threshold - 1))

    def p_under(self, line: float) -> float:
        return 1.0 - self.p_over(line) - self.p_push(line)

    def p_push(self, line: float) -> float:
        """Whole-number lines can push (exact equal). Half-point lines can't."""
        if self.dist_family == "normal" or line != int(line):
            return 0.0
        return float(self._dist.pmf(int(line)))

    def quantile(self, q: float) -> float:
        return float(self._dist.ppf(q))


def project_stat(player: str, stat: str, sport: str,
                 base_mean: float, dist_family: str,
                 opp_factor: float = 1.0, pace_factor: float = 1.0,
                 sd: float | None = None, dispersion: float = 0.25) -> StatProjection:
    """Build a projection. base_mean is the player's form/usage rate;
    opp_factor and pace_factor multiplicatively adjust it (1.0 = neutral,
    1.1 = +10% from a weak opponent or fast pace, 0.9 = tough D / slow pace)."""
    mean = base_mean * opp_factor * pace_factor
    if dist_family == "poisson":
        d = _poisson_dist(mean)
    elif dist_family == "negbinom":
        d = _negbinom_dist(mean, dispersion)
    elif dist_family == "normal":
        d = _normal_dist(mean, sd if sd is not None else 0.35 * mean)
    else:
        raise ValueError(f"unknown dist_family {dist_family}")
    return StatProjection(player, stat, sport, mean, dist_family, d)


def price_line(proj: StatProjection, line: float) -> dict:
    """Everything you need to decide a prop: over/under/push probs, the
    model's median, and the implied fair odds."""
    po, pu, pp = proj.p_over(line), proj.p_under(line), proj.p_push(line)
    return {
        "player": proj.player, "stat": proj.stat, "line": line,
        "mean": round(proj.mean, 2), "median": round(proj.quantile(0.5), 1),
        "p_over": round(po, 4), "p_under": round(pu, 4), "p_push": round(pp, 4),
        "fair_over_odds": round(1.0 / po, 2) if po > 0 else None,
        "fair_under_odds": round(1.0 / pu, 2) if pu > 0 else None,
    }

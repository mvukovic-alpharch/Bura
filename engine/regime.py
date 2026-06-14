"""Market-Efficiency Regime Engine — ArchAlpha DNA transplanted.

Instead of regime-detecting the macro tape, we regime-detect MARKET
EFFICIENCY itself, per market family. The posture-lock philosophy:
you don't bet because you have a model; you bet because the market
is in a regime where models can win.

Signal: cross-book dispersion of devigged probabilities, z-scored
against that family's trailing baseline.

  EFFICIENT  -> books agree (low dispersion). Stand down. No bet,
                regardless of model opinion. (Posture Lock.)
  NOISY      -> moderate disagreement. Watch list only.
  DISLOCATED -> books materially disagree -> someone is wrong ->
                fair-value vs outlier book is harvestable. Gates open.

This is also the Periphery thesis quantified: thin-consensus leagues
live in DISLOCATED far more often than the NBA does.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = ["RegimeCall", "classify_market", "dispersion"]

EFFICIENT, NOISY, DISLOCATED = "EFFICIENT", "NOISY", "DISLOCATED"


def dispersion(devig_probs: dict[str, float]) -> float:
    """Cross-book stdev of no-vig probs for the SAME outcome.
    devig_probs: {book_id: prob}. Needs >= 2 books."""
    vals = np.asarray(list(devig_probs.values()), dtype=float)
    if len(vals) < 2:
        return float("nan")
    return float(vals.std(ddof=1))


@dataclass
class RegimeCall:
    regime: str
    dispersion: float
    zscore: float
    n_books: int
    can_bet: bool
    note: str


def classify_market(
    devig_probs: dict[str, float],
    baseline_mean: float,
    baseline_std: float,
    z_noisy: float = 1.0,
    z_dislocated: float = 2.0,
    min_books: int = 3,
) -> RegimeCall:
    """Classify one market snapshot against its family's trailing baseline.

    baseline_mean/std: trailing dispersion stats for this (sport, family)
    bucket, computed from odds_snapshots history (e.g. 30-day window).
    """
    d = dispersion(devig_probs)
    n = len(devig_probs)

    if n < min_books or np.isnan(d):
        return RegimeCall(NOISY, d, float("nan"), n, False,
                          "insufficient book coverage — watch only")

    z = (d - baseline_mean) / baseline_std if baseline_std > 0 else 0.0

    if z >= z_dislocated:
        return RegimeCall(DISLOCATED, d, z, n, True,
                          "books materially disagree — gates open")
    if z >= z_noisy:
        return RegimeCall(NOISY, d, z, n, False,
                          "elevated disagreement — watch list")
    return RegimeCall(EFFICIENT, d, z, n, False,
                      "consensus tight — posture lock, stand down")

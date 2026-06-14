"""Devig: strip bookmaker hold from quoted odds -> honest probabilities.

Three methods, selected per market family (config in settings):
  - multiplicative: fine near pick'em two-ways
  - power:          handles favorite-longshot bias on lopsided lines
  - shin:           sharp-desk workhorse; models insider-money fraction z

All functions take a list of DECIMAL odds for the full outcome set of one
market (e.g. [1.91, 1.91] for -110/-110) and return a list of no-vig
probabilities summing to 1.0.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

__all__ = ["implied", "devig_multiplicative", "devig_power", "devig_shin", "devig"]


def implied(decimal_odds: list[float]) -> np.ndarray:
    """Raw implied probabilities (contain the vig). Sum > 1 by the hold."""
    odds = np.asarray(decimal_odds, dtype=float)
    if np.any(odds <= 1.0):
        raise ValueError(f"decimal odds must be > 1.0, got {decimal_odds}")
    return 1.0 / odds


def devig_multiplicative(decimal_odds: list[float]) -> np.ndarray:
    """Proportional: p_i = pi_i / sum(pi). Spreads vig evenly."""
    pi = implied(decimal_odds)
    return pi / pi.sum()


def devig_power(decimal_odds: list[float]) -> np.ndarray:
    """Solve k such that sum(pi_i ** k) == 1.

    k > 1 when there's hold; pushes proportionally more vig onto
    longshots, correcting favorite-longshot bias.
    """
    pi = implied(decimal_odds)
    booksum = pi.sum()
    if abs(booksum - 1.0) < 1e-12:
        return pi  # already fair

    def f(k: float) -> float:
        return np.power(pi, k).sum() - 1.0

    # booksum > 1 -> need k > 1; bracket generously
    k = brentq(f, 1.0, 10.0, xtol=1e-12)
    p = np.power(pi, k)
    return p / p.sum()  # renormalize residual float error


def devig_shin(decimal_odds: list[float]) -> np.ndarray:
    """Shin (1992/1993): back out implied insider fraction z, devig with it.

    p_i = ( sqrt(z^2 + 4(1-z) * pi_i^2 / B) - z ) / ( 2(1-z) )
    where B = sum(pi) and z solves sum(p_i) == 1.
    """
    pi = implied(decimal_odds)
    B = pi.sum()
    if abs(B - 1.0) < 1e-12:
        return pi

    def p_of_z(z: float) -> np.ndarray:
        return (np.sqrt(z * z + 4.0 * (1.0 - z) * (pi * pi) / B) - z) / (2.0 * (1.0 - z))

    def f(z: float) -> float:
        return p_of_z(z).sum() - 1.0

    # z in (0, ~booksum-1] practically; f(0+) > 0, find sign change
    lo, hi = 1e-9, 0.5
    if f(hi) > 0:  # pathological huge hold; widen
        hi = 0.95
    z = brentq(f, lo, hi, xtol=1e-12)
    p = p_of_z(z)
    return p / p.sum()


_METHODS = {
    "multiplicative": devig_multiplicative,
    "power": devig_power,
    "shin": devig_shin,
}


def devig(decimal_odds: list[float], method: str = "shin") -> np.ndarray:
    """Dispatch. The method string you store in odds_snapshots.devig_method
    MUST be the one actually used — this is the labeling bug fixed."""
    try:
        fn = _METHODS[method]
    except KeyError:
        raise ValueError(f"unknown devig method '{method}'; use {list(_METHODS)}")
    return fn(decimal_odds)

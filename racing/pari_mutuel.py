"""Pari-mutuel engine — the heart of the horse racing sleeve.

Racing is NOT fixed-odds. There is no bookmaker line to beat. You bet
against the POOL, and the edge structure inverts:

  Sports:  model fair value vs a lazy book's mispriced line.
  Racing:  model true win prob vs the CROWD's implied prob in the pool,
           and you only win if your disagreement survives TAKEOUT (~16-20%).

Takeout is the brutal part. The track skims 16-20% off every pool before
paying out, so the breakeven bar is far higher than sports. A horse the
crowd sends off at 4-1 is NOT a 20% shot to you — after takeout the pool
is overround by ~120-125%, so the crowd's true implied prob is lower than
the naive 1/(odds+1). Strip that overround first, then compare to model.

This module:
  1. tote_to_prob   — strip pool overround -> crowd's true implied probs
  2. edge_after_takeout — model prob vs crowd prob, net of takeout
  3. harville_exacta/trifecta — derive exotic probs from win probs
  4. kelly_pool     — sizing into a pari-mutuel pool (your bet moves the odds)
"""
from __future__ import annotations

import itertools

import numpy as np

__all__ = [
    "tote_to_prob", "edge_after_takeout", "harville_order_prob",
    "henery_order_prob", "exacta_prob", "trifecta_prob", "kelly_pool",
]


def tote_to_prob(win_odds: list[float]) -> np.ndarray:
    """Convert tote-board WIN odds (decimal, e.g. 4-1 -> 5.0 payout incl stake,
    so pass 5.0) into the crowd's true implied probabilities.

    The raw 1/odds sum to >1 (the overround = takeout + rounding). We strip
    it proportionally to recover what the crowd actually believes."""
    odds = np.asarray(win_odds, dtype=float)
    if np.any(odds <= 1.0):
        raise ValueError("pass full decimal payout per $1 incl stake, all > 1.0")
    raw = 1.0 / odds
    return raw / raw.sum()          # normalize out the overround


def edge_after_takeout(model_p: np.ndarray, crowd_p: np.ndarray,
                       takeout: float = 0.17) -> np.ndarray:
    """Expected value per $1 bet to win, for each horse.

    In a pari-mutuel win pool, if you bet a horse with true prob model_p,
    the pool pays out (1 - takeout) of the total, distributed across winning
    tickets in proportion to the crowd's money. Your EV per $1:

        EV_i = model_p_i * (1 - takeout) / crowd_p_i  - 1

    crowd_p_i is the fraction of the win pool on horse i (its implied prob).
    Positive EV means your model thinks the horse is live relative to how
    much crowd money is on it, even after the house skim."""
    crowd_p = np.clip(crowd_p, 1e-9, 1.0)
    return model_p * (1.0 - takeout) / crowd_p - 1.0


def harville_order_prob(win_p: np.ndarray, order: tuple[int, ...]) -> float:
    """Harville (1973): probability of a specific finishing ORDER given win
    probs. P(A 1st, B 2nd, C 3rd) = pA * pB/(1-pA) * pC/(1-pA-pB).

    The classic model. Known to be biased (it ignores that being 'best of
    the rest' isn't independent of who won), but it's the canonical baseline
    and the foundation every refinement (Henery, Stern) builds on."""
    p = win_p
    remaining = 1.0
    used = 0.0
    out = 1.0
    for h in order:
        denom = 1.0 - used
        if denom <= 0:
            return 0.0
        out *= p[h] / denom
        used += p[h]
    return out


def henery_order_prob(win_p: np.ndarray, order: tuple[int, ...],
                      lambdas: tuple[float, ...] = (1.0, 0.81, 0.65)) -> float:
    """Henery refinement of Harville. Harville's flaw: it assumes the running
    for 2nd uses the SAME strengths as the running for 1st, which overstates
    favorites placing. Henery discounts each horse's strength as the race
    progresses by raising probs to a power lambda_k < 1 at finishing position
    k, flattening the field for the minor placings.

    lambdas: discount per position. (1.0, ~0.81, ~0.65) are the empirically
    fitted values from the racing literature. position 1 undiscounted."""
    p = np.asarray(win_p, dtype=float)
    out = 1.0
    used = np.zeros(len(p), dtype=bool)
    for k, h in enumerate(order):
        lam = lambdas[k] if k < len(lambdas) else lambdas[-1]
        pw = p ** lam
        denom = pw[~used].sum()
        if denom <= 0:
            return 0.0
        out *= pw[h] / denom
        used[h] = True
    return out


def exacta_prob(win_p: np.ndarray, i: int, j: int, model: str = "henery") -> float:
    """P(horse i wins, horse j second). Henery default (less favorite-biased)."""
    if model == "henery":
        return henery_order_prob(win_p, (i, j))
    return harville_order_prob(win_p, (i, j))


def trifecta_prob(win_p: np.ndarray, i: int, j: int, k: int,
                  model: str = "henery") -> float:
    """P(i-j-k exact finishing order). Henery default."""
    if model == "henery":
        return henery_order_prob(win_p, (i, j, k))
    return harville_order_prob(win_p, (i, j, k))


def kelly_pool(model_p: float, crowd_p: float, takeout: float,
               bankroll: float, pool_size: float, lam: float = 0.25) -> float:
    """Fractional Kelly into a pari-mutuel pool, accounting for the fact that
    YOUR bet dilutes the very odds you're betting into (large bets in small
    pools move the price against you). Approximated here for small bet/pool
    ratios; refine with full pool-impact when bet > ~2% of pool."""
    payout_odds = (1.0 - takeout) / crowd_p          # approx decimal payout
    b = payout_odds - 1.0
    if b <= 0:
        return 0.0
    edge = model_p * payout_odds - 1.0
    if edge <= 0:
        return 0.0
    f = edge / b
    stake = bankroll * f * lam
    # cap so the bet doesn't blow up the pool price
    return round(min(stake, 0.02 * pool_size), 2)

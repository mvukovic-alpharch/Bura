"""Portfolio layer: judge the betting book like a macro fund, not a bettor.

Daily return series -> Sharpe, Sortino, max drawdown, CLV diagnostics.
Sizing via fractional Kelly with uncertainty shrink.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["kelly_stake", "daily_returns", "tearsheet"]


def kelly_stake(
    fair_prob: float,
    decimal_odds: float,
    bankroll: float,
    lam: float = 0.25,
    uncertainty: float = 0.0,
    cap: float | None = None,
) -> float:
    """Quarter-Kelly default, shrunk by model uncertainty in [0,1)."""
    b = decimal_odds - 1.0
    edge = fair_prob * decimal_odds - 1.0  # EV per unit staked
    if b <= 0 or edge <= 0:
        return 0.0
    f_full = edge / b  # = (p*b - q)/b
    stake = bankroll * f_full * lam * max(0.0, 1.0 - uncertainty)
    if cap is not None:
        stake = min(stake, cap)
    return round(stake, 2)


def daily_returns(bets: pd.DataFrame, bankroll: float) -> pd.Series:
    """bets needs columns: ts (datetime), stake, pnl. Returns daily pct returns
    on bankroll (constant-bankroll convention for diagnostics)."""
    df = bets.copy()
    df["date"] = pd.to_datetime(df["ts"]).dt.date
    daily_pnl = df.groupby("date")["pnl"].sum()
    return daily_pnl / bankroll


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def tearsheet(bets: pd.DataFrame, bankroll: float, periods_per_year: int = 252) -> dict:
    """The numbers a PM would ask for. bets columns:
    ts, stake, pnl, entry_prob, close_prob (close optional -> CLV NaN-safe).
    """
    r = daily_returns(bets, bankroll)
    if len(r) < 2:
        raise ValueError("need >= 2 trading days for a tearsheet")

    mu, sd = r.mean(), r.std(ddof=1)
    downside = r[r < 0]
    dd_dev = downside.std(ddof=1) if len(downside) > 1 else np.nan

    ann = np.sqrt(periods_per_year)
    sharpe = float(mu / sd * ann) if sd > 0 else np.nan
    sortino = float(mu / dd_dev * ann) if dd_dev and dd_dev > 0 else np.nan

    equity = (1.0 + r).cumprod()
    maxdd = _max_drawdown(equity)

    out = {
        "n_bets": int(len(bets)),
        "n_days": int(len(r)),
        "total_return_pct": float((equity.iloc[-1] - 1.0) * 100),
        "ann_sharpe": round(sharpe, 2),
        "ann_sortino": round(sortino, 2),
        "max_drawdown_pct": round(maxdd * 100, 2),
        "hit_rate_pct": round(float((bets["pnl"] > 0).mean() * 100), 1),
        "avg_stake": round(float(bets["stake"].mean()), 2),
    }

    # CLV block — the real KPI for the first 1,000 bets
    if {"entry_prob", "close_prob"}.issubset(bets.columns):
        # CLV convention: positive = you beat the close = the market moved
        # TOWARD your side after entry => close implied prob > entry implied prob
        clv_bps = (bets["close_prob"] - bets["entry_prob"]) * 10_000
        clv_bps = clv_bps.dropna()
        if len(clv_bps):
            n = len(clv_bps)
            mean_clv = float(clv_bps.mean())
            se = float(clv_bps.std(ddof=1) / np.sqrt(n)) if n > 1 else np.nan
            out.update(
                {
                    "clv_n": n,
                    "clv_mean_bps": round(mean_clv, 1),
                    "clv_tstat": round(mean_clv / se, 2) if se and se > 0 else np.nan,
                    "clv_positive_pct": round(float((clv_bps > 0).mean() * 100), 1),
                }
            )
    return out

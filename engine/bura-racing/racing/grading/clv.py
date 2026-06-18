"""Grading + CLV loop. CLV is the honest signal long before P&L means anything.

Racing CLV: did the horse you backed get bet DOWN by post time (you beat the
closing odds = positive CLV) or drift OUT (negative)? Beating the close in a
pari-mutuel market means the crowd moved toward your opinion after you formed
it — the racing analogue of beating a sharp sportsbook close.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GradedBet:
    bet_type: str
    selection: tuple[int, ...]
    stake: float
    entry_odds: float           # decimal payout when you bet
    close_odds: float           # decimal payout at post
    won: bool
    payout: float               # gross returned
    clv_pct: float              # (entry_implied - close_implied)/close_implied


def clv(entry_odds: float, close_odds: float) -> float:
    """Positive when your entry odds were LONGER than the close — i.e. the
    horse got bet down, the crowd validated your read."""
    entry_implied = 1.0 / entry_odds
    close_implied = 1.0 / close_odds
    return (close_implied - entry_implied) / entry_implied


def grade_win_bet(selection: int, stake: float, entry_odds: float,
                  close_odds: float, winner: int) -> GradedBet:
    won = (selection == winner)
    payout = stake * close_odds if won else 0.0   # pari-mutuel pays the close
    return GradedBet("win", (selection,), stake, entry_odds, close_odds,
                     won, payout, clv(entry_odds, close_odds))


def session_summary(bets: list[GradedBet]) -> dict:
    if not bets:
        return {"n": 0}
    n = len(bets)
    staked = sum(b.stake for b in bets)
    returned = sum(b.payout for b in bets)
    clvs = [b.clv_pct for b in bets]
    return {
        "n": n,
        "staked": round(staked, 2),
        "returned": round(returned, 2),
        "roi_pct": round((returned - staked) / staked * 100, 1) if staked else 0,
        "hit_rate_pct": round(sum(b.won for b in bets) / n * 100, 1),
        "mean_clv_pct": round(sum(clvs) / n * 100, 1),
        "clv_positive_pct": round(sum(c > 0 for c in clvs) / n * 100, 1),
    }

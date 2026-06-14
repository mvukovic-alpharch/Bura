"""End-to-end demo on synthetic data. Proves every module runs and the
math behaves, with zero API keys. Run:  python -m engine.demo
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .devig import devig
from .portfolio import kelly_stake, tearsheet
from .periphery import rank_universe
from .props_board import PropQuote, build_board

rng = np.random.default_rng(7)


def check_devig() -> None:
    print("=" * 64)
    print("DEVIG VERIFICATION")
    print("=" * 64)
    # symmetric -110/-110 -> all methods must give 0.500
    for m in ("multiplicative", "power", "shin"):
        p = devig([1.909, 1.909], m)
        assert abs(p[0] - 0.5) < 1e-9, f"{m} failed symmetry"
        print(f"  -110/-110  {m:>14}: {p[0]:.4f} / {p[1]:.4f}  sum={p.sum():.6f}")
    # lopsided 1.30 / 3.80 -> methods must DIVERGE (favorite-longshot)
    print("  lopsided 1.30 / 3.80:")
    for m in ("multiplicative", "power", "shin"):
        p = devig([1.30, 3.80], m)
        print(f"    {m:>14}: fav={p[0]:.4f}  dog={p[1]:.4f}")
    pm = devig([1.30, 3.80], "multiplicative")
    ps = devig([1.30, 3.80], "shin")
    assert ps[1] < pm[1], "shin should price the longshot BELOW multiplicative"
    print("  ✓ shin prices longshot below multiplicative (favorite-longshot handled)")
    print("  ✓ method labels now match math actually applied\n")


def synth_book(n_days: int = 120, bets_per_day: int = 8, bankroll: float = 25_000):
    """Simulate a book with a genuine ~2.5% mean edge to show what the
    tearsheet looks like WHEN the edge is real."""
    rows = []
    dates = pd.bdate_range("2026-01-05", periods=n_days)
    for d in dates:
        for _ in range(bets_per_day):
            fair = rng.uniform(0.40, 0.62)
            edge = rng.normal(0.025, 0.012)            # real but noisy edge
            mkt_prob = np.clip(fair - edge, 0.05, 0.95)
            odds = 1.0 / mkt_prob * (1 - 0.018)        # ~1.8% residual cost
            stake = kelly_stake(fair, odds, bankroll, lam=0.25, uncertainty=0.2,
                                cap=bankroll * 0.01)
            if stake <= 0:
                continue
            win = rng.random() < fair
            pnl = stake * (odds - 1.0) if win else -stake
            # close converges ~70% of the way from entry toward fair + noise
            close_prob = np.clip(mkt_prob + 0.7 * edge + rng.normal(0, 0.01),
                                 0.05, 0.95)
            rows.append({"ts": d, "stake": stake, "pnl": pnl,
                         "entry_prob": mkt_prob, "close_prob": close_prob})
    return pd.DataFrame(rows), bankroll


def main() -> None:
    check_devig()

    print("=" * 64)
    print("PERIPHERY UNIVERSE RANKING (priors — Layer 0 replaces with measured)")
    print("=" * 64)
    for name, score, region in rank_universe():
        bar = "█" * int(score * 30)
        print(f"  {name:<24} {region:<8} {score:.3f}  {bar}")
    print()

    print("=" * 64)
    print("FUND TEARSHEET — synthetic 120-day book, real ~2.5% edge, 1/4 Kelly")
    print("=" * 64)
    bets, bankroll = synth_book()
    ts = tearsheet(bets, bankroll)
    for k, v in ts.items():
        print(f"  {k:<22} {v}")
    print()

    print("=" * 64)
    print("PROPS BOARD — sample big-5 scan (synthetic quotes)")
    print("=" * 64)
    weights = {"pinnacle": 0.60, "circa": 0.25, "dk": 0.08, "fd": 0.07}
    baseline = {"NBA": (0.008, 0.004), "NFL": (0.010, 0.005),
                "EPL": (0.009, 0.004)}
    props = [
        PropQuote("m1", "NBA", "Player A", "PTS o27.5",
                  {"pinnacle": (1.92, 1.92), "dk": (2.10, 1.78), "fd": (2.05, 1.80)}),
        PropQuote("m2", "NFL", "Player B", "Rec o5.5",
                  {"pinnacle": (1.87, 1.95), "dk": (1.90, 1.92), "fd": (1.88, 1.94)}),
        PropQuote("m3", "EPL", "Player C", "Shots o2.5",
                  {"pinnacle": (1.95, 1.89), "dk": (2.25, 1.70), "fd": (2.18, 1.72)}),
    ]
    board = build_board(props, weights, baseline)
    hdr = f"  {'mkt':<4}{'sport':<6}{'player':<10}{'market':<12}{'book':<6}" \
          f"{'odds':<7}{'fair':<8}{'mkt_p':<8}{'edge':<8}{'EV':<8}{'regime':<12}{'action'}"
    print(hdr)
    for r in board:
        print(f"  {r.market_id:<4}{r.sport:<6}{r.player:<10}{r.market:<12}"
              f"{r.best_book:<6}{r.best_odds:<7.2f}{r.fair_prob:<8.4f}"
              f"{r.market_prob:<8.4f}{r.edge:<8.4f}{r.ev:<8.4f}{r.regime:<12}{r.action}")
    print("\n  Note how m2 (books agree) lands EFFICIENT/PASS while m1/m3")
    print("  (soft books off vs sharp consensus) open the gates. That's the")
    print("  regime engine doing ArchAlpha posture-lock on a sports market.")


if __name__ == "__main__":
    main()

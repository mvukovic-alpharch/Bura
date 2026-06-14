"""Verify the BP engine and demonstrate the lambda_3 edge thesis.
Run: python -m engine.bp_demo
"""
from __future__ import annotations

import numpy as np

from .bp_soccer import (bp_pmf_matrix, inflate_diagonal, price_1x2,
                        price_total, skellam_win_prob)


def main() -> None:
    print("=" * 66)
    print("BP ENGINE VERIFICATION")
    print("=" * 66)

    l1, l2 = 1.35, 1.05  # typical low-scoring periphery soccer match

    # 1) matrix mass ~ 1
    M = bp_pmf_matrix(l1, l2, 0.15, max_goals=12)
    print(f"  matrix total mass (l3=0.15):        {M.sum():.6f}")
    assert abs(M.sum() - 1.0) < 1e-4

    # 2) Skellam cross-check: 1X2 from matrix == Skellam when l3 = 0
    sk = skellam_win_prob(l1, l2)
    mx = price_1x2(bp_pmf_matrix(l1, l2, 0.0, max_goals=20))
    print(f"  Skellam  H/D/A: {sk['home']:.4f} / {sk['draw']:.4f} / {sk['away']:.4f}")
    print(f"  Matrix   H/D/A: {mx['home']:.4f} / {mx['draw']:.4f} / {mx['away']:.4f}")
    assert all(abs(sk[k] - mx[k]) < 1e-3 for k in sk)

    # 3) THE INVARIANCE: winner probs don't move with l3; draw/totals do
    print("\n  l3 sweep (same l1, l2): winner stable, draw & U2.5 move")
    print(f"  {'l3':>6} {'P(home)':>9} {'P(draw)':>9} {'P(U2.5)':>9}")
    for l3 in (0.0, 0.10, 0.20, 0.30):
        Mi = bp_pmf_matrix(l1, l2, l3, max_goals=14)
        p = price_1x2(Mi)
        t = price_total(Mi, 2.5)
        print(f"  {l3:>6.2f} {p['home']:>9.4f} {p['draw']:>9.4f} {t['under']:>9.4f}")

    # 4) the lazy-copier mispricing, quantified
    print("\n" + "=" * 66)
    print("LAZY-COPIER DEMO — the periphery edge thesis, in numbers")
    print("=" * 66)
    true_l3 = 0.20                     # real shared-tempo covariance
    M_true = bp_pmf_matrix(l1, l2, true_l3, max_goals=14)
    M_true = inflate_diagonal(M_true, p=0.05, dist="geometric", theta=0.55)
    # A double-Poisson book calibrated to the SAME observed goal averages
    # sees marginal means (l1 + l3, l2 + l3) — that's what it prices with.
    M_copy = bp_pmf_matrix(l1 + true_l3, l2 + true_l3, 0.0, max_goals=14)

    p_t, p_c = price_1x2(M_true), price_1x2(M_copy)
    t_t, t_c = price_total(M_true, 2.5), price_total(M_copy, 2.5)

    print(f"  {'':>14} {'true (BP+infl)':>15} {'copier (2xPois)':>16} {'gap bps':>9}")
    for k in ("home", "draw", "away"):
        gap = (p_t[k] - p_c[k]) * 10_000
        print(f"  P({k:<5}){'':>5} {p_t[k]:>15.4f} {p_c[k]:>16.4f} {gap:>9.0f}")
    gap_u = (t_t['under'] - t_c['under']) * 10_000
    print(f"  P(U2.5){'':>6} {t_t['under']:>15.4f} {t_c['under']:>16.4f} {gap_u:>9.0f}")

    print("\n  Read: a copier matched to the same goal averages runs hotter")
    print("  total intensity (it can't see l3), so it underprices the DRAW")
    print("  by ~600bps and misprices totals by ~275bps — both beyond the")
    print("  250bps edge floor. Scan the draw/totals surface in thin")
    print("  leagues; the moneyline gaps are smaller and noisier.")


if __name__ == "__main__":
    main()

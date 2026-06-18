"""Paper-mode card runner. Full pipeline on a synthetic card, no data needed.
Run: python -m racing.run_card_demo

card -> feature store -> win model -> tote board -> bet construction
     -> grade vs result -> CLV. This is the whole system breathing.
"""
from __future__ import annotations

import datetime as dt
import numpy as np

from .models import Card, Race, Entry, Horse, PastPerformance
from .features.store import build_feature_matrix
from .win_model import win_probs
from .betting.construct import construct_bets
from .grading.clv import grade_win_bet, session_summary

rng = np.random.default_rng(17)


def _synth_horse(hid: str, quality: float, style_bias: float) -> Horse:
    """quality shifts speed figs; style_bias shifts early/late pace."""
    pps = []
    base = dt.date(2026, 6, 1)
    for k in range(rng.integers(3, 8)):
        pps.append(PastPerformance(
            date=base - dt.timedelta(days=20 * k + int(rng.integers(0, 10))),
            speed_fig=80 + quality * 12 + rng.normal(0, 4),
            class_level=50 + quality * 10 + rng.normal(0, 5),
            finish_pos=int(rng.integers(1, 9)), field_size=8,
            early_pace=style_bias + rng.normal(0, 0.3),
            late_pace=-style_bias + rng.normal(0, 0.3),
            surface="dirt", distance_furlongs=8.5))
    return Horse(hid, hid, pps)


def build_synthetic_route() -> Race:
    """8-horse dirt route. Horse 1 = strong lone-speed (the edge horse)."""
    styles = [1.4, -0.3, -0.6, 0.0, -0.8, -0.5, 0.1, -1.0]  # early bias
    quals = [0.95, 1.0, 0.4, 0.7, 0.9, 0.3, 0.85, 0.5]      # raw quality
    entries = []
    for i in range(8):
        h = _synth_horse(f"#{i+1}", quals[i], styles[i])
        entries.append(Entry(
            program_number=i + 1, horse=h,
            jockey=f"J{i}", trainer=f"T{i}",
            jockey_sr=0.12 + rng.random() * 0.08,
            trainer_sr=0.12 + rng.random() * 0.10,
            post_position=i + 1, weight=120 + rng.integers(-3, 4)))
    return Race("R1", "Parx", 4, dt.date(2026, 6, 14), "dirt", 8.5, 55.0,
                entries=entries)


def main() -> None:
    print("=" * 70)
    print("BURA RACING — paper-mode card run (synthetic Parx route)")
    print("=" * 70)

    race = build_synthetic_route()
    feat = build_feature_matrix(race)        # also fills run_style, pace_fit
    mp = win_probs(feat)
    for i, e in enumerate(race.entries):
        e.model_win_prob = float(mp[i])

    print(f"\n  Race: {race.track} R{race.race_number}, "
          f"{race.distance_furlongs}f {race.surface}, route={race.is_route}")
    print(f"\n  {'#':>3} {'style':>6} {'pace':>6} {'model%':>8}")
    for e in race.entries:
        print(f"  {e.program_number:>3} {e.run_style:>6} "
              f"{e.pace_fit:>+6.2f} {e.model_win_prob*100:>7.1f}%")

    # a tote board: crowd bets raw quality, UNDERrates the lone-speed #1
    crowd = mp.copy()
    crowd[0] *= 0.6          # crowd misses #1's pace edge
    crowd = crowd / crowd.sum()
    tote = (1.0 / crowd) * (1 - race.takeout_win)
    tote = np.maximum(tote, 1.05)

    bets = construct_bets(mp, tote, race.takeout_win, race.takeout_exotic)

    print("\n  +EV WIN bets (after takeout):")
    if bets["win"]:
        for b in bets["win"]:
            i = b.selection[0]
            print(f"    #{i+1} at {tote[i]-1:.1f}x  EV {b.ev*100:+.1f}%  ({b.note})")
    else:
        print("    none — pool efficient, no play")

    print("\n  Top exotic structures (fair prices, key the edge horse):")
    for b in bets["exotic"][:3]:
        sel = "-".join(f"#{s+1}" for s in b.selection)
        print(f"    {b.bet_type} {sel}: fair ${b.fair_payout:.0f} for $1")

    # grade: simulate the race by TRUE model prob, pay at the close
    winner = int(rng.choice(len(mp), p=mp))
    print(f"\n  Race result: #{winner+1} wins")
    graded = []
    for b in bets["win"]:
        i = b.selection[0]
        entry_odds = tote[i]
        close_odds = tote[i] * (0.85 if i == 0 else 1.0)  # #1 bet down late
        graded.append(grade_win_bet(i, 2.0, entry_odds, close_odds, winner))
    if graded:
        s = session_summary(graded)
        print(f"\n  Paper session: {s['n']} bets, ROI {s['roi_pct']}%, "
              f"hit {s['hit_rate_pct']}%, mean CLV {s['mean_clv_pct']}%, "
              f"CLV+ {s['clv_positive_pct']}%")
        print("  (CLV is the signal that matters across hundreds of races,")
        print("   not the result of any single one.)")


if __name__ == "__main__":
    main()

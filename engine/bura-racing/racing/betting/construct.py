"""Bet construction — model probabilities + tote board -> actionable bets.

Decides not just WHICH horse but WHICH BET TYPE. Often the win pool is dead
(crowd efficient) but an exotic keying your edge horse is live, because exotic
pools are softer and the Henery prices diverge more from the crowd there.
"""
from __future__ import annotations

from dataclasses import dataclass
import itertools

import numpy as np

from ..pari_mutuel import (tote_to_prob, edge_after_takeout,
                          exacta_prob, trifecta_prob)


@dataclass
class BetCandidate:
    bet_type: str               # win | exacta | trifecta
    selection: tuple[int, ...]  # program-number indices
    model_prob: float
    fair_payout: float          # $ per $1 at true prob
    ev: float                   # expected value per $1 after takeout
    note: str = ""


def find_win_bets(model_p: np.ndarray, tote_odds: np.ndarray,
                  takeout: float, min_ev: float = 0.05,
                  min_prob: float = 0.05, max_odds: float = 20.0) -> list[BetCandidate]:
    """+EV win bets, with the longshot-trap guards that keep this from
    blowing up: a horse must clear min_prob (model conviction) AND be under
    max_odds. At tiny probabilities the model's error swamps any computed
    edge, so a '+EV' 100-1 shot is noise, not a bet. This gate is the
    difference between a pari-mutuel model and a bankroll incinerator."""
    crowd_p = tote_to_prob(tote_odds)
    ev = edge_after_takeout(model_p, crowd_p, takeout)
    out = []
    for i in np.argsort(ev)[::-1]:
        if ev[i] < min_ev:
            break
        if model_p[i] < min_prob:
            continue                    # model doesn't believe it — skip
        if (tote_odds[i] - 1.0) > max_odds:
            continue                    # too long; error dominates edge
        out.append(BetCandidate("win", (int(i),), float(model_p[i]),
                                1.0 / model_p[i], float(ev[i]),
                                f"crowd {crowd_p[i]*100:.0f}% vs model {model_p[i]*100:.0f}%"))
    return out


def find_exotic_bets(model_p: np.ndarray, takeout: float,
                     top_k: int = 4, min_ev: float = 0.10) -> list[BetCandidate]:
    """Exotics priced off Henery win probs. Without live exotic-pool data we
    price the FAIR side; EV vs pool is computed when tote exotic probables
    are available. Here we surface the structurally strongest combinations
    keyed off the model's edge horses."""
    top = np.argsort(model_p)[::-1][:top_k]
    out = []
    # exactas among top_k
    for i, j in itertools.permutations(top, 2):
        p = exacta_prob(model_p, int(i), int(j))
        if p > 0:
            out.append(BetCandidate("exacta", (int(i), int(j)), p, 1.0 / p,
                                    float("nan"),  # EV needs exotic pool data
                                    "fair price; compare to exacta probables"))
    out.sort(key=lambda b: b.model_prob, reverse=True)
    return out[:top_k]


def construct_bets(model_p: np.ndarray, tote_odds: np.ndarray,
                   takeout_win: float, takeout_exotic: float) -> dict:
    return {
        "win": find_win_bets(model_p, tote_odds, takeout_win),
        "exotic": find_exotic_bets(model_p, takeout_exotic),
    }

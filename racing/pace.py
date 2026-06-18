"""Pace projection — the realest edge in route racing.

Why this matters more than raw speed figures: a route race (2 turns) is won
or lost on PACE SHAPE. If one horse has clear early speed and nobody else
wants the lead, it gets a 'lone speed' uncontested front-running trip and
massively overperforms its raw figures. Conversely, four speed horses in
one race = a pace meltdown that sets it up for closers. The crowd
systematically underrates lone speed and overrates closers with 'big late
kicks' that need a fast pace to materialize.

Pipeline:
  1. classify each horse's run style from its early-pace numbers
     (E = need-the-lead, EP = pressers, P = stalkers, S = closers)
  2. project the race's pace scenario (how contested is the lead?)
  3. score each horse's fit to that scenario -> a pace_fit feature that
     feeds the win model
"""
from __future__ import annotations

import numpy as np

__all__ = ["RUN_STYLES", "classify_style", "project_pace", "pace_fit_scores"]

RUN_STYLES = ["E", "EP", "P", "S"]   # early, early-presser, presser, sustained


def classify_style(early_speed: float, late_speed: float) -> str:
    """From normalized early vs late energy (z-scores). E horses spend energy
    early; S horses save it. Simple, robust quadrant logic."""
    if early_speed > 0.8:
        return "E"
    if early_speed > 0.2:
        return "EP"
    if early_speed > -0.4:
        return "P"
    return "S"


def project_pace(styles: list[str]) -> dict:
    """How contested is the lead? Count genuine early speed. The key number
    is n_E (need-the-lead types): 0-1 = soft pace (favors speed),
    3+ = hot/contested pace (favors closers)."""
    n_E = styles.count("E")
    n_EP = styles.count("EP")
    pressure = n_E + 0.5 * n_EP
    if pressure <= 1.0:
        scenario = "soft"      # lone or uncontested speed -> front-runners win
    elif pressure <= 2.5:
        scenario = "honest"
    else:
        scenario = "hot"       # pace meltdown -> closers win
    return {"scenario": scenario, "pressure": pressure,
            "n_E": n_E, "n_EP": n_EP}


def pace_fit_scores(styles: list[str], pace: dict) -> np.ndarray:
    """Score each horse's fit to the projected pace, in [-1, 1].
    Positive = the scenario helps this horse's style.

    The exploitable asymmetry: in a SOFT pace, a lone E horse gets a big
    positive score (uncontested lead) — that's the bet the crowd misses.
    In a HOT pace, closers (S) get the boost."""
    scenario = pace["scenario"]
    n_E = pace["n_E"]
    out = []
    for s in styles:
        if scenario == "soft":
            # lone speed is gold; the rarer the speed, the bigger the edge
            if s == "E":
                out.append(1.0 if n_E == 1 else 0.6)
            elif s == "EP":
                out.append(0.4)
            elif s == "P":
                out.append(-0.1)
            else:
                out.append(-0.6)            # closers hate a slow pace
        elif scenario == "hot":
            if s == "S":
                out.append(1.0)
            elif s == "P":
                out.append(0.5)
            elif s == "EP":
                out.append(-0.3)
            else:
                out.append(-0.9)            # speed gets cooked in a meltdown
        else:                               # honest pace, mild effects
            out.append({"E": 0.2, "EP": 0.1, "P": 0.0, "S": -0.1}[s])
    return np.asarray(out, dtype=float)

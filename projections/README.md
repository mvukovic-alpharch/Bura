# Bura — Projections Module

Calibrated player-prop projections for NFL, NBA, EPL, La Liga, Serie A.
Distribution-first: predicts the full probability distribution of a stat,
not a point estimate — so it prices ANY line into a calibrated P(over).

NOT an edge-finder against efficient books. It's an honest projection so
your parlay legs and DFS picks are educated, not vibes. Skin in the game
with a real model behind every pick.

## Pieces
- `engine.py` — distribution families (Poisson/NegBinom/Normal), opponent
  + pace adjustment, line pricing to over/under/push probability
- `sports_config.py` — which distribution fits each stat, per sport
- `parlay.py` — correlated parlay scoring (Gaussian copula); the naive
  parlay calculator ignores leg correlation, this doesn't
- `demo.py` — runs everything on synthetic inputs

## Run
    python -m projections.demo

## Status
PAPER / pre-season. Runs on synthetic inputs now. When NFL/NBA/soccer
seasons open, plug a free odds + player-stats feed into `project_stat`'s
base_mean / opp_factor / pace_factor and it produces live projections.
DFS-optimizer layer (lineup construction) is the planned next layer on top.

## Honest notes
- Correlation effect on parlays must be COMPUTED, not assumed — direction
  depends on where lines sit vs means. The engine computes it.
- Distribution family choice per stat is the real domain work and is the
  thing to refine against real data once seasons start.

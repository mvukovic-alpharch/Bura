# Bura — Racing Module (paper mode)

Pari-mutuel Thoroughbred modeling under the Bura umbrella. Event-driven,
not a continuous poller. Targets **dirt route races at mid-tier tracks** —
the periphery of racing, where pools are softer, same logic as Bura's
thin-consensus leagues. Paper mode only: prices and grades, never wagers.

## Why racing is structurally different
There is no bookmaker line to beat. You bet against the **pool**, and you
only win if your edge survives **takeout** (~16–20%). The edge is almost
never the horse you think wins — it's the overlay the crowd ignores, and
you **fade the chalk** the public overbets.

## The pipeline (all verified offline)
```
card -> feature store -> win model -> tote board -> bet construction -> grade -> CLV
```
- **models.py** — canonical Card/Race/Entry/Horse/PastPerformance types
- **features/store.py** — past performances -> within-race standardized
  feature matrix; classifies run style + projects pace as a side effect
- **win_model.py** — conditional logit (Plackett-Luce top-1); softmax over
  the field; `fit_mle` learns weights from results (recovers signal at
  r=0.998 on synthetic data)
- **pace.py** — run-style classification + pace projection; finds the
  lone-speed-in-a-soft-pace edge the crowd underrates
- **pari_mutuel.py** — tote devig, takeout-adjusted EV, Harville AND Henery
  exotic pricing (Henery fixes Harville's favorite-placing bias)
- **betting/construct.py** — +EV win bets and exotic structures, WITH the
  longshot-trap guard (min prob floor + max odds cap)
- **grading/clv.py** — racing CLV: did your horse get bet down by post?
- **db/schema.sql** — races, entries, past_performances, tote_snapshots,
  results, bets, clv_log

## Run it
```bash
python -m racing.run_card_demo     # full paper card, synthetic
python -m engine.horse_demo        # pari-mutuel + win model + MLE recovery
python -m engine.pace_demo         # pace edge + Harville vs Henery
```

## Honest known limitations (the real work ahead)
1. **Pace weight is under-calibrated.** The hand-set beta gives pace_fit
   0.45, which isn't enough to fully express the lone-speed edge against
   within-race standardization. This is NOT a bug — it's why `fit_mle`
   exists. Real results will learn pace's true predictive weight.
2. **Harville/Henery are win-prob-derived.** Exotic EV vs the actual exotic
   POOL needs live exacta/trifecta probables, not yet ingested.
3. **No real data yet.** Everything is verified on synthetic cards. The next
   phase is sourcing real race cards + tote boards (Equibase/ADW feeds).

## The longshot-trap fix (why the demo says "no play")
A 1%-probability horse at 100-1 can show "+EV" on paper because at tiny
probabilities model error swamps the edge. The win-bet gate enforces a
minimum model probability and a maximum odds cap. A disciplined "no play"
is the correct output far more often than a bet — that's the whole point.

## Gate discipline (same as Bura)
Paper -> measure CLV over a large sample of cards -> only then consider live.
CLV > 0 across hundreds of races is the signal, never any single result.
```
PAPER MODE = always, until CLV proven. No ADW wiring in this build.
```

# SportsAlpha — Periphery Edition

ArchAlpha's playbook applied to sports markets. Three ideas nobody else
is combining:

**1. The Periphery Engine** — the alpha sleeve. Every syndicate models the
NBA; almost nobody systematically farms Croatian HNL, Serbian SuperLiga,
Colombian Primera A, Liga MX, KBO — leagues where Pinnacle posts a real
line, soft-book coverage is thin and lazily copied, and team news breaks
in languages quant desks don't read. Native language + physical presence
in the Balkans and LatAm is the operator moat. Each league gets a
PeripheryScore (consensus thinness × copy lag × news moat × liquidity
floor); priors ship in `engine/periphery.py` and Layer 0 replaces them
with measured values from `odds_snapshots`.

**2. The Market-Efficiency Regime Engine** — ArchAlpha posture-lock
transplanted. Cross-book dispersion of devigged probabilities, z-scored
against a trailing per-family baseline, classifies each market
EFFICIENT / NOISY / DISLOCATED. You don't bet because the model has an
opinion; you bet because the market is in a regime where models can win.
EFFICIENT = stand down, regardless of edge estimate.

**3. The fund tearsheet** — the book is judged like a macro PM: annualized
Sharpe, Sortino, max drawdown, hit rate, and granular CLV (mean bps,
t-stat, % positive). CLV is the only KPI that matters for the first
1,000 bets.

The big-5 props board (NBA/NFL/MLB/NHL/EPL) is the benchmark surface:
rich data calibrates the devig + sharpness weights + regime baselines,
and gives you the major-prop viewing screen. The periphery is where the
calibrated machinery goes to eat.

## Modules

| File | What it does |
|---|---|
| `engine/devig.py` | Real multiplicative / power / Shin devig (root-solved, not stubs) |
| `engine/regime.py` | Dispersion-based market-efficiency regime classifier |
| `engine/periphery.py` | Grey-market league scoring + seed universe |
| `engine/props_board.py` | Big-5 prop scan: devig → weighted fair value → regime gate → ranked board |
| `engine/portfolio.py` | Kelly sizing, Sharpe/Sortino/maxDD tearsheet, CLV stats (sign-verified) |
| `engine/demo.py` | End-to-end synthetic run proving all the math |
| `db/schema.sql` | Corrected Postgres DDL (composite-key closes, ID resolution, regime baselines) |

## Run it

```bash
pip install numpy scipy pandas
python -m engine.demo
```

No API keys needed — the demo verifies devig math, ranks the periphery
universe, simulates a 120-day book with a genuine 2.5% edge through the
tearsheet, and builds a sample props board showing the regime gate
passing/blocking correctly.

## Schema fixes vs. the prior artifact

1. `closing_lines` keyed `(market_id, book_id)` — one close per reference
   book, not one per market (the bug that silently destroyed CLV grading).
2. `id_resolution` table — the feed→canonical mapping layer that was
   missing entirely.
3. `devig_method` column now provably matches the math applied (the old
   stubs labeled everything "shin" while computing multiplicative).
4. `regime_baselines` and `leagues` tables for the two new engines.

## Gates (unchanged discipline)

- Tier 0 → 1: CLV > 0 over ≥500 paper bets, t-stat significant
- Tier 1 → 2: fill rate ≥ 80% at modeled price
- Tier 2 → 3: realized edge ≈ modeled edge, max DD ≤ 2.5× expected

Periphery-specific Layer 0 addition: measure each league's actual
soft-book copy lag vs Pinnacle from snapshots. If HNL/Primera A lag
priors (~15–20 min) hold up measured, the sleeve is real.

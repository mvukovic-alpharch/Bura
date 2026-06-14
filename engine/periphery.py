"""Periphery Engine — the grey-market alpha sleeve.

Thesis: every syndicate models the NBA. Almost nobody systematically
farms leagues where (a) Pinnacle still posts a real line, (b) soft-book
coverage is thin and lazily copied, and (c) team news breaks in
languages quant desks don't read. Same underserved-markets moat as
ArchAlpha — Balkans and LatAm first because that's where the operator
has native language + physical presence.

Each league gets a PeripheryScore in [0,1]:

  score = w1*thinness + w2*copy_lag + w3*news_moat + w4*liquidity_floor

  thinness        1 - n_books/n_books_max   (fewer books pricing it)
  copy_lag        observed median minutes for soft books to follow a
                  Pinnacle move (measured from odds_snapshots; seeded
                  with priors until measured)
  news_moat       0/0.5/1 — does the operator read the local press in
                  the native language / have local presence
  liquidity_floor penalty if limits are too small to matter (a perfect
                  edge you can bet $20 on is a hobby)

The big-5 leagues stay in the universe as the BENCHMARK surface —
they calibrate the devig + regime machinery where data is rich, and
the props board runs there. The periphery is where the machinery
goes to eat.
"""
from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["League", "periphery_score", "DEFAULT_UNIVERSE"]

WEIGHTS = {"thinness": 0.35, "copy_lag": 0.30, "news_moat": 0.20, "liquidity": 0.15}
N_BOOKS_MAX = 40  # roughly what an NBA side trades at across US books


@dataclass
class League:
    key: str
    name: str
    region: str
    n_books_prior: int          # how many books typically price it
    copy_lag_min_prior: float   # prior: median soft-book lag vs Pinnacle (minutes)
    news_moat: float            # 0 none, 0.5 partial, 1.0 native language + presence
    typical_limit_usd: float    # rough max useful stake at a soft book
    notes: str = ""
    measured: dict = field(default_factory=dict)  # filled from odds_snapshots later


def periphery_score(lg: League, copy_lag_cap_min: float = 30.0) -> float:
    thinness = max(0.0, 1.0 - lg.n_books_prior / N_BOOKS_MAX)
    copy_lag = min(lg.copy_lag_min_prior, copy_lag_cap_min) / copy_lag_cap_min
    liquidity = min(lg.typical_limit_usd, 1000.0) / 1000.0  # floor utility at $1k
    s = (
        WEIGHTS["thinness"] * thinness
        + WEIGHTS["copy_lag"] * copy_lag
        + WEIGHTS["news_moat"] * lg.news_moat
        + WEIGHTS["liquidity"] * liquidity
    )
    return round(s, 3)


# Seed universe. Priors are STARTING POINTS — Layer 0 replaces them with
# measured values from odds_snapshots (n_books observed, actual copy lag).
DEFAULT_UNIVERSE: list[League] = [
    # ---- Periphery sleeve ----
    League("hnl", "Croatian HNL", "Balkans", 8, 18.0, 1.0, 500,
           "Native language + presence. Lineup news via Sportske novosti / Index.hr "
           "breaks well before English-language consensus."),
    League("superliga_srb", "Serbian SuperLiga", "Balkans", 6, 22.0, 0.5, 400,
           "Mutually intelligible language; partial moat."),
    League("prva_liga_slo", "Slovenian PrvaLiga", "Balkans", 5, 25.0, 0.5, 300, ""),
    League("primera_col", "Colombian Primera A", "LatAm", 9, 15.0, 1.0, 600,
           "Spanish-native household + Cartagena presence; El Tiempo / Win Sports "
           "news cycle."),
    League("liga_mx", "Liga MX", "LatAm", 18, 8.0, 0.5, 1500,
           "More liquid; partial edge, good stepping stone."),
    League("primera_arg", "Argentine Primera", "LatAm", 14, 10.0, 0.5, 1000, ""),
    League("kbo", "KBO (Korea baseball)", "Asia", 10, 12.0, 0.0, 800,
           "No language moat but rich modelable structure; classic thin-consensus."),
    League("npb", "NPB (Japan baseball)", "Asia", 12, 10.0, 0.0, 1000, ""),
    # ---- Benchmark surface (big-5 props board lives here) ----
    League("nba", "NBA", "US", 40, 1.5, 0.0, 5000, "Benchmark + props board."),
    League("nfl", "NFL", "US", 40, 2.0, 0.0, 5000, "Benchmark + props board."),
    League("mlb", "MLB", "US", 35, 2.5, 0.0, 3000, "Benchmark + props board."),
    League("nhl", "NHL", "US", 30, 3.0, 0.0, 2000, "Benchmark + props board."),
    League("epl", "EPL", "EU", 38, 2.0, 0.0, 5000, "Benchmark + props board."),
]


def rank_universe(universe: list[League] | None = None) -> list[tuple[str, float, str]]:
    uni = universe or DEFAULT_UNIVERSE
    scored = [(lg.name, periphery_score(lg), lg.region) for lg in uni]
    return sorted(scored, key=lambda t: t[1], reverse=True)

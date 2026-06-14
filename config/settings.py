"""Bura central config. Everything tunable lives here or in .env."""
from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# --- secrets (from .env, never committed) ---
DB_URL = os.getenv("DB_URL", "postgresql://localhost/bura")
SGO_API_KEY = os.getenv("SGO_API_KEY", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- universe ---
# sleeve: 'periphery' = the alpha hunting ground, 'benchmark' = big-5 calibration + props board
LEAGUES = {
    # key: (display, region, sleeve, news_moat)
    "hnl":          ("Croatian HNL",        "Balkans", "periphery", 1.0),
    "superliga_srb":("Serbian SuperLiga",   "Balkans", "periphery", 0.5),
    "prva_liga_slo":("Slovenian PrvaLiga",  "Balkans", "periphery", 0.5),
    "primera_col":  ("Colombian Primera A", "LatAm",   "periphery", 1.0),
    "liga_mx":      ("Liga MX",             "LatAm",   "periphery", 0.5),
    "primera_arg":  ("Argentine Primera",   "LatAm",   "periphery", 0.5),
    "kbo":          ("KBO",                 "Asia",    "periphery", 0.0),
    "npb":          ("NPB",                 "Asia",    "periphery", 0.0),
    "nba":          ("NBA",                 "US",      "benchmark", 0.0),
    "nfl":          ("NFL",                 "US",      "benchmark", 0.0),
    "mlb":          ("MLB",                 "US",      "benchmark", 0.0),
    "nhl":          ("NHL",                 "US",      "benchmark", 0.0),
    "epl":          ("EPL",                 "EU",      "benchmark", 0.0),
}

# devig method per market family — the choice that matters (see devig.py)
DEVIG_METHOD = {
    "side":  "shin",     # moneyline / spreads
    "total": "shin",     # over/under
    "draw":  "shin",
    "prop":  "power",    # props skew; power handles longshot bias
}

# regime thresholds (z-score of cross-book dispersion vs trailing baseline)
Z_NOISY = 1.0
Z_DISLOCATED = 2.0
MIN_BOOKS = 3

# gate stack
MIN_EDGE_PROP = 0.025
MIN_EDGE_SIDE = 0.015
KELLY_LAMBDA = 0.25
MAX_STAKE_FRAC = 0.01      # 1% bankroll hard cap per bet

# polling budget guard — free tier safety
DAILY_API_CALL_BUDGET = int(os.getenv("DAILY_API_CALL_BUDGET", "900"))
POLL_INTERVAL_BENCHMARK_MIN = 5
POLL_INTERVAL_PERIPHERY_MIN = 12

PAPER_MODE = True          # Tier 0: never places real money. Flip only after CLV gate.
MODEL_VER = "bura-0.1.0"

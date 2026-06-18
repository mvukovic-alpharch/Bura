"""Per-sport, per-stat config: which distribution fits which stat, and the
default shape parameters. This is the domain knowledge layer — picking the
right distribution family is most of the battle in honest prop projection.
"""
from __future__ import annotations

# family: poisson (low-mean counts) | negbinom (overdispersed counts) | normal (continuous)
# For normal, sd_frac = sd as a fraction of mean. For negbinom, dispersion k.

STAT_CONFIG = {
    "NFL": {
        "pass_yds":   {"family": "normal",   "sd_frac": 0.28},
        "pass_tds":   {"family": "poisson"},
        "rush_yds":   {"family": "negbinom", "dispersion": 0.45},  # boom/bust
        "rush_att":   {"family": "negbinom", "dispersion": 0.20},
        "receptions": {"family": "negbinom", "dispersion": 0.30},
        "rec_yds":    {"family": "negbinom", "dispersion": 0.50},
        "anytime_td": {"family": "poisson"},
    },
    "NBA": {
        "points":     {"family": "normal",   "sd_frac": 0.30},
        "rebounds":   {"family": "negbinom", "dispersion": 0.20},
        "assists":    {"family": "negbinom", "dispersion": 0.25},
        "threes":     {"family": "poisson"},
        "pra":        {"family": "normal",   "sd_frac": 0.25},   # pts+reb+ast
        "steals":     {"family": "poisson"},
        "blocks":     {"family": "poisson"},
    },
    "EPL": {
        "shots":          {"family": "negbinom", "dispersion": 0.30},
        "shots_on_target":{"family": "poisson"},
        "goals":          {"family": "poisson"},
        "assists":        {"family": "poisson"},
        "passes":         {"family": "normal",   "sd_frac": 0.20},
        "tackles":        {"family": "negbinom", "dispersion": 0.25},
    },
    "La Liga": {
        "shots":          {"family": "negbinom", "dispersion": 0.30},
        "shots_on_target":{"family": "poisson"},
        "goals":          {"family": "poisson"},
        "assists":        {"family": "poisson"},
        "passes":         {"family": "normal",   "sd_frac": 0.20},
    },
    "Serie A": {
        "shots":          {"family": "negbinom", "dispersion": 0.30},
        "shots_on_target":{"family": "poisson"},
        "goals":          {"family": "poisson"},
        "assists":        {"family": "poisson"},
        "passes":         {"family": "normal",   "sd_frac": 0.20},
    },
}


def config_for(sport: str, stat: str) -> dict:
    try:
        return STAT_CONFIG[sport][stat]
    except KeyError:
        raise ValueError(f"no config for {sport}/{stat}; "
                         f"known {sport} stats: {list(STAT_CONFIG.get(sport, {}))}")

"""Config-driven DraftKings soccer score reconstruction.

``actual_dk_points`` is deliberately null when any event that the canonical
dataset claims to reconstruct is null.  Unsupported event types are reported
separately and make ``scoring_complete`` false; they are never imputed as zero.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping


DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "draftkings_soccer.json"


@dataclass(frozen=True)
class DKScoringResult:
    actual_dk_points: float | None
    scoring_completeness: str
    scoring_complete: bool
    missing_components: tuple[str, ...]
    unreconstructable_components: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "actual_dk_points": self.actual_dk_points,
            "scoring_completeness": self.scoring_completeness,
            "scoring_complete": self.scoring_complete,
            "missing_components": list(self.missing_components),
            "unreconstructable_components": list(self.unreconstructable_components),
        }


def load_scoring_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    """Load and minimally validate an easily replaceable scoring ruleset."""
    with Path(path).open(encoding="utf-8") as handle:
        config = json.load(handle)
    required = {"weights", "reconstructable_core", "unreconstructable"}
    missing = required.difference(config)
    if missing:
        raise ValueError(f"scoring config missing keys: {sorted(missing)}")
    unknown = set(config["reconstructable_core"]) - set(config["weights"])
    if unknown:
        raise ValueError(f"core components have no weights: {sorted(unknown)}")
    return config


def score_player_match(
    row: Mapping[str, Any], config: Mapping[str, Any] | None = None
) -> DKScoringResult:
    """Reconstruct a score without interpreting null event counts as zero.

    The returned score is usable for the current core-stat benchmark when all
    core inputs are observed.  ``scoring_complete`` has the stricter meaning:
    every component in the DraftKings ruleset was reconstructable.
    """
    rules = dict(config or load_scoring_config())
    weights = rules["weights"]
    position = row.get("position")
    core = tuple(name for name in rules["reconstructable_core"] if not (name == "interceptions" and position == "G"))
    if position == "G":
        core += ("saves", "goals_conceded", "penalties_saved")
    unsupported = tuple(rules["unreconstructable"])
    participation_field = rules.get("participation_field", "minutes")
    participated = row.get(participation_field) is not None
    null_is_zero = set(rules.get("null_means_zero_when_participated", ()))
    normalized = {
        component: (0 if participated and component in null_is_zero and row.get(component) is None else row.get(component))
        for component in core
    }
    missing = tuple(component for component in core if normalized[component] is None)
    if not participated:
        missing = (participation_field,) + missing

    if missing:
        points = None
        completeness = "unusable"
    else:
        points = sum(float(normalized[name]) * float(weights[name]) for name in core)
        if position == "D" and row.get("clean_sheet") is True:
            points += float(weights["defender_clean_sheet"])
        if position == "G":
            if row.get("clean_sheet") is True:
                points += float(weights["goalkeeper_clean_sheet"])
            if row.get("goalkeeper_win") is True:
                points += float(weights["goalkeeper_win"])
        points = round(points, 4)
        completeness = "partial" if unsupported else "complete"

    return DKScoringResult(
        actual_dk_points=points,
        scoring_completeness=completeness,
        scoring_complete=points is not None and not unsupported,
        missing_components=missing,
        unreconstructable_components=unsupported,
    )


def add_dk_score(row: Mapping[str, Any], config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return a canonical player-match mapping augmented with scoring fields."""
    return {**row, **score_player_match(row, config).as_dict()}

"""Canonical race-card data structures. Everything downstream consumes these,
not raw feed JSON — so a new data source only needs a parser that emits these.

Same discipline as Bura's normalized Quote: one internal shape, many possible
sources.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt


@dataclass
class PastPerformance:
    """One prior race line for a horse — the raw material for features."""
    date: dt.date
    speed_fig: float            # Beyer-style figure
    class_level: float          # purse/class proxy
    finish_pos: int
    field_size: int
    early_pace: float           # normalized E1/E2 pace number
    late_pace: float            # normalized late/closing number
    surface: str                # dirt | turf | synthetic
    distance_furlongs: float


@dataclass
class Horse:
    horse_id: str
    name: str
    past: list[PastPerformance] = field(default_factory=list)


@dataclass
class Entry:
    """A horse entered in a specific race — the join of horse + race context."""
    program_number: int
    horse: Horse
    jockey: str
    trainer: str
    jockey_sr: float            # strike rate (win %), trailing
    trainer_sr: float
    post_position: int
    weight: float               # pounds carried
    morning_line: float | None = None   # decimal payout incl stake
    # filled by the model pipeline:
    run_style: str | None = None
    pace_fit: float | None = None
    model_win_prob: float | None = None


@dataclass
class Race:
    race_id: str
    track: str
    race_number: int
    date: dt.date
    surface: str
    distance_furlongs: float
    class_level: float          # race's own class/purse
    takeout_win: float = 0.17
    takeout_exotic: float = 0.21
    entries: list[Entry] = field(default_factory=list)

    @property
    def is_route(self) -> bool:
        return self.distance_furlongs >= 8.0   # 1 mile+

    @property
    def field_size(self) -> int:
        return len(self.entries)


@dataclass
class Card:
    track: str
    date: dt.date
    races: list[Race] = field(default_factory=list)

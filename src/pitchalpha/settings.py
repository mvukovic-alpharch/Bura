from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    base_url: str
    raw_dir: Path
    database_path: Path
    league_id: int = 39

    @classmethod
    def load(cls, require_api_key: bool = False) -> "Settings":
        load_dotenv(PROJECT_ROOT / ".env")
        key = os.getenv("API_FOOTBALL_KEY")
        if require_api_key and not key:
            raise RuntimeError("API_FOOTBALL_KEY is not set; copy .env.example to .env")
        return cls(
            api_key=key,
            base_url=os.getenv("API_FOOTBALL_BASE_URL", "https://v3.football.api-sports.io").rstrip("/"),
            raw_dir=PROJECT_ROOT / "data" / "raw",
            database_path=PROJECT_ROOT / os.getenv("PITCHALPHA_DATABASE", "data/processed/pitchalpha.duckdb"),
        )


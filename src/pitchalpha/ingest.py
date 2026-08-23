from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from pitchalpha.api import ApiFootballClient


class EPLIngestor:
    def __init__(self, client: ApiFootballClient, league_id: int = 39):
        self.client, self.league_id = client, league_id

    def seasons(self):
        return self.client.get("/leagues", id=self.league_id)

    def fixtures(self, season: int):
        return self.client.get("/fixtures", league=self.league_id, season=season)

    def teams(self, season: int):
        return self.client.get("/teams", league=self.league_id, season=season)

    def players(self, season: int):
        return list(self.client.get_all_pages("/players", league=self.league_id, season=season))

    def injuries(self, season: int):
        return self.client.get("/injuries", league=self.league_id, season=season)

    def odds(self, season: int):
        return list(self.client.get_all_pages("/odds", league=self.league_id, season=season))

    def player_match_statistics(self, fixture_id: int):
        return self.client.get("/fixtures/players", fixture=fixture_id)

    def team_match_statistics(self, fixture_id: int):
        return self.client.get("/fixtures/statistics", fixture=fixture_id)

    def lineups(self, fixture_id: int):
        return self.client.get("/fixtures/lineups", fixture=fixture_id)

    def collect_live(self, season: int, date: str) -> dict[str, int]:
        """Timestamp current fixture, provider lineup, and injury state for a date."""
        fixtures_payload, _ = self.client.get("/fixtures", league=self.league_id, season=season, date=date)
        fixtures = fixtures_payload.get("response") or []
        injuries_payload, _ = self.client.get("/injuries", league=self.league_id, season=season, date=date)
        lineup_rows = 0
        for fixture in fixtures:
            payload, _ = self.lineups(fixture["fixture"]["id"])
            lineup_rows += len(payload.get("response") or [])
        return {"fixtures": len(fixtures), "lineup_team_blocks": lineup_rows,
                "injuries": len(injuries_payload.get("response") or [])}

    def ingest_season(self, season: int, include_odds: bool = True) -> dict[str, int]:
        counts: dict[str, int] = {}
        league_payload, _ = self.seasons()
        counts["seasons"] = len(league_payload.get("response") or [])
        fixtures_payload, _ = self.fixtures(season)
        fixtures = fixtures_payload.get("response") or []
        counts["fixtures"] = len(fixtures)
        teams_payload, _ = self.teams(season)
        counts["teams"] = len(teams_payload.get("response") or [])
        counts["player_pages"] = len(self.players(season))
        injuries_payload, _ = self.injuries(season)
        counts["injuries"] = len(injuries_payload.get("response") or [])
        completed = [f for f in fixtures if (f.get("fixture", {}).get("status", {}).get("short")) in {"1H","HT","2H","ET","P","FT","AET","PEN"}]
        detail_calls = 0
        skipped_calls = 0
        for fixture in completed:
            fixture_id = fixture["fixture"]["id"]
            for endpoint, fetch in (
                ("/fixtures/players", self.player_match_statistics),
                ("/fixtures/statistics", self.team_match_statistics),
                ("/fixtures/lineups", self.lineups),
            ):
                if self.client.raw_store.has_success(endpoint, {"fixture": fixture_id}):
                    skipped_calls += 1
                else:
                    fetch(fixture_id)
                    detail_calls += 1
        counts["fixture_detail_calls"] = detail_calls
        counts["fixture_detail_calls_skipped"] = skipped_calls
        if include_odds:
            counts["odds_pages"] = len(self.odds(season))
        return counts

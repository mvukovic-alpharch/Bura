from __future__ import annotations

from difflib import SequenceMatcher

from pitchalpha.dk_ingest import _candidates, _initial_surname, normalize_name


def unresolved_player_candidates(con, slate_id: str, limit: int = 3) -> list[dict]:
    candidates = _candidates(con)
    rows = con.execute(
        """SELECT dk_player_id, dk_name, team, salary FROM dfs_players
        WHERE slate_id=? AND api_football_player_id IS NULL
        ORDER BY salary DESC, dk_name""",
        [slate_id],
    ).fetchall()
    output = []
    for dk_id, name, team, _salary in rows:
        positions = [
            row[0]
            for row in con.execute(
                """SELECT position FROM dfs_player_eligibility
                WHERE slate_id=? AND dk_player_id=? ORDER BY position""",
                [slate_id, dk_id],
            ).fetchall()
        ]
        best_by_id = {}
        for candidate in candidates:
            same_team = team == str(candidate.get("team") or "").upper()
            score = SequenceMatcher(
                None, normalize_name(name), normalize_name(candidate["player_name"])
            ).ratio() + (0.04 if same_team else 0)
            abbreviation = (
                _initial_surname(name) is not None
                and _initial_surname(name) == _initial_surname(candidate["player_name"])
            )
            score = max(score, 0.98 if abbreviation and same_team else 0.94 if abbreviation else 0)
            player_id = int(candidate["player_id"])
            item = {
                "api_football_player_id": player_id,
                "candidate_name": candidate["player_name"],
                "candidate_team": candidate.get("team"),
                "confidence": round(min(score, 1.0), 3),
            }
            if player_id not in best_by_id or item["confidence"] > best_by_id[player_id]["confidence"]:
                best_by_id[player_id] = item
        output.append(
            {
                "dk_name": name,
                "dk_id": dk_id,
                "team": team,
                "position": positions,
                "candidate_matches": sorted(
                    best_by_id.values(),
                    key=lambda item: (-item["confidence"], item["api_football_player_id"]),
                )[:limit],
            }
        )
    return output

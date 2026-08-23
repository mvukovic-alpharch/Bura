from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pitchalpha.build import build_all
from pitchalpha.schema import connect


def parse_as_of(value: str) -> datetime:
    """Parse an ISO-8601 information cutoff and normalize it to UTC."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid --as-of timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError("--as-of must include a timezone (for example, Z or +00:00)")
    return parsed.astimezone(timezone.utc)


def default_snapshot_path(project_root: Path, as_of: datetime) -> Path:
    stamp = as_of.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return project_root / "data" / "snapshots" / f"pitchalpha_asof_{stamp}.duckdb"


def create_snapshot(raw_dir: Path, output_path: Path, as_of: datetime) -> dict:
    """Build a frozen database using only observations known by ``as_of``.

    The raw archive is read-only. Eligible envelopes are copied into a temporary
    directory and the normal canonical builders run against that filtered view.
    """
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    cutoff = as_of.astimezone(timezone.utc)
    output_path = Path(output_path)
    if output_path.exists():
        raise FileExistsError(f"snapshot already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    included = excluded = 0
    with tempfile.TemporaryDirectory(prefix="pitchalpha-snapshot-") as temp_name:
        filtered_raw = Path(temp_name) / "raw"
        for source in sorted(Path(raw_dir).rglob("*.json")):
            doc = json.loads(source.read_text(encoding="utf-8"))
            requested_at = (doc.get("provenance") or {}).get("requested_at")
            if not requested_at:
                raise ValueError(f"raw envelope lacks provenance.requested_at: {source}")
            observed_at = parse_as_of(str(requested_at))
            if observed_at > cutoff:
                excluded += 1
                continue
            destination = filtered_raw / source.relative_to(raw_dir)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            included += 1

        try:
            with connect(output_path) as con:
                tables = build_all(con, filtered_raw)
                con.execute(
                    """CREATE TABLE snapshot_metadata AS
                       SELECT ?::TIMESTAMPTZ AS as_of, ?::BIGINT AS included_raw_files,
                              ?::BIGINT AS excluded_raw_files, current_timestamp AS built_at""",
                    [cutoff, included, excluded],
                )
        except Exception:
            output_path.unlink(missing_ok=True)
            raise

    return {
        "as_of": cutoff.isoformat(),
        "path": str(output_path),
        "included_raw_files": included,
        "excluded_raw_files": excluded,
        "tables": tables,
    }

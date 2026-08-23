from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RawStore:
    """Append-only JSON response archive; existing files are never overwritten."""

    def __init__(self, root: Path):
        self.root = root

    def save(
        self, endpoint: str, params: dict[str, Any], payload: dict[str, Any], requested_at: datetime
    ) -> Path:
        stamp = requested_at.astimezone(timezone.utc)
        safe_endpoint = re.sub(r"[^a-zA-Z0-9_-]+", "_", endpoint.strip("/"))
        fingerprint = hashlib.sha256(
            json.dumps(params, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:12]
        folder = self.root / safe_endpoint / stamp.strftime("%Y/%m/%d")
        folder.mkdir(parents=True, exist_ok=True)
        base = f"{stamp.strftime('%Y%m%dT%H%M%S.%fZ')}_{fingerprint}"
        path = folder / f"{base}.json"
        counter = 1
        while path.exists():
            path = folder / f"{base}_{counter}.json"
            counter += 1
        envelope = {
            "provenance": {
                "endpoint": endpoint,
                "params": params,
                "requested_at": stamp.isoformat(),
            },
            "payload": payload,
        }
        path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def has_success(self, endpoint: str, params: dict[str, Any]) -> bool:
        safe_endpoint = re.sub(r"[^a-zA-Z0-9_-]+", "_", endpoint.strip("/"))
        folder = self.root / safe_endpoint
        if not folder.exists():
            return False
        for path in folder.rglob("*.json"):
            doc = json.loads(path.read_text(encoding="utf-8"))
            provenance = doc.get("provenance") or {}
            payload = doc.get("payload") or {}
            if provenance.get("params") == params and not payload.get("errors"):
                return True
        return False


def iter_raw(root: Path, endpoint: str | None = None):
    paths = (root / endpoint).rglob("*.json") if endpoint else root.rglob("*.json")
    for path in sorted(paths):
        doc = json.loads(path.read_text(encoding="utf-8"))
        yield path, doc

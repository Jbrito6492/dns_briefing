from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_fingerprint_snapshot(data_dir: str) -> dict[str, Any] | None:
    """
    Read fingerprint snapshot written by dump-fingerprints.sh before this run.
    Returns None if unavailable or empty — callers must handle gracefully.
    """
    path = Path(data_dir) / "fingerprint_snapshot.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            data: dict[str, Any] = json.load(f)
        if not data.get("available") or not data.get("devices"):
            return None
        return data
    except Exception:
        return None

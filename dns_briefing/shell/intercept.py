from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_intercept_stats(data_dir: str) -> dict[str, Any] | None:
    """
    Read DNS intercept stats written by dump-intercept-stats.sh before this run.
    Returns None if unavailable — callers must handle gracefully.
    """
    path = Path(data_dir) / "intercept_stats.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            data: dict[str, Any] = json.load(f)
        if not data.get("available"):
            return None
        if data.get("intercepted_queries", 0) == 0:
            return None
        return data
    except Exception:
        return None

from __future__ import annotations

from pathlib import Path
from typing import Any

from dns_briefing.shell._io import read_json_file


def read_intercept_stats(data_dir: str) -> dict[str, Any] | None:
    data = read_json_file(Path(data_dir) / "intercept_stats.json")
    if data is None or not data.get("available") or data.get("intercepted_queries", 0) == 0:
        return None
    return data

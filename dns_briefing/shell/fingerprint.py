from __future__ import annotations

from pathlib import Path
from typing import Any

from dns_briefing.shell._io import read_json_file


def read_fingerprint_snapshot(data_dir: str) -> dict[str, Any] | None:
    data = read_json_file(Path(data_dir) / "fingerprint_snapshot.json")
    if data is None or not data.get("available") or not data.get("devices"):
        return None
    return data

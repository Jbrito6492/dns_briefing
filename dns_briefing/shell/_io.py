from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data: dict[str, Any] = json.loads(path.read_text())
        return data
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to read %s", path, exc_info=True)
        return None

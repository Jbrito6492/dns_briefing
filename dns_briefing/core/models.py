from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class QueryEntry:
    time: datetime
    client: str
    domain: str
    query_type: str
    reason: str
    blocked: bool
    block_rule: str

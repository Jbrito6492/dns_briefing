from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import requests

# All AGH reason codes that mean "this query was blocked by a filter".
# Adding a new AGH filter type = add it here, no other changes needed.
_BLOCKED_REASONS: frozenset[str] = frozenset(
    {
        "FilteredBlackList",
        "FilteredSafeSearch",
        "FilteredParental",
        "FilteredCustom",
    }
)


@dataclass
class QueryEntry:
    time: datetime
    client: str
    domain: str
    query_type: str
    reason: str
    blocked: bool
    block_rule: str


def _parse_entry(raw: dict[str, Any]) -> QueryEntry:
    return QueryEntry(
        time=datetime.fromisoformat(raw["time"].replace("Z", "+00:00")),
        client=raw.get("client", ""),
        domain=raw["question"]["name"],
        query_type=raw["question"]["type"],
        reason=raw.get("reason", ""),
        blocked=raw.get("reason", "") in _BLOCKED_REASONS,
        block_rule=raw.get("rule", ""),
    )


class AdGuardClient:
    def __init__(self, base_url: str, username: str, password: str):
        self._base_url = base_url.rstrip("/")
        self._auth = (username, password)

    def _fetch_page(self, older_than: str) -> tuple[list[dict[str, Any]], str]:
        params: dict[str, str | int] = {"limit": 1000}
        if older_than:
            params["older_than"] = older_than
        resp = requests.get(
            f"{self._base_url}/control/querylog",
            params=params,
            auth=self._auth,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", []), data.get("oldest", "")

    def fetch_window(self, hours: int, now: datetime | None = None) -> list[QueryEntry]:
        if now is None:
            now = datetime.now(tz=UTC)
        cutoff = now - timedelta(hours=hours)

        entries: list[QueryEntry] = []
        older_than = ""

        while True:
            page, oldest_str = self._fetch_page(older_than)

            if not page:
                break

            for raw in page:
                entry = _parse_entry(raw)
                if entry.time < cutoff:
                    return entries
                entries.append(entry)

            if not oldest_str:
                break

            oldest_dt = datetime.fromisoformat(oldest_str.replace("Z", "+00:00"))
            if oldest_dt < cutoff:
                break

            older_than = oldest_str

        return entries

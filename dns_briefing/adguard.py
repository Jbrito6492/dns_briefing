from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import requests


@dataclass
class QueryEntry:
    time: datetime
    client: str
    domain: str
    query_type: str
    reason: str
    blocked: bool
    block_rule: str


class AdGuardClient:
    def __init__(self, base_url: str, username: str, password: str):
        self._base_url = base_url.rstrip("/")
        self._auth = (username, password)

    def fetch_last_24h(self, now: datetime | None = None) -> list[QueryEntry]:
        if now is None:
            now = datetime.now(tz=timezone.utc)
        cutoff = now - timedelta(hours=24)

        entries: list[QueryEntry] = []
        older_than = ""

        while True:
            params = {"limit": 1000}
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

            page = data.get("data", [])
            oldest_str = data.get("oldest", "")

            if not page:
                break

            for raw in page:
                t = datetime.fromisoformat(raw["time"].replace("Z", "+00:00"))
                if t < cutoff:
                    return entries
                entries.append(QueryEntry(
                    time=t,
                    client=raw.get("client", ""),
                    domain=raw["question"]["name"],
                    query_type=raw["question"]["type"],
                    reason=raw.get("reason", ""),
                    blocked=raw.get("reason", "") == "FilteredBlackList",
                    block_rule=raw.get("rule", ""),
                ))

            if not oldest_str:
                break

            oldest_dt = datetime.fromisoformat(oldest_str.replace("Z", "+00:00"))
            if oldest_dt < cutoff:
                break

            older_than = oldest_str

        return entries

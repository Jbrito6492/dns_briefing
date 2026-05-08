from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "querylog_24h.json"

# Window: 2026-05-08 07:00 UTC → 2026-05-09 07:00 UTC (midnight→midnight Phoenix/MST-7)
WINDOW_START = datetime(2026, 5, 8, 7, 0, 0, tzinfo=UTC)
WINDOW_END = datetime(2026, 5, 9, 7, 0, 0, tzinfo=UTC)  # exclusive upper bound

# Off-hours in UTC: 01:00–05:00 Phoenix = 08:00–12:00 UTC on 2026-05-08
OFF_HOURS_START_UTC = datetime(2026, 5, 8, 8, 0, 0, tzinfo=UTC)
OFF_HOURS_END_UTC = datetime(2026, 5, 8, 12, 0, 0, tzinfo=UTC)


def make_entry(
    time_utc: datetime,
    client: str,
    domain: str,
    reason: str = "NotFilteredNotFound",
    rule: str = "",
    filter_list_id: int | None = None,
) -> dict:
    return {
        "answer": [{"type": "A", "value": "1.2.3.4", "ttl": 300}],
        "answer_dnssec": False,
        "cached": False,
        "client": client,
        "client_info": {
            "whois": {},
            "name": "",
            "disallowed": False,
            "disallowed_rule": client,
        },
        "client_proto": "",
        "elapsedMs": "5.0",
        "question": {"class": "IN", "name": domain, "type": "A"},
        "reason": reason,
        "rules": [{"filter_list_id": filter_list_id, "text": rule}] if rule else [],
        "rule": rule,
        "status": "NOERROR",
        "time": time_utc.strftime("%Y-%m-%dT%H:%M:%S.000000000Z"),
        "upstream": "tls://9.9.9.9:853",
    }


def build_fixture_entries() -> list[dict]:
    entries = []

    # ── Normal daytime traffic ────────────────────────────────────────────
    normal: list[tuple[str, list[str]]] = [
        ("192.168.1.25", ["apple.com", "icloud.com", "weather-data.apple.com"]),
        ("192.168.1.30", ["github.com", "pypi.org", "docs.python.org"]),
        ("192.168.1.40", ["youtube.com", "google.com", "fonts.googleapis.com"]),
        ("192.168.1.10", ["firetvcaptiveportal.com", "mas-ext.amazon.com"]),
        ("192.168.1.15", ["clients3.google.com", "time.google.com"]),
    ]
    daytime_start = datetime(2026, 5, 8, 19, 0, 0, tzinfo=UTC)  # noon Phoenix
    for i in range(400):
        t = daytime_start + timedelta(seconds=i * 57)
        client, domains = normal[i % len(normal)]
        domain = domains[i % len(domains)]
        entries.append(make_entry(t, client, domain))

    # ── Off-hours normal (expected: phones ping home services) ────────────
    for i in range(15):
        t = OFF_HOURS_START_UTC + timedelta(minutes=i * 14)
        entries.append(make_entry(t, "192.168.1.25", "apple.com"))
        entries.append(make_entry(t, "192.168.1.25", "icloud.com"))

    # ── ANOMALY 1: Suspicious off-hours domain at 03:00 Phoenix (10:00 UTC)
    suspicious_time = datetime(2026, 5, 8, 10, 0, 0, tzinfo=UTC)
    entries.append(
        make_entry(suspicious_time, "192.168.1.10", "telemetry-sink.sketchy-analytics.io")
    )
    entries.append(
        make_entry(
            suspicious_time + timedelta(seconds=5), "192.168.1.10", "cdn.sketchy-analytics.io"
        )
    )

    # ── ANOMALY 2: 192.168.1.10 volume spike (10x normal) ─────────────────
    spike_start = datetime(2026, 5, 9, 1, 0, 0, tzinfo=UTC)  # 6pm Phoenix
    for i in range(200):
        t = spike_start + timedelta(seconds=i * 18)
        entries.append(make_entry(t, "192.168.1.10", "firetvcaptiveportal.com"))

    # ── ANOMALY 3: Brand-new domain never seen before ─────────────────────
    entries.append(
        make_entry(
            datetime(2026, 5, 8, 21, 0, 0, tzinfo=UTC),
            "192.168.1.30",
            "app.new-saas-tool-never-seen.io",
        )
    )
    entries.append(
        make_entry(
            datetime(2026, 5, 8, 21, 5, 0, tzinfo=UTC),
            "192.168.1.30",
            "api.new-saas-tool-never-seen.io",
        )
    )

    # ── Blocked domains ───────────────────────────────────────────────────
    blocked = [
        ("teams.events.data.microsoft.com", "||teams.events.data.microsoft.com^", 1),
        ("firebaselogging-pa.googleapis.com", "||firebaselogging-pa.googleapis.com^", 1),
        ("telemetry.example-vendor.com", "||telemetry.example-vendor.com^", 2),
    ]
    for i, (domain, rule, fid) in enumerate(blocked):
        for j in range(20):
            t = WINDOW_START + timedelta(hours=i * 6, minutes=j * 15)
            entries.append(make_entry(t, "192.168.1.40", domain, "FilteredBlackList", rule, fid))

    # Newest-first (AGH querylog order)
    entries.sort(key=lambda e: e["time"], reverse=True)

    # Guard: no entry should fall outside the declared window
    for e in entries:
        t = datetime.fromisoformat(e["time"].replace("Z", "+00:00"))
        assert WINDOW_START <= t <= WINDOW_END, (
            f"Fixture entry {e['question']['name']} at {t} outside window"
        )

    return entries


@pytest.fixture
def sample_entries() -> list[dict]:
    return build_fixture_entries()


@pytest.fixture
def fixture_path(tmp_path) -> Path:
    entries = build_fixture_entries()
    p = tmp_path / "querylog_24h.json"
    p.write_text(json.dumps({"data": entries}, indent=2))
    return p

from __future__ import annotations

import json
from datetime import date as Date
from datetime import datetime

import pytest

from dns_briefing.adguard import QueryEntry
from tests.conftest import build_fixture_entries

DEVICE_MAP = {
    "192.168.1.10": "Smart-TV",
    "192.168.1.25": "Phone",
    "192.168.1.30": "Laptop",
    "192.168.1.40": "Desktop",
    "192.168.1.15": "Google-Device",
}

BASELINE = {
    "192.168.1.10": {"mean": 15.0, "stddev": 2.1, "days": 14},
    "192.168.1.25": {"mean": 80.0, "stddev": 5.0, "days": 14},
    "192.168.1.30": {"mean": 60.0, "stddev": 4.0, "days": 14},
    "192.168.1.40": {"mean": 200.0, "stddev": 10.0, "days": 14},
}

NEW_DOMAIN_SET = {
    "app.new-saas-tool-never-seen.io",
    "api.new-saas-tool-never-seen.io",
    "telemetry-sink.sketchy-analytics.io",
    "cdn.sketchy-analytics.io",
}


def parse_entries(raw_list: list[dict]) -> list[QueryEntry]:
    result = []
    for r in raw_list:
        t = datetime.fromisoformat(r["time"].replace("Z", "+00:00"))
        result.append(
            QueryEntry(
                time=t,
                client=r["client"],
                domain=r["question"]["name"],
                query_type=r["question"]["type"],
                reason=r["reason"],
                blocked=r["reason"] == "FilteredBlackList",
                block_rule=r.get("rule", ""),
            )
        )
    return result


@pytest.fixture
def entries() -> list[QueryEntry]:
    return parse_entries(build_fixture_entries())


@pytest.fixture
def packet(entries: list[QueryEntry]) -> dict:
    from dns_briefing.aggregator import build_evidence_packet

    return build_evidence_packet(
        entries=entries,
        known_domains=NEW_DOMAIN_SET,
        volume_baseline=BASELINE,
        today=Date(2026, 5, 8),
        config_timezone="America/Phoenix",
        off_hours_start="01:00",
        off_hours_end="05:00",
        device_map=DEVICE_MAP,
    )


def test_top_domains_present(packet: dict) -> None:
    domains = [d["domain"] for d in packet["top_domains"]]
    assert "firetvcaptiveportal.com" in domains


def test_off_hours_contains_sketchy_domain(packet: dict) -> None:
    off = packet["off_hours_activity"]
    domains = [e["domain"] for e in off["entries"]]
    assert "telemetry-sink.sketchy-analytics.io" in domains


def test_off_hours_window_metadata(packet: dict) -> None:
    off = packet["off_hours_activity"]
    assert off["window_start"] == "01:00"
    assert off["window_end"] == "05:00"
    assert off["timezone"] == "America/Phoenix"


def test_new_domains_detected(packet: dict) -> None:
    new = [d["domain"] for d in packet["new_domains"]]
    assert any("new-saas-tool-never-seen" in d for d in new)
    assert any("sketchy-analytics" in d for d in new)


def test_volume_anomaly_spike_detected(packet: dict) -> None:
    anomalies = packet["volume_anomalies"]
    devices = [a["device"] for a in anomalies]
    assert "Smart-TV" in devices
    spike = next(a for a in anomalies if a["device"] == "Smart-TV")
    assert spike["today_count"] > spike["baseline_mean"] * 3


def test_blocked_domains_surfaced(packet: dict) -> None:
    blocked = packet["blocked_domains"]
    domains = [b["domain"] for b in blocked]
    assert "teams.events.data.microsoft.com" in domains


def test_per_client_breakdown(packet: dict) -> None:
    clients = packet["per_client"]
    assert any(c["device"] == "Smart-TV" for c in clients)


def test_evidence_packet_json_serializable(packet: dict) -> None:
    json.dumps(packet)  # must not raise


def test_summary_counts(packet: dict) -> None:
    s = packet["summary"]
    assert s["total_queries"] > 0
    assert s["total_blocked"] > 0
    assert s["unique_clients"] > 0
    assert s["unique_domains"] > 0

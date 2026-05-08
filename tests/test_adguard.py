import json
from datetime import datetime, timezone, timedelta
import responses as resp_lib
import pytest
from dns_briefing.adguard import AdGuardClient, QueryEntry


BASE_URL = "http://localhost:3080"
USER = "admin"
PASS = "secret"


def make_agh_response(entries: list, oldest: str | None = None) -> dict:
    return {
        "data": entries,
        "oldest": oldest or (entries[-1]["time"] if entries else ""),
    }


def make_raw_entry(time_iso: str, client: str, domain: str, reason: str = "NotFilteredNotFound") -> dict:
    return {
        "answer": [{"type": "A", "value": "1.2.3.4", "ttl": 300}],
        "answer_dnssec": False,
        "cached": False,
        "client": client,
        "client_info": {"whois": {}, "name": "", "disallowed": False},
        "client_proto": "",
        "elapsedMs": "5.0",
        "question": {"class": "IN", "name": domain, "type": "A"},
        "reason": reason,
        "rules": [],
        "rule": "",
        "status": "NOERROR",
        "time": time_iso,
        "upstream": "tls://9.9.9.9:853",
    }


@resp_lib.activate
def test_fetch_returns_entries_within_window():
    now = datetime(2026, 5, 8, 15, 0, 0, tzinfo=timezone.utc)
    in_window = now - timedelta(hours=12)
    out_of_window = now - timedelta(hours=25)

    entry_in = make_raw_entry(in_window.strftime("%Y-%m-%dT%H:%M:%SZ"), "192.168.1.10", "example.com")
    entry_out = make_raw_entry(out_of_window.strftime("%Y-%m-%dT%H:%M:%SZ"), "192.168.1.10", "old.com")

    resp_lib.add(
        resp_lib.GET,
        f"{BASE_URL}/control/querylog",
        json=make_agh_response([entry_in], oldest=in_window.strftime("%Y-%m-%dT%H:%M:%SZ")),
    )
    resp_lib.add(
        resp_lib.GET,
        f"{BASE_URL}/control/querylog",
        json=make_agh_response([entry_out], oldest=out_of_window.strftime("%Y-%m-%dT%H:%M:%SZ")),
    )

    client = AdGuardClient(BASE_URL, USER, PASS)
    entries = client.fetch_last_24h(now=now)

    assert len(entries) == 1
    assert entries[0].domain == "example.com"


@resp_lib.activate
def test_fetch_paginates_until_cutoff():
    now = datetime(2026, 5, 8, 15, 0, 0, tzinfo=timezone.utc)
    page1_entries = [
        make_raw_entry((now - timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"), "192.168.1.10", f"domain{i}.com")
        for i in range(1, 4)
    ]
    page2_entries = [
        make_raw_entry((now - timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"), "192.168.1.10", f"domain{i}.com")
        for i in range(4, 7)
    ]
    page3_entries = [
        make_raw_entry((now - timedelta(hours=25)).strftime("%Y-%m-%dT%H:%M:%SZ"), "192.168.1.10", "old.com")
    ]

    resp_lib.add(resp_lib.GET, f"{BASE_URL}/control/querylog",
                 json=make_agh_response(page1_entries, oldest=page1_entries[-1]["time"]))
    resp_lib.add(resp_lib.GET, f"{BASE_URL}/control/querylog",
                 json=make_agh_response(page2_entries, oldest=page2_entries[-1]["time"]))
    resp_lib.add(resp_lib.GET, f"{BASE_URL}/control/querylog",
                 json=make_agh_response(page3_entries, oldest=page3_entries[-1]["time"]))

    client = AdGuardClient(BASE_URL, USER, PASS)
    entries = client.fetch_last_24h(now=now)

    assert len(entries) == 6
    assert all(e.domain.startswith("domain") for e in entries)


@resp_lib.activate
def test_entry_blocked_flag():
    now = datetime(2026, 5, 8, 15, 0, 0, tzinfo=timezone.utc)
    raw = make_raw_entry(now.strftime("%Y-%m-%dT%H:%M:%SZ"), "192.168.1.10", "ads.example.com", "FilteredBlackList")
    raw["rule"] = "||ads.example.com^"
    raw["rules"] = [{"filter_list_id": 1, "text": "||ads.example.com^"}]

    resp_lib.add(resp_lib.GET, f"{BASE_URL}/control/querylog",
                 json=make_agh_response([raw], oldest=now.strftime("%Y-%m-%dT%H:%M:%SZ")))
    resp_lib.add(resp_lib.GET, f"{BASE_URL}/control/querylog",
                 json=make_agh_response([], oldest=""))

    client = AdGuardClient(BASE_URL, USER, PASS)
    entries = client.fetch_last_24h(now=now)

    assert entries[0].blocked is True
    assert entries[0].block_rule == "||ads.example.com^"

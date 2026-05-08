# dns_briefing/aggregator.py
# Pure functional core — no I/O, no state DB calls, no side effects.
# All state-derived data (known_domains, volume_baseline) is passed in by run.py.
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import duckdb

from dns_briefing.core.models import QueryEntry


def _parse_hhmm(hhmm: str, tz: ZoneInfo, ref_date: date) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime(ref_date.year, ref_date.month, ref_date.day, h, m, tzinfo=tz)


def _top_domains_for_client(con: duckdb.DuckDBPyConnection, client: str) -> list[dict[str, Any]]:
    return [
        {"domain": r[0], "count": r[1]}
        for r in con.execute(
            """
            SELECT domain, COUNT(*) AS cnt
            FROM entries
            WHERE client = ? AND NOT blocked
            GROUP BY domain ORDER BY cnt DESC LIMIT 5
            """,
            [client],
        ).fetchall()
    ]


def build_evidence_packet(
    entries: list[QueryEntry],
    known_domains: set[str],
    volume_baseline: dict[str, dict[str, float]],
    today: date,
    config_timezone: str,
    off_hours_start: str,
    off_hours_end: str,
    device_map: dict[str, str],
) -> dict[str, Any]:
    tz = ZoneInfo(config_timezone)

    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE entries (
            time TIMESTAMP,
            client TEXT,
            domain TEXT,
            query_type TEXT,
            reason TEXT,
            blocked BOOLEAN,
            block_rule TEXT
        )
    """)
    con.executemany(
        "INSERT INTO entries VALUES (?,?,?,?,?,?,?)",
        [
            (
                e.time.astimezone(UTC).replace(tzinfo=None),
                e.client,
                e.domain,
                e.query_type,
                e.reason,
                e.blocked,
                e.block_rule,
            )
            for e in entries
        ],
    )

    def device(ip: str) -> str:
        return device_map.get(ip, ip)

    # ── Summary ──────────────────────────────────────────────────────────
    row = con.execute("""
        SELECT COUNT(*), COUNT(DISTINCT client), COUNT(DISTINCT domain), SUM(blocked::INT)
        FROM entries
    """).fetchone()
    assert row is not None
    summary: dict[str, Any] = {
        "date": today.isoformat(),
        "total_queries": row[0],
        "unique_clients": row[1],
        "unique_domains": row[2],
        "total_blocked": row[3],
    }

    # ── Top domains ───────────────────────────────────────────────────────
    top_domains: list[dict[str, Any]] = [
        {"domain": r[0], "count": r[1]}
        for r in con.execute("""
            SELECT domain, COUNT(*) AS cnt
            FROM entries WHERE NOT blocked
            GROUP BY domain ORDER BY cnt DESC LIMIT 20
        """).fetchall()
    ]

    # ── Per-client breakdown ──────────────────────────────────────────────
    per_client: list[dict[str, Any]] = [
        {
            "client": r[0],
            "device": device(r[0]),
            "total": r[1],
            "blocked": r[2],
            "top_domains": _top_domains_for_client(con, r[0]),
        }
        for r in con.execute("""
            SELECT client, COUNT(*) AS total, SUM(blocked::INT) AS blocked
            FROM entries GROUP BY client ORDER BY total DESC
        """).fetchall()
    ]

    # ── Off-hours activity ────────────────────────────────────────────────
    off_start = _parse_hhmm(off_hours_start, tz, today).astimezone(UTC).replace(tzinfo=None)
    off_end = _parse_hhmm(off_hours_end, tz, today).astimezone(UTC).replace(tzinfo=None)

    off_rows = con.execute(
        """
        SELECT time, client, domain, reason, blocked, block_rule
        FROM entries WHERE time >= ? AND time < ?
        ORDER BY time
    """,
        [off_start, off_end],
    ).fetchall()

    off_hours: dict[str, Any] = {
        "window_start": off_hours_start,
        "window_end": off_hours_end,
        "timezone": config_timezone,
        "total_queries": len(off_rows),
        "entries": [
            {
                "time_local": row[0].replace(tzinfo=UTC).astimezone(tz).strftime("%H:%M"),
                "device": device(row[1]),
                "domain": row[2],
                "reason": row[3],
                "blocked": row[4],
            }
            for row in off_rows
        ],
    }

    # ── New domains ───────────────────────────────────────────────────────
    new_domains: list[dict[str, Any]] = []
    if known_domains:
        new_domains = [
            {"domain": r[0], "count": r[1], "first_client": device(r[2])}
            for r in con.execute(
                """
                SELECT domain, COUNT(*) AS cnt, FIRST(client) AS first_client
                FROM entries
                WHERE domain IN (SELECT UNNEST(?))
                GROUP BY domain ORDER BY cnt DESC
            """,
                [list(known_domains)],
            ).fetchall()
        ]

    # ── Volume anomalies ──────────────────────────────────────────────────
    client_counts: dict[str, int] = {
        r[0]: r[1]
        for r in con.execute("SELECT client, COUNT(*) FROM entries GROUP BY client").fetchall()
    }

    volume_anomalies: list[dict[str, Any]] = []
    for client_ip, count in client_counts.items():
        if client_ip not in volume_baseline:
            continue
        b = volume_baseline[client_ip]
        mean, stddev = b["mean"], b["stddev"]
        if stddev > 0:
            z = (count - mean) / stddev
        elif mean > 0:
            z = (count - mean) / mean
        else:
            z = 0.0
        if abs(z) >= 2.0 or count >= mean * 3:
            volume_anomalies.append(
                {
                    "client": client_ip,
                    "device": device(client_ip),
                    "today_count": count,
                    "baseline_mean": round(mean, 1),
                    "baseline_stddev": round(stddev, 1),
                    "z_score": round(z, 2),
                    "baseline_days": b["days"],
                }
            )
    volume_anomalies.sort(key=lambda x: abs(x["z_score"]), reverse=True)

    # ── Blocked domains ───────────────────────────────────────────────────
    blocked_domains: list[dict[str, Any]] = [
        {"domain": r[0], "count": r[1], "rule": r[2]}
        for r in con.execute("""
            SELECT domain, COUNT(*) AS cnt, FIRST(block_rule) AS rule
            FROM entries WHERE blocked
            GROUP BY domain ORDER BY cnt DESC LIMIT 20
        """).fetchall()
    ]

    return {
        "summary": summary,
        "top_domains": top_domains,
        "per_client": per_client,
        "off_hours_activity": off_hours,
        "new_domains": new_domains,
        "volume_anomalies": volume_anomalies,
        "blocked_domains": blocked_domains,
    }

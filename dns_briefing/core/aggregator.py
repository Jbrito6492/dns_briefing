# dns_briefing/aggregator.py
# Pure functional core — no I/O, no state DB calls, no side effects.
# All state-derived data (unseen_domains, volume_baseline) is passed in by run.py.
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


_OFF_HOURS_DOMAIN_LIMIT = 10


def _aggregate_off_hours(
    con: duckdb.DuckDBPyConnection,
    off_start: datetime,
    off_end: datetime,
    off_hours_start: str,
    off_hours_end: str,
    timezone: str,
    device_map: dict[str, str],
) -> dict[str, Any]:
    tz = ZoneInfo(timezone)

    rows = con.execute(
        """
        SELECT
            client,
            domain,
            bool_or(blocked)  AS blocked,
            COUNT(*)          AS count,
            MIN(time)         AS first_seen,
            MAX(time)         AS last_seen
        FROM entries
        WHERE time >= ? AND time < ?
        GROUP BY client, domain
        ORDER BY count DESC
        """,
        [off_start, off_end],
    ).fetchall()

    # Rows globally sorted by count DESC — first domain per client is their highest.
    by_client: dict[str, list[dict[str, Any]]] = {}
    client_totals: dict[str, int] = {}

    for client, domain, blocked, count, first_seen, last_seen in rows:
        client_totals[client] = client_totals.get(client, 0) + count
        if client not in by_client:
            by_client[client] = []
        if len(by_client[client]) < _OFF_HOURS_DOMAIN_LIMIT:
            by_client[client].append(
                {
                    "domain": domain,
                    "count": count,
                    "blocked": blocked,
                    "first_seen_local": first_seen.replace(tzinfo=UTC)
                    .astimezone(tz)
                    .strftime("%H:%M"),
                    "last_seen_local": last_seen.replace(tzinfo=UTC)
                    .astimezone(tz)
                    .strftime("%H:%M"),
                }
            )

    by_device = sorted(
        [
            {
                "device": device_map.get(client, client),
                "client": client,
                "total": client_total,
                "top_domains": by_client[client],
            }
            for client, client_total in client_totals.items()
        ],
        key=lambda x: x["total"],  # type: ignore[return-value, arg-type]
        reverse=True,
    )

    return {
        "window_start": off_hours_start,
        "window_end": off_hours_end,
        "timezone": timezone,
        "total_queries": sum(client_totals.values()),
        "by_device": by_device,
    }


def build_evidence_packet(
    entries: list[QueryEntry],
    unseen_domains: set[str],
    volume_baseline: dict[str, dict[str, float]],
    today: date,
    config_timezone: str,
    off_hours_start: str,
    off_hours_end: str,
    device_map: dict[str, str],
    intercept_stats: dict[str, Any] | None = None,
    fingerprint_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tz = ZoneInfo(config_timezone)

    with duckdb.connect(":memory:") as con:
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
        if row is None:
            raise RuntimeError("aggregate query returned no rows")
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

        off_hours = _aggregate_off_hours(
            con, off_start, off_end, off_hours_start, off_hours_end, config_timezone, device_map
        )

        # ── New domains ───────────────────────────────────────────────────────
        new_domains: list[dict[str, Any]] = []
        if unseen_domains:
            new_domains = [
                {"domain": r[0], "count": r[1], "first_client": device(r[2])}
                for r in con.execute(
                    """
                    SELECT domain, COUNT(*) AS cnt, FIRST(client) AS first_client
                    FROM entries
                    WHERE domain IN (SELECT UNNEST(?))
                    GROUP BY domain ORDER BY cnt DESC
                """,
                    [list(unseen_domains)],
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

        packet: dict[str, Any] = {
            "summary": summary,
            "top_domains": top_domains,
            "per_client": per_client,
            "off_hours_activity": off_hours,
            "new_domains": new_domains,
            "volume_anomalies": volume_anomalies,
            "blocked_domains": blocked_domains,
        }

        if fingerprint_snapshot:
            packet["device_profiles"] = {
                "devices": fingerprint_snapshot.get("devices", []),
                "recent_changes": fingerprint_snapshot.get("recent_changes", []),
                "note": (
                    "OS fingerprints collected passively by p0f from TCP SYN packets. "
                    "No active scanning. 'distance_hops' is estimated hops from mav. "
                    "Changes indicate a device OS shift — may mean firmware update, IP reassignment, or anomaly."
                ),
            }

        if intercept_stats:
            packet["dns_enforcement"] = {
                "intercepted_queries": intercept_stats.get("intercepted_queries", 0),
                "intercepted_bytes": intercept_stats.get("intercepted_bytes", 0),
                "udp_queries": intercept_stats.get("udp_queries", 0),
                "tcp_queries": intercept_stats.get("tcp_queries", 0),
                "note": (
                    "Queries intercepted from devices that bypassed DHCP DNS "
                    "and sent to hardcoded public resolvers (8.8.8.8, 1.1.1.1, etc). "
                    "These were silently redirected to AdGuard."
                ),
            }

        return packet

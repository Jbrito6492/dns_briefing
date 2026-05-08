from __future__ import annotations

from datetime import date, timedelta
from types import TracebackType

import duckdb


class StateDB:
    def __init__(self, db_path: str):
        self._con = duckdb.connect(db_path)
        self._init_schema()

    def __enter__(self) -> StateDB:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._con.close()

    def _init_schema(self) -> None:
        self._con.execute("""
            CREATE TABLE IF NOT EXISTS known_domains (
                domain TEXT PRIMARY KEY,
                first_seen DATE NOT NULL,
                last_seen DATE NOT NULL
            )
        """)
        self._con.execute("""
            CREATE TABLE IF NOT EXISTS daily_client_volume (
                date DATE NOT NULL,
                client_ip TEXT NOT NULL,
                query_count INTEGER NOT NULL,
                PRIMARY KEY (date, client_ip)
            )
        """)

    def update_known_domains(self, domains: list[str], today: date, window_days: int) -> list[str]:
        """Insert/update domains. Return list of domains new within window."""
        window_start = today - timedelta(days=window_days)

        known = {
            row[0]
            for row in self._con.execute(
                "SELECT domain FROM known_domains WHERE last_seen >= ?",
                [window_start],
            ).fetchall()
        }

        new_domains = [d for d in domains if d not in known]

        # Bulk upsert via temp table — avoids N individual SQL round-trips
        self._con.execute("CREATE TEMP TABLE IF NOT EXISTS _bulk_domains (domain TEXT, d DATE)")
        self._con.execute("DELETE FROM _bulk_domains")
        self._con.executemany(
            "INSERT INTO _bulk_domains VALUES (?, ?)",
            [(d, today) for d in domains],
        )
        self._con.execute("""
            INSERT INTO known_domains (domain, first_seen, last_seen)
            SELECT domain, d, d FROM _bulk_domains
            ON CONFLICT (domain) DO UPDATE SET last_seen = excluded.last_seen
        """)

        return new_domains

    def record_daily_volume(self, client_counts: dict[str, int], day: date) -> None:
        self._con.executemany(
            """
            INSERT INTO daily_client_volume (date, client_ip, query_count)
            VALUES (?, ?, ?)
            ON CONFLICT (date, client_ip) DO UPDATE SET query_count = excluded.query_count
            """,
            [(day, ip, count) for ip, count in client_counts.items()],
        )

    def get_volume_baseline(
        self, baseline_days: int, reference_date: date
    ) -> dict[str, dict[str, float]]:
        """Return {client_ip: {mean, stddev, days}} over window excluding reference_date."""
        window_start = reference_date - timedelta(days=baseline_days)
        rows = self._con.execute(
            """
            SELECT
                client_ip,
                AVG(query_count)::DOUBLE AS mean,
                STDDEV_POP(query_count)::DOUBLE AS stddev,
                COUNT(*) AS days
            FROM daily_client_volume
            WHERE date >= ? AND date < ?
            GROUP BY client_ip
        """,
            [window_start, reference_date],
        ).fetchall()

        return {row[0]: {"mean": row[1], "stddev": row[2] or 0.0, "days": row[3]} for row in rows}

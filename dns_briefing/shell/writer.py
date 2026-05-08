# dns_briefing/shell/writer.py
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import boto3


class ReportWriter:
    def __init__(
        self,
        local_dir: str,
        s3_bucket: str,
        s3_client: Any = None,
        dry_run: bool = False,
    ) -> None:
        self._local_dir = Path(local_dir)
        self._s3_bucket = s3_bucket
        self._s3 = s3_client
        self._dry_run = dry_run

    @classmethod
    def from_config(
        cls,
        local_dir: str,
        s3_bucket: str,
        region: str,
        dry_run: bool = False,
    ) -> ReportWriter:
        return cls(
            local_dir=local_dir,
            s3_bucket=s3_bucket,
            s3_client=boto3.client("s3", region_name=region),
            dry_run=dry_run,
        )

    def write(self, report: str, report_date: date) -> None:
        self._write_local(report, report_date)
        if not self._dry_run:
            self._write_s3(report, report_date)

    def _write_local(self, report: str, report_date: date) -> None:
        self._local_dir.mkdir(parents=True, exist_ok=True)
        dated = self._local_dir / f"{report_date.isoformat()}.md"
        dated.write_text(report, encoding="utf-8")

        latest = self._local_dir / "latest.md"
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(dated.name)

    def _write_s3(self, report: str, report_date: date) -> None:
        body = report.encode("utf-8")
        key = f"{report_date.year}/{report_date.month:02d}/{report_date.day:02d}.md"
        self._s3.put_object(Bucket=self._s3_bucket, Key=key, Body=body, ContentType="text/markdown")
        self._s3.put_object(
            Bucket=self._s3_bucket,
            Key="latest.md",
            Body=body,
            ContentType="text/markdown",
        )

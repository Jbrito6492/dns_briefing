# tests/test_writer.py
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from dns_briefing.shell.writer import ReportWriter

REPORT = "## TL;DR\n- Nothing bad happened\n"


@pytest.fixture
def local_dir(tmp_path: Path) -> Path:
    d = tmp_path / "reports"
    d.mkdir()
    return d


def test_write_local_creates_dated_file(local_dir: Path) -> None:
    writer = ReportWriter(
        local_dir=str(local_dir),
        s3_bucket="test-bucket",
        s3_client=MagicMock(),
    )
    writer.write(REPORT, date(2026, 5, 8))
    assert (local_dir / "2026-05-08.md").read_text() == REPORT


def test_write_local_creates_latest_symlink(local_dir: Path) -> None:
    writer = ReportWriter(
        local_dir=str(local_dir),
        s3_bucket="test-bucket",
        s3_client=MagicMock(),
    )
    writer.write(REPORT, date(2026, 5, 8))
    latest = local_dir / "latest.md"
    assert latest.is_symlink()
    assert latest.read_text() == REPORT


def test_write_s3_puts_dated_and_latest(local_dir: Path) -> None:
    mock_s3 = MagicMock()
    writer = ReportWriter(
        local_dir=str(local_dir),
        s3_bucket="mav-dns-briefing",
        s3_client=mock_s3,
    )
    writer.write(REPORT, date(2026, 5, 8))
    keys = [c[1]["Key"] for c in mock_s3.put_object.call_args_list]
    assert "2026/05/08.md" in keys
    assert "latest.md" in keys


def test_write_skips_s3_on_dry_run(local_dir: Path) -> None:
    mock_s3 = MagicMock()
    writer = ReportWriter(
        local_dir=str(local_dir),
        s3_bucket="mav-dns-briefing",
        s3_client=mock_s3,
        dry_run=True,
    )
    writer.write(REPORT, date(2026, 5, 8))
    mock_s3.put_object.assert_not_called()


def test_symlink_updates_on_second_write(local_dir: Path) -> None:
    writer = ReportWriter(
        local_dir=str(local_dir),
        s3_bucket="test-bucket",
        s3_client=MagicMock(),
    )
    writer.write("day one\n", date(2026, 5, 7))
    writer.write("day two\n", date(2026, 5, 8))
    assert (local_dir / "latest.md").read_text() == "day two\n"

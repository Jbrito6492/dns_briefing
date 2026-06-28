# dns_briefing/__main__.py
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from dns_briefing.config import load_config
from dns_briefing.run import run
from dns_briefing.shell.writer import ReportWriter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stderr,
)

logger = logging.getLogger(__name__)


def _rerender(config_path: Path) -> None:
    config = load_config(config_path)
    writer = ReportWriter.from_config(
        local_dir=config.report.local_dir,
        s3_bucket=config.aws.s3_bucket,
        region=config.aws.region,
        network_name=config.report.network_name,
    )
    reports_dir = Path(config.report.local_dir)
    md_files = sorted(reports_dir.glob("????-??-??.md"))
    if not md_files:
        logger.warning("No dated report files found in %s", reports_dir)
        return
    for md_path in md_files:
        report_date = date.fromisoformat(md_path.stem)
        report_text = md_path.read_text(encoding="utf-8")
        logger.info("Re-rendering %s", md_path.name)
        writer.write(report_text, report_date)
    logger.info("Done — re-rendered %d report(s)", len(md_files))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="dns-briefing — daily DNS network intelligence report"
    )
    parser.add_argument(
        "--config",
        default="/app/config.toml",
        help="Path to config.toml (default: /app/config.toml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip S3 write; print report to stdout",
    )
    parser.add_argument(
        "--rerender",
        action="store_true",
        help="Re-render all existing .md reports as HTML and upload to S3",
    )
    args = parser.parse_args()

    if args.rerender:
        _rerender(Path(args.config))
        return

    config = load_config(Path(args.config))
    report = run(config, dry_run=args.dry_run)

    if args.dry_run:
        print(report)


if __name__ == "__main__":
    main()

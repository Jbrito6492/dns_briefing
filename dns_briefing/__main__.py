# dns_briefing/__main__.py
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dns_briefing.config import load_config
from dns_briefing.run import run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stderr,
)


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
    args = parser.parse_args()

    config = load_config(Path(args.config))
    report = run(config, dry_run=args.dry_run)

    if args.dry_run:
        print(report)


if __name__ == "__main__":
    main()

# dns_briefing/run.py
# Orchestrator — Functional Core / Imperative Shell.
# Shell calls at top and bottom; pure core in the middle.
# No logic lives here — only plumbing.
from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, date, datetime

from dns_briefing.config import Config
from dns_briefing.core.aggregator import build_evidence_packet
from dns_briefing.core.prompt import build_prompt
from dns_briefing.shell.adguard import AdGuardClient
from dns_briefing.shell.bedrock import BedrockClient
from dns_briefing.shell.state import StateDB
from dns_briefing.shell.writer import ReportWriter

logger = logging.getLogger(__name__)


def run(config: Config, dry_run: bool = False) -> str:
    now = datetime.now(tz=UTC)
    today = date.today()

    # ── Shell: fetch raw data ─────────────────────────────────────────────
    logger.info("Fetching AdGuard query log (last %dh)...", config.report.window_hours)
    agh = AdGuardClient(config.adguard.base_url, config.adguard.username, config.adguard.password)
    entries = agh.fetch_window(hours=config.report.window_hours, now=now)
    logger.info("Fetched %d entries", len(entries))

    # ── Shell: read state, compute inputs for core ────────────────────────
    with StateDB(config.state.db_path) as state:
        all_domains = [e.domain for e in entries]
        known_domains = set(
            state.update_known_domains(all_domains, today, config.state.known_domains_window_days)
        )
        volume_baseline = state.get_volume_baseline(config.state.volume_baseline_days, today)
        client_counts = dict(Counter(e.client for e in entries))
        state.record_daily_volume(client_counts, today)

    # ── Core: pure aggregation ────────────────────────────────────────────
    logger.info("Building evidence packet...")
    packet = build_evidence_packet(
        entries=entries,
        known_domains=known_domains,
        volume_baseline=volume_baseline,
        today=today,
        config_timezone=config.report.timezone,
        off_hours_start=config.report.off_hours_start,
        off_hours_end=config.report.off_hours_end,
        device_map=config.devices,
    )

    # ── Core: build prompt ────────────────────────────────────────────────
    messages = build_prompt(
        packet=packet,
        date=today.isoformat(),
        timezone=config.report.timezone,
        off_hours_start=config.report.off_hours_start,
        off_hours_end=config.report.off_hours_end,
    )

    # ── Shell: call Bedrock ───────────────────────────────────────────────
    logger.info("Generating report via Bedrock (%s)...", config.aws.bedrock_model_id)
    bedrock = BedrockClient.from_config(config.aws.region, config.aws.bedrock_model_id)
    report = bedrock.generate_report(messages)

    # ── Shell: write output ───────────────────────────────────────────────
    writer = ReportWriter.from_config(
        local_dir=config.report.local_dir,
        s3_bucket=config.aws.s3_bucket,
        region=config.aws.region,
        network_name=config.report.network_name,
        dry_run=dry_run,
    )
    writer.write(report, today)
    logger.info("Report written (dry_run=%s)", dry_run)

    return report

# dns_briefing/config.py
from __future__ import annotations
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AdGuardConfig:
    base_url: str
    username: str
    password: str


@dataclass
class AWSConfig:
    region: str
    bedrock_model_id: str
    s3_bucket: str


@dataclass
class ReportConfig:
    local_dir: str
    off_hours_start: str
    off_hours_end: str
    timezone: str
    network_name: str


@dataclass
class StateConfig:
    db_path: str
    known_domains_window_days: int
    volume_baseline_days: int


@dataclass
class Config:
    adguard: AdGuardConfig
    aws: AWSConfig
    report: ReportConfig
    state: StateConfig
    devices: dict[str, str] = field(default_factory=dict)


def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise ValueError(f"Required env var {name!r} is not set")
    return val


def load_config(path: Path) -> Config:
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    devices: dict[str, str] = dict(raw.get("devices", {}))

    # Merge local config (gitignored) — adds/overrides [devices]
    local_path = Path(path).parent / "config.local.toml"
    if local_path.exists():
        with open(local_path, "rb") as f:
            local = tomllib.load(f)
        devices.update(local.get("devices", {}))

    return Config(
        adguard=AdGuardConfig(
            base_url=raw["adguard"]["base_url"],
            password=_require_env("AGH_PASSWORD"),
            username=_require_env("AGH_USERNAME"),
        ),
        aws=AWSConfig(
            region=raw["aws"]["region"],
            bedrock_model_id=raw["aws"]["bedrock_model_id"],
            s3_bucket=raw["aws"]["s3_bucket"],
        ),
        report=ReportConfig(
            local_dir=raw["report"]["local_dir"],
            off_hours_start=raw["report"]["off_hours_start"],
            off_hours_end=raw["report"]["off_hours_end"],
            timezone=raw["report"]["timezone"],
            network_name=raw["report"]["network_name"],
        ),
        state=StateConfig(
            db_path=raw["state"]["db_path"],
            known_domains_window_days=raw["state"]["known_domains_window_days"],
            volume_baseline_days=raw["state"]["volume_baseline_days"],
        ),
        devices=devices,
    )

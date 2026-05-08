# tests/test_config.py
import os
import pytest
from pathlib import Path

CONFIG_TOML = Path(__file__).parent.parent / "config.toml"


def test_load_config_reads_toml(monkeypatch):
    monkeypatch.setenv("AGH_USERNAME", "admin")
    monkeypatch.setenv("AGH_PASSWORD", "secret")

    from dns_briefing.config import load_config
    cfg = load_config(CONFIG_TOML)

    assert cfg.adguard.base_url == "http://localhost:3080"
    assert cfg.adguard.username == "admin"
    assert cfg.adguard.password == "secret"
    assert cfg.aws.region == "us-west-2"
    assert cfg.aws.s3_bucket == "mav-dns-briefing"
    assert cfg.report.timezone == "America/Phoenix"
    assert cfg.report.off_hours_start == "01:00"


def test_local_config_devices_loaded(monkeypatch, tmp_path):
    monkeypatch.setenv("AGH_USERNAME", "admin")
    monkeypatch.setenv("AGH_PASSWORD", "secret")

    # Write a minimal config.toml in tmp_path
    base = tmp_path / "config.toml"
    base.write_text("""
[adguard]
base_url = "http://localhost:3080"

[aws]
region = "us-west-2"
bedrock_model_id = "us.anthropic.claude-sonnet-4-6"
s3_bucket = "test-bucket"

[report]
local_dir = "/tmp/reports"
off_hours_start = "01:00"
off_hours_end = "05:00"
timezone = "America/Phoenix"
network_name = "Test Net"

[state]
db_path = "/tmp/state.db"
known_domains_window_days = 30
volume_baseline_days = 14

[devices]
""")
    # Write config.local.toml with device map
    local = tmp_path / "config.local.toml"
    local.write_text("""
[devices]
"192.168.1.10" = "Smart TV"
"192.168.1.20" = "Phone"
""")

    from dns_briefing.config import load_config
    cfg = load_config(base)

    assert cfg.devices["192.168.1.10"] == "Smart TV"
    assert cfg.devices["192.168.1.20"] == "Phone"


def test_no_local_config_is_fine(monkeypatch, tmp_path):
    monkeypatch.setenv("AGH_USERNAME", "admin")
    monkeypatch.setenv("AGH_PASSWORD", "secret")

    base = tmp_path / "config.toml"
    base.write_text("""
[adguard]
base_url = "http://localhost:3080"

[aws]
region = "us-west-2"
bedrock_model_id = "us.anthropic.claude-sonnet-4-6"
s3_bucket = "test-bucket"

[report]
local_dir = "/tmp/reports"
off_hours_start = "01:00"
off_hours_end = "05:00"
timezone = "America/Phoenix"
network_name = "Test Net"

[state]
db_path = "/tmp/state.db"
known_domains_window_days = 30
volume_baseline_days = 14

[devices]
""")
    # No config.local.toml — should not error

    from dns_briefing.config import load_config
    cfg = load_config(base)

    assert cfg.devices == {}


def test_missing_env_var_raises(monkeypatch):
    monkeypatch.delenv("AGH_PASSWORD", raising=False)
    monkeypatch.delenv("AGH_USERNAME", raising=False)

    from dns_briefing.config import load_config
    with pytest.raises(ValueError, match="AGH_PASSWORD"):
        load_config(CONFIG_TOML)

from datetime import date, timedelta
import pytest
from dns_briefing.state import StateDB


@pytest.fixture
def db(tmp_path):
    return StateDB(str(tmp_path / "test.db"))


def test_new_domains_detected_on_first_run(db):
    today = date(2026, 5, 8)
    domains = ["github.com", "google.com", "newsite.io"]
    new = db.update_known_domains(domains, today, window_days=30)
    assert set(new) == {"github.com", "google.com", "newsite.io"}


def test_previously_seen_domains_not_new(db):
    today = date(2026, 5, 8)
    yesterday = today - timedelta(days=1)
    db.update_known_domains(["github.com", "google.com"], yesterday, window_days=30)
    new = db.update_known_domains(["github.com", "newsite.io"], today, window_days=30)
    assert "github.com" not in new
    assert "newsite.io" in new


def test_domains_outside_window_are_new_again(db):
    today = date(2026, 5, 8)
    old_date = today - timedelta(days=35)
    db.update_known_domains(["oldsite.com"], old_date, window_days=30)
    new = db.update_known_domains(["oldsite.com"], today, window_days=30)
    assert "oldsite.com" in new


def test_record_and_get_volume_baseline(db):
    today = date(2026, 5, 8)
    for i in range(14):
        d = today - timedelta(days=i + 1)
        db.record_daily_volume({"192.168.1.10": 100, "192.168.1.20": 50}, d)
    baseline = db.get_volume_baseline(baseline_days=14, reference_date=today)
    assert "192.168.1.10" in baseline
    assert abs(baseline["192.168.1.10"]["mean"] - 100.0) < 0.01
    assert baseline["192.168.1.10"]["stddev"] == 0.0


def test_baseline_excludes_reference_date(db):
    today = date(2026, 5, 8)
    for i in range(14):
        d = today - timedelta(days=i + 1)
        db.record_daily_volume({"192.168.1.10": 100}, d)
    # Record a spike on today itself — should NOT appear in baseline
    db.record_daily_volume({"192.168.1.10": 9999}, today)
    baseline = db.get_volume_baseline(baseline_days=14, reference_date=today)
    assert abs(baseline["192.168.1.10"]["mean"] - 100.0) < 0.01


def test_get_volume_baseline_returns_mean_stddev_days(db):
    today = date(2026, 5, 8)
    for i in range(14):
        d = today - timedelta(days=i + 1)
        db.record_daily_volume({"192.168.1.10": 100 + (i % 3) * 10}, d)
    baseline = db.get_volume_baseline(baseline_days=14, reference_date=today)
    assert "mean" in baseline["192.168.1.10"]
    assert "stddev" in baseline["192.168.1.10"]
    assert baseline["192.168.1.10"]["days"] == 14

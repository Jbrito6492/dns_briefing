from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

from dns_briefing.bedrock import BedrockClient
from dns_briefing.prompt import build_prompt


def _sample_packet() -> dict[str, Any]:
    return {
        "summary": {
            "date": "2026-05-08",
            "total_queries": 697,
            "unique_clients": 5,
            "unique_domains": 142,
            "total_blocked": 60,
        },
        "top_domains": [
            {"domain": "firetvcaptiveportal.com", "count": 210},
            {"domain": "apple.com", "count": 45},
        ],
        "per_client": [
            {
                "client": "192.168.1.10",
                "device": "Smart-TV",
                "total": 215,
                "blocked": 0,
                "top_domains": [{"domain": "firetvcaptiveportal.com", "count": 210}],
            }
        ],
        "off_hours_activity": {
            "window_start": "01:00",
            "window_end": "05:00",
            "timezone": "America/Phoenix",
            "total_queries": 32,
            "entries": [
                {
                    "time_local": "03:00",
                    "device": "Smart-TV",
                    "domain": "telemetry-sink.sketchy-analytics.io",
                    "reason": "NotFilteredNotFound",
                    "blocked": False,
                }
            ],
        },
        "new_domains": [
            {
                "domain": "app.new-saas-tool-never-seen.io",
                "count": 1,
                "first_client": "Laptop",
            },
            {
                "domain": "telemetry-sink.sketchy-analytics.io",
                "count": 1,
                "first_client": "Smart-TV",
            },
        ],
        "volume_anomalies": [
            {
                "client": "192.168.1.10",
                "device": "Smart-TV",
                "today_count": 215,
                "baseline_mean": 15.0,
                "baseline_stddev": 2.1,
                "z_score": 95.2,
                "baseline_days": 14,
            }
        ],
        "blocked_domains": [
            {
                "domain": "teams.events.data.microsoft.com",
                "count": 20,
                "rule": "||teams.events.data.microsoft.com^",
            }
        ],
    }


def test_build_prompt_embeds_evidence() -> None:
    msgs = build_prompt(_sample_packet(), "2026-05-08", "America/Phoenix", "01:00", "05:00")
    combined = json.dumps(msgs)
    assert "telemetry-sink.sketchy-analytics.io" in combined
    assert "Smart-TV" in combined
    assert "TL;DR" in combined


def test_build_prompt_returns_message_list() -> None:
    msgs = build_prompt(_sample_packet(), "2026-05-08", "America/Phoenix", "01:00", "05:00")
    assert isinstance(msgs, list)
    assert len(msgs) >= 1
    assert all("role" in m and "content" in m for m in msgs)
    assert msgs[0]["role"] == "user"


def test_bedrock_client_invokes_model() -> None:
    mock_boto = MagicMock()
    mock_body = json.dumps(
        {
            "content": [{"type": "text", "text": "## TL;DR\n- Nothing bad"}],
            "stop_reason": "end_turn",
        }
    ).encode()
    mock_boto.invoke_model.return_value = {"body": MagicMock(read=lambda: mock_body)}

    client = BedrockClient(mock_boto, "us.anthropic.claude-sonnet-4-6")
    result = client.generate_report(
        messages=[{"role": "user", "content": "test"}],
        system="You are an analyst.",
    )

    assert "TL;DR" in result
    mock_boto.invoke_model.assert_called_once()
    call_kwargs = mock_boto.invoke_model.call_args[1]
    assert call_kwargs["modelId"] == "us.anthropic.claude-sonnet-4-6"

# dns_briefing/prompt.py
# THE most important file in the project.
# Report quality is determined here. If reports are generic or boring, fix this file first.
#
# Design principles encoded in the prompt:
# - Reader is technical (software engineer running own DNS infra). No hand-holding.
# - Demand interpretation, not description. Restating numbers is useless output.
# - "Don't fabricate threats" — without this, models invent drama from normal traffic.
# - Sections are fixed so the reader builds muscle memory for where to look.
# - Short is explicitly valued — a boring day should produce a short report.
from __future__ import annotations

import json
from typing import Any

# Establishes role and quality bar before the data arrives.
# The "don't fabricate" rule is load-bearing — models default to treating
# unusual domains as threats without this constraint.
SYSTEM_PROMPT = """\
You are a network intelligence analyst writing a daily DNS briefing for the owner of a home network.

The owner is a software engineer who runs their own DNS infrastructure. They are technically \
sophisticated. Do not explain what DNS is. Do not explain what a block list is. Do not pad.

Your job is to interpret the data, not describe it. Restating what the numbers say without \
adding interpretation is a bad report. A good report tells the owner something they did not \
already know, or confirms confidently that nothing notable happened.

Rules:
- Do not fabricate threats. If something looks suspicious, say why — do not call it an attack.
- Do not hedge everything into uselessness. Make a call. Be wrong sometimes. \
That is more useful than "this could be normal or abnormal."
- If the day was boring, say so in two sentences and stop. Do not pad a boring day.
- Short is better than long. Cut anything that does not add signal.\
"""

# The user turn. Evidence packet embedded as JSON so the model can cite specific numbers.
# Section structure is fixed — changing section names breaks the reader's muscle memory.
_USER_TEMPLATE = """\
DNS activity summary for {date} — timezone: {timezone}.
Off-hours window (owner asleep): {off_hours_start}–{off_hours_end} local time.

Evidence packet:

```json
{evidence_json}
```

Write a markdown briefing with exactly these sections. Do not add sections. Do not rename them.

## TL;DR
3 bullets maximum. The headline. What actually matters today.

## Off-Hours Activity
What happened between {off_hours_start} and {off_hours_end}. Interpret aggressively — \
a smart TV querying a telemetry endpoint at 3am warrants more suspicion than a laptop doing it. \
If nothing interesting happened, one sentence is enough.

## New Domains
Domains seen on this network for the first time. For each, make a call: CDN, tracker, \
legitimate new service, or unclear. Group obviously related domains (same registrable domain). \
Skip domains that are obvious CDN noise with no interesting characteristics.

## Volume Anomalies
Devices querying significantly more or less than their 14-day baseline. \
Speculate on causes when there is a reasonable explanation.

## Notable
Anything else worth a human look. Blocked domain patterns, unexpected service calls, \
timing correlations. Be opinionated. This is where you earn your keep.

## All Clear
1–2 lines on what was normal and boring today. Give the owner permission to stop reading.

---
Output only the markdown report. No preamble. No "Here is your report". No closing remarks.\
"""


def build_prompt(
    packet: dict[str, Any],
    date: str,
    timezone: str,
    off_hours_start: str,
    off_hours_end: str,
) -> list[dict[str, str]]:
    content = _USER_TEMPLATE.format(
        date=date,
        timezone=timezone,
        off_hours_start=off_hours_start,
        off_hours_end=off_hours_end,
        evidence_json=json.dumps(packet, indent=2),
    )
    return [{"role": "user", "content": content}]

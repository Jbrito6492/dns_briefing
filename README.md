# dns-briefing

Daily DNS network intelligence report, written by an LLM, based on what AdGuard Home saw in the last 24 hours.

Not a dashboard. Not a SIEM. A **briefing** — written like a thoughtful analyst reviewing yesterday's logs over coffee. Surfaces things you wouldn't otherwise notice: weird 3am queries, domains your devices started talking to that they never have before, trackers you didn't know were active, devices behaving out of character.

If the reports become boring or generic, the project has failed.

## What it does

```
AdGuard Home HTTP API
  → paginated 24h query log fetch
  → DuckDB aggregation (top domains, off-hours, new domains, per-device z-scores, blocked)
  → structured JSON evidence packet
  → Claude Sonnet via AWS Bedrock
  → Markdown + HTML report → S3 + local file
  → served via nginx (mobile-friendly dark UI)
```

Runs daily via a systemd timer. Two Docker containers: one oneshot job, one nginx serving the web UI.

## Requirements

- AdGuard Home (self-hosted)
- AWS account with Bedrock access (Claude Sonnet, us-west-2 or region of your choice)
- Docker
- A machine to run it on (tested on Ubuntu 24.04 aarch64 — Orange Pi 5)

## Setup

### 1. AWS

Create an IAM user with the following policy, then create access keys:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
      "Resource": [
        "arn:aws:bedrock:us-west-2::foundation-model/anthropic.*",
        "arn:aws:bedrock:us-west-2:ACCOUNT_ID:inference-profile/us.anthropic.*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject"],
      "Resource": "arn:aws:s3:::YOUR_BUCKET/*"
    },
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::YOUR_BUCKET"
    }
  ]
}
```

Create an S3 bucket in the same region.

### 2. Configuration

Copy and edit the config files:

```bash
cp config.toml.example config.toml        # committed, no secrets
cp config.local.toml.example config.local.toml  # gitignored, device map
```

Edit `config.toml`:

```toml
[adguard]
base_url = "http://localhost:3080"   # your AGH address

[aws]
region = "us-west-2"
bedrock_model_id = "us.anthropic.claude-sonnet-4-6"
s3_bucket = "your-bucket-name"

[report]
local_dir = "/path/to/reports"
off_hours_start = "01:00"
off_hours_end = "05:00"
timezone = "America/Phoenix"       # your local timezone
network_name = "Home Network"
window_hours = 24

[state]
db_path = "/path/to/data/state.db"
known_domains_window_days = 30
volume_baseline_days = 14
```

Edit `config.local.toml` with your device map (never committed):

```toml
[devices]
"192.168.1.1"  = "Router"
"192.168.1.10" = "Living Room TV"
"192.168.1.25" = "My Phone"
```

### 3. Environment variables

Create `/path/to/.env.dns_briefing` (mode 600):

```bash
AGH_USERNAME=your_agh_username
AGH_PASSWORD=your_agh_password
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-west-2
```

### 4. Build and run

```bash
docker build -t dns-briefing:latest .

# Test with dry-run (no S3 write, prints to stdout)
docker run --rm \
  --env-file /path/to/.env.dns_briefing \
  --network host \
  -v /path/to/data:/home/ubuntu/dns_briefing/data \
  -v /path/to/reports:/home/ubuntu/dns_briefing/reports \
  dns-briefing:latest \
  python -m dns_briefing --dry-run
```

### 5. Web UI (optional)

Serve the HTML reports via nginx. On your server:

```bash
docker run -d \
  --name dns-briefing-web \
  --restart unless-stopped \
  -p 8765:80 \
  -v /path/to/reports:/usr/share/nginx/html:ro \
  nginx:alpine
```

Then browse to `http://your-host:8765`. Each daily run regenerates `index.html`, `latest.html`, and a dated `YYYY-MM-DD.html`.

If you use Tailscale, this is accessible from any device on your tailnet with no port forwarding.

### 6. systemd timer (runs daily at 08:00 local time)

Copy the unit files from `systemd/` to `/etc/systemd/system/`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable dns-briefing.timer
sudo systemctl start dns-briefing.timer
```

**Note:** The first time you invoke the Bedrock model, it must be done by a user with AWS Marketplace permissions to enable it account-wide. Run the dry-run once with admin credentials if the IAM user gets an AccessDeniedException on first use.

## Architecture

```
dns_briefing/
  core/            # pure functions — no I/O, fully testable without mocks
    models.py      # QueryEntry dataclass
    aggregator.py  # DuckDB evidence packet builder
    prompt.py      # Bedrock prompt template (most important file)
  shell/           # I/O wrappers — all side effects live here
    adguard.py     # AGH HTTP client
    bedrock.py     # Bedrock InvokeModel
    intercept.py   # reads DNS intercept stats (optional)
    state.py       # DuckDB state (known domains, volume baseline)
    writer.py      # S3 + local filesystem writer
  config.py        # config loader (TOML + env vars)
  run.py           # orchestrator — shell → core → shell, no logic
  __main__.py      # CLI entrypoint
scripts/
  dump-intercept-stats.sh  # dumps iptables DNS_INTERCEPT counters before each run
```

Follows **Functional Core / Imperative Shell** (Gary Bernhardt). Core never imports from shell. Shell may import types from core.

## Development

```bash
uv pip install -e ".[dev]"
uv run pytest tests/ -q
uv run mypy dns_briefing/
uv run ruff check dns_briefing/ tests/
```

## DNS enforcement (optional)

If your router supports static routes, you can force devices that hardcode public DNS servers (Chromecasts, smart TVs) through AdGuard. The briefing will include a **DNS Enforcement** section reporting how many bypass attempts were intercepted.

**How it works:** Add static `/32` routes on your router for common public DNS IPs (`8.8.8.8`, `1.1.1.1`, etc.) pointing to your mav IP. Then run `dns-intercept.sh` on the host — it sets up iptables DNAT rules that redirect port 53 traffic to AdGuard, and blackhole routes that drop non-DNS traffic to those IPs (preventing routing loops).

**Setup:**
1. Copy `scripts/dump-intercept-stats.sh` to your host
2. The `systemd/dns-briefing.service` already includes an `ExecStartPre` line that runs it before each briefing
3. Stats are written to `data/intercept_stats.json` and mounted into the container

If the iptables chain doesn't exist (intercept not set up), the section is silently omitted.

Optionally, drop a `fingerprint_snapshot.json` in the data directory before each run to get a **Device Profiles** section — OS fingerprints cross-referenced with per-client DNS behavior. The file format:

```json
{
  "available": true,
  "devices": [
    {"ip": "192.168.1.10", "os": "Linux 3.x", "link_type": "Ethernet", "distance_hops": 1, "uptime_min": 1234, "http_os": ""}
  ],
  "recent_changes": [
    {"ip": "192.168.1.10", "detected_at": "...", "previous_os": "Windows NT", "current_os": "Linux 3.x"}
  ]
}
```

Any tool that passively fingerprints your network (p0f, etc.) can generate this. If the file is absent or `available` is false, the section is silently omitted.

## Tuning the reports

The prompt lives in `dns_briefing/core/prompt.py`. It's the most important file in the project. If reports are generic or boring, that's where to look. The file has comments explaining the purpose of each instruction.

## License

MIT

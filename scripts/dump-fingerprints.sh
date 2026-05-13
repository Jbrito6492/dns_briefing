#!/bin/bash
# Query the p0f fingerprint DuckDB and write fingerprint_snapshot.json for dns_briefing.
# Run as ExecStartPre before the dns-briefing Docker container.

DB="${FINGERPRINT_DB:-/home/ubuntu/mav/data/fingerprints.db}"
OUTPUT="/home/ubuntu/dns_briefing/data/fingerprint_snapshot.json"

if [ ! -f "$DB" ]; then
    echo '{"available": false, "reason": "fingerprint DB not found"}' > "$OUTPUT"
    exit 0
fi

python3 - "$DB" "$OUTPUT" <<'EOF'
import sys, json, duckdb

db_path, out_path = sys.argv[1], sys.argv[2]

with duckdb.connect(db_path, read_only=True) as con:
    devices = [
        {
            "ip": r[0],
            "first_seen": r[1].isoformat(),
            "last_seen": r[2].isoformat(),
            "os": f"{r[3]} {r[4]}".strip() or "unknown",
            "http_os": r[5] or "",
            "distance_hops": r[6],
            "uptime_min": r[7],
        }
        for r in con.execute(
            "SELECT ip, first_seen, last_seen, os_name, os_flavor, http_name, distance, uptime_min "
            "FROM fingerprints ORDER BY last_seen DESC"
        ).fetchall()
    ]
    changes = [
        {
            "ip": r[0],
            "detected_at": r[1].isoformat(),
            "previous_os": r[2],
            "current_os": r[3],
        }
        for r in con.execute(
            "SELECT ip, detected_at, previous_os, current_os "
            "FROM fingerprint_changes ORDER BY detected_at DESC LIMIT 20"
        ).fetchall()
    ]

with open(out_path, "w") as f:
    json.dump({"available": True, "devices": devices, "recent_changes": changes}, f, indent=2)

print(f"Fingerprint snapshot written: {len(devices)} devices, {len(changes)} recent changes")
EOF

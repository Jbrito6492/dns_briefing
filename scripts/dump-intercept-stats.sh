#!/bin/bash
# Dump DNS_INTERCEPT iptables counters to JSON for dns_briefing to include in evidence packet.
# Run as ExecStartPre before the dns-briefing Docker container.
# Zeroes the chain counters after reading so each day's count is a clean delta.

OUTPUT="/home/ubuntu/dns_briefing/data/intercept_stats.json"

CHAIN=$(sudo iptables -t nat -L DNS_INTERCEPT -n -v -x 2>/dev/null)
if [ -z "$CHAIN" ]; then
    echo '{"available": false, "reason": "DNS_INTERCEPT chain not found"}' > "$OUTPUT"
    exit 0
fi

UDP_PKTS=$(echo "$CHAIN" | grep "udp dpt:53" | awk '{print $1}')
TCP_PKTS=$(echo "$CHAIN" | grep "tcp dpt:53" | awk '{print $1}')
UDP_BYTES=$(echo "$CHAIN" | grep "udp dpt:53" | awk '{print $2}')
TCP_BYTES=$(echo "$CHAIN" | grep "tcp dpt:53" | awk '{print $2}')

UDP_PKTS=${UDP_PKTS:-0}
TCP_PKTS=${TCP_PKTS:-0}
UDP_BYTES=${UDP_BYTES:-0}
TCP_BYTES=${TCP_BYTES:-0}
TOTAL_PKTS=$(( UDP_PKTS + TCP_PKTS ))
TOTAL_BYTES=$(( UDP_BYTES + TCP_BYTES ))

python3 -c "
import json, datetime
print(json.dumps({
    'available': True,
    'timestamp': datetime.datetime.now(datetime.UTC).isoformat(),
    'intercepted_queries': $TOTAL_PKTS,
    'intercepted_bytes': $TOTAL_BYTES,
    'udp_queries': $UDP_PKTS,
    'tcp_queries': $TCP_PKTS,
}, indent=2))
" > "$OUTPUT"

# Zero counters so tomorrow's run gets a clean daily delta
sudo iptables -t nat -Z DNS_INTERCEPT 2>/dev/null || true

echo "Intercept stats dumped: ${TOTAL_PKTS} queries intercepted"

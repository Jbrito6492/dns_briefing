#!/usr/bin/env bash
set -euo pipefail

TARGET="ubuntu@mav"
REMOTE_DIR="/home/ubuntu/dns_briefing"

rsync -av --delete \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.venv' \
  --exclude='tests/' \
  --exclude='docs/' \
  --exclude='*.db' \
  --exclude='reports/' \
  --exclude='data/' \
  --exclude='.env*' \
  --exclude='config.local.toml' \
  "$(dirname "$0")/" "$TARGET:$REMOTE_DIR/"

ssh "$TARGET" "cd $REMOTE_DIR && docker build -t dns-briefing:latest ."
echo "Deploy complete."

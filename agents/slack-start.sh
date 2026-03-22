#!/bin/bash
# Start VNC + Chrome with Slack for slack-cli.py

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/chrome-app-start.sh" \
  "Slack" \
  "https://app.slack.com" \
  "${SLACK_CDP_PORT:-9223}" \
  "${SLACK_CHROME_DATA_DIR:-$HOME/.config/agent-tools/chrome-slack}" \
  "${SLACK_CHROME_LOG:-/tmp/slack-chrome.log}" \
  "python3 ~/slack-cli.py channels" \
  "${SLACK_VNC_DISPLAY:-:3}" \
  "${SLACK_VNC_PORT:-5903}"
# Port map: VNC :3/5903, CDP 9223

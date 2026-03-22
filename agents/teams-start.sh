#!/bin/bash
# Start VNC + Chrome with Teams for teams-cli.py

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/chrome-app-start.sh" \
  "Teams" \
  "https://teams.microsoft.com" \
  "${TEAMS_CDP_PORT:-9222}" \
  "${TEAMS_CHROME_DATA_DIR:-$HOME/.config/agent-tools/chrome-teams}" \
  "${TEAMS_CHROME_LOG:-/tmp/teams-chrome.log}" \
  "python3 ~/teams-cli.py chats" \
  "${TEAMS_VNC_DISPLAY:-:2}" \
  "${TEAMS_VNC_PORT:-5902}"
# Port map: VNC :2/5902, CDP 9222

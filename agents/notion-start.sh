#!/bin/bash
# Start VNC + Chrome with Notion for notion-browser-cli.py

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/chrome-app-start.sh" \
  "Notion" \
  "https://www.notion.so/" \
  "${NOTION_CDP_PORT:-9225}" \
  "${NOTION_CHROME_DATA_DIR:-$HOME/.config/agent-tools/chrome-notion}" \
  "${NOTION_CHROME_LOG:-/tmp/notion-chrome.log}" \
  "python3 ~/notion-browser-cli.py status" \
  "${NOTION_VNC_DISPLAY:-:5}" \
  "${NOTION_VNC_PORT:-5905}"
# Port map: VNC :5/5905, CDP 9225

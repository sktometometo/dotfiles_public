#!/bin/bash
# Start VNC + Chrome with freee accounting/tax flow on an isolated profile.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/chrome-app-start.sh" \
  "freee" \
  "https://secure.freee.co.jp/annual_reports/final_return/wizards" \
  "${FREEE_CDP_PORT:-9225}" \
  "${FREEE_CHROME_DATA_DIR:-$HOME/.config/agent-tools/chrome-freee}" \
  "${FREEE_CHROME_LOG:-/tmp/freee-chrome.log}" \
  "CHROME_SITE_CDP_URL=http://localhost:${FREEE_CDP_PORT:-9225} CHROME_SITE_MATCH_URL=secure.freee.co.jp python3 ~/chrome-site-cli.py targets" \
  "${FREEE_VNC_DISPLAY:-:4}" \
  "${FREEE_VNC_PORT:-5904}"

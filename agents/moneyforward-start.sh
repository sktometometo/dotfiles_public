#!/bin/bash
# Start VNC + Chrome with Money Forward for moneyforward-cli.py

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/chrome-app-start.sh" \
  "Money Forward" \
  "https://moneyforward.com/" \
  "${MONEYFORWARD_CDP_PORT:-9224}" \
  "${MONEYFORWARD_CHROME_DATA_DIR:-/tmp/chrome-moneyforward}" \
  "${MONEYFORWARD_CHROME_LOG:-/tmp/moneyforward-chrome.log}" \
  "python3 ~/moneyforward-cli.py status" \
  "${MONEYFORWARD_VNC_DISPLAY:-:2}" \
  "${MONEYFORWARD_VNC_PORT:-5902}"

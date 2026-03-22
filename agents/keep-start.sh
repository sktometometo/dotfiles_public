#!/bin/bash
# Start VNC + Chrome with Google Keep for keep-cli.py

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/chrome-app-start.sh" \
  "Google Keep" \
  "https://keep.google.com" \
  "${KEEP_CDP_PORT:-9221}" \
  "${KEEP_CHROME_DATA_DIR:-/tmp/chrome-keep}" \
  "${KEEP_CHROME_LOG:-/tmp/keep-chrome.log}" \
  "python3 ~/keep-cli.py list" \
  "${KEEP_VNC_DISPLAY:-:1}" \
  "${KEEP_VNC_PORT:-5901}"

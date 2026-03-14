#!/bin/bash
# Start Chrome with Notion on an existing X display for notion-browser-cli.py

set -euo pipefail

DISPLAY_ID="${NOTION_DISPLAY:-:2}"
CDP_PORT="${NOTION_CDP_PORT:-9226}"
CHROME_DATA_DIR="${NOTION_CHROME_DATA_DIR:-$HOME/.config/agent-tools/chrome-notion}"
CHROME_LOG="${NOTION_CHROME_LOG:-/tmp/notion-chrome.log}"

if [ ! -S "/tmp/.X11-unix/X${DISPLAY_ID#:}" ]; then
  echo "ERROR: display ${DISPLAY_ID} is not available."
  echo "Available X sockets:"
  ls -1 /tmp/.X11-unix 2>/dev/null || true
  exit 1
fi

mkdir -p "$CHROME_DATA_DIR"

DISPLAY="$DISPLAY_ID" XAUTHORITY="${NOTION_XAUTHORITY:-$HOME/.Xauthority}" \
  setsid -f google-chrome \
  --remote-debugging-port="$CDP_PORT" \
  --no-first-run \
  --disable-gpu \
  --disable-software-rasterizer \
  --disable-dev-shm-usage \
  --no-sandbox \
  --password-store=basic \
  --user-data-dir="$CHROME_DATA_DIR" \
  "https://www.notion.so/" >"$CHROME_LOG" 2>&1

sleep 5

if curl -s "http://127.0.0.1:$CDP_PORT/json/version" >/dev/null 2>&1; then
  echo "Chrome CDP ready at http://127.0.0.1:$CDP_PORT on display $DISPLAY_ID"
  echo "Use: python3 ~/notion-browser-cli.py status"
else
  echo "ERROR: Chrome CDP not responding on port $CDP_PORT"
  echo "Log: $CHROME_LOG"
  exit 1
fi

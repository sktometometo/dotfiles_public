#!/bin/bash
# Start or reuse an xpra session that serves only the dedicated freee Chrome window.

set -euo pipefail

XPRA_DISPLAY="${FREEE_XPRA_DISPLAY:-:14}"
XPRA_HTML_BIND="${FREEE_XPRA_HTML_BIND:-127.0.0.1:14500}"
FREEE_CDP_PORT="${FREEE_CDP_PORT:-9225}"
FREEE_PROFILE_DIR="${FREEE_CHROME_DATA_DIR:-$HOME/.config/agent-tools/chrome-freee}"
FREEE_LOG_FILE="${FREEE_CHROME_LOG:-/tmp/freee-chrome.log}"
STATE_DIR="${CHROME_APP_STATE_DIR:-$HOME/.cache/agent-tools/chrome-sessions}"
STATE_FILE="${FREEE_XPRA_STATE_FILE:-$STATE_DIR/freee-xpra.json}"
CHROME_BIN="${CHROME_APP_CHROME_BIN:-google-chrome}"
APP_URL="${FREEE_URL:-https://secure.freee.co.jp/annual_reports/final_return/wizards}"

mkdir -p "$STATE_DIR" "$FREEE_PROFILE_DIR"

write_state() {
  cat >"$STATE_FILE" <<EOF
{
  "app_name": "freee-xpra",
  "xpra_display": "$XPRA_DISPLAY",
  "html_bind": "$XPRA_HTML_BIND",
  "html_url": "http://$XPRA_HTML_BIND/",
  "cdp_port": $FREEE_CDP_PORT,
  "cdp_url": "http://localhost:$FREEE_CDP_PORT",
  "profile_dir": "$FREEE_PROFILE_DIR",
  "log_file": "$FREEE_LOG_FILE"
}
EOF
}

if xpra info "$XPRA_DISPLAY" >/dev/null 2>&1; then
  write_state
  echo "Reusing existing xpra session for freee"
  echo "HTML5 client: http://$XPRA_HTML_BIND/"
  echo "Chrome CDP: http://localhost:$FREEE_CDP_PORT"
  echo "Session state saved to $STATE_FILE"
  exit 0
fi

xpra stop "$XPRA_DISPLAY" >/dev/null 2>&1 || true
pkill -f -- "Xvfb-for-Xpra-$XPRA_DISPLAY" 2>/dev/null || true
rm -f "/tmp/.X${XPRA_DISPLAY#:}-lock" "/tmp/.X11-unix/X${XPRA_DISPLAY#:}" 2>/dev/null || true

# Stop any existing Chrome using the same dedicated profile so session files are reusable.
pkill -f -- "--user-data-dir=$FREEE_PROFILE_DIR" 2>/dev/null || true
for _ in $(seq 1 20); do
  if ! pgrep -f -- "--user-data-dir=$FREEE_PROFILE_DIR" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

START_CHILD="$CHROME_BIN --remote-debugging-port=$FREEE_CDP_PORT --no-first-run --disable-gpu --disable-software-rasterizer --disable-dev-shm-usage --no-sandbox --password-store=basic --user-data-dir=$FREEE_PROFILE_DIR $APP_URL"

xpra start "$XPRA_DISPLAY" \
  --daemon=yes \
  --mdns=no \
  --notifications=no \
  --pulseaudio=no \
  --webcam=no \
  --speaker=off \
  --microphone=off \
  --clipboard=yes \
  --printing=no \
  --file-transfer=no \
  --open-files=no \
  --open-url=no \
  --bind-tcp="$XPRA_HTML_BIND" \
  --html=on \
  --exit-with-children=yes \
  --start-child="$START_CHILD" \
  --log-file=/tmp/freee-xpra.log

write_state
echo "xpra session started for freee"
echo "HTML5 client: http://$XPRA_HTML_BIND/"
echo "Chrome CDP: http://localhost:$FREEE_CDP_PORT"
echo "Session state saved to $STATE_FILE"

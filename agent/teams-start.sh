#!/bin/bash
# Start VNC + Chrome with Teams for teams-cli.py
# Usage: ~/teams-start.sh
#   Then connect VNC at localhost:5901 to login if needed.
#   After login: python3 ~/teams-cli.py chats

set -e

VNC_DISPLAY=":1"
VNC_PORT=5901
CDP_PORT=9222
CHROME_DATA_DIR="/tmp/chrome-teams3"

# Kill existing sessions
pkill -9 chrome 2>/dev/null || true
vncserver -kill "$VNC_DISPLAY" 2>/dev/null || true
sleep 2

# Start VNC
vncserver "$VNC_DISPLAY" -geometry 1920x1080 -depth 24 -xstartup /usr/bin/xterm 2>&1
echo "VNC started on port $VNC_PORT (display $VNC_DISPLAY)"
echo "  Connect: vncviewer localhost:$VNC_PORT"
echo "  SSH tunnel: ssh -L $VNC_PORT:localhost:$VNC_PORT <host>"

# Wait for VNC
sleep 2

# Start Chrome
DISPLAY="$VNC_DISPLAY" google-chrome \
  --remote-debugging-port="$CDP_PORT" \
  --no-first-run \
  --disable-gpu \
  --disable-software-rasterizer \
  --disable-dev-shm-usage \
  --no-sandbox \
  --user-data-dir="$CHROME_DATA_DIR" \
  "https://teams.microsoft.com" &>/dev/null &

echo "Chrome starting on display $VNC_DISPLAY with CDP on port $CDP_PORT..."
sleep 5

# Verify
if curl -s "http://localhost:$CDP_PORT/json/version" >/dev/null 2>&1; then
  echo "Chrome CDP ready at http://localhost:$CDP_PORT"
  echo ""
  echo "If first time, connect via VNC to login to Teams."
  echo "Then use: python3 ~/teams-cli.py chats"
else
  echo "ERROR: Chrome CDP not responding. Check VNC display."
  exit 1
fi

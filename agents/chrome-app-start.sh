#!/bin/bash
# Start a dedicated VNC + Chrome session for an app-specific CLI.

set -euo pipefail

if [ "$#" -lt 6 ]; then
  echo "Usage: chrome-app-start.sh <app-name> <url> <cdp-port> <profile-dir> <log-file> <hint-command> [vnc-display] [vnc-port]"
  exit 1
fi

APP_NAME="$1"
APP_URL="$2"
CDP_PORT="$3"
CHROME_DATA_DIR="$4"
LOG_FILE="$5"
HINT_COMMAND="$6"
VNC_DISPLAY="${7:-:1}"
VNC_PORT="${8:-5901}"
XSTARTUP_SCRIPT="$HOME/.vnc/xstartup-agent"

mkdir -p "$HOME/.vnc"
cat >"$XSTARTUP_SCRIPT" <<'EOF'
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
export XDG_SESSION_TYPE=x11
export XDG_CURRENT_DESKTOP=XFCE
exec dbus-launch --exit-with-session startxfce4
EOF
chmod 755 "$XSTARTUP_SCRIPT"

vncserver -kill "$VNC_DISPLAY" 2>/dev/null || true
sleep 2

vncserver "$VNC_DISPLAY" -geometry 1920x1080 -depth 24 -xstartup "$XSTARTUP_SCRIPT" 2>&1
echo "VNC started on port $VNC_PORT (display $VNC_DISPLAY) for $APP_NAME"
echo "  Connect: vncviewer localhost:$VNC_PORT"
echo "  SSH tunnel: ssh -L $VNC_PORT:localhost:$VNC_PORT <host>"

echo "Waiting for desktop session on $VNC_DISPLAY..."
sleep 8

DISPLAY="$VNC_DISPLAY" setsid -f google-chrome \
  --remote-debugging-port="$CDP_PORT" \
  --no-first-run \
  --disable-gpu \
  --disable-software-rasterizer \
  --disable-dev-shm-usage \
  --no-sandbox \
  --password-store=basic \
  --user-data-dir="$CHROME_DATA_DIR" \
  "$APP_URL" >"$LOG_FILE" 2>&1 &

echo "Chrome starting on display $VNC_DISPLAY with CDP on port $CDP_PORT..."
for _ in $(seq 1 20); do
  if curl -s "http://localhost:$CDP_PORT/json/version" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if curl -s "http://localhost:$CDP_PORT/json/version" >/dev/null 2>&1; then
  echo "Chrome CDP ready at http://localhost:$CDP_PORT"
  echo ""
  echo "If first time, connect via VNC to login to $APP_NAME."
  echo "Then use: $HINT_COMMAND"
else
  echo "ERROR: Chrome CDP not responding. Check VNC display."
  echo "Log: $LOG_FILE"
  exit 1
fi

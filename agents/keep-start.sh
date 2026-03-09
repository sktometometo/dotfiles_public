#!/bin/bash
# Start VNC + Chrome with Google Keep for keep-cli.py

set -e

VNC_DISPLAY=":1"
VNC_PORT=5901
CDP_PORT=9222
CHROME_DATA_DIR="/tmp/chrome-keep"
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

pkill -9 chrome 2>/dev/null || true
vncserver -kill "$VNC_DISPLAY" 2>/dev/null || true
sleep 2

vncserver "$VNC_DISPLAY" -geometry 1920x1080 -depth 24 -xstartup "$XSTARTUP_SCRIPT" 2>&1
echo "VNC started on port $VNC_PORT (display $VNC_DISPLAY)"
echo "  Connect: vncviewer localhost:$VNC_PORT"
echo "  SSH tunnel: ssh -L $VNC_PORT:localhost:$VNC_PORT <host>"

echo "Waiting for desktop session on $VNC_DISPLAY..."
sleep 8

DISPLAY="$VNC_DISPLAY" nohup google-chrome \
  --remote-debugging-port="$CDP_PORT" \
  --no-first-run \
  --disable-gpu \
  --disable-software-rasterizer \
  --disable-dev-shm-usage \
  --no-sandbox \
  --user-data-dir="$CHROME_DATA_DIR" \
  "https://keep.google.com" >/tmp/keep-chrome.log 2>&1 &

echo "Chrome starting on display $VNC_DISPLAY with CDP on port $CDP_PORT..."
for _ in $(seq 1 15); do
  if curl -s "http://localhost:$CDP_PORT/json/version" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if curl -s "http://localhost:$CDP_PORT/json/version" >/dev/null 2>&1; then
  echo "Chrome CDP ready at http://localhost:$CDP_PORT"
  echo ""
  echo "If first time, connect via VNC to login to Google Keep."
  echo "Then use: python3 ~/keep-cli.py list"
else
  echo "ERROR: Chrome CDP not responding. Check VNC display."
  echo "Log: /tmp/keep-chrome.log"
  exit 1
fi

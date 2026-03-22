#!/bin/bash
# Start noVNC (websockify) proxies for all agent VNC displays.
# Access each display from a web browser.
#
# Usage:
#   ~/novnc-start.sh          # start all
#   ~/novnc-start.sh stop     # stop all
#   ~/novnc-start.sh status   # show running proxies
#
# Web ports: 6080 + display number
#   :1  → http://localhost:6081
#   :2  → http://localhost:6082
#   ...
#   :11 → http://localhost:6091

set -euo pipefail

NOVNC_DIR="${NOVNC_DIR:-$HOME/.local/share/noVNC}"
PIDDIR="$HOME/.local/state/novnc"
mkdir -p "$PIDDIR"

# ── Port map ──
# Format: "display vnc_port web_port label"
DISPLAYS=(
  "1  5901 6081 Keep"
  "2  5902 6082 Teams"
  "3  5903 6083 Slack"
  "4  5904 6084 MoneyForward"
  "5  5905 6085 Notion"
  "11 5911 6091 Concur"
)

cmd="${1:-start}"

stop_all() {
  for entry in "${DISPLAYS[@]}"; do
    read -r disp vnc_port web_port label <<< "$entry"
    pidfile="$PIDDIR/novnc-$disp.pid"
    if [ -f "$pidfile" ]; then
      pid=$(cat "$pidfile")
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        echo "Stopped :$disp ($label) — was pid $pid"
      fi
      rm -f "$pidfile"
    fi
  done
}

start_all() {
  if [ ! -f "$NOVNC_DIR/vnc.html" ]; then
    echo "ERROR: noVNC not found at $NOVNC_DIR"
    echo "Install: git clone --depth 1 https://github.com/novnc/noVNC.git $NOVNC_DIR"
    exit 1
  fi
  if ! command -v websockify &>/dev/null; then
    echo "ERROR: websockify not found"
    echo "Install: pip3 install --user websockify"
    exit 1
  fi

  # Generate portal page
  generate_portal

  for entry in "${DISPLAYS[@]}"; do
    read -r disp vnc_port web_port label <<< "$entry"
    pidfile="$PIDDIR/novnc-$disp.pid"

    # Skip if already running
    if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
      echo "Already running: :$disp ($label) → http://localhost:$web_port"
      continue
    fi

    # Check if VNC is actually listening
    if ! ss -tlnp 2>/dev/null | grep -q ":$vnc_port " && \
       ! [ -S "/tmp/.X11-unix/X$disp" ]; then
      echo "Skipped: :$disp ($label) — VNC port $vnc_port not listening"
      continue
    fi

    websockify \
      --web="$NOVNC_DIR" \
      --daemon \
      "$web_port" \
      "localhost:$vnc_port" \
      2>/dev/null

    # Find the PID (websockify daemonizes)
    sleep 0.3
    pid=$(ss -tlnp 2>/dev/null | grep ":$web_port " | grep -oP 'pid=\K[0-9]+' | head -1 || true)
    if [ -n "$pid" ]; then
      echo "$pid" > "$pidfile"
      echo "Started: :$disp ($label) → http://localhost:$web_port  (pid $pid)"
    else
      echo "Warning: :$disp ($label) — websockify may not have started on port $web_port"
    fi
  done

  echo ""
  echo "Portal: http://localhost:6080/portal.html"
  echo "  or open individual displays with the URLs above."
}

show_status() {
  printf "%-6s %-15s %-8s %-8s %s\n" "Disp" "Tool" "WebPort" "PID" "Status"
  printf "%-6s %-15s %-8s %-8s %s\n" "----" "----" "-------" "---" "------"
  for entry in "${DISPLAYS[@]}"; do
    read -r disp vnc_port web_port label <<< "$entry"
    pidfile="$PIDDIR/novnc-$disp.pid"
    if [ -f "$pidfile" ]; then
      pid=$(cat "$pidfile")
      if kill -0 "$pid" 2>/dev/null; then
        status="running"
      else
        status="dead"
        pid="-"
      fi
    else
      pid="-"
      status="stopped"
    fi
    printf ":%-5s %-15s %-8s %-8s %s\n" "$disp" "$label" "$web_port" "$pid" "$status"
  done
}

generate_portal() {
  local portal="$NOVNC_DIR/portal.html"
  cat > "$portal" << 'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent VNC Portal</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; background: #1a1a2e; color: #e0e0e0; }
  h1 { color: #eee; border-bottom: 1px solid #333; padding-bottom: 12px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; margin-top: 20px; }
  .card { background: #16213e; border: 1px solid #0f3460; border-radius: 8px; padding: 20px; text-decoration: none; color: #e0e0e0; transition: transform 0.15s, box-shadow 0.15s; }
  .card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.4); border-color: #e94560; }
  .card h2 { margin: 0 0 8px 0; font-size: 1.1em; color: #fff; }
  .card .port { color: #888; font-size: 0.85em; font-family: monospace; }
  .section { margin-top: 32px; }
  .section h3 { color: #aaa; font-size: 0.9em; text-transform: uppercase; letter-spacing: 1px; }
</style>
</head>
<body>
<h1>Agent VNC Portal</h1>

<div class="section">
<h3>Personal Tools</h3>
<div class="grid">
  <a class="card" href="/vnc.html?autoconnect=true&port=6081"><h2>Keep</h2><div class="port">:1 &mdash; port 6081</div></a>
  <a class="card" href="/vnc.html?autoconnect=true&port=6082"><h2>Teams</h2><div class="port">:2 &mdash; port 6082</div></a>
  <a class="card" href="/vnc.html?autoconnect=true&port=6083"><h2>Slack</h2><div class="port">:3 &mdash; port 6083</div></a>
  <a class="card" href="/vnc.html?autoconnect=true&port=6084"><h2>MoneyForward</h2><div class="port">:4 &mdash; port 6084</div></a>
  <a class="card" href="/vnc.html?autoconnect=true&port=6085"><h2>Notion</h2><div class="port">:5 &mdash; port 6085</div></a>
</div>
</div>

<div class="section">
<h3>Work Tools (pfr-mics-tools)</h3>
<div class="grid">
  <a class="card" href="/vnc.html?autoconnect=true&port=6091"><h2>Concur</h2><div class="port">:11 &mdash; port 6091</div></a>
</div>
</div>

</body>
</html>
HTMLEOF
}

case "$cmd" in
  start)   start_all ;;
  stop)    stop_all ;;
  status)  show_status ;;
  restart) stop_all; sleep 1; start_all ;;
  *)       echo "Usage: $0 {start|stop|status|restart}" ;;
esac

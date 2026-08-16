#!/bin/bash
# Start noVNC (websockify) proxies for all agent VNC displays.
# Access each display from a web browser.
#
# Usage:
#   ~/novnc-start.sh          # start all
#   ~/novnc-start.sh stop     # stop all
#   ~/novnc-start.sh status   # show running proxies
#   ~/novnc-start.sh portal   # only regenerate portal.html
#
# Web ports: 6080 + display number
#   :1  → http://localhost:6081
#   :2  → http://localhost:6082
#   ...
#   :11 → http://localhost:6091

set -euo pipefail

SCRIPT_PATH="$(readlink -f "$0")"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")"; pwd)"
SERVICES_FILE="${AGENT_SERVICES_FILE:-$SCRIPT_DIR/services.json}"
NOVNC_DIR="${NOVNC_DIR:-$HOME/.local/share/noVNC}"
WEBSOCKIFY_BIN="${WEBSOCKIFY_BIN:-}"
if [ -z "$WEBSOCKIFY_BIN" ]; then
  if command -v websockify &>/dev/null; then
    WEBSOCKIFY_BIN="$(command -v websockify)"
  elif [ -x "$HOME/.cache/agent-tools/moneyforward-mcp-venv/bin/websockify" ]; then
    WEBSOCKIFY_BIN="$HOME/.cache/agent-tools/moneyforward-mcp-venv/bin/websockify"
  else
    WEBSOCKIFY_BIN="websockify"
  fi
fi
PIDDIR="$HOME/.local/state/novnc"
mkdir -p "$PIDDIR"

# ── Port map ──
# services.json is the single source of truth.
if [ ! -f "$SERVICES_FILE" ]; then
  echo "ERROR: service inventory not found: $SERVICES_FILE" >&2
  exit 1
fi
mapfile -t DISPLAYS < <(python3 - "$SERVICES_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    for item in json.load(handle)["services"]:
        print(item["display"], item["vnc_port"], item["novnc_port"], item["group"], item["label"])
PY
)

cmd="${1:-start}"

stop_all() {
  for entry in "${DISPLAYS[@]}"; do
    read -r disp vnc_port web_port group label <<< "$entry"
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
  if ! command -v "$WEBSOCKIFY_BIN" &>/dev/null && [ ! -x "$WEBSOCKIFY_BIN" ]; then
    echo "ERROR: websockify not found"
    echo "Install it or set WEBSOCKIFY_BIN=/path/to/websockify"
    exit 1
  fi

  # Generate portal page
  generate_portal

  for entry in "${DISPLAYS[@]}"; do
    read -r disp vnc_port web_port group label <<< "$entry"
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

    "$WEBSOCKIFY_BIN" \
      --web="$NOVNC_DIR" \
      --daemon \
      "127.0.0.1:$web_port" \
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
  echo "Portal: http://localhost:6084/portal.html"
  echo "  or open individual displays with the URLs above."
}

show_status() {
  printf "%-6s %-15s %-8s %-8s %s\n" "Disp" "Tool" "WebPort" "PID" "Status"
  printf "%-6s %-15s %-8s %-8s %s\n" "----" "----" "-------" "---" "------"
  for entry in "${DISPLAYS[@]}"; do
    read -r disp vnc_port web_port group label <<< "$entry"
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
HTMLEOF

  local entry disp vnc_port web_port group label
  for entry in "${DISPLAYS[@]}"; do
    read -r disp vnc_port web_port group label <<< "$entry"
    if [ "$group" = "personal" ]; then
      printf '  <a class="card" href="/vnc.html?autoconnect=true&amp;port=%s"><h2>%s</h2><div class="port">:%s &mdash; port %s</div></a>\n' \
        "$web_port" "$label" "$disp" "$web_port" >> "$portal"
    fi
  done

  cat >> "$portal" << 'HTMLEOF'
</div></div>
<div class="section"><h3>Work Tools</h3><div class="grid">
HTMLEOF

  for entry in "${DISPLAYS[@]}"; do
    read -r disp vnc_port web_port group label <<< "$entry"
    if [ "$group" = "work" ]; then
      printf '  <a class="card" href="/vnc.html?autoconnect=true&amp;port=%s"><h2>%s</h2><div class="port">:%s &mdash; port %s</div></a>\n' \
        "$web_port" "$label" "$disp" "$web_port" >> "$portal"
    fi
  done

  cat >> "$portal" << 'HTMLEOF'
</div></div></body></html>
HTMLEOF
}

case "$cmd" in
  start)   start_all ;;
  stop)    stop_all ;;
  status)  show_status ;;
  portal)  generate_portal; echo "Generated: $NOVNC_DIR/portal.html" ;;
  restart) stop_all; sleep 1; start_all ;;
  *)       echo "Usage: $0 {start|stop|status|portal|restart}" ;;
esac

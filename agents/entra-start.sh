#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")"; pwd)"
export CHROME_APP_VNC_SECURITY_TYPES="${ENTRA_VNC_SECURITY_TYPES:-None}"
exec "$SCRIPT_DIR/chrome-app-start.sh" \
  "Microsoft Entra" \
  "https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade" \
  "${ENTRA_CDP_PORT:-9226}" \
  "${ENTRA_CHROME_DATA_DIR:-$HOME/.config/agent-tools/chrome-entra}" \
  "${ENTRA_CHROME_LOG:-/tmp/entra-chrome.log}" \
  "Open App registrations and create the OneNote CLI public client" \
  "${ENTRA_VNC_DISPLAY:-:6}" \
  "${ENTRA_VNC_PORT:-5906}"

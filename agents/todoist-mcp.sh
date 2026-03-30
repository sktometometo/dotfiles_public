#!/bin/bash

set -euo pipefail

TOKEN_FILE="${TODOIST_API_KEY_FILE:-$HOME/.config/agent-tools/todoist-api-key.txt}"

if [ -z "${TODOIST_API_KEY:-}" ] && [ -f "$TOKEN_FILE" ]; then
    TODOIST_API_KEY="$(tr -d '\r\n' < "$TOKEN_FILE")"
    export TODOIST_API_KEY
fi

if [ -z "${TODOIST_API_KEY:-}" ]; then
    echo "TODOIST_API_KEY is not set." >&2
    echo "Set TODOIST_API_KEY or write the token to $TOKEN_FILE" >&2
    exit 1
fi

exec npx -y @doist/todoist-ai

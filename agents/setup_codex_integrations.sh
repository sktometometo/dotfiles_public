#!/bin/bash

set -euo pipefail

AGENTS_DIR="$(cd "$(dirname "$0")"; pwd)"
FREEE_SKILL_DIR="$HOME/.codex/skills/freee-api-skill"
SKILL_INSTALLER="$HOME/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py"

if ! command -v codex &>/dev/null; then
    echo "codex command not found"
    exit 1
fi

echo "Setting up Codex MCP integrations"

if codex mcp get todoist >/dev/null 2>&1; then
    echo "  todoist MCP: already configured"
else
    codex mcp add todoist -- "$AGENTS_DIR/todoist-mcp.sh"
    echo "  todoist MCP: added"
fi

if codex mcp get freee >/dev/null 2>&1; then
    echo "  freee MCP: already configured"
else
    codex mcp add freee --url https://mcp.freee.co.jp/mcp
    echo "  freee MCP: added"
fi

if [ -d "$FREEE_SKILL_DIR" ]; then
    echo "  freee-api-skill: already installed"
else
    python3 "$SKILL_INSTALLER" --repo freee/freee-mcp --path skills/freee-api-skill
    echo "  freee-api-skill: installed"
fi

echo ""
echo "Next steps:"
echo "  1. If freee is not logged in yet, run: codex mcp login freee"
echo "  2. Put your Todoist API token in: ~/.config/agent-tools/todoist-api-key.txt"
echo "  3. Restart Codex to pick up new skills."

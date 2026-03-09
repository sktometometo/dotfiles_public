#!/bin/bash
# Setup script for AI agent tools.
# Creates symlinks, installs dependencies, and initializes config.

set -e

AGENTS_DIR="$(cd "$(dirname "$0")"; pwd)"

echo "Setting up agent tools from $AGENTS_DIR"

# ── Symlinks ──
echo ""
echo "=== Symlinks ==="
for f in teams-cli.py teams-start.sh onenote-cli.py keep-cli.py gdocs-cli.py; do
    src="$AGENTS_DIR/$f"
    dst="$HOME/$f"
    if [ -f "$src" ]; then
        ln -sf "$src" "$dst"
        echo "  $dst -> $src"
    fi
done

# ── Config ──
CONFIG_DIR="$HOME/.config/agent-tools"
CONFIG_FILE="$CONFIG_DIR/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo ""
    echo "=== Config ==="
    mkdir -p "$CONFIG_DIR"
    cp "$AGENTS_DIR/config.example.json" "$CONFIG_FILE"
    echo "  Created $CONFIG_FILE (edit to add credentials)"
fi

# ── Install tools ──
echo ""
echo "=== Install tools ==="

# himalaya (Gmail CLI)
if command -v himalaya &>/dev/null; then
    echo "  himalaya: already installed ($(himalaya --version 2>/dev/null || echo 'unknown'))"
else
    read -p "  Install himalaya (Gmail CLI)? [y/N] " answer
    if [ "$answer" = "y" ]; then
        mkdir -p ~/.local/bin
        curl -sSL https://raw.githubusercontent.com/pimalaya/himalaya/master/install.sh | PREFIX=~/.local sh
        echo "  himalaya installed to ~/.local/bin/"
    fi
fi

# gcalcli (Google Calendar CLI)
if command -v gcalcli &>/dev/null; then
    echo "  gcalcli: already installed"
else
    read -p "  Install gcalcli (Google Calendar CLI)? [y/N] " answer
    if [ "$answer" = "y" ]; then
        pip3 install --user --break-system-packages gcalcli[vobject]
        echo "  gcalcli installed"
    fi
fi

# gkeepapi (Google Keep)
if python3 -c "import gkeepapi" &>/dev/null; then
    echo "  gkeepapi: already installed"
else
    read -p "  Install gkeepapi (Google Keep)? [y/N] " answer
    if [ "$answer" = "y" ]; then
        pip3 install --user --break-system-packages gkeepapi gpsoauth
        echo "  gkeepapi + gpsoauth installed"
    fi
fi

# google-api-python-client (Google Docs CLI)
if python3 -c "import googleapiclient" &>/dev/null; then
    echo "  google-api-python-client: already installed"
else
    read -p "  Install google-api-python-client (Google Docs CLI)? [y/N] " answer
    if [ "$answer" = "y" ]; then
        pip3 install --user --break-system-packages google-api-python-client google-auth-oauthlib
        echo "  google-api-python-client + google-auth-oauthlib installed"
    fi
fi

# websockets (Teams CLI dependency)
if python3 -c "import websockets" &>/dev/null; then
    echo "  websockets: already installed"
else
    read -p "  Install websockets (Teams CLI dependency)? [y/N] " answer
    if [ "$answer" = "y" ]; then
        pip3 install --user --break-system-packages websockets
        echo "  websockets installed"
    fi
fi

echo ""
echo "Agent tools setup done. See README.md for authentication setup."

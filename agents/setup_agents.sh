#!/bin/bash
# Setup script for AI agent tools.
# Creates symlinks, installs dependencies, and initializes config.

set -e

AGENTS_DIR="$(cd "$(dirname "$0")"; pwd)"

echo "Setting up agent tools from $AGENTS_DIR"

# ── Symlinks ──
echo ""
echo "=== Symlinks ==="
for f in teams-cli.py teams-start.sh onenote-cli.py keep-cli.py keep-start.sh gdocs-cli.py; do
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

# websockets (Teams / Keep CLI dependency)
if python3 -c "import websockets" &>/dev/null; then
    echo "  websockets: already installed"
else
    read -p "  Install websockets (Teams / Keep CLI dependency)? [y/N] " answer
    if [ "$answer" = "y" ]; then
        pip3 install --user --break-system-packages websockets
        echo "  websockets installed"
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

# GUI packages for Teams / Keep browser automation
missing_gui=()
for cmd in google-chrome vncserver startxfce4 dbus-launch; do
    if ! command -v "$cmd" &>/dev/null; then
        missing_gui+=("$cmd")
    fi
done

if [ "${#missing_gui[@]}" -eq 0 ]; then
    echo "  browser automation deps: already installed"
else
    echo "  browser automation deps missing: ${missing_gui[*]}"
    echo "    Install with: sudo apt install tigervnc-standalone-server xfce4 dbus-x11 google-chrome-stable"
    read -p "  Install browser automation deps on this host? [y/N] " answer
    if [ "$answer" = "y" ]; then
        sudo apt update
        sudo apt install -y tigervnc-standalone-server xfce4 dbus-x11
        if apt-cache show google-chrome-stable >/dev/null 2>&1; then
            sudo apt install -y google-chrome-stable
        else
            chrome_deb="/tmp/google-chrome-stable_current_amd64.deb"
            curl -fsSL -o "$chrome_deb" https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
            sudo apt install -y "$chrome_deb"
        fi
        echo "  browser automation deps installed"
    else
        read -p "  Show browser automation setup help (Teams / Keep)? [y/N] " answer
        if [ "$answer" = "y" ]; then
            echo "    After install:"
            echo "      ~/teams-start.sh   # Teams"
            echo "      ~/keep-start.sh    # Google Keep"
        fi
    fi
fi

echo ""
echo "Agent tools setup done. See README.md for authentication setup."

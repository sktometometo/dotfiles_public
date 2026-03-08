#!/bin/bash
# Setup script for dotfiles_public
# Creates symlinks, installs agent tools, and optionally runs sub-setup scripts.

set -e

DOTFILES_DIR="$(cd "$(dirname "$0")"; pwd)"

echo "Setting up dotfiles from $DOTFILES_DIR"

# ── Agent tools: symlinks ──
echo ""
echo "=== Agent tools: symlinks ==="
for f in teams-cli.py teams-start.sh onenote-cli.py keep-cli.py; do
    src="$DOTFILES_DIR/agent/$f"
    dst="$HOME/$f"
    if [ -f "$src" ]; then
        ln -sf "$src" "$dst"
        echo "  $dst -> $src"
    fi
done

# ── Agent tools: config ──
CONFIG_DIR="$HOME/.config/agent-tools"
CONFIG_FILE="$CONFIG_DIR/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo ""
    echo "=== Agent tools: config ==="
    mkdir -p "$CONFIG_DIR"
    cp "$DOTFILES_DIR/agent/config.example.json" "$CONFIG_FILE"
    echo "  Created $CONFIG_FILE (edit to add credentials)"
fi

# ── Agent tools: install ──
echo ""
echo "=== Agent tools: install ==="

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

# Teams CLI dependencies
if python3 -c "import websockets" &>/dev/null; then
    echo "  websockets: already installed"
else
    read -p "  Install websockets (Teams CLI dependency)? [y/N] " answer
    if [ "$answer" = "y" ]; then
        pip3 install --user --break-system-packages websockets
        echo "  websockets installed"
    fi
fi

# ── Sub-setup scripts ──
echo ""
echo "=== Sub-setup scripts ==="
for script in bashrc/setup_bashrc.sh emacs/setup_emacs.sh vim/setup_vim.sh \
              tmux/setup_tmux.sh ssh/setup_ssh.sh latex/setup_latex.sh; do
    if [ -f "$DOTFILES_DIR/$script" ]; then
        read -p "  Run $script? [y/N] " answer
        if [ "$answer" = "y" ]; then
            bash "$DOTFILES_DIR/$script"
        fi
    fi
done

echo ""
echo "Done. See README.md for authentication setup."

#!/bin/bash
# Setup script for dotfiles_public
# Creates symlinks and optionally runs sub-setup scripts.

set -e

DOTFILES_DIR="$(cd "$(dirname "$0")"; pwd)"

echo "Setting up dotfiles from $DOTFILES_DIR"

# Agent tools - symlink to home
echo ""
echo "=== Agent tools ==="
for f in teams-cli.py teams-start.sh onenote-cli.py keep-cli.py; do
    src="$DOTFILES_DIR/agent/$f"
    dst="$HOME/$f"
    if [ -f "$src" ]; then
        ln -sf "$src" "$dst"
        echo "  $dst -> $src"
    fi
done

# Sub-setup scripts
echo ""
echo "=== Sub-setup scripts ==="
for script in bashrc/setup_bashrc.sh emacs/setup_emacs.sh vim/setup_vim.sh \
              tmux/setup_tmux.sh ssh/setup_ssh.sh latex/setup_latex.sh; do
    if [ -f "$DOTFILES_DIR/$script" ]; then
        read -p "Run $script? [y/N] " answer
        if [ "$answer" = "y" ]; then
            bash "$DOTFILES_DIR/$script"
        fi
    fi
done

echo ""
echo "Done."

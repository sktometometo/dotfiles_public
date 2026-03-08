#!/bin/bash
# Setup script for dotfiles_public
# Runs sub-setup scripts interactively.

set -e

DOTFILES_DIR="$(cd "$(dirname "$0")"; pwd)"

echo "Setting up dotfiles from $DOTFILES_DIR"
echo ""

for script in agents/setup_agents.sh bashrc/setup_bashrc.sh emacs/setup_emacs.sh \
              vim/setup_vim.sh tmux/setup_tmux.sh ssh/setup_ssh.sh latex/setup_latex.sh; do
    if [ -f "$DOTFILES_DIR/$script" ]; then
        read -p "Run $script? [y/N] " answer
        if [ "$answer" = "y" ]; then
            bash "$DOTFILES_DIR/$script"
        fi
    fi
done

echo ""
echo "Done."

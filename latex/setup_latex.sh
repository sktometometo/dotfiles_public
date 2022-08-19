#!/bin/bash

# Directory
FILEDIR="$(cd $(dirname $0); pwd)" # 設定ファイルの場所

# Usage
function usage {
    cat <<EOM
Usage: $(basename "$0") [OPTIONS]...
    -h      Display help
EOM

exit 2
}

function install_latex {
    sudo apt-get install texlive-full
}

function setup_latexmkrc {
    if [ ! -e ~/.latexmkrc ]; then
        ln -sf $FILEDIR/.latexmkrc ~/.latexmkrc
    fi
}

# Options
while getopts "h" optKey; do
    case "$optKey" in
        h|* )
            usage
            ;;
    esac
done

install_latex
setup_latexmkrc

#!/bin/bash

#
# Directory
#
FILEDIR="$(cd $(dirname $0); pwd)" # 設定ファイルの場所
SRCDIR="$HOME/Sources/emacs" # source のクローン先
DESTDIR="" # インストール先 空の場合はデフォルト

# Options
readonly BUILD=false

#
# Install vim from source
#
if "${BUILD}"; then
    if [ -e /etc/debian_version ] || [ -e /etc/debian_release ]; then
        # remove emacs from apt
        sudo apt-get remove emacs
        # install requirements
        sudo apt-get install -y gcc make libxpm-dev gnutls-bin texinfo gnutils-bin
    else
        echo "Unknown distribution"
    fi

    #
    # build
    #
    if [ -e $SRCTDIR ]; then
        cd $SRCDIR
        sudo make uninstall
        git pull
    else
        mkdir -p $SRCDIR
        git clone https://github.com/emacs-mirror/emacs.git $DESTDIR
        cd $SRCDIR
        git checkout emacs-26
    fi

    if [ -n "$DSTDIR" ]; then
        ./configure --with-gnutls=no --prefix=$DSTDIR
    else
        ./configure --with-gnutls=no
    fi
    make
    sudo make install
fi

#
# config
#
if [ ! -e $HOME/.emacs.d ]; then
    mkdir $HOME/.emacs.d
    ln -s $FILEDIR/init.el $HOME/.emacs.d/init.el
else
    if [[ -L "$HOME/.emacs.d/init.el" ]]; then
        rm $HOME/.emacs.d/init.el
    else
        mv $HOME/.emacs.d/init.el $HOME/.emacs.d/init.el.bak
    fi
    ln -s $FILEDIR/init.el $HOME/.emacs.d/init.el
fi

#
# euslime
#
if [ $(lsb_release -sr) == "18.04" ]; then
    sudo apt install ros-melodic-euslime
else
    echo "euslime does not support your environment"
fi

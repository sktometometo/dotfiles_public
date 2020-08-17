#!/bin/sh

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
if [ $HOME/.emacs.d ]; then
    rm -rf $HOME/.emacs.d
fi

mkdir $HOME/.emacs.d
ln -s $FILEDIR/init.el $HOME/.emacs.d/init.el

#
# euslime
#
cd $HOME/.emacs.d
git clone https://github.com/Affonso-Gui/euslime.git
git clone https://github.com/slime/slime.git
git clone https://github.com/deadtrickster/slime-repl-ansi-color.git
sudo pip install -U -e euslime

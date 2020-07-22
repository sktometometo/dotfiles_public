#!/bin/sh

# Directory
FILEDIR="$(cd $(dirname $0); pwd)" # 設定ファイルの場所
SRCDIR="$HOME/Sources/tmux" # source のクローン先
DSTDIR="" # インストール先 空の場合はデフォルト

# Options
readonly BUILD=false

#
# Install vim from source
#
if "${BUILD}"; then
    if [ -e /etc/debian_version ] || [ -e /etc/debian_release ]; then
        ## uninstall tmux from apt
        sudo apt remove tmux
        ## install dependencies from apt
        sudo apt install -y libevent-dev libncurses-dev 
        sudo apt install -y make autoconf pkg-config automake
        sudo apt install -y bison
    else
        echo "Unknown distribution"
    fi

    ## install from source
    if [ $SRCDIR ];then
        cd $SRCDIR
        sudo make uninstall
        git pull
    else
        mkdir -p $SRCDIR
        ## clone repository and build and install
        git clone https://github.com/tmux/tmux.git $SRCDIR
        cd $SRCDIR
    fi
    sh autogeno.sh
    if [ -n "$DSTDIR" ]; then
        ./configure --prefix=$DSTDIR
    else
        ./configure
    fi
    make
    sudo make install
fi



#
# Install configuration files
#
## create symbolic link of tmux.conf
if [ $HOME/.tmux.conf ]; then
    rm $HOME/.tmux.conf
fi
ln -s $FILEDIR/tmux.conf     $HOME/.tmux.conf
## make log directory
if [ ! $HOME/.tmux/log ]; then
    mkdir -p $HOME/.tmux/log
fi

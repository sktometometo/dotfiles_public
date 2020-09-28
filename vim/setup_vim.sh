#!/bin/sh

#
# Directory
#
FILEDIR="$(cd $(dirname $0); pwd)" # 設定ファイルの場所
SRCDIR="$HOME/Sources/vim" # source のクローン先
DSTDIR="" # インストール先 空の場合はデフォルト

# Options
readonly BUILD=false

#
# Install vim from source
#
if "${BUILD}"; then
    if [ -e /etc/debian_version ] || [ -e /etc/debian_release ]; then
        # remove vim from apt
        sudo apt remove vim
        # install dependencies
        sudo apt-get install -y \
            git \
            build-essential \
            ncurses-dev \
            lua5.2 \
            lua5.2-dev \
            luajit \
            libperl-dev \
            python-dev \
            python3-dev \
            ruby-dev \
            libluajit-5.1 \
            gettext \
            libtinfo-dev
        pip3 install --user --upgrade pynvim
    elif [ -e /etc/centos-release ]; then
        #
        sudo yum update
    else
        echo "Unknown distribution"
    fi

    if [ -e $SRCDIR ]; then
        cd $SRCDIR
        sudo make uninstall
        git pull
    else
        mkdir -p $SRCDIR
        git clone https://github.com/vim/vim.git $SRCDIR
        cd $SRCDIR
    fi
    if [ -n "$DSTDIR" ]; then
        ./configure \
            --with-features=huge \
            --enable-gui=gtk2 \
            --enable-perlinterp \
            --enable-pythoninterp \
            --enable-python3interp \
            --enable-rubyinterp \
            --enable-luainterp \
            --with-luajit \
            --enable-fail-if-missing \
            --prefix=$DSTDIR
    else
        ./configure \
            --with-features=huge \
            --enable-gui=gtk2 \
            --enable-perlinterp \
            --enable-pythoninterp \
            --enable-python3interp \
            --enable-rubyinterp \
            --enable-luainterp \
            --with-luajit \
            --enable-fail-if-missing
    fi
    make
    sudo make install
fi



#
# Install required packages for vim8
#
pip3 install --user pynvim



#
# Install configuration files for vim8
#
if [ -e $HOME/.vimrc ]; then
    rm -rf $HOME/.vimrc
fi
if [ -e $HOME/.vim ]; then
    rm -rf $HOME/.vim
fi
if [ -e $HOME/.config/nvim/init.vim ]; then
    rm -rf $HOME/.config/nvim/init.vim
fi
if [ ! -e $HOME/.config/nvim ] ;then
    mkdir -p $HOME/.config/nvim
fi
ln -s $FILEDIR/vimrc $HOME/.vimrc
ln -s $FILEDIR/vim   $HOME/.vim
ln -s $FILEDIR/init.vim $HOME/.config/nvim/init.vim

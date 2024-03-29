#!/bin/bash

# Usage
function usage {
    cat <<EOM
Usage: $(basename "$0") [OPTIONS]...
    -h      Display help
    -b      Build vim from source
    -s      Skip vim install (just config installation)
EOM

exit 2
}

BUILD=false
SKIP_INSTALL=0

# Options
while getopts "bhs" optKey; do
    case "$optKey" in
        b)
            BUILD=true
            ;;
        s)
            SKIP_INSTALL=1
            ;;
        h|* )
            usage
            ;;
    esac
done

# Directory
FILEDIR="$(cd $(dirname $0); pwd)" # 設定ファイルの場所
SRCDIR="$HOME/Sources/vim" # source のクローン先
DSTDIR="" # インストール先 空の場合はデフォルト

# Install vim from source
if [[ $SKIP_INSTALL == 0 ]];then
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
        fi

# Install required packages for vim8
echo "Installing required packages for vim8"
sudo apt install python3-pip
pip3 install --user pynvim

# Install formatter
echo "Installing formatter"
sudo apt install clang-format
sudo apt install python3-autopep8
sudo apt install tidy

# Install Deno
curl -fsSL https://deno.land/install.sh | sh
echo "export DENO_INSTALL=\"/home/sktometometo/.deno\"" >> ~/.bashrc
echo "export PATH=\"\$DENO_INSTALL/bin:\$PATH\"" >> ~/.bashrc

# Install configuration files for vim8
echo "Installing configuration files for vim8"
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

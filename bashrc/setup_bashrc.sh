#!/bin/sh

FILEDIR="$(cd $(dirname $0); pwd)/../files"

echo "FILEDIR":$FILEDIR
echo "HOME:"$HOME

# delete existing files
if [ -e $HOME/.bashrc ]; then
    rm -f  $HOME/.bashrc
fi
if [ -e $HOME/.gitconfig ]; then
    rm -f  $HOME/.gitconfig
fi

# create config bashrc file
if [ ! -e $HOME/.bashrc_config ]; then
    cp $FILEDIR/template/.bashrc_config ~/.bashrc_config
fi

# symbolic links
ln -s $FILEDIR/bashrc/.bashrc        $HOME/.bashrc
ln -s $FILEDIR/config/.gitconfig     $HOME/.gitconfig

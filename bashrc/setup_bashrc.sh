#!/bin/sh

FILEDIR="$(cd $(dirname $0); pwd)"

if [ $HOME/.bashrc ]; then
    mv $HOME/.bashrc $HOME/.bashrc_backup
fi
cp $FILEDIR/bashrc $HOME/.bashrc
cat $FILEDIR/bashrc_main >> $HOME/.bashrc

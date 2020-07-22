#!/bin/sh

#
# Directory
#
FILEDIR="$(cd $(dirname $0); pwd)" # 設定ファイルの場所
SSHCONFIGDIR="$HOME/.ssh" # home 以下の設定ファイルの場所
SSHSOURCEDIR="$HOME/Sources/openssh" # source のクローン先

#
# Install configuration files
#
## .ssh dir make
if [ ! -e $SSHCONFIGDIR/configs ]; then
    mkdir -p $SSHCONFIGDIR/configs
fi
## config link
## TODO: Opensshのバージョンに応じてシンボリックリンクを変える
if [ ! -e $SSHCONFIGDIR/config ]; then
    ln -s $FILEDIR/config $SSHCONFIGDIR/config
fi

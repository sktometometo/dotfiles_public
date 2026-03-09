# Google Keep アクセスガイド

Google Keep へのアクセスは `keep-cli.py` (Chrome CDP 経由) で行う。

`gkeepapi` / `gpsoauth` ベースの認証は不安定なため、ブラウザ自動化方式に切り替えている。

## 前提

```bash
sudo apt install tigervnc-standalone-server google-chrome-stable
pip3 install --user --break-system-packages websockets
```

## セットアップ

```bash
# 1. VNC + Chrome を起動
~/keep-start.sh

# 2. 初回のみ VNC で Google Keep にログイン
#    VNC 接続: localhost:5901
#    SSH トンネル: ssh -L 5901:localhost:5901 <host>
```

Chrome プロファイルは `/tmp/chrome-keep` に保存される。

## CLI ツール

```bash
~/keep-cli.py list                                   # 表示中のノート一覧
~/keep-cli.py list --limit 50                        # 件数指定
~/keep-cli.py search <query>                         # Keep 内検索
~/keep-cli.py open "<query>"                         # ノートを開いて読む
~/keep-cli.py read                                   # 現在開いているノートを読む
~/keep-cli.py create "タイトル" "本文"                # テキストノート作成
~/keep-cli.py dump                                   # ページ全文 (debug)
```

## 制約

- Chrome と Google Keep セッションが起動中である必要がある
- DOM 構造に依存するため、Google Keep の UI 変更で修正が必要になる
- 現状はテキストノート中心。画像、リマインダー、ラベル編集は未対応

# Slack CLI アクセスガイド

Slack へのアクセスは Chrome DevTools Protocol (CDP) 経由で DOM を読み取る方式で行う。

## アーキテクチャ

```
slack-cli.py --[CDP/WebSocket]--> Chrome (VNC :3, port 9223) ---> app.slack.com
```

## セットアップ

### 前提パッケージ

```bash
# Ubuntu/Debian
sudo apt install tigervnc-standalone-server google-chrome-stable
pip3 install --user --break-system-packages websockets
```

### 設定

`~/.config/agent-tools/config.json` にワークスペース情報を記述（任意）:

```json
{
  "slack": {
    "workspaces": {
      "myws": "Workspace Name"
    }
  }
}
```

### ファイル配置

```bash
# dotfiles_public/agents/ からホームにシンボリックリンクを張る
# (./agents/setup_agents.sh を実行すると自動で作成される)
ln -sf ~/dotfiles_public/agents/slack-cli.py ~/slack-cli.py
ln -sf ~/dotfiles_public/agents/slack-start.sh ~/slack-start.sh
```

## 起動手順

```bash
# 1. VNC + Chrome を起動
~/slack-start.sh

# 2. 初回のみ: VNC で Slack にログイン
#    VNC 接続: localhost:5903
#    SSH トンネル: ssh -L 5903:localhost:5903 <host>

# 3. CLI で操作
python3 ~/slack-cli.py channels
```

## コマンド一覧

```bash
# ワークスペース
python3 ~/slack-cli.py workspaces                   # 設定済みワークスペース一覧
python3 ~/slack-cli.py workspace <name>              # ワークスペースを切替

# チャネル・DM
python3 ~/slack-cli.py channels                      # サイドバーのチャネル/DM 一覧
python3 ~/slack-cli.py open "<name>"                  # チャネル/DM を名前で開く
python3 ~/slack-cli.py read                           # 現在のチャネルのメッセージを読む

# メッセージ送信
python3 ~/slack-cli.py post "<body>"                  # 現在のチャネルに投稿
echo "<body>" | python3 ~/slack-cli.py post -         # stdin から本文を読んで投稿

# スレッド
python3 ~/slack-cli.py thread "<query>"               # スレッドを開いて返信を読む
python3 ~/slack-cli.py reply "<body>"                  # 開いているスレッドに返信
echo "<body>" | python3 ~/slack-cli.py reply -         # stdin から本文を読んで返信

# 検索
python3 ~/slack-cli.py search "<query>"               # メッセージを検索

# その他
python3 ~/slack-cli.py goto "<url>"                   # URL 直接指定
python3 ~/slack-cli.py reload                         # ページリロード
python3 ~/slack-cli.py dump                           # ページ全テキスト (debug)
```

ワークスペースのキーと名前は `~/.config/agent-tools/config.json` の `slack.workspaces` で定義する。

## 制約・既知の問題

- VNC + Chrome が起動している必要がある
- `open` は textContent の部分一致でクリック対象を選択（最短一致）
- Chrome セッション有効中のみログイン状態を保持
- Slack 用の CDP ポート既定値は `9223`

必要なら環境変数で上書きできる。

```bash
SLACK_CDP_PORT=9325 SLACK_VNC_DISPLAY=:7 SLACK_VNC_PORT=5907 ~/slack-start.sh
SLACK_CDP_URL=http://localhost:9325 python3 ~/slack-cli.py channels
```

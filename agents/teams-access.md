# Teams CLI アクセスガイド

Microsoft Teams へのアクセスは Chrome DevTools Protocol (CDP) 経由で DOM を読み取る方式で行う。
Graph API にはチャット読み取りスコープがなく、Teams 新クライアントは Service Worker 経由のためネットワーク傍受も困難であり、DOM scraping が唯一の安定手法である。

## アーキテクチャ

```
teams-cli.py --[CDP/WebSocket]--> Chrome (VNC :2, port 9222) ---> teams.cloud.microsoft
```

## セットアップ

### 前提パッケージ

```bash
# Ubuntu/Debian
sudo apt install tigervnc-standalone-server google-chrome-stable
pip3 install --user --break-system-packages websockets
```

### 設定

1. `~/.config/agent-tools/config.json` に組織情報を記述（テンプレート: `config.example.json`）
2. `./setup.sh` でシンボリックリンクを作成

### ファイル配置

```bash
# dotfiles_public/agents/ からホームにシンボリックリンクを張る
# (./agents/setup_agents.sh を実行すると自動で作成される)
ln -sf ~/dotfiles_public/agents/teams-cli.py ~/teams-cli.py
ln -sf ~/dotfiles_public/agents/teams-start.sh ~/teams-start.sh
```

## 起動手順

```bash
# 1. VNC + Chrome を起動
~/teams-start.sh

# 2. 初回のみ: VNC で Teams にログイン
#    VNC 接続: localhost:5902
#    SSH トンネル: ssh -L 5902:localhost:5902 <host>

# 3. CLI で操作
python3 ~/teams-cli.py chats
```

## コマンド一覧

```bash
# 組織切り替え
python3 ~/teams-cli.py orgs                              # 利用可能な組織一覧
python3 ~/teams-cli.py org <key>                          # 組織を切替

# チャット
python3 ~/teams-cli.py chats                              # チャット一覧
python3 ~/teams-cli.py open "<name>"                      # チャットを名前で開く
python3 ~/teams-cli.py read                               # 現在開いているチャットを読む

# チーム・チャネル
python3 ~/teams-cli.py teams                              # チーム・チャネル一覧
python3 ~/teams-cli.py team <team> <channel>              # チームのチャネルを開いて読む
python3 ~/teams-cli.py team <team>                        # デフォルトで「一般」チャネル

# その他
python3 ~/teams-cli.py post "<body>"                          # 現在のチャネルに投稿
python3 ~/teams-cli.py post -s "<subject>" "<body>"           # 件名付きで投稿
echo "<body>" | python3 ~/teams-cli.py post -               # stdin から本文を読んで投稿
python3 ~/teams-cli.py post -s "<subject>" -                  # stdin + 件名
python3 ~/teams-cli.py thread "<query>"                       # スレッドを開いて返信を読む
python3 ~/teams-cli.py goto "<url>"                       # URL 直接指定
python3 ~/teams-cli.py dump                               # ページ全テキスト (debug)
```

組織のキーと名前は `~/.config/agent-tools/config.json` の `teams.orgs` で定義する。

## MCP サーバー (Graph API 不要の外部テナント向け)

`teams-cli.py` と同じロジックを MCP (Model Context Protocol) サーバーとしても提供している。
Graph API のチャット読み取りスコープが無効な外部テナントでも、Teams 新クライアントの
DOM を CDP 経由で読む方式のため利用可能。Claude Code に限らず、stdio 対応の MCP クライアント
（Claude Desktop 等）から `tool_use` として直接呼び出せる。

実体: `~/dotfiles_public/agents/teams-mcp-server.py`（`~/teams-mcp-server.py` にシンボリックリンク）
依存: `pip3 install --user --break-system-packages mcp`（`setup_agents.sh` でインストール確認可）

### 起動前提

`teams-cli.py` と同じく、事前に `~/teams-start.sh` で VNC + Chrome を起動し、Teams にログイン済みであること。

### Claude Code への登録

```bash
claude mcp add teams -- python3 ~/teams-mcp-server.py
```

または `~/.claude.json` / プロジェクトの `.mcp.json` に直接:

```json
{
  "mcpServers": {
    "teams": {
      "command": "python3",
      "args": ["/home/shinjo/teams-mcp-server.py"]
    }
  }
}
```

### 提供ツール

`teams-cli.py` の各コマンドに対応する形で以下を公開している。

- `teams_orgs` / `teams_switch_org(org_key)`
- `teams_list_chats` / `teams_list_teams`
- `teams_open_channel(team_name, channel_name)` / `teams_open_chat(name)`
- `teams_read_current` / `teams_read_thread(query)` / `teams_goto(url)`
- `teams_post(body, subject)`
- `teams_copy_message_link(query)`
- `teams_reload` / `teams_dump_page`
- `teams_screenshot(out_path, full_page)` / `teams_save_images(out_dir)`

### 動作確認 (単体)

```bash
python3 ~/dotfiles_public/agents/teams-mcp-server.py
# stdio で待受する。手動テストは MCP クライアント経由 (ClientSession) で行う。
```

### 制約

`teams-cli.py` と同じ制約（VNC/Chrome 常駐必須、CDP ポート既定 9222 など）を継承する。
各ツール呼び出しごとに CDP 接続を張り直す実装のため、連続呼び出し時のレイテンシは
CLI を都度起動する場合と同程度。

## SharePoint ファイルダウンロード

Teams チャネルに添付されたファイルは SharePoint に保存されている。CDP 経由でブラウザの localStorage からトークンを取得し、SharePoint REST API でダウンロード可能。

### トークン取得

```python
# CDP evaluate で localStorage から MSAL キャッシュの .secret を取得
# key に対象ドメインと "sharepoint" を含むエントリ（-my. を除外）
```

### ファイルダウンロード

```python
SP_SITE = "https://<tenant>.sharepoint.com/sites/<site_id>"

# ファイルダウンロード
api_url = f"{SP_SITE}/_api/web/GetFileByServerRelativeUrl('{encoded_path}')/$value"
# Authorization: Bearer {token}

# フォルダ一覧
api_url = f"{SP_SITE}/_api/web/GetFolderByServerRelativeUrl('{encoded_folder}')/Files"
```

チャネルフォルダパス: `Shared Documents/{チャネル名}`

## 制約・既知の問題

- VNC + Chrome が起動している必要がある
- `open` は textContent の部分一致でクリック対象を選択（最短一致）
- Chromeセッションは`~/.config/agent-tools/chrome-teams`に保持する。ディレクトリには認証状態が含まれるため共有・commitしない
- Teams 用の CDP ポート既定値は `9222`

必要なら環境変数で上書きできる。

```bash
TEAMS_CDP_PORT=9324 TEAMS_VNC_DISPLAY=:6 TEAMS_VNC_PORT=5906 ~/teams-start.sh
TEAMS_CDP_URL=http://localhost:9324 python3 ~/teams-cli.py chats
```
- 大容量ファイル（100MB超）は base64 変換タイムアウトの可能性あり

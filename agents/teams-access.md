# Teams CLI アクセスガイド

Microsoft Teams へのアクセスは Chrome DevTools Protocol (CDP) 経由で DOM を読み取る方式で行う。
Graph API にはチャット読み取りスコープがなく、Teams 新クライアントは Service Worker 経由のためネットワーク傍受も困難であり、DOM scraping が唯一の安定手法である。

## アーキテクチャ

```
teams-cli.py --[CDP/WebSocket]--> Chrome (VNC :1, port 9222) ---> teams.cloud.microsoft
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
#    VNC 接続: localhost:5901
#    SSH トンネル: ssh -L 5901:localhost:5901 <host>

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
python3 ~/teams-cli.py goto "<url>"                       # URL 直接指定
python3 ~/teams-cli.py dump                               # ページ全テキスト (debug)
```

組織のキーと名前は `~/.config/agent-tools/config.json` の `teams.orgs` で定義する。

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
- Chrome セッション有効中のみトークンを保持（`/tmp/chrome-teams3` に永続化）
- 大容量ファイル（100MB超）は base64 変換タイムアウトの可能性あり

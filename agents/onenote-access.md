# OneNote アクセスガイド

OneNote へのアクセスは `onenote-cli.py` (Microsoft Graph API ラッパー) で行う。

## セットアップ

1. `~/.config/agent-tools/config.json` に設定を記述（テンプレート: `config.example.json`）
2. Microsoft Entraのアプリでパブリッククライアントフローを許可し、委任権限`Notes.ReadWrite`を設定
3. Authentication > Add a platform > Mobile and desktop applicationsで`http://localhost`をredirect URIに追加
4. `~/onenote-cli.py auth`でlocalhost＋PKCEのブラウザ認証

アプリ登録画面を専用Chromeプロファイルで開く場合:

```bash
~/entra-start.sh
# VNC: localhost:5906 / noVNC: http://localhost:6086/vnc.html
```

Entra専用VNCは既定で`SecurityTypes=None`だが、VNCとnoVNCの双方をlocalhostだけにbindする。SSH tunnelまたは同一PCから利用する。パスワード認証へ戻す場合は`ENTRA_VNC_SECURITY_TYPES=VncAuth ~/entra-start.sh`を使う。

## CLI ツール

```bash
# ローカル設定診断（Graph APIは呼ばない）
~/onenote-cli.py doctor

# 閲覧
~/onenote-cli.py notebooks                        # ノートブック一覧
~/onenote-cli.py sections <notebook>               # セクション一覧
~/onenote-cli.py pages <section>                   # ページ一覧
~/onenote-cli.py read <page_id>                    # ページ内容をテキストで取得
~/onenote-cli.py read-html <page_id>               # ページの生HTML取得 (data-id確認用)
~/onenote-cli.py search <query> --notebook <nb>    # タイトル検索

# 編集
~/onenote-cli.py append <page_id> <text|-> [--html]           # テキスト追記 (- でstdin)
~/onenote-cli.py replace <page_id> <target> <text|-> [--html] # 要素内容を置換
~/onenote-cli.py insert <page_id> <target> <text|-> [--position before|after] [--html]
                                                               # 要素の前後に挿入
~/onenote-cli.py delete-page <page_id> --yes       # ページ削除（明示確認必須）
~/onenote-cli.py patch <page_id> <json|->          # PATCH コマンドを直接送信

# 作成
~/onenote-cli.py create-page <section> <title> [--notebook NB] [--body-file PATH]
~/onenote-cli.py append-body <page_id> --body-file body.html   # 既存ページ末尾へHTML追記

# 認証
~/onenote-cli.py auth                              # 個人・組織向けブラウザ認証（PKCE）
~/onenote-cli.py auth-device                       # 対応する組織テナント向けdevice code
```

### 編集コマンドの使い方

`--html` を付けると入力をそのまま HTML として送信する。省略するとプレーンテキストを `<p>` タグに変換する。`-` を指定すると stdin から読み取る。

`replace` / `insert` の`target`は`body`（ページ本体）または`#<data-id>`（要素指定）。`read-html`は更新に必要な`includeIDs=true`を付けてHTMLを取得する。

```bash
# テキストを追記
~/onenote-cli.py append <page_id> "追記テキスト"

# stdin から HTML を追記
echo "<p>追記</p>" | ~/onenote-cli.py append <page_id> - --html

# 要素を置換
~/onenote-cli.py replace <page_id> "#p:{guid}" "新しい内容" --html
```

ノートブック名・セクション名のエイリアスは `config.json` の `onenote.notebooks` / `onenote.sections` で定義する。

環境変数`ONENOTE_CONFIG_FILE`、`ONENOTE_TOKEN_FILE`、`ONENOTE_TENANT`で設定を上書き可能。個人Microsoftアカウントは`tenant=consumers`、組織と個人の両方を許容する構成では`common`を使用する。

## 認証

`~/onenote-cli.py auth`を実行するとブラウザが開き、認証後にlocalhost callbackでauthorization codeを受け取る。CLIはPKCEを使用するためclient secretを保存しない。トークンは`config.json`の`onenote.token_file`で指定したパスへ権限`0600`で保存される。OneNote Graph APIは委任認証を使い、バックグラウンド継続利用のため`offline_access`でrefresh tokenを取得する。

`auth-device`はMicrosoft Entraの組織テナントでdevice code flowを使う場合だけ利用する。個人Microsoftアカウントでは`auth`を使用する。

## Graph API 直接アクセス（参考）

CLI を使わず Graph API を直接叩く場合:

```bash
TOKEN=$(cat <token_file> | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
# ノートブック一覧
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://graph.microsoft.com/v1.0/me/onenote/notebooks?\$select=id,displayName"
# セクション一覧 (ID 中の ! は %21 にエンコード)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://graph.microsoft.com/v1.0/me/onenote/notebooks/{NOTEBOOK_ID}/sections?\$select=id,displayName"
# ページ一覧
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://graph.microsoft.com/v1.0/me/onenote/sections/{SECTION_ID}/pages?\$select=id,title,createdDateTime,lastModifiedDateTime&\$orderby=createdDateTime%20desc&\$top=20"
```

## MCP 固有の注意事項

OneNote MCP サーバーを利用する場合の既知の制限:

| MCP ツール | 問題 |
|------------|------|
| `listNotebooks` | `displayName` ではなく `title` を参照するためノートブック名が "undefined" と表示される |
| `searchPages` / `getPageByTitle` | セクション数が多いアカウントでは "The number of maximum sections is exceeded" エラーになる |
| `authenticate` | デバイスコードフローが動作しないことがある |

ページ ID が分かれば `getPageContent` MCP ツールでも内容を取得できる:
```
mcp__onenote__getPageContent(pageId: "...", format: "text")
```

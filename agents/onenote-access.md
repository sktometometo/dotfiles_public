# OneNote アクセスガイド

OneNote へのアクセスは `onenote-cli.py` (Graph API ラッパー) で行う。

## セットアップ

1. `~/.config/agent-tools/config.json` に設定を記述（テンプレート: `config.example.json`）
2. `~/onenote-cli.py auth` で認証

## CLI ツール

```bash
~/onenote-cli.py notebooks                        # ノートブック一覧
~/onenote-cli.py sections <notebook>               # セクション一覧
~/onenote-cli.py pages <section>                   # ページ一覧
~/onenote-cli.py read <page_id>                    # ページ内容をテキストで取得
~/onenote-cli.py search <query> --notebook <nb>    # タイトル検索
~/onenote-cli.py auth                              # 認証（デバイスコードフロー）
```

ノートブック名・セクション名のエイリアスは `config.json` の `onenote.notebooks` / `onenote.sections` で定義する。

環境変数 `ONENOTE_TOKEN_FILE` でトークンファイルのパスを上書き可能。

## 認証

`~/onenote-cli.py auth` を実行するとデバイスコードフローで認証URL とコードが表示される。ユーザーにブラウザでサインインしてもらう。トークンは `config.json` の `onenote.token_file` で指定したパスに保存される。

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

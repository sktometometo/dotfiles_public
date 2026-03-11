# OneNote アクセスガイド

OneNote へのアクセスは `onenote-cli.py` (Graph API ラッパー) で行う。

## セットアップ

1. `~/.config/agent-tools/config.json` に設定を記述（テンプレート: `config.example.json`）
2. `~/onenote-cli.py auth` で認証

## CLI ツール

```bash
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
~/onenote-cli.py delete-page <page_id>             # ページ削除
~/onenote-cli.py patch <page_id> <json|->          # PATCH コマンドを直接送信

# 作成
~/onenote-cli.py create-page <section> <title> [--notebook NB] [--body-file PATH]

# 認証
~/onenote-cli.py auth                              # デバイスコードフロー認証
```

### 編集コマンドの使い方

`--html` を付けると入力をそのまま HTML として送信する。省略するとプレーンテキストを `<p>` タグに変換する。`-` を指定すると stdin から読み取る。

`replace` / `insert` の `target` は `body` (ページ本体) または `#<data-id>` (要素指定)。
data-id は `read-html` で確認できる。

```bash
# テキストを追記
~/onenote-cli.py append <page_id> "追記テキスト"

# stdin から HTML を追記
echo "<p>追記</p>" | ~/onenote-cli.py append <page_id> - --html

# 要素を置換
~/onenote-cli.py replace <page_id> "#p:{guid}" "新しい内容" --html
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

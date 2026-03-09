# Google Docs アクセスガイド

Google Docs へのアクセスは `gdocs-cli.py` (Google APIs ラッパー) で行う。

## インストール

```bash
pip3 install --user --break-system-packages google-api-python-client google-auth-oauthlib
```

## セットアップ

### 1. Google Cloud で OAuth2 クライアントを作成

1. [Google Cloud Console](https://console.developers.google.com/) でプロジェクトを作成（他の Google ツールと共用可）
2. Google Docs API と Google Drive API を有効化
3. OAuth 同意画面を設定（テストユーザーに自分を追加）
4. OAuth クライアント ID を作成（種類: デスクトップアプリ）
5. Client ID と Client Secret を控える

### 2. 設定ファイルに記述

`~/.config/agent-tools/config.json` の `gdocs` セクションに記述:

```json
{
  "gdocs": {
    "client_id": "<client_id>",
    "client_secret": "<client_secret>"
  }
}
```

### 3. 初期認証

```bash
~/gdocs-cli.py auth
```

認証 URL がターミナルに表示されるので、ブラウザで開いて Google アカウントでログインする。
ローカルの `http://localhost:8085/` にリダイレクトされ、自動的にトークンが取得される。

リモートサーバーの場合は事前に SSH トンネルを張る:

```bash
ssh -L 8085:localhost:8085 <host>
```

トークンは `~/.config/agent-tools/gdocs-token.json` に保存される。

## コマンド一覧

```bash
# 認証
~/gdocs-cli.py auth                                  # OAuth 認証

# ドキュメント一覧
~/gdocs-cli.py list                                   # 最近のドキュメント
~/gdocs-cli.py list --limit 50                        # 件数指定
~/gdocs-cli.py list --json                            # JSON 出力

# ドキュメント読み取り
~/gdocs-cli.py read <doc_id>                          # プレーンテキストで表示
~/gdocs-cli.py read <doc_id> --json                   # 生の API レスポンス

# 検索
~/gdocs-cli.py search <query>                         # 名前で検索
~/gdocs-cli.py search <query> --limit 10 --json       # オプション付き

# 作成
~/gdocs-cli.py create "タイトル"                       # 空のドキュメント作成
~/gdocs-cli.py create "タイトル" "本文テキスト"         # 本文付きで作成

# テキスト追加
~/gdocs-cli.py append <doc_id> "追加テキスト"          # 末尾にテキストを追加
```

エージェントから使う場合は `--json` を付けると構造化データが得られる。

## 制約

- テーブル内テキストは読み取れるが、セル構造の完全な再現は行わない
- 画像・図形・埋め込みオブジェクトは非対応
- 書式付きテキスト（太字・色など）はプレーンテキストとして読み取られる
- ドキュメントの構造的な編集（見出し設定、書式変更等）は未実装

# Gmail アクセスガイド

Gmail へのアクセスは [himalaya](https://github.com/pimalaya/himalaya) で行う。

## インストール

```bash
curl -sSL https://raw.githubusercontent.com/pimalaya/himalaya/master/install.sh | PREFIX=~/.local sh
```

## セットアップ

### 1. Google Cloud で OAuth2 クライアントを作成

1. [Google Cloud Console](https://console.developers.google.com/) でプロジェクトを作成
2. Gmail API を有効化
3. OAuth 同意画面を設定（テストユーザーに自分を追加）
4. OAuth クライアント ID を作成（種類: デスクトップアプリ）
5. Client ID と Client Secret を控える

### 2. himalaya の設定

`~/.config/himalaya/config.toml` を作成:

```toml
[accounts.<account_name>]
email = "<your_email>"
folder.aliases.inbox = "INBOX"
folder.aliases.sent = "[Gmail]/Sent Mail"
folder.aliases.drafts = "[Gmail]/Drafts"
folder.aliases.trash = "[Gmail]/Trash"

backend.type = "imap"
backend.host = "imap.gmail.com"
backend.port = 993
backend.login = "<your_email>"
backend.auth.type = "oauth2"
backend.auth.method = "xoauth2"
backend.auth.client-id = "<client_id>"
backend.auth.client-secret.keyring = "gmail-imap-client-secret"
backend.auth.access-token.keyring = "gmail-imap-access-token"
backend.auth.refresh-token.keyring = "gmail-imap-refresh-token"
backend.auth.auth-url = "https://accounts.google.com/o/oauth2/v2/auth"
backend.auth.token-url = "https://www.googleapis.com/oauth2/v3/token"
backend.auth.pkce = true
backend.auth.scope = "https://mail.google.com/"

message.send.backend.type = "smtp"
message.send.backend.host = "smtp.gmail.com"
message.send.backend.port = 465
message.send.backend.login = "<your_email>"
message.send.backend.auth.type = "oauth2"
message.send.backend.auth.method = "xoauth2"
message.send.backend.auth.client-id = "<client_id>"
message.send.backend.auth.client-secret.keyring = "gmail-smtp-client-secret"
message.send.backend.auth.access-token.keyring = "gmail-smtp-access-token"
message.send.backend.auth.refresh-token.keyring = "gmail-smtp-refresh-token"
message.send.backend.auth.auth-url = "https://accounts.google.com/o/oauth2/v2/auth"
message.send.backend.auth.token-url = "https://www.googleapis.com/oauth2/v3/token"
message.send.backend.auth.pkce = true
message.send.backend.auth.scope = "https://mail.google.com/"
```

### 3. 認証

```bash
himalaya account configure <account_name>
```

ブラウザが開くので Google アカウントでログインする。

## コマンド一覧

```bash
# メール一覧
himalaya envelope list                              # INBOX を表示
himalaya envelope list --folder "[Gmail]/Sent Mail"  # 送信済み
himalaya envelope list --output json                 # JSON 出力
himalaya envelope list --page 2                      # ページネーション

# メール読み取り
himalaya message read <id>                           # メール本文を表示

# メール送信
himalaya message write                               # エディタで作成して送信
echo "Subject: Test\nTo: user@example.com\n\nBody" | himalaya message send  # stdin から送信

# 返信・転送
himalaya message reply <id>
himalaya message forward <id>

# 移動・削除
himalaya message move <id> "[Gmail]/Trash"
himalaya message delete <id>

# フォルダ
himalaya folder list
```

エージェントから使う場合は `--output json` を付けると構造化データが得られる。

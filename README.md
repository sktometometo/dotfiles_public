# dotfiles_public

dotfiles と AI エージェント用 CLI ツールの管理リポジトリ。

## クイックスタート

```bash
git clone <repo> ~/dotfiles_public
cd ~/dotfiles_public
./setup.sh
```

`setup.sh` は以下を行う:

- `agent/` 内のスクリプトを `~/` にシンボリックリンク
- `~/.config/agent-tools/config.json` を作成（初回のみ）
- himalaya, gcalcli, gkeepapi 等のインストール（対話式）
- 各種 dotfiles セットアップスクリプトの実行（対話式）

## エージェントツール

| ツール | サービス | コマンド | ドキュメント |
|--------|---------|---------|-------------|
| himalaya | Gmail | `himalaya` | [gmail-access.md](agent/gmail-access.md) |
| gcalcli | Google Calendar | `gcalcli` | [gcal-access.md](agent/gcal-access.md) |
| keep-cli.py | Google Keep | `~/keep-cli.py` | [keep-access.md](agent/keep-access.md) |
| onenote-cli.py | OneNote | `~/onenote-cli.py` | [onenote-access.md](agent/onenote-access.md) |
| teams-cli.py | Teams | `~/teams-cli.py` | [teams-access.md](agent/teams-access.md) |

### 認証セットアップ

#### Gmail (himalaya)

1. [Google Cloud Console](https://console.developers.google.com/) でプロジェクトを作成
2. Gmail API を有効化
3. OAuth 同意画面を設定し、テストユーザーに自分を追加
4. OAuth クライアント ID を作成（種類: デスクトップアプリ）
5. `~/.config/himalaya/config.toml` を作成（テンプレートは [gmail-access.md](agent/gmail-access.md) 参照）
6. 認証を実行:

```bash
himalaya account configure <account_name>
```

#### Google Calendar (gcalcli)

1. Google Cloud Console で Google Calendar API を有効化（Gmail と同じプロジェクトで可）
2. OAuth クライアント ID を作成（Gmail と共用可）
3. 初期認証:

```bash
gcalcli --client-id=<client_id>.apps.googleusercontent.com init
```

#### Google Keep (keep-cli.py)

1. Google アカウントで 2 段階認証を有効化
2. [アプリパスワード](https://myaccount.google.com/apppasswords) を生成
3. マスタートークンを取得:

```bash
python3 -c "
from gpsoauth import perform_master_login
email = input('Email: ')
password = input('App Password: ')
result = perform_master_login(email, password)
token = result.get('Token')
if token:
    print(f'Master token: {token}')
else:
    print(f'Error: {result}')
"
```

4. `~/.config/agent-tools/config.json` に記述:

```json
{
  "keep": {
    "email": "<email>",
    "master_token": "<token>"
  }
}
```

#### OneNote (onenote-cli.py)

1. Azure AD でアプリ登録（パブリッククライアント、リダイレクト URI 不要）
2. API アクセス許可: `Notes.Read`, `Notes.ReadWrite`, `Notes.Create`, `User.Read`
3. `~/.config/agent-tools/config.json` に Client ID を記述:

```json
{
  "onenote": {
    "client_id": "<client_id>",
    "token_file": "~/onenotemcp/.access-token.txt",
    "notebooks": {},
    "sections": {}
  }
}
```

4. 認証:

```bash
~/onenote-cli.py auth
```

#### Teams (teams-cli.py)

1. 前提パッケージをインストール:

```bash
sudo apt install tigervnc-standalone-server google-chrome-stable
```

2. VNC + Chrome を起動:

```bash
~/teams-start.sh
```

3. VNC で接続して Teams にログイン:

```bash
ssh -L 5901:localhost:5901 <host>   # リモートの場合
vncviewer localhost:5901
```

4. ログイン完了後、CLI で操作:

```bash
python3 ~/teams-cli.py chats
```

組織情報は `~/.config/agent-tools/config.json` の `teams.orgs` に記述する。

### 設定ファイル

| ファイル | 内容 |
|---------|------|
| `~/.config/agent-tools/config.json` | OneNote, Teams, Keep の認証情報・設定 |
| `~/.config/himalaya/config.toml` | himalaya の IMAP/SMTP 設定 |
| `~/.local/share/gcalcli/oauth` | gcalcli の OAuth トークン |
| `~/.config/agent-tools/keep-state.json` | gkeepapi の同期キャッシュ |

テンプレート: [agent/config.example.json](agent/config.example.json)

### マルチエージェント対応

| エージェント | 設定ファイル |
|------------|-------------|
| Claude Code | `~/.claude/CLAUDE.md`（`@` で `agent/*.md` を参照） |
| Codex | `AGENTS.md`（リポジトリルート）+ `~/.codex/instructions.md` |

## dotfiles

| ディレクトリ | 内容 |
|-------------|------|
| `bashrc/` | Bash 設定 |
| `emacs/` | Emacs 設定 |
| `vim/` | Vim/Neovim 設定 |
| `tmux/` | tmux 設定 |
| `ssh/` | SSH 設定 |
| `latex/` | LaTeX 設定 |

各ディレクトリの `setup_*.sh` で個別にセットアップ可能（`./setup.sh` から対話式に実行もできる）。

## Ubuntu 環境構築

```bash
sudo apt update
sudo ubuntu-drivers install
```

追加でインストールするもの: dropbox, keepassxc, slack, Google Chrome, inkscape, Vivaldi, Docker + nvidia-docker, CUDA

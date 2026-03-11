# dotfiles_public

dotfiles と AI エージェント用 CLI ツールの管理リポジトリ。

## クイックスタート

```bash
git clone <repo> ~/dotfiles_public
cd ~/dotfiles_public
./setup.sh
```

`setup.sh` は各ディレクトリの `setup_*.sh` を対話式に実行する。エージェントツールのみセットアップする場合は `./agents/setup_agents.sh` を直接実行する。

## エージェントツール

| ツール | サービス | コマンド | ドキュメント |
|--------|---------|---------|-------------|
| himalaya | Gmail | `himalaya` | [gmail-access.md](agents/gmail-access.md) |
| gcalcli | Google Calendar | `gcalcli` | [gcal-access.md](agents/gcal-access.md) |
| keep-cli.py | Google Keep | `~/keep-cli.py` | [keep-access.md](agents/keep-access.md) |
| chrome-site-cli.py | Generic Chrome Site | `~/chrome-site-cli.py` | [chrome-site-access.md](agents/chrome-site-access.md) |
| onenote-cli.py | OneNote | `~/onenote-cli.py` | [onenote-access.md](agents/onenote-access.md) |
| teams-cli.py | Teams | `~/teams-cli.py` | [teams-access.md](agents/teams-access.md) |

### 認証セットアップ

#### Gmail (himalaya)

**アプリパスワード方式（推奨）:**

1. Google アカウントで 2 段階認証を有効化
2. [アプリパスワード](https://myaccount.google.com/apppasswords) を生成
3. パスワードをファイルに保存:

```bash
echo -n "<app_password>" > ~/.config/agent-tools/gmail-app-password.txt
chmod 600 ~/.config/agent-tools/gmail-app-password.txt
```

4. `~/.config/himalaya/config.toml` を作成（テンプレートは [gmail-access.md](agents/gmail-access.md) の方法 A 参照）

OAuth2 方式も利用可能（[gmail-access.md](agents/gmail-access.md) の方法 B 参照）。

#### Google Calendar (gcalcli)

1. Google Cloud Console で Google Calendar API を有効化（Gmail と同じプロジェクトで可）
2. OAuth クライアント ID を作成（Gmail と共用可）
3. 初期認証:

```bash
gcalcli --client-id=<client_id>.apps.googleusercontent.com init
```

#### Google Keep (keep-cli.py)

1. 前提パッケージをインストール:

```bash
sudo apt install tigervnc-standalone-server xfce4 dbus-x11 google-chrome-stable
pip3 install --user --break-system-packages websockets
```

2. VNC + Chrome を起動:

```bash
~/keep-start.sh
```

3. VNC で接続して Google Keep にログイン:

```bash
ssh -L 5901:localhost:5901 <host>   # リモートの場合
vncviewer localhost:5901
```

Keep は専用 Chrome プロファイル `/tmp/chrome-keep`、CDP ポート `9223` を使う。

4. ログイン完了後、CLI で操作:

```bash
python3 ~/keep-cli.py list
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
sudo apt install tigervnc-standalone-server xfce4 dbus-x11 google-chrome-stable
```

2. VNC + Chrome を起動:

```bash
~/teams-start.sh
```

3. VNC で接続して Teams にログイン:

```bash
ssh -L 5902:localhost:5902 <host>   # リモートの場合
vncviewer localhost:5902
```

Teams は専用 Chrome プロファイル `/tmp/chrome-teams3`、CDP ポート `9224` を使う。

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
| `/tmp/chrome-keep` | Google Keep 用 Chrome プロファイル |
| `/tmp/chrome-teams3` | Teams 用 Chrome プロファイル |

テンプレート: [agents/config.example.json](agents/config.example.json)

### マルチエージェント対応

| エージェント | 設定ファイル |
|------------|-------------|
| Claude Code | `~/.claude/CLAUDE.md`（`@` で `agents/*.md` を参照） |
| Codex | `AGENTS.md`（リポジトリルート）+ `~/.codex/instructions.md` |
| Gemini CLI | `GEMINI.md`（リポジトリルート） |

## dotfiles

| ディレクトリ | 内容 |
|-------------|------|
| `agents/` | AI エージェント用 CLI ツール・ドキュメント |
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

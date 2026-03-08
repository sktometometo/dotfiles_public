# Agent Instructions

このリポジトリは dotfiles と AI エージェント用のツール・設定を管理する。

## セットアップ

```bash
# 1. リポジトリをクローン
git clone <repo> ~/dotfiles_public

# 2. 設定ファイルを作成（テンプレートからコピー）
mkdir -p ~/.config/agent-tools
cp ~/dotfiles_public/agent/config.example.json ~/.config/agent-tools/config.json
# config.json を編集して実際の値を設定

# 3. シンボリックリンクを作成
./setup.sh
```

## 利用可能なツール

### Gmail

Gmail の読み書きを himalaya CLI で行う。

- ツール: `himalaya`
- 詳細: [agent/gmail-access.md](agent/gmail-access.md)

### Google Calendar

Google Calendar の読み書きを gcalcli で行う。

- ツール: `gcalcli`
- 詳細: [agent/gcal-access.md](agent/gcal-access.md)

### Google Keep

Google Keep のノート読み書きを keep-cli.py (gkeepapi ラッパー) で行う。

- ツール: `~/keep-cli.py`
- 詳細: [agent/keep-access.md](agent/keep-access.md)

### OneNote

OneNote のノートブック・セクション・ページを読み書きする CLI ツール。

- ツール: `~/onenote-cli.py`
- 詳細: [agent/onenote-access.md](agent/onenote-access.md)

### Teams

Microsoft Teams のチャット・チャネルを読み取る CLI ツール（Chrome CDP 経由）。

- ツール: `~/teams-cli.py`
- 起動: `~/teams-start.sh`
- 詳細: [agent/teams-access.md](agent/teams-access.md)

## 設定

すべての機密情報（Client ID、組織名、トークン等）は `~/.config/agent-tools/config.json` に記述する。テンプレート: [agent/config.example.json](agent/config.example.json)

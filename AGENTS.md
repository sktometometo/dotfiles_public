# Agent Instructions

このリポジトリは dotfiles と AI エージェント用のツール・設定を管理する。

## セットアップ

```bash
# 1. リポジトリをクローン
git clone <repo> ~/dotfiles_public

# 2. エージェントツールをセットアップ
./agents/setup_agents.sh
```

## 利用可能なツール

### Gmail

Gmail の読み書きを himalaya CLI で行う。

- ツール: `himalaya`
- 詳細: [agents/gmail-access.md](agents/gmail-access.md)

### Google Calendar

Google Calendar の読み書きを gcalcli で行う。

- ツール: `gcalcli`
- 詳細: [agents/gcal-access.md](agents/gcal-access.md)

### Google Keep

Google Keep のノート読み書きを keep-cli.py (Chrome CDP 経由) で行う。

- ツール: `~/keep-cli.py`
- 詳細: [agents/keep-access.md](agents/keep-access.md)

### Generic Chrome Site

任意サイトの探索・暫定操作を Chrome CDP 経由で行う汎用 CLI。

- ツール: `~/chrome-site-cli.py`, `~/chrome-app-start.sh`
- 詳細: [agents/chrome-site-access.md](agents/chrome-site-access.md)

### OneNote

OneNote のノートブック・セクション・ページを読み書きする CLI ツール。

- ツール: `~/onenote-cli.py`
- 詳細: [agents/onenote-access.md](agents/onenote-access.md)

### Teams

Microsoft Teams のチャット・チャネルを読み取る CLI ツール（Chrome CDP 経由）。

- ツール: `~/teams-cli.py`
- 起動: `~/teams-start.sh`
- 詳細: [agents/teams-access.md](agents/teams-access.md)

## 設定

すべての機密情報（Client ID、組織名、トークン等）は `~/.config/agent-tools/config.json` に記述する。テンプレート: [agents/config.example.json](agents/config.example.json)

# Codex Personal Instructions

このファイルは `~/.codex/instructions.md` に symlink して使う前提の、個人用 Codex 指示テンプレート。

## Startup behavior

1. まずこのファイル自身の指示を適用する。
2. 次に `~/dotfiles_public/AGENTS.md` を読み、この dotfiles リポジトリで管理しているエージェント向けルールとツール一覧を把握する。
3. 必要に応じて `~/dotfiles_public/agents/*.md` を読む。特に、利用するツールやサービスに対応する access 文書を優先する。
4. `~/.codex/instructions.local.md` が存在する場合は、それも読む。こちらは `dotfiles_public` 外で管理する個人用・機密用・一時的な追加指示として扱う。

## Intent

- `~/dotfiles_public/` にある md は、共有可能な恒久ルールとツール手順の置き場
- `~/.codex/instructions.local.md` は、このマシン固有の個人プロンプトや機密性のある補足の置き場

## Guidance

- `~/dotfiles_public/AGENTS.md` と、現在作業中のリポジトリにある `AGENTS.md` の両方がある場合は、より近いディレクトリの `AGENTS.md` を優先しつつ、矛盾しない範囲で両方を使う。
- `~/dotfiles_public/agents/*.md` を毎回全件読む必要はない。タスクに必要な文書だけ読む。
- `~/.codex/instructions.local.md` が存在しても、内容をそのまま反復せず、実行方針に必要な範囲で使う。

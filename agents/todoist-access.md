# Todoist アクセスガイド

Todoist は公式 MCP サーバー `@doist/todoist-ai` を使う。

Codex では、Remote HTTP よりもローカル stdio ラッパーのほうが扱いやすいため、`~/dotfiles_public/agents/todoist-mcp.sh` 経由で登録する。

## 推奨セットアップ

```bash
~/dotfiles_public/agents/setup_codex_integrations.sh
```

## 手動セットアップ

### 1. API トークンを保存

```bash
mkdir -p ~/.config/agent-tools
printf '%s' '<todoist_api_token>' > ~/.config/agent-tools/todoist-api-key.txt
chmod 600 ~/.config/agent-tools/todoist-api-key.txt
```

### 2. MCP を登録

```bash
codex mcp add todoist -- ~/dotfiles_public/agents/todoist-mcp.sh
```

## 接続確認

```bash
codex mcp list
codex mcp get todoist
```

`todoist-mcp.sh` は以下の優先順で API キーを読む:

1. 環境変数 `TODOIST_API_KEY`
2. 環境変数 `TODOIST_API_KEY_FILE`
3. 既定ファイル `~/.config/agent-tools/todoist-api-key.txt`

## 参考

- 公式リポジトリ: `https://github.com/doist/todoist-ai`
- 公式 MCP パッケージ: `@doist/todoist-ai`

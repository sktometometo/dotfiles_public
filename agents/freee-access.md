# freee アクセスガイド

freee は Chrome CDP ではなく、公式 `freee/freee-mcp` と公式 Skill `freee-api-skill` を使う。

## 推奨セットアップ

```bash
~/dotfiles_public/agents/setup_codex_integrations.sh
```

このスクリプトは以下を行う:

- `codex mcp add freee --url https://mcp.freee.co.jp/mcp`
- `freee-api-skill` を `~/.codex/skills/freee-api-skill` にインストール

## 手動セットアップ

### 1. MCP を登録

```bash
codex mcp add freee --url https://mcp.freee.co.jp/mcp
```

初回はブラウザで OAuth ログインが必要。追加後に未認証の場合は:

```bash
codex mcp login freee
```

### 2. Skill をインストール

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo freee/freee-mcp \
  --path skills/freee-api-skill
```

インストール後は Codex を再起動する。

## 接続確認

```bash
codex mcp list
codex mcp get freee
```

期待状態:

- URL が `https://mcp.freee.co.jp/mcp`
- Auth が `Logged in` になる
- Skill `freee-api-skill` が `~/.codex/skills/` にある

## legacy 手順

`~/freee-start.sh` と `~/chrome-site-cli.py` を使う Chrome CDP ベースの運用は残してあるが、通常は使わない。freee 操作は公式 MCP/Skill を優先する。

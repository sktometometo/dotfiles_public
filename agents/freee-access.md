# freee アクセスガイド

freee へのアクセスは、汎用の Chrome CDP 基盤で行う。
Keep / Teams と干渉しないように、freee 用の Chrome は専用プロファイル・専用 CDP ポート・専用 VNC ディスプレイで起動する。

## セットアップ

```bash
# 1. freee 専用セッションを起動
~/freee-start.sh

# 2. 初回のみ VNC で freee にログイン
#    VNC 接続: localhost:5904
#    SSH トンネル: ssh -L 5904:localhost:5904 <host>
```

デフォルト設定:

- Chrome プロファイル: `~/.config/agent-tools/chrome-freee`
- CDP ポート: `9225`
- VNC display: `:4`
- VNC ポート: `5904`
- ログ: `/tmp/freee-chrome.log`

起動後、セッション情報は `~/.cache/agent-tools/chrome-sessions/freee.json` に保存される。

## 汎用 CLI の使い方

```bash
export CHROME_SITE_CDP_URL=http://localhost:9225
export CHROME_SITE_MATCH_URL=secure.freee.co.jp

python3 ~/chrome-site-cli.py targets
python3 ~/chrome-site-cli.py title
python3 ~/chrome-site-cli.py dump --limit 4000
python3 ~/chrome-site-cli.py eval "document.title"
python3 ~/chrome-site-cli.py goto "https://secure.freee.co.jp/annual_reports/final_return/wizards"
```

## 再利用

同じ CDP ポートに freee 用 Chrome が起動済みなら、`~/freee-start.sh` を再実行しても既存セッションを再利用する。
プロファイルを維持したまま再接続できるため、ログイン状態や cookie を持ち越せる。

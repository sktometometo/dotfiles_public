# Chrome Site CLI アクセスガイド

任意のサイトを Chrome DevTools Protocol (CDP) 経由で最低限操作するための汎用 CLI は `chrome-site-cli.py` を使う。

これはサービス固有 CLI を作る前の探索用・デバッグ用・暫定操作用のツールで、以下のような用途を想定する。

- どのタブが開いているか確認する
- 特定サイトのタブへ接続する
- 画面テキストや HTML を取得する
- JavaScript を直接評価する
- テキスト一致で要素をクリックする
- 現在フォーカス中の入力欄へ文字を送る

## 前提

Chrome は `chrome-app-start.sh` などで `--remote-debugging-port` 付きで起動しておく。

例:

```bash
~/chrome-app-start.sh "Example" "https://example.com" 9330 /tmp/chrome-example /tmp/example-chrome.log "python3 ~/chrome-site-cli.py targets" :3 5903
```

## 使い方

接続先の Chrome と対象タブは環境変数で指定する。

```bash
export CHROME_SITE_CDP_URL=http://localhost:9330
export CHROME_SITE_MATCH_URL=example.com
```

その上で CLI を使う。

```bash
python3 ~/chrome-site-cli.py targets
python3 ~/chrome-site-cli.py title
python3 ~/chrome-site-cli.py dump --limit 4000
python3 ~/chrome-site-cli.py html --limit 4000
python3 ~/chrome-site-cli.py eval "document.title"
python3 ~/chrome-site-cli.py click-text "Sign in"
python3 ~/chrome-site-cli.py type "hello"
python3 ~/chrome-site-cli.py goto "https://example.com/docs"
```

## Agent で使うときの指針

- まず `targets` で接続先タブを確認する
- 次に `title` と `dump` でページ状態を把握する
- 安定化の前は `eval` で DOM を直接観察する
- 操作フローが固まったら、そのサイト専用 CLI を別途作る

## 制約

- DOM 依存なので UI が変わると壊れる
- `click-text` は最短一致の要素を押すだけで、誤クリックの可能性がある
- 入力は現在フォーカス中の要素に対してのみ行う
